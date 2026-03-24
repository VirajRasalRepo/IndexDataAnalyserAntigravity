"""
Adapter that runs the signal engine's backtest logic using DatabaseManager.
Reuses CandleBuilder, OIAnalyser, SignalEngine from nifty_signal_engine.py
without modifying that file.
"""

import sys
import logging
from pathlib import Path
from datetime import timedelta
from decimal import Decimal

import pandas as pd

# Ensure project root is on path so nifty_signal_engine can be imported
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from nifty_signal_engine import (
    CandleBuilder, OIAnalyser, SignalEngine,
    IV_MAX, MIN_RANGE_PTS, MIN_TARGET_PTS, SL_POINTS, TARGET_POINTS,
    LOT_SIZE, MAX_CONSEC, TRADE_START, TRADE_END,
    HIGH_CORR_STOCKS, MIN_STOCK_AGREE,
)
from core.database import DatabaseManager

logger = logging.getLogger(__name__)


def _dec(v):
    """Convert Decimal/None to float."""
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _td_to_str(td):
    """Convert timedelta or time object to HH:MM:SS string."""
    if isinstance(td, timedelta):
        total = int(td.total_seconds())
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    return str(td)


class SignalBacktestAdapter:
    """Runs signal engine backtest using the dashboard's DatabaseManager."""

    def get_available_dates(self) -> list:
        """Return dates that have sufficient OI data for backtesting."""
        with DatabaseManager.get_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT DISTINCT Date
                FROM nifty_oc_historical
                WHERE ce_oi IS NOT NULL
                ORDER BY Date DESC
                LIMIT 90
            """)
            rows = cursor.fetchall()
        return [r["Date"].isoformat() if hasattr(r["Date"], "isoformat") else str(r["Date"]) for r in rows]

    def run_backtest_for_date(self, date_str: str) -> dict:
        """
        Run the full signal engine backtest for a single date.
        Returns structured dict with assessment, signals, candles, summary.
        """
        # ── 1. Pre-fetch ALL OI data for the date in one query ──
        oi_all = self._fetch_all_oi(date_str)
        if oi_all.empty:
            return {"status": "error", "message": f"No OI data for {date_str}"}

        # ── 2. Get spot series ──
        spot_df = self._fetch_spot_series(date_str)
        if spot_df.empty:
            return {"status": "error", "message": f"No spot data for {date_str}"}

        # ── 3. Build 5-min candles ──
        cb = CandleBuilder()
        candles_df = cb.build_from_df(spot_df, date_str)
        if candles_df.empty:
            return {"status": "error", "message": f"No candles built for {date_str}"}

        # ── 4. Get open OI snapshot and init day ──
        engine = SignalEngine()
        open_time = candles_df.iloc[0]["dt"].strftime("%H:%M:%S")
        oi_open = self._filter_oi_at_time(oi_all, open_time)

        if oi_open.empty:
            return {"status": "error", "message": f"No OI at market open for {date_str}"}

        spot_open = float(candles_df.iloc[0]["close"])
        assessment = engine.init_day(oi_open, spot_open)

        # ── 5. Iterate candles and collect signals ──
        signals = []
        candles_out = []
        history = []

        for _, row in candles_df.iterrows():
            candle = row.to_dict()
            t_str = candle["dt"].strftime("%H:%M:%S")

            # Record candle for output
            candles_out.append({
                "time": candle["dt"].strftime("%H:%M"),
                "open": round(float(candle["open"]), 2),
                "high": round(float(candle["high"]), 2),
                "low": round(float(candle["low"]), 2),
                "close": round(float(candle["close"]), 2),
                "range": round(float(candle.get("range", 0)), 2),
                "body": round(float(candle.get("body", 0)), 2),
                "body_pct": round(float(candle.get("body_pct", 0)), 1),
                "bull": bool(candle.get("bull", True)),
                "pattern": str(candle.get("pattern", "")),
            })

            # Get OI at this candle time
            oi_now = self._filter_oi_at_time(oi_all, t_str)
            spot_now = float(candle["close"])

            # Stock snapshot (optional)
            stock_snap = self._fetch_stock_snapshot(date_str, candle["dt"].strftime("%H:%M") + ":00")

            signal = engine.evaluate_candle(candle, history, oi_now, spot_now, stock_snap)
            if signal:
                # Convert any non-serialisable values
                clean = {}
                for k, v in signal.items():
                    if isinstance(v, (Decimal, float)):
                        clean[k] = round(float(v), 2)
                    elif isinstance(v, bool):
                        clean[k] = v
                    else:
                        clean[k] = v
                signals.append(clean)

            history.append(candle)

        # ── 6. Build summary ──
        entries = [s for s in signals if s.get("type") == "ENTRY"]
        exits = [s for s in signals if s.get("type") == "EXIT"]
        wins = [s for s in exits if s.get("win")]
        losses = [s for s in exits if not s.get("win")]
        total_pnl = sum(s.get("pnl_lot", 0) for s in exits)

        summary = {
            "total_signals": len(signals),
            "entries": len(entries),
            "exits": len(exits),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / max(len(exits), 1) * 100, 1),
            "total_pnl": round(total_pnl, 0),
            "open_trades": len(entries) - len(exits),
        }

        # ── 7. Format assessment ──
        assess_out = {
            "tradeable": assessment.get("tradeable", False),
            "iv_open": assessment.get("iv_open", 0),
            "pe_iv_open": assessment.get("pe_iv_open", 0),
            "pcr": assessment.get("pcr", 1.0),
            "allowed_dirs": assessment.get("allowed_dirs", []),
            "ce_walls": [[s, round(o, 2)] for s, o in assessment.get("ce_walls", [])],
            "pe_walls": [[s, round(o, 2)] for s, o in assessment.get("pe_walls", [])],
            "block_reason": assessment.get("block_reason"),
        }

        return {
            "status": "success",
            "date": date_str,
            "assessment": assess_out,
            "signals": signals,
            "candles": candles_out,
            "summary": summary,
        }

    # ── Private helpers ───────────────────────────────────────────

    def _fetch_all_oi(self, date_str: str) -> pd.DataFrame:
        """Pre-fetch all OI rows for a date. Column names are mapped to engine expectations."""
        with DatabaseManager.get_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT
                    Time,
                    Strike_price   AS Strike,
                    Spot_price,
                    ce_oi / 100000 AS ce_oi,
                    ce_volume,
                    ce_IV          AS ce_iv,
                    ce_delta,
                    ce_price       AS ce_ltp,
                    pe_price       AS pe_ltp,
                    pe_delta,
                    pe_IV          AS pe_iv,
                    pe_volume,
                    pe_oi / 100000 AS pe_oi
                FROM nifty_oc_historical
                WHERE Date = %s
                ORDER BY Time, Strike_price
            """, (date_str,))
            rows = cursor.fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        # Convert timedelta Time to string
        df["Time"] = df["Time"].apply(_td_to_str)
        # Convert Decimals to float
        for col in df.columns:
            if col != "Time":
                df[col] = df[col].apply(_dec)
        return df

    def _filter_oi_at_time(self, oi_all: pd.DataFrame, at_time: str) -> pd.DataFrame:
        """Filter pre-fetched OI data to the latest snapshot at or before given time.
        Falls back to earliest available if at_time is before all data."""
        if oi_all.empty:
            return oi_all
        mask = oi_all["Time"] <= at_time
        subset = oi_all[mask]
        if subset.empty:
            # Fall back to the earliest available OI snapshot
            earliest_time = oi_all["Time"].min()
            return oi_all[oi_all["Time"] == earliest_time].reset_index(drop=True)
        latest_time = subset["Time"].max()
        return subset[subset["Time"] == latest_time].reset_index(drop=True)

    def _fetch_spot_series(self, date_str: str) -> pd.DataFrame:
        """Fetch distinct (Time, Spot) pairs for candle building."""
        with DatabaseManager.get_cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT DISTINCT Time, Spot_price AS spot
                FROM nifty_oc_historical
                WHERE Date = %s
                ORDER BY Time
            """, (date_str,))
            rows = cursor.fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["Time"] = df["Time"].apply(_td_to_str)
        df["spot"] = df["spot"].apply(_dec)
        return df

    def _fetch_stock_snapshot(self, date_str: str, time_str: str) -> dict | None:
        """Get stock LTP snapshot from market_feed_realtime."""
        try:
            with DatabaseManager.get_cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT
                        infosys_ltp, lt_ltp, tcs_ltp, icici_bank_ltp,
                        nifty_50_ltp, india_vix_ltp,
                        infosys_open, lt_open, tcs_open, icici_bank_open
                    FROM market_feed_realtime
                    WHERE DATE(timestamp) = %s
                      AND TIME(timestamp) <= %s
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (date_str, time_str))
                row = cursor.fetchone()
            if not row:
                return None
            return {k: _dec(v) for k, v in row.items()}
        except Exception:
            return None


def get_engine_config() -> dict:
    """Return the engine's configuration parameters."""
    return {
        "iv_max": IV_MAX,
        "min_range_pts": MIN_RANGE_PTS,
        "min_target_pts": MIN_TARGET_PTS,
        "sl_points": SL_POINTS,
        "target_points": TARGET_POINTS,
        "lot_size": LOT_SIZE,
        "max_consec": MAX_CONSEC,
        "trade_start": TRADE_START,
        "trade_end": TRADE_END,
        "high_corr_stocks": HIGH_CORR_STOCKS,
        "min_stock_agree": MIN_STOCK_AGREE,
    }
