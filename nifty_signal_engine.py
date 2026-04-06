"""
╔══════════════════════════════════════════════════════════════════════╗
║         NIFTY 50 OPTIONS SIGNAL ENGINE                              ║
║         Automated entry/exit signal generator                       ║
║         Uses: MySQL DB (OI data) + Dhan API (live prices)          ║
║         Strategy: StrongCandle + OI walls + IV + PCR + scoring      ║
╚══════════════════════════════════════════════════════════════════════╝

INSTALL:
    pip install dhanhq mysql-connector-python pandas sqlalchemy

USAGE:
    python nifty_signal_engine.py              # live mode (runs every 5 min)
    python nifty_signal_engine.py --backtest   # backtest from DB data
    python nifty_signal_engine.py --today      # scan today's DB data once

HOW IT WORKS:
    1. Pulls OI data from YOUR MySQL database (same tables as the CSVs)
    2. Pulls live Nifty spot price from Dhan API every 5 minutes
    3. Builds 5-min candles in memory
    4. Scores candles on 8 filters (PCR, StrongCandle, Time, Range, Walls, VIX, OI Buildup...)
    5. Prints BUY CALL / BUY PUT signals with score and entry prices
    6. Tracks open trades and prints EXIT signals when target/SL hit
    7. Logs everything to a CSV file for your records

NOTE: This is a SIGNAL GENERATOR only. It does NOT place orders.
      You place the trade manually on your Dhan app after seeing the signal.
"""

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION — edit these before running
# ─────────────────────────────────────────────────────────────────────

DHAN_CLIENT_ID   = "1107702034"
DHAN_ACCESS_TOKEN = "PASTE_YOUR_FRESH_TOKEN_HERE"   # refresh daily from DhanHQ

DB_CONFIG = {
    "host":     "localhost",       # your MySQL host
    "port":     3306,
    "user":     "your_db_user",
    "password": "your_db_password",
    "database": "your_db_name",
}

# Table names in your MySQL database (adjust if different)
OI_TABLE        = "NiftyHistorical"      # your OI + option chain table
SHARES_TABLE    = "TopSharesData"        # your stock LTP table

# Strategy parameters (tuned from backtest)
IV_MAX          = 20.0      # skip day if ATM IV >= this at open
VIX_MAX         = 20.0      # skip CALL signals if India VIX > this
MIN_RANGE_PTS   = 50        # last 4 candles combined range must exceed this
WALL_DIST_MIN   = 25        # OI wall must be at least this far from entry
WALL_DIST_MAX   = 80        # OI wall must be at most this far (reachable)
SL_POINTS       = 50        # stop loss in Nifty points
TARGET_POINTS   = 80        # profit target in Nifty points
LOT_SIZE        = 75        # Nifty lot size
MAX_CONSEC      = 3         # skip if N consecutive opposite candles before signal
TRADE_START     = "10:15"   # preferred entry window start
TRADE_END       = "14:45"   # preferred entry window end
SCAN_INTERVAL   = 300       # seconds between scans in live mode (5 min)
MIN_SCORE       = 5         # minimum filter score out of 8 to generate signal

# Nifty 50 security details for Dhan API
NIFTY_SECURITY_ID    = "13"
NIFTY_EXCHANGE_SEG   = "NSE_IDX"
NIFTY_INSTRUMENT     = "INDEX"

# ─────────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────────────

import sys
import time
import argparse
import logging
from datetime import datetime, timedelta, date
from collections import deque

import pandas as pd
import numpy as np

# Optional — only needed in live mode
try:
    from dhanhq import dhanhq
    DHAN_OK = True
except ImportError:
    DHAN_OK = False
    print("⚠  dhanhq not installed. Live mode disabled. Run: pip install dhanhq")

try:
    import mysql.connector
    MYSQL_OK = True
except ImportError:
    MYSQL_OK = False
    print("⚠  mysql-connector not installed. Run: pip install mysql-connector-python")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("nifty_signals.log"),
    ]
)
log = logging.getLogger("NiftyEngine")

# ─────────────────────────────────────────────────────────────────────
# DATABASE LAYER
# ─────────────────────────────────────────────────────────────────────

class DBClient:
    """Handles all MySQL reads from your existing database."""

    def __init__(self, config: dict):
        self.config = config
        self._conn  = None

    def connect(self):
        if self._conn is None or not self._conn.is_connected():
            self._conn = mysql.connector.connect(**self.config)
        return self._conn

    def query(self, sql: str, params=None) -> pd.DataFrame:
        conn = self.connect()
        return pd.read_sql(sql, conn, params=params)

    def get_oi_snapshot(self, at_time: str, target_date: str) -> pd.DataFrame:
        """
        Get latest OI snapshot at or before a given time for a date.
        Returns one row per strike with CE/PE OI, IV, LTP, Delta.
        """
        sql = f"""
            SELECT Time, Strike,
                   `CE_OI(L)` AS ce_oi, CE_Volume AS ce_volume,
                   CE_IV       AS ce_iv,  CE_Delta  AS ce_delta,
                   CE_LTP      AS ce_ltp,
                   PE_LTP      AS pe_ltp, PE_Delta  AS pe_delta,
                   PE_IV       AS pe_iv,  PE_Volume AS pe_volume,
                   `PE_OI(L)` AS pe_oi
            FROM {OI_TABLE}
            WHERE Date = %s
              AND Time <= %s
            ORDER BY Time DESC
            LIMIT 500
        """
        df = self.query(sql, params=(target_date, at_time))
        if df.empty:
            return df
        # Keep only latest timestamp
        latest = df['Time'].max()
        return df[df['Time'] == latest].reset_index(drop=True)

    def get_spot_series(self, target_date: str,
                        from_time: str = "09:15",
                        to_time: str = "15:30") -> pd.DataFrame:
        """
        Reconstruct Nifty spot price from OI data using put-call parity:
        Spot ≈ ATM Strike + (CE_LTP - PE_LTP) / (CE_Delta - PE_Delta)
        """
        sql = f"""
            SELECT Time, Strike,
                   CE_LTP AS ce_ltp, PE_LTP AS pe_ltp,
                   CE_Delta AS ce_delta, PE_Delta AS pe_delta,
                   CE_IV AS ce_iv
            FROM {OI_TABLE}
            WHERE Date = %s AND Time >= %s AND Time <= %s
            ORDER BY Time, Strike
        """
        df = self.query(sql, params=(target_date, from_time, to_time))
        if df.empty:
            return pd.DataFrame(columns=["Time", "spot", "ce_iv"])

        # For each timestamp, find ATM and compute spot
        rows = []
        for t, grp in df.groupby("Time"):
            grp = grp.copy()
            grp["diff"] = abs(grp["ce_ltp"] - grp["pe_ltp"])
            atm = grp.nsmallest(1, "diff").iloc[0]
            d_diff = (atm["ce_delta"] - atm["pe_delta"])
            if abs(d_diff) < 0.01:
                d_diff = 0.01
            spot = atm["Strike"] + (atm["ce_ltp"] - atm["pe_ltp"]) / d_diff
            rows.append({"Time": t, "spot": round(spot, 2),
                         "ce_iv": atm["ce_iv"], "atm_strike": atm["Strike"]})

        return pd.DataFrame(rows).sort_values("Time").reset_index(drop=True)

    def get_stock_snapshot(self, target_date: str,
                           at_time: str) -> dict:
        """
        Get stock LTP snapshot at a given time from TopSharesData.
        Returns dict of {column: value} for high-corr stocks.
        """
        # Round to nearest minute for lookup
        sql = f"""
            SELECT timestamp,
                   infosys_ltp, lt_ltp, tcs_ltp, icici_bank_ltp,
                   nifty_50_ltp, india_vix_ltp
            FROM {SHARES_TABLE}
            WHERE DATE(timestamp) = %s
              AND TIME(timestamp) <= %s
            ORDER BY timestamp DESC
            LIMIT 1
        """
        df = self.query(sql, params=(target_date, at_time))
        if df.empty:
            return {}
        return df.iloc[0].to_dict()

    def get_vix_snapshot(self, target_date: str, at_time: str) -> float | None:
        """Get India VIX LTP at a given time from TopSharesData."""
        sql = f"""
            SELECT india_vix_ltp
            FROM {SHARES_TABLE}
            WHERE DATE(timestamp) = %s
              AND TIME(timestamp) <= %s
            ORDER BY timestamp DESC
            LIMIT 1
        """
        df = self.query(sql, params=(target_date, at_time))
        if df.empty:
            return None
        val = df.iloc[0]["india_vix_ltp"]
        return float(val) if val is not None else None

    def get_available_dates(self) -> list:
        sql = f"SELECT DISTINCT Date FROM {OI_TABLE} ORDER BY Date"
        df = self.query(sql)
        return df["Date"].tolist() if not df.empty else []


# ─────────────────────────────────────────────────────────────────────
# LIVE PRICE LAYER (Dhan API)
# ─────────────────────────────────────────────────────────────────────

class DhanLiveClient:
    """Fetches live Nifty spot price from Dhan API."""

    def __init__(self):
        self.dhan = None
        if DHAN_OK:
            try:
                self.dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
                log.info("Dhan API connected")
            except Exception as e:
                log.error(f"Dhan API connection failed: {e}")

    def get_spot(self) -> float | None:
        """Get current Nifty 50 spot price."""
        if not self.dhan:
            return None
        try:
            resp = self.dhan.ticker_data({
                "NSE_IDX": [NIFTY_SECURITY_ID]
            })
            if resp and "data" in resp:
                data = resp["data"].get("NSE_IDX", {})
                if NIFTY_SECURITY_ID in data:
                    return float(data[NIFTY_SECURITY_ID]["last_price"])
        except Exception as e:
            log.warning(f"Spot price fetch failed: {e}")
        return None

    def get_option_chain_snapshot(self, expiry: str) -> pd.DataFrame:
        """
        Get live option chain for Nifty.
        expiry format: 'YYYY-MM-DD'
        """
        if not self.dhan:
            return pd.DataFrame()
        try:
            resp = self.dhan.option_chain(
                under_security_id=int(NIFTY_SECURITY_ID),
                under_exchange_segment="NSE_IDX",
                expiry=expiry
            )
            if resp and resp.get("status") == "success":
                data = resp.get("data", {})
                oc   = data.get("oc", {})
                rows = []
                for strike_str, vals in oc.items():
                    ce = vals.get("call_options", {})
                    pe = vals.get("put_options", {})
                    rows.append({
                        "Strike":   int(strike_str),
                        "ce_oi":    ce.get("oi", 0) / 100000,   # convert to Lakhs
                        "ce_iv":    ce.get("implied_volatility", 0),
                        "ce_ltp":   ce.get("last_price", 0),
                        "ce_delta": ce.get("delta", 0),
                        "pe_oi":    pe.get("oi", 0) / 100000,
                        "pe_iv":    pe.get("implied_volatility", 0),
                        "pe_ltp":   pe.get("last_price", 0),
                        "pe_delta": pe.get("delta", 0),
                    })
                return pd.DataFrame(rows).sort_values("Strike").reset_index(drop=True)
        except Exception as e:
            log.warning(f"Option chain fetch failed: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────
# CANDLE BUILDER
# ─────────────────────────────────────────────────────────────────────

class CandleBuilder:
    """Builds and maintains 5-minute OHLC candles from tick data."""

    def __init__(self, window: int = 30):
        self.candles  = deque(maxlen=window)   # rolling window of last N candles
        self._current = None

    def feed_tick(self, timestamp: datetime, price: float):
        """Feed a new price tick. Returns completed candle dict if candle closed."""
        bucket = timestamp.replace(second=0, microsecond=0)
        bucket = bucket - timedelta(minutes=bucket.minute % 5)

        if self._current is None:
            self._current = self._new_candle(bucket, price)
            return None

        if bucket == self._current["dt"]:
            self._current["high"]  = max(self._current["high"], price)
            self._current["low"]   = min(self._current["low"],  price)
            self._current["close"] = price
            return None
        else:
            closed = self._current.copy()
            closed = self._enrich(closed)
            self.candles.append(closed)
            self._current = self._new_candle(bucket, price)
            return closed

    def feed_series(self, time_price_series: list) -> list:
        """Feed a list of (datetime, price) and return all completed candles."""
        completed = []
        for ts, price in time_price_series:
            c = self.feed_tick(ts, price)
            if c:
                completed.append(c)
        return completed

    def build_from_df(self, spot_df: pd.DataFrame, date_str: str) -> pd.DataFrame:
        """Build 5-min candles from a spot price DataFrame (from DB)."""
        spot_df = spot_df.copy()
        spot_df["dt"] = pd.to_datetime(date_str + " " + spot_df["Time"])
        spot_df = spot_df.set_index("dt")["spot"].sort_index()

        g = spot_df.resample("5min")
        c = pd.DataFrame({
            "open":  g.first(),
            "high":  g.max(),
            "low":   g.min(),
            "close": g.last(),
        }).dropna().reset_index()
        c.columns = ["dt", "open", "high", "low", "close"]
        c = c.apply(self._enrich_row, axis=1, result_type="expand")
        return c

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _new_candle(bucket: datetime, price: float) -> dict:
        return {"dt": bucket, "open": price, "high": price,
                "low": price, "close": price}

    @staticmethod
    def _enrich(c: dict) -> dict:
        rng  = c["high"] - c["low"]
        body = abs(c["close"] - c["open"])
        c["range"]    = round(rng, 2)
        c["body"]     = round(body, 2)
        c["body_pct"] = round(body / max(rng, 0.01) * 100, 1)
        c["upper"]    = round(c["high"] - max(c["open"], c["close"]), 2)
        c["lower"]    = round(min(c["open"], c["close"]) - c["low"],  2)
        c["bull"]     = c["close"] >= c["open"]
        c["pattern"]  = CandleBuilder._classify(c)
        return c

    @staticmethod
    def _enrich_row(row) -> pd.Series:
        d = row.to_dict()
        d = CandleBuilder._enrich(d)
        return pd.Series(d)

    @staticmethod
    def _classify(c: dict) -> str:
        if c["range"] < 1:   return "Flat"
        bp = c["body_pct"]
        up = c["upper"] / max(c["range"], 0.01) * 100
        lo = c["lower"] / max(c["range"], 0.01) * 100
        if bp < 10:                          return "Doji"
        if bp > 55 and (up < 20 or lo < 20): return "StrongCandle"
        if lo > 50 and up < 15:             return "Hammer"
        if up > 50 and lo < 15:             return "Shooting Star"
        return "Bull" if c["bull"] else "Bear"

    def get_recent(self, n: int = 10) -> list:
        return list(self.candles)[-n:]


# ─────────────────────────────────────────────────────────────────────
# OI ANALYSER
# ─────────────────────────────────────────────────────────────────────

class OIAnalyser:
    """Extracts PCR, IV, OI walls from option chain snapshot."""

    @staticmethod
    def get_atm_iv(oi_df: pd.DataFrame, spot: float) -> tuple[float, float]:
        """Returns (ce_iv, pe_iv) at ATM strike."""
        if oi_df.empty:
            return 15.0, 15.0
        oi_df = oi_df.copy()
        oi_df["dist"] = abs(oi_df["Strike"] - spot)
        atm = oi_df.nsmallest(1, "dist").iloc[0]
        return float(atm["ce_iv"]), float(atm["pe_iv"])

    @staticmethod
    def get_pcr(oi_df: pd.DataFrame) -> float:
        """Total PCR = sum(PE_OI) / sum(CE_OI)."""
        if oi_df.empty:
            return 1.0
        total_pe = oi_df["pe_oi"].sum()
        total_ce = oi_df["ce_oi"].sum()
        return round(total_pe / max(total_ce, 0.01), 3)

    @staticmethod
    def get_walls(oi_df: pd.DataFrame, spot: float,
                  top_n: int = 3) -> tuple[list, list]:
        """
        Returns (ce_walls_above_spot, pe_walls_below_spot)
        Each is a list of (strike, oi_lakhs) sorted by OI desc.
        """
        if oi_df.empty:
            return [], []
        above = oi_df[oi_df["Strike"] >  spot].nlargest(top_n, "ce_oi")
        below = oi_df[oi_df["Strike"] <= spot].nlargest(top_n, "pe_oi")
        ce_walls = [(int(r["Strike"]), float(r["ce_oi"])) for _, r in above.iterrows()]
        pe_walls = [(int(r["Strike"]), float(r["pe_oi"])) for _, r in below.iterrows()]
        return ce_walls, pe_walls

    @staticmethod
    def get_nearest_wall(walls: list) -> tuple[int | None, float]:
        """Returns (strike, oi) of the nearest wall by strike, or (None, 0)."""
        if not walls:
            return None, 0.0
        return walls[0][0], walls[0][1]

    @staticmethod
    def get_oi_change_at_strike(oi_curr: pd.DataFrame, oi_prev: pd.DataFrame,
                                strike: int, side: str) -> float:
        """
        Returns OI change (in lakhs) at a specific strike for CE or PE.
        side = "ce" or "pe".  Positive = buildup, negative = unwinding.
        """
        col = f"{side}_oi"
        curr_val = oi_curr.loc[oi_curr["Strike"] == strike, col]
        prev_val = oi_prev.loc[oi_prev["Strike"] == strike, col]
        c = float(curr_val.iloc[0]) if len(curr_val) > 0 else 0.0
        p = float(prev_val.iloc[0]) if len(prev_val) > 0 else 0.0
        return c - p


# ─────────────────────────────────────────────────────────────────────
# SIGNAL ENGINE  (the brain)
# ─────────────────────────────────────────────────────────────────────

class SignalEngine:
    """
    Scores candles on 8 filters and generates BUY / EXIT signals.
    Signal fires when score >= MIN_SCORE (default 5/8).

    State machine:
        IDLE   → waiting for a valid signal
        IN_TRADE → tracking an open position for exit
    """

    FILTER_NAMES = [
        "pcr_direction", "strong_candle", "time_window",
        "no_consecutive", "range_ok", "wall_distance_ok", "vix_ok",
        "oi_buildup",
    ]

    def __init__(self):
        self.state         = "IDLE"
        self.open_trade    = None   # dict with trade details
        self.day_trades    = 0

        # Day-level values (set at open, persist all day)
        self.day_iv_ok     = False
        self.allowed_dirs  = ["CALL", "PUT"]
        self.pcr_open      = 1.0
        self.iv_open       = 15.0
        self.open_ce_walls = []
        self.open_pe_walls = []
        self.oi_open       = pd.DataFrame()   # OI snapshot at market open

        self.signal_log    = []

    # ── called once at market open (09:15) ──────────────────────────

    def init_day(self, oi_df: pd.DataFrame, spot: float) -> dict:
        """
        Run all pre-market checks. Must be called before any candle checks.
        Returns a dict with the day assessment.
        """
        self.day_trades         = 0
        self.state              = "IDLE"
        self.open_trade         = None
        self.oi_open            = oi_df.copy()

        ce_iv, pe_iv = OIAnalyser.get_atm_iv(oi_df, spot)
        self.iv_open = ce_iv
        self.pcr_open = OIAnalyser.get_pcr(oi_df)
        self.open_ce_walls, self.open_pe_walls = OIAnalyser.get_walls(oi_df, spot)

        # ── FILTER 1: IV check (hard gate — blocks entire day)
        self.day_iv_ok = (ce_iv < IV_MAX)

        # ── PCR direction
        if self.pcr_open > 1.2:
            self.allowed_dirs = ["PUT"]
        elif self.pcr_open < 0.8:
            self.allowed_dirs = ["CALL"]
        else:
            self.allowed_dirs = ["CALL", "PUT"]

        assessment = {
            "tradeable":     self.day_iv_ok,
            "iv_open":       round(ce_iv, 2),
            "pe_iv_open":    round(pe_iv, 2),
            "pcr":           round(self.pcr_open, 3),
            "allowed_dirs":  self.allowed_dirs,
            "ce_walls":      self.open_ce_walls,
            "pe_walls":      self.open_pe_walls,
            "block_reason":  None if self.day_iv_ok else f"IV {ce_iv:.1f}% ≥ {IV_MAX}%",
        }
        return assessment

    # ── called on every completed 5-min candle ──────────────────────

    def evaluate_candle(self, candle: dict, candles_history: list,
                        oi_df: pd.DataFrame, spot: float,
                        vix: float | None = None,
                        oi_prev: pd.DataFrame | None = None) -> dict | None:
        """
        Score-based evaluation. Returns a signal dict or None.
        Signal fires when score >= MIN_SCORE (default 5/8).
        Signal types:  'ENTRY'  or  'EXIT'
        """
        now_str = candle["dt"].strftime("%H:%M") if hasattr(candle["dt"], "strftime") \
                  else str(candle["dt"])[:5]

        # ── Check for exit first (if in trade) ──────────────────────
        if self.state == "IN_TRADE":
            return self._check_exit(candle, spot, now_str)

        # ── Hard gate: IV at open (only day-level block) ─────────────
        if not self.day_iv_ok:
            return None

        direction = "CALL" if candle["bull"] else "PUT"

        # ── Score each filter ────────────────────────────────────────
        score = 0
        passed = []

        # 1. PCR direction match
        if direction in self.allowed_dirs:
            score += 1
            passed.append("pcr_direction")

        # 2. StrongCandle pattern
        if candle["pattern"] == "StrongCandle":
            score += 1
            passed.append("strong_candle")

        # 3. Time window
        if TRADE_START <= now_str <= TRADE_END:
            score += 1
            passed.append("time_window")

        # 4. No consecutive opposite candles
        consec_ok = True
        if len(candles_history) >= MAX_CONSEC:
            prev_n = candles_history[-MAX_CONSEC:]
            if direction == "PUT"  and all(c["bull"] for c in prev_n):
                consec_ok = False
            if direction == "CALL" and all(not c["bull"] for c in prev_n):
                consec_ok = False
        if consec_ok:
            score += 1
            passed.append("no_consecutive")

        # 5. Range check (last 4 candles)
        rng4 = 999
        if len(candles_history) >= 4:
            last4 = candles_history[-4:]
            rng4  = max(c["high"] for c in last4) - min(c["low"] for c in last4)
        range_ok = rng4 >= MIN_RANGE_PTS
        if range_ok:
            score += 1
            passed.append("range_ok")

        # 6. Wall distance (merged: 25 <= dist <= 80)
        live_ce_walls, live_pe_walls = OIAnalyser.get_walls(oi_df, spot)
        entry_spot = candle["close"]

        if direction == "CALL":
            target_strike, target_oi = OIAnalyser.get_nearest_wall(
                [(s, o) for s, o in live_ce_walls if s > entry_spot])
        else:
            target_strike, target_oi = OIAnalyser.get_nearest_wall(
                [(s, o) for s, o in live_pe_walls if s < entry_spot])

        wall_dist = abs(target_strike - entry_spot) if target_strike else 0
        wall_ok = WALL_DIST_MIN <= wall_dist <= WALL_DIST_MAX
        if wall_ok:
            score += 1
            passed.append("wall_distance_ok")

        # 7. VIX check (skip CALL only when VIX > threshold)
        vix_ok = True
        if vix is not None and vix > VIX_MAX and direction == "CALL":
            vix_ok = False
        if vix_ok:
            score += 1
            passed.append("vix_ok")

        # 8. OI buildup at target wall confirms direction
        oi_ref = oi_prev if oi_prev is not None else self.oi_open
        buildup_ok = True  # pass by default if no data to compare
        oi_change_val = 0.0  # OI change at the relevant wall (in lakhs)
        oi_change_strike = None
        if target_strike and not oi_ref.empty:
            if direction == "CALL":
                # PE OI increasing at nearest support wall = writers building support
                pe_strike, _ = OIAnalyser.get_nearest_wall(
                    [(s, o) for s, o in live_pe_walls if s < entry_spot])
                if pe_strike:
                    oi_change_val = OIAnalyser.get_oi_change_at_strike(oi_df, oi_ref, pe_strike, "pe")
                    oi_change_strike = pe_strike
                    buildup_ok = oi_change_val > 0
            else:
                # CE OI increasing at nearest resistance wall = writers building resistance
                oi_change_val = OIAnalyser.get_oi_change_at_strike(oi_df, oi_ref, target_strike, "ce")
                oi_change_strike = target_strike
                buildup_ok = oi_change_val > 0
        if buildup_ok:
            score += 1
            passed.append("oi_buildup")

        # ── Check minimum score ──────────────────────────────────────
        if score < MIN_SCORE:
            return self._skip(now_str, direction,
                              f"Score {score}/8 < {MIN_SCORE} (passed: {', '.join(passed)})")

        # ── SCORE MET — GENERATE ENTRY SIGNAL ────────────────────────
        sl_level = (entry_spot - SL_POINTS) if direction == "CALL" \
                   else (entry_spot + SL_POINTS)

        # Estimate option price
        atm_row = oi_df.copy()
        atm_row["dist"] = abs(atm_row["Strike"] - entry_spot)
        atm = atm_row.nsmallest(1, "dist").iloc[0] if not atm_row.empty else None
        est_option_price = float(atm["ce_ltp"]) if (atm is not None and direction == "CALL") \
                      else float(atm["pe_ltp"]) if (atm is not None) else 0.0
        est_sl_px        = round(est_option_price * 0.5, 1)

        opt_strike = target_strike - 50 if direction == "CALL" else target_strike + 50
        buy_label  = f"NIFTY {opt_strike} {direction}"

        signal = {
            "type":         "ENTRY",
            "time":         now_str,
            "direction":    direction,
            "action":       f"BUY {direction}",
            "buy_label":    buy_label,
            "strike":       opt_strike,
            "entry_spot":   round(entry_spot, 2),
            "target_spot":  target_strike,
            "sl_spot":      round(sl_level, 2),
            "target_pts":   TARGET_POINTS,
            "sl_pts":       SL_POINTS,
            "option_price": round(est_option_price, 2),
            "option_sl":    est_sl_px,
            "pcr":          round(OIAnalyser.get_pcr(oi_df), 3),
            "target_wall":  target_strike,
            "wall_oi_L":    round(target_oi, 2),
            "wall_dist":    round(wall_dist, 0),
            "oi_change_L":  round(oi_change_val, 2),
            "oi_change_strike": oi_change_strike,
            "rng4":         round(rng4, 1),
            "body_pct":     candle["body_pct"],
            "vix":          round(vix, 2) if vix else None,
            "score":        score,
            "score_max":    8,
            "filters_passed": passed,
        }

        self.state      = "IN_TRADE"
        self.open_trade = signal.copy()
        self.open_trade["entry_time"] = now_str
        self.day_trades += 1

        self.signal_log.append({**signal, "outcome": "OPEN"})
        return signal

    # ── exit checker ─────────────────────────────────────────────────

    def _check_exit(self, candle: dict, spot: float, now_str: str) -> dict | None:
        if self.open_trade is None:
            self.state = "IDLE"
            return None

        direction    = self.open_trade["direction"]
        entry_spot   = self.open_trade["entry_spot"]
        target_spot  = self.open_trade["target_spot"]
        sl_level     = self.open_trade["sl_spot"]
        curr         = candle["close"]

        move   = (curr - entry_spot) if direction == "CALL" else (entry_spot - curr)
        exit_reason = None

        if move >= TARGET_POINTS:
            exit_reason = f"TARGET HIT +{move:.0f}pts"
        elif direction == "CALL" and target_spot and curr >= target_spot - 20:
            exit_reason = f"CE WALL REACHED {target_spot}"
        elif direction == "PUT"  and target_spot and curr <= target_spot + 20:
            exit_reason = f"PE WALL REACHED {target_spot}"
        elif direction == "CALL" and curr <= sl_level:
            exit_reason = f"STOP LOSS HIT -{abs(move):.0f}pts"
        elif direction == "PUT"  and curr >= sl_level:
            exit_reason = f"STOP LOSS HIT -{abs(move):.0f}pts"
        elif now_str >= TRADE_END:
            exit_reason = f"TIME EXIT {TRADE_END}"

        if exit_reason is None:
            return None   # trade still alive

        pnl_pts    = move
        pnl_lot    = round(pnl_pts * 0.5 * LOT_SIZE, 0)
        win        = pnl_pts > 0

        signal = {
            "type":        "EXIT",
            "time":        now_str,
            "direction":   direction,
            "action":      f"EXIT {direction}",
            "entry_spot":  entry_spot,
            "exit_spot":   round(curr, 2),
            "move_pts":    round(pnl_pts, 1),
            "pnl_lot":     pnl_lot,
            "win":         win,
            "reason":      exit_reason,
        }

        for s in self.signal_log:
            if s.get("outcome") == "OPEN" and s["direction"] == direction:
                s["outcome"]  = "WIN" if win else "LOSS"
                s["exit_time"]= now_str
                s["pnl_lot"]  = pnl_lot
                break

        self.state      = "IDLE"
        self.open_trade = None
        return signal

    # ── skip helper ──────────────────────────────────────────────────

    def _skip(self, now_str, direction, reason):
        log.debug(f"  SKIP {now_str} {direction}: {reason}")
        return None   # return None means no signal printed


# ─────────────────────────────────────────────────────────────────────
# SIGNAL PRINTER
# ─────────────────────────────────────────────────────────────────────

def print_signal(signal: dict):
    """Pretty-print a signal to console."""
    sep = "═" * 65
    if signal["type"] == "ENTRY":
        d = signal["direction"]
        clr = "🟢" if d == "CALL" else "🔴"
        sc = signal.get("score", "?")
        mx = signal.get("score_max", 8)
        fp = ", ".join(signal.get("filters_passed", []))
        print(f"\n{sep}")
        print(f"  {clr}  SIGNAL: {signal['action']}  [{signal['time']}]  Score: {sc}/{mx}")
        print(f"{sep}")
        print(f"  Entry spot    :  {signal['entry_spot']:,.2f}")
        print(f"  Target spot   :  {signal['target_spot']:,.0f}  (OI wall  {signal['wall_oi_L']:.1f}L)")
        print(f"  Wall distance :  {signal.get('wall_dist', 0):.0f} pts")
        print(f"  Stop loss     :  {signal['sl_spot']:,.2f}  (−{signal['sl_pts']} pts)")
        print(f"  Reward        :  +{signal['target_pts']} pts target")
        print(f"  Option ~price :  ₹{signal['option_price']:.1f}  |  Option SL ≈ ₹{signal['option_sl']:.1f}")
        print(f"  PCR           :  {signal['pcr']}")
        print(f"  Range (4 can) :  {signal.get('rng4', 0):.0f} pts")
        print(f"  Candle body   :  {signal['body_pct']:.0f}%")
        vix_val = signal.get("vix")
        print(f"  VIX           :  {vix_val:.1f}" if vix_val else "  VIX           :  N/A")
        print(f"  Filters       :  [{fp}]")
        print(f"  Max P&L/lot   :  ₹{round(signal['target_pts']*0.5*LOT_SIZE):,}")
        print(f"{sep}\n")

    elif signal["type"] == "EXIT":
        wl  = "✓ WIN" if signal["win"] else "✗ LOSS"
        clr = "💰" if signal["win"] else "🛑"
        print(f"\n  {clr}  EXIT SIGNAL  [{signal['time']}]  {wl}")
        print(f"     Entry: {signal['entry_spot']} → Exit: {signal['exit_spot']}")
        print(f"     Move : {signal['move_pts']:+.1f} pts   P&L: ₹{signal['pnl_lot']:,.0f}/lot")
        print(f"     Reason: {signal['reason']}\n")


# ─────────────────────────────────────────────────────────────────────
# BACKTEST RUNNER
# ─────────────────────────────────────────────────────────────────────

def run_backtest(db: DBClient, dates: list = None):
    """
    Run backtest across all available dates in the database.
    """
    if dates is None:
        dates = db.get_available_dates()

    if not dates:
        print("No dates found in database.")
        return

    print(f"\n{'═'*65}")
    print(f"  BACKTEST MODE — {len(dates)} dates")
    print(f"{'═'*65}")

    all_trades   = []
    cb           = CandleBuilder()

    for target_date in sorted(dates):
        date_str = str(target_date)[:10]
        print(f"\n─── {date_str} ───")

        engine = SignalEngine()

        # Get spot series from DB
        spot_df = db.get_spot_series(date_str)
        if spot_df.empty:
            print("  No market data. Skipping.")
            continue

        # Build 5-min candles
        candles_df = cb.build_from_df(spot_df, date_str)
        if candles_df.empty:
            print("  No candles built. Skipping.")
            continue

        # Open OI snapshot
        open_t   = candles_df.iloc[0]["dt"].strftime("%H:%M:%S")
        oi_open  = db.get_oi_snapshot(open_t, date_str)
        if oi_open.empty:
            print("  No OI data at open. Skipping.")
            continue

        spot_open = candles_df.iloc[0]["close"]

        # Init day
        assess = engine.init_day(oi_open, spot_open)
        iv_s   = f"IV {assess['iv_open']:.1f}%"
        pcr_s  = f"PCR {assess['pcr']:.3f}"
        dir_s  = str(assess["allowed_dirs"])

        if not assess["tradeable"]:
            print(f"  {iv_s}  {pcr_s}  → BLOCKED: {assess['block_reason']}")
            continue

        print(f"  {iv_s}  {pcr_s}  Allowed: {dir_s}  Candles: {len(candles_df)}")

        # Scan candles
        history  = []
        for _, row in candles_df.iterrows():
            candle = row.to_dict()
            t_str  = candle["dt"].strftime("%H:%M")

            # Get live OI at this candle time
            oi_now = db.get_oi_snapshot(candle["dt"].strftime("%H:%M:%S"), date_str)
            spot_now = candle["close"]

            # VIX snapshot
            vix = None
            try:
                vix = db.get_vix_snapshot(date_str, t_str + ":00")
            except Exception:
                pass

            signal = engine.evaluate_candle(candle, history, oi_now,
                                            spot_now, vix)
            if signal:
                print_signal(signal)
                if signal["type"] == "ENTRY":
                    all_trades.append({**signal, "date": date_str})

            history.append(candle)

    # Summary
    if all_trades:
        rdf = pd.DataFrame(all_trades)
        print(f"\n{'═'*65}")
        print(f"  BACKTEST SUMMARY")
        print(f"{'═'*65}")
        print(f"  Total entry signals : {len(rdf)}")
        log_df = pd.DataFrame([s for e in [engine.signal_log] for s in e])
        closed = log_df[log_df.get("outcome", pd.Series()).isin(["WIN","LOSS"])] if not log_df.empty else pd.DataFrame()
        if not closed.empty:
            wins = closed[closed["outcome"]=="WIN"]
            print(f"  Completed trades    : {len(closed)}")
            print(f"  Win rate            : {len(wins)}/{len(closed)} = {len(wins)/len(closed)*100:.1f}%")
            print(f"  Total P&L           : ₹{closed['pnl_lot'].sum():,.0f}")
        rdf.to_csv("backtest_signals.csv", index=False)
        print(f"\n  Saved → backtest_signals.csv")


# ─────────────────────────────────────────────────────────────────────
# LIVE RUNNER
# ─────────────────────────────────────────────────────────────────────

def run_live(db: DBClient):
    """
    Live mode: runs continuously, polls Dhan API every 5 minutes,
    reads OI from DB, generates signals.
    """
    if not DHAN_OK:
        print("Cannot run live mode — dhanhq not installed.")
        return

    live    = DhanLiveClient()
    engine  = SignalEngine()
    cb      = CandleBuilder()
    history = []
    today   = date.today().strftime("%Y-%m-%d")
    day_initialized = False

    print(f"\n{'═'*65}")
    print(f"  LIVE MODE — {today}")
    print(f"  Scanning every {SCAN_INTERVAL//60} minutes")
    print(f"  Press Ctrl+C to stop")
    print(f"{'═'*65}\n")

    while True:
        now = datetime.now()
        t_str = now.strftime("%H:%M")

        # Only run during market hours
        if t_str < "09:10" or t_str > "15:35":
            print(f"  [{t_str}] Outside market hours. Waiting...")
            time.sleep(60)
            continue

        try:
            # Get live spot price
            spot = live.get_spot()
            if spot is None:
                log.warning("Could not fetch live spot. Retrying...")
                time.sleep(30)
                continue

            log.info(f"Spot: {spot:.2f}")

            # Get latest OI from DB
            oi_now = db.get_oi_snapshot(now.strftime("%H:%M:%S"), today)
            if oi_now.empty:
                log.warning(f"No OI data in DB for {today} at {t_str}")
                time.sleep(SCAN_INTERVAL)
                continue

            # Initialize day at open
            if not day_initialized and t_str >= "09:15":
                assess = engine.init_day(oi_now, spot)
                print(f"\n  📊 DAY ASSESSMENT [{today}]")
                print(f"     IV : {assess['iv_open']:.1f}%  {'✓ TRADEABLE' if assess['tradeable'] else '✗ BLOCKED — ' + str(assess['block_reason'])}")
                print(f"     PCR: {assess['pcr']:.3f}  →  Allowed directions: {assess['allowed_dirs']}")
                ce_w = assess.get("ce_walls", [])
                pe_w = assess.get("pe_walls", [])
                if ce_w: print(f"     CE walls (resistance): {[(s,round(o,1)) for s,o in ce_w[:3]]}")
                if pe_w: print(f"     PE walls (support)   : {[(s,round(o,1)) for s,o in pe_w[:3]]}")
                day_initialized = True

                if not assess["tradeable"]:
                    print(f"\n  ⛔ NO TRADES TODAY — {assess['block_reason']}")
                    break

            # Feed tick to candle builder
            completed_candle = cb.feed_tick(now, spot)

            if completed_candle:
                log.info(f"Candle completed: {completed_candle['dt'].strftime('%H:%M')} "
                         f"O:{completed_candle['open']:.0f} "
                         f"H:{completed_candle['high']:.0f} "
                         f"L:{completed_candle['low']:.0f} "
                         f"C:{completed_candle['close']:.0f} "
                         f"→ {completed_candle['pattern']}")

                # VIX snapshot from DB
                vix = None
                try:
                    vix = db.get_vix_snapshot(today, t_str + ":00")
                except Exception:
                    pass

                signal = engine.evaluate_candle(completed_candle, history,
                                                oi_now, spot, vix)
                if signal:
                    print_signal(signal)

                    # Save to CSV
                    pd.DataFrame([signal]).to_csv(
                        "live_signals.csv",
                        mode="a", header=not __import__("os").path.exists("live_signals.csv"),
                        index=False
                    )

                history.append(completed_candle)

        except KeyboardInterrupt:
            print("\n  Stopped by user.")
            break
        except Exception as e:
            log.error(f"Error in main loop: {e}", exc_info=True)

        time.sleep(SCAN_INTERVAL)


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Nifty Options Signal Engine")
    parser.add_argument("--backtest", action="store_true",
                        help="Run backtest on all DB dates")
    parser.add_argument("--today",    action="store_true",
                        help="Run on today's data from DB (one pass)")
    parser.add_argument("--date",     type=str, default=None,
                        help="Run on specific date YYYY-MM-DD")
    args = parser.parse_args()

    # ── Connect to DB
    if not MYSQL_OK:
        print("MySQL connector not available. Install with: pip install mysql-connector-python")
        sys.exit(1)

    try:
        db = DBClient(DB_CONFIG)
        db.connect()
        print("✓ Database connected")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        print("  Check DB_CONFIG at top of file.")
        sys.exit(1)

    # ── Run mode
    if args.backtest:
        run_backtest(db)
    elif args.today:
        today = date.today().strftime("%Y-%m-%d")
        run_backtest(db, dates=[today])
    elif args.date:
        run_backtest(db, dates=[args.date])
    else:
        run_live(db)


if __name__ == "__main__":
    main()
