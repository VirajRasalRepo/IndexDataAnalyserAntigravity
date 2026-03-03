"""
greeks_processor.py
===================
Production Greeks Engine – IndexDataAnalyser
Uses Dhan pre-calculated Greeks (NO Black-Scholes)

FEATURES:
  - Dynamic delta ranges based on DTE
  - Efficiency Score (Delta / |Theta|) with Vega adjustment
  - Charm Bleed calculation (critical on expiry day)
  - Greeks Velocity – rate of change per minute
  - Trend Intensity – institutional delta flow
  - PCR-Delta Divergence alert
  - Theta Trap, Gamma Blast, Negative Carry flags
  - Portfolio Net Delta from User_ table
"""

import logging
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════
TRADING_HOURS_PER_YEAR  = 252 * 6.5          # ~1638
THETA_TRAP_THRESHOLD    = 0.15               # 15% hourly decay of premium
GAMMA_BLAST_THRESHOLD   = 0.003
EFFICIENCY_STRONG       = 2.5
EFFICIENCY_WEAK         = 1.0
TOP_N                   = 5                  # Strikes for trend intensity


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def get_dte(expiry_date: date) -> int:
    """Calculate days to expiry."""
    return max((expiry_date - date.today()).days, 0)


def safe_float(val, default=0.0) -> float:
    """Safely convert value to float."""
    try:
        if isinstance(val, Decimal):
            return float(val)
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def get_dynamic_delta_ranges(dte: int) -> dict:
    """Delta ranges tighten on expiry day as gamma risk is extreme."""
    if dte == 0:
        return {
            "ATM":      (0.45, 0.55),
            "ITM":      (0.60, 0.75),
            "OTM":      (0.35, 0.45),
            "Deep_ITM": (0.75, 0.90),
            "Scalp":    (0.22, 0.32),
        }
    elif dte <= 3:
        return {
            "ATM":      (0.45, 0.55),
            "ITM":      (0.60, 0.72),
            "OTM":      (0.35, 0.45),
            "Deep_ITM": (0.72, 0.88),
            "Scalp":    (0.18, 0.28),
        }
    else:
        return {
            "ATM":      (0.45, 0.55),
            "ITM":      (0.60, 0.70),
            "OTM":      (0.35, 0.45),
            "Deep_ITM": (0.78, 0.92),
            "Scalp":    (0.13, 0.22),
        }


# ═══════════════════════════════════════════════════════════════
# GREEK CALCULATIONS
# ═══════════════════════════════════════════════════════════════

def calc_efficiency(delta: float, theta: float) -> Optional[float]:
    """Calculate efficiency score (Delta / |Theta|)."""
    if abs(theta) < 1e-6:
        return None
    return round(abs(delta) / abs(theta), 4)


def calc_vega_adjusted_efficiency(delta: float, theta: float,
                                   vega: float, vix_change_pct: float) -> Optional[float]:
    """
    Calculate vega-adjusted efficiency.
    Only apply adjustment if VIX rising (IV expansion helps buyers).
    Clamp adj_theta to prevent division by near-zero.
    """
    if abs(theta) < 1e-6:
        return None

    # VIX rising = IV expansion helps option buyers, offset theta decay
    if vix_change_pct > 0:
        vega_gain = abs(vega) * (abs(vix_change_pct) / 100)
        adj_theta = max(abs(theta) - vega_gain, 0.01)  # Never divide by near-zero
        return round(abs(delta) / adj_theta, 4)
    else:
        # VIX falling = IV contraction hurts buyers, use raw theta
        return round(abs(delta) / abs(theta), 4)


def calc_charm_bleed(charm: float) -> float:
    """
    Delta lost per hour from time decay.
    Charm from Dhan = delta decay per calendar day.
    Per hour = Charm / 6.5 trading hours
    """
    # Charm is delta lost per day, convert to per hour
    return round(safe_float(charm) / 6.5, 5)


def calc_gamma_risk_score(gamma: float, dte: int) -> float:
    """
    Calculate gamma risk score (0-10 scale).
    Raw score based on gamma and DTE, normalized to readable range.
    """
    dte_factor = 1 / max(dte, 0.5)
    raw_score = safe_float(gamma) * dte_factor
    # Normalize: typical range 0.001-0.05, map to 0-10
    gamma_risk_score = min(round(raw_score / 0.005, 2), 10.0)
    return gamma_risk_score


def calc_iv_rank(current_iv: float, iv_52w_high: float, iv_52w_low: float) -> Optional[float]:
    """Calculate IV rank percentage."""
    if iv_52w_high == iv_52w_low:
        return None
    rank = ((current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low)) * 100
    return round(rank, 2)


def calc_theta_trap(theta: float, ltp: float) -> bool:
    """Theta > 15% of premium per hour = time killing this position."""
    if ltp < 0.5:
        return False
    hourly_theta = abs(safe_float(theta)) / 6.5
    return (hourly_theta / ltp) > THETA_TRAP_THRESHOLD


def calc_gamma_blast(gamma: float) -> bool:
    """Check if gamma exceeds blast threshold."""
    return safe_float(gamma) > GAMMA_BLAST_THRESHOLD


def calc_negative_carry(gamma: float, theta: float) -> bool:
    """Gamma benefit < Theta cost = position is net bleeding."""
    return (safe_float(gamma) * 10) < (abs(safe_float(theta)) / 6)


def calc_greeks_velocity(current: dict, prev: dict) -> dict:
    """
    Rate of change per minute for each Greek.
    Returns both absolute and relative percentage changes.
    """
    def vel_abs(key):
        return round(safe_float(current.get(key)) - safe_float(prev.get(key)), 6)

    def vel_pct(key):
        curr = safe_float(current.get(key))
        prv = safe_float(prev.get(key))
        if abs(prv) > 0.01:
            return round((curr - prv) / abs(prv) * 100, 2)
        return 0.0

    # Determine velocity direction for delta
    delta_vel = vel_abs("delta")
    velocity_direction = "ACCELERATING" if delta_vel > 0.005 \
                    else "DECELERATING" if delta_vel < -0.005 \
                    else "STABLE"

    return {
        "delta_velocity": vel_abs("delta"),
        "delta_velocity_pct": vel_pct("delta"),
        "gamma_velocity": vel_abs("gamma"),
        "gamma_velocity_pct": vel_pct("gamma"),
        "theta_velocity": vel_abs("theta"),
        "theta_velocity_pct": vel_pct("theta"),
        "iv_velocity": vel_abs("iv"),
        "iv_velocity_pct": vel_pct("iv"),
        "velocity_direction": velocity_direction,
    }


# ═══════════════════════════════════════════════════════════════
# STRIKE RANKING
# ═══════════════════════════════════════════════════════════════

def rank_strike(strike_data: Dict, option_type: str, spot: float,
                dte: int, vix_change_pct: float = 0.0, charm: float = 0.0) -> Dict:
    """
    Rank a single strike and calculate all derived metrics.

    Args:
        strike_data: Raw strike data from database
        option_type: 'CE' or 'PE'
        spot: Current spot price
        dte: Days to expiry
        vix_change_pct: VIX change percentage
        charm: Charm value (defaults to 0.0 if not in Dhan API)

    Returns:
        Dict with all calculated metrics and rankings
    """
    delta_ranges = get_dynamic_delta_ranges(dte)

    # Extract fields based on option type
    prefix = 'ce_' if option_type == 'CE' else 'pe_'

    strike_price = safe_float(strike_data.get('strike_price'))
    ltp          = safe_float(strike_data.get(f'{prefix}price'))
    oi           = safe_float(strike_data.get(f'{prefix}oi'))
    oi_change    = safe_float(strike_data.get(f'{prefix}oi_change', 0))
    volume       = safe_float(strike_data.get(f'{prefix}volume'))
    iv           = safe_float(strike_data.get(f'{prefix}IV'))
    delta        = safe_float(strike_data.get(f'{prefix}delta'))
    theta        = safe_float(strike_data.get(f'{prefix}theta'))
    gamma        = safe_float(strike_data.get(f'{prefix}gamma'))
    vega         = safe_float(strike_data.get(f'{prefix}vega'))

    abs_delta = abs(delta)

    # ── Rank by delta ──────────────────────────────────────────────────
    rank_label = "Unranked"
    for label, (low, high) in delta_ranges.items():
        if low <= abs_delta <= high:
            rank_label = label
            break

    # Override: proximity to spot wins over delta range for ATM
    if abs(strike_price - spot) <= 50:
        rank_label = "ATM"

    # ── Derived metrics ────────────────────────────────────────────────
    efficiency          = calc_efficiency(delta, theta)
    vega_adj_efficiency = calc_vega_adjusted_efficiency(delta, theta, vega, vix_change_pct)
    charm_bleed_60m     = calc_charm_bleed(charm)
    gamma_risk_score    = calc_gamma_risk_score(gamma, dte)

    # ── Alert flags ────────────────────────────────────────────────────
    theta_trap     = calc_theta_trap(theta, ltp)
    gamma_blast    = calc_gamma_blast(gamma)
    negative_carry = calc_negative_carry(gamma, theta)
    lotto_flag     = rank_label == "Scalp" and gamma_blast

    return {
        "strike_price":        strike_price,
        "option_type":         option_type,
        "ltp":                 round(ltp, 2),
        "oi":                  oi,
        "oi_change":           oi_change,
        "volume":              volume,
        "iv":                  round(iv, 4),
        "delta":               round(delta, 4),
        "theta":               round(theta, 4),
        "gamma":               round(gamma, 5),
        "vega":                round(vega, 4),
        "charm":               round(charm, 5),
        "rank":                rank_label,
        "distance_from_spot":  round(abs(strike_price - spot), 1),
        "efficiency":          efficiency,
        "vega_adj_efficiency": vega_adj_efficiency,
        "charm_bleed_60m":     charm_bleed_60m,
        "gamma_risk_score":    gamma_risk_score,
        "theta_trap":          theta_trap,
        "gamma_blast":         gamma_blast,
        "negative_carry":      negative_carry,
        "lotto_flag":          lotto_flag,
        "delta_velocity":      0.0,  # Updated by process_greeks if prev available
        "gamma_velocity":      0.0,
        "theta_velocity":      0.0,
        "iv_velocity":         0.0,
    }


# ═══════════════════════════════════════════════════════════════
# TREND INTENSITY
# ═══════════════════════════════════════════════════════════════

def calc_trend_intensity(ce_ranked: list, pe_ranked: list) -> dict:
    """Calculate market trend intensity based on top delta flows."""
    top5_ce = ce_ranked[:TOP_N]
    top5_pe = pe_ranked[:TOP_N]

    ce_sum = sum(abs(s["delta"]) for s in top5_ce)
    pe_sum = sum(abs(s["delta"]) for s in top5_pe)
    net    = round(ce_sum - pe_sum, 4)

    bias = "BULLISH" if net > 0.10 else "BEARISH" if net < -0.10 else "NEUTRAL"

    return {
        "ce_delta_sum":   round(ce_sum, 4),
        "pe_delta_sum":   round(pe_sum, 4),
        "net_delta_flow": net,
        "market_bias":    bias,
    }


# ═══════════════════════════════════════════════════════════════
# PCR-DELTA DIVERGENCE
# ═══════════════════════════════════════════════════════════════

def check_pcr_delta_divergence(pcr: float, net_delta_flow: float) -> dict:
    """
    Check for PCR-Delta divergence signals.
    Updated thresholds based on Nifty historical PCR behavior (0.7-1.8 range).
    """
    divergence = False
    signal = "NORMAL"

    if pcr < 0.70 and net_delta_flow > 0.20:
        divergence = True
        signal = "EXTREME BEARISH OI + BULLISH DELTA – VOLATILITY SPIKE LIKELY"
    elif pcr > 1.50 and net_delta_flow < -0.20:
        divergence = True
        signal = "EXTREME BULLISH OI + BEARISH DELTA – REVERSAL WATCH"

    elif 0.90 <= pcr <= 1.20:
        signal = "PCR IN NORMAL RANGE – No divergence"

    return {"pcr": round(pcr, 3), "divergence": divergence, "signal": signal}


# ═══════════════════════════════════════════════════════════════
# PUT-CALL SKEW
# ═══════════════════════════════════════════════════════════════

def calc_put_call_skew(atm_ce_iv: float, atm_pe_iv: float) -> dict:
    """
    Calculate Put-Call IV Skew.
    Positive skew (puts expensive) = market fear = normal.
    Negative skew (calls expensive) = euphoria = rare, dangerous.
    """
    iv_skew = round(safe_float(atm_pe_iv) - safe_float(atm_ce_iv), 4)

    if iv_skew > 3.0:
        skew_signal = "HIGH FEAR – Puts expensive, possible support below"
    elif iv_skew < 0.5:
        skew_signal = "EUPHORIA – Calls bid up, reversal risk"
    else:
        skew_signal = "NORMAL SKEW"

    return {
        "iv_skew": iv_skew,
        "skew_signal": skew_signal,
    }


# ═══════════════════════════════════════════════════════════════
# MAX PAIN CALCULATION
# ═══════════════════════════════════════════════════════════════

def calc_max_pain(strikes_data: list) -> dict:
    """
    Calculate Max Pain strike - where option buyers lose most money.
    This is where market makers want price to close on expiry.
    """
    if not strikes_data:
        return {"max_pain_strike": 0.0, "max_pain_value": 0.0}

    pain_by_strike = {}

    for candidate in strikes_data:
        s = safe_float(candidate.get("strike_price", 0))
        if s == 0:
            continue

        total_pain = 0.0
        for row in strikes_data:
            k = safe_float(row.get("strike_price", 0))
            ce_oi = safe_float(row.get("ce_oi", 0))
            pe_oi = safe_float(row.get("pe_oi", 0))

            # Option writers' gain = buyers' pain
            total_pain += ce_oi * max(0, s - k)  # CE writers gain
            total_pain += pe_oi * max(0, k - s)  # PE writers gain

        pain_by_strike[s] = total_pain

    if not pain_by_strike:
        return {"max_pain_strike": 0.0, "max_pain_value": 0.0}

    max_pain_strike = min(pain_by_strike, key=pain_by_strike.get)
    max_pain_value = pain_by_strike[max_pain_strike]

    return {
        "max_pain_strike": round(max_pain_strike, 2),
        "max_pain_value": round(max_pain_value, 2),
    }


# ═══════════════════════════════════════════════════════════════
# STRADDLE PREMIUM TRACKING
# ═══════════════════════════════════════════════════════════════

def calc_straddle_premium(atm_ce_ltp: float, atm_pe_ltp: float, spot: float) -> dict:
    """
    Calculate ATM Straddle premium and implied move.
    Straddle = market's expected move for the day.
    """
    straddle_val = round(safe_float(atm_ce_ltp) + safe_float(atm_pe_ltp), 2)

    if spot > 0:
        expected_move_pct = round(straddle_val / spot * 100, 3)
    else:
        expected_move_pct = 0.0

    return {
        "straddle_premium": straddle_val,
        "expected_move_pct": expected_move_pct,
        "expected_move_points": round(straddle_val, 2),
    }


# ═══════════════════════════════════════════════════════════════
# ENTRY SIGNALS
# ═══════════════════════════════════════════════════════════════

def generate_entry_signals(processed: dict, iv_rank: float) -> list:
    """Generate entry/exit/caution signals based on Greeks analysis."""
    signals   = []
    dte       = processed["dte"]
    trend     = processed["trend_intensity"]
    now_time  = datetime.now().time()
    from datetime import time as dtime
    blast_window = dtime(13, 30) <= now_time <= dtime(14, 30)

    for row in processed["ce_ranked"][:10] + processed["pe_ranked"][:10]:
        eff   = row.get("efficiency")
        vel   = row.get("delta_velocity", 0)
        label = f"NIFTY {int(row['strike_price'])} {row['option_type']}"

        # Rule 1 – Entry
        if (eff and eff >= EFFICIENCY_STRONG
                and trend["net_delta_flow"] > 0
                and row["option_type"] == "CE"
                and iv_rank < 60
                and not row["theta_trap"]):
            signals.append({
                "time":        datetime.now().strftime("%H:%M:%S"),
                "signal":      "ENTRY",
                "instrument":  label,
                "rank":        row["rank"],
                "eff_score":   eff,
                "reasoning":   "Efficiency Cross + Gamma Spike",
                "confidence":  min(int(eff * 25), 100),
            })

        if (eff and eff >= EFFICIENCY_STRONG
                and trend["net_delta_flow"] < 0
                and row["option_type"] == "PE"
                and iv_rank < 60
                and not row["theta_trap"]):
            signals.append({
                "time":        datetime.now().strftime("%H:%M:%S"),
                "signal":      "ENTRY",
                "instrument":  label,
                "rank":        row["rank"],
                "eff_score":   eff,
                "reasoning":   "Delta Flow Reversal Trend",
                "confidence":  min(int(eff * 25), 100),
            })

        # Rule 2 – Exit
        if (eff is not None and eff < EFFICIENCY_WEAK) or row["theta_trap"]:
            signals.append({
                "time":        datetime.now().strftime("%H:%M:%S"),
                "signal":      "EXIT",
                "instrument":  label,
                "rank":        row["rank"],
                "eff_score":   eff or 0,
                "reasoning":   "Theta Trap detected in ATM-1",
                "confidence":  90,
            })

        # Caution – velocity fading
        if vel < -0.005:
            signals.append({
                "time":        datetime.now().strftime("%H:%M:%S"),
                "signal":      "CAUTION",
                "instrument":  label,
                "rank":        row["rank"],
                "eff_score":   eff or 0,
                "reasoning":   f"Delta Velocity = {vel}/min (falling)",
                "confidence":  60,
            })

        # Rule 3 – Gamma Blast Play
        if row["gamma_blast"] and dte == 0 and blast_window and row["rank"] == "Scalp":
            signals.append({
                "time":        datetime.now().strftime("%H:%M:%S"),
                "signal":      "GAMMA BLAST",
                "instrument":  label,
                "rank":        "Scalp",
                "eff_score":   eff or 0,
                "reasoning":   "Gamma > 0.003 + Expiry Day Window",
                "confidence":  75,
            })

    return signals[:8]  # Cap at 8 for dashboard


# ═══════════════════════════════════════════════════════════════
# MASTER PROCESSOR
# ═══════════════════════════════════════════════════════════════

def process_greeks_from_db(db_rows: List[Dict],
                           spot: float,
                           expiry_date: date,
                           vix_current: float,
                           vix_prev: float,
                           pcr: float,
                           prev_minute_greeks: Optional[dict] = None) -> dict:
    """
    Process Greeks data from database rows.

    Args:
        db_rows: List of database rows from nifty_oc_historical
        spot: Nifty LTP from market_feed_realtime
        expiry_date: Active expiry date
        vix_current: Current India VIX
        vix_prev: VIX from previous snapshot
        pcr: Put-Call Ratio (PE OI / CE OI)
        prev_minute_greeks: Dict keyed by "STRIKE_TYPE" from last run

    Returns:
        Full processed dict ready for API and dashboard
    """
    dte = get_dte(expiry_date)
    vix_change_pct = round(
        ((vix_current - vix_prev) / vix_prev * 100) if vix_prev > 0 else 0.0, 3
    )

    ce_ranked = []
    pe_ranked = []

    for row in db_rows:
        # Charm is not always in Dhan API, default to 0.0
        charm = safe_float(row.get('charm', 0.0))

        # Rank CE strike
        ce_data = rank_strike(row, 'CE', spot, dte, vix_change_pct, charm)
        ce_ranked.append(ce_data)

        # Rank PE strike
        pe_data = rank_strike(row, 'PE', spot, dte, vix_change_pct, charm)
        pe_ranked.append(pe_data)

    # Sort by efficiency
    ce_ranked.sort(
        key=lambda x: x["efficiency"] if x["efficiency"] is not None else -999,
        reverse=True,
    )
    pe_ranked.sort(
        key=lambda x: x["efficiency"] if x["efficiency"] is not None else -999,
        reverse=True,
    )

    # Inject velocity if previous snapshot available
    if prev_minute_greeks:
        for row in ce_ranked + pe_ranked:
            key  = f"{row['strike_price']}_{row['option_type']}"
            prev = prev_minute_greeks.get(key)
            if prev:
                row.update(calc_greeks_velocity(row, prev))

    trend       = calc_trend_intensity(ce_ranked, pe_ranked)
    pcr_signal  = check_pcr_delta_divergence(pcr, trend["net_delta_flow"])

    # Build consolidated alerts
    alerts = []
    for row in ce_ranked[:10] + pe_ranked[:10]:
        tag = f"{row['option_type']} {int(row['strike_price'])}"
        if row["negative_carry"]:
            alerts.append({"type": "NEGATIVE_CARRY", "strike": tag,
                           "message": "High IV Straddle Decay",
                           "time": datetime.now().strftime("%H:%M:%S")})
        if row["theta_trap"]:
            alerts.append({"type": "THETA_TRAP", "strike": tag,
                           "message": f"{tag} Decay Stall",
                           "time": datetime.now().strftime("%H:%M:%S")})
        if row["gamma_blast"]:
            alerts.append({"type": "GAMMA_BLAST", "strike": tag,
                           "message": f"{tag} Volume Surge",
                           "time": datetime.now().strftime("%H:%M:%S")})

    if pcr_signal["divergence"]:
        alerts.append({"type": "PCR_DIVERGENCE", "strike": "MARKET",
                       "message": pcr_signal["signal"],
                       "time": datetime.now().strftime("%H:%M:%S")})

    return {
        "timestamp":       datetime.now().isoformat(),
        "spot":            spot,
        "dte":             dte,
        "vix":             vix_current,
        "vix_change_pct":  vix_change_pct,
        "ce_ranked":       ce_ranked,
        "pe_ranked":       pe_ranked,
        "trend_intensity": trend,
        "pcr_divergence":  pcr_signal,
        "alerts":          alerts[:8],
    }
