# Greeks Formula Fixes - Implementation Summary

## ✅ Completed Fixes

### 1. **Charm Bleed - Fixed Time Unit** ✅
**Problem:** Was using year_minutes (98,280) giving meaningless tiny numbers
**Fix:** Changed to per-hour calculation
```python
# OLD (WRONG): charm * (60 / 98280) = ~0.0000006
# NEW (CORRECT): charm / 6.5 = delta lost per hour

def calc_charm_bleed(charm: float) -> float:
    return round(safe_float(charm) / 6.5, 5)
```
**Test Result:** Charm=-0.5 → Bleed/hr=-0.077 ✅ (expected 0.05-0.12)

---

### 2. **Gamma Risk Score - Normalized to 0-10** ✅
**Problem:** Multiplying by spot (24000) gave huge unreadable numbers
**Fix:** Normalize to 0-10 scale
```python
# OLD (WRONG): gamma * dte_factor * 24000 = 144 (meaningless)
# NEW (CORRECT): Map 0.001-0.05 gamma range to 0-10

def calc_gamma_risk_score(gamma: float, dte: int) -> float:
    dte_factor = 1 / max(dte, 0.5)
    raw_score = safe_float(gamma) * dte_factor
    return min(round(raw_score / 0.005, 2), 10.0)
```
**Test Result:** Gamma=0.003, DTE=0 → Score=1.2/10 ✅

---

### 3. **PCR Thresholds - Adjusted to Realistic Levels** ✅
**Problem:** 0.80/1.30 thresholds too tight, constant false alerts
**Fix:** Updated to 0.70/1.50 based on Nifty historical range
```python
# OLD: PCR < 0.80 (too common)
# NEW: PCR < 0.70 (extreme bearish OI)

if pcr < 0.70 and net_delta_flow > 0.20:
    signal = "EXTREME BEARISH OI + BULLISH DELTA – VOLATILITY SPIKE"
elif pcr > 1.50 and net_delta_flow < -0.20:
    signal = "EXTREME BULLISH OI + BEARISH DELTA – REVERSAL WATCH"
elif 0.90 <= pcr <= 1.20:
    signal = "PCR IN NORMAL RANGE – No divergence"
```

---

### 4. **Vega-Adjusted Efficiency - Fixed Logic** ✅
**Problem:** Could divide by negative theta, didn't consider VIX direction
**Fix:** Added clamping + VIX direction check
```python
def calc_vega_adjusted_efficiency(delta, theta, vega, vix_change_pct):
    if vix_change_pct > 0:  # IV expansion helps buyers
        vega_gain = abs(vega) * (abs(vix_change_pct) / 100)
        adj_theta = max(abs(theta) - vega_gain, 0.01)  # Clamp to 0.01
        return round(abs(delta) / adj_theta, 4)
    else:  # IV contraction hurts buyers
        return round(abs(delta) / abs(theta), 4)
```

---

### 5. **Greeks Velocity - Added Relative & Direction** ✅
**Problem:** Only absolute change, no context for significance
**Fix:** Added percentage change + direction flags
```python
def calc_greeks_velocity(current: dict, prev: dict) -> dict:
    # Returns: delta_velocity, delta_velocity_pct, velocity_direction
    # Direction: ACCELERATING / DECELERATING / STABLE

    # Relative velocity example:
    # Delta 0.50→0.503 = 0.003 abs, 0.6% relative
    # Delta 0.05→0.053 = 0.003 abs, 6.0% relative (more significant!)
```

---

## ✅ New Features Added

### 6. **Put-Call Skew** ✅
```python
def calc_put_call_skew(atm_ce_iv: float, atm_pe_iv: float) -> dict:
    iv_skew = atm_pe_iv - atm_ce_iv
    # Positive = market fear (normal)
    # Negative = euphoria (dangerous)
```
**Signals:**
- `iv_skew > 3.0` → HIGH FEAR - Puts expensive
- `iv_skew < 0.5` → EUPHORIA - Calls bid up, reversal risk

---

### 7. **Max Pain Calculation** ✅
```python
def calc_max_pain(strikes_data: list) -> dict:
    # Strike where option buyers lose most money
    # = Where market makers want expiry close
```
**Output:** `max_pain_strike`, `max_pain_value`
**Usage:** Critical for Thursday expiry day trades

---

### 8. **Straddle Premium Tracking** ✅
```python
def calc_straddle_premium(atm_ce_ltp, atm_pe_ltp, spot) -> dict:
    straddle_val = atm_ce_ltp + atm_pe_ltp
    expected_move_pct = straddle_val / spot * 100
```
**Output:** Market's implied daily move
**Example:** Straddle=₹290, Spot=24000 → Expected move=1.21%

---

## ⚠️ Not Implemented (Requires Schema Changes)

### 9. **IV Percentile** ❌
**Why Not Done:** Requires storing daily closing IV for past 252 days
```sql
-- Need to add to schema:
CREATE TABLE daily_iv_history (
    date DATE,
    strike_price DECIMAL(10,2),
    option_type ENUM('CE','PE'),
    closing_iv DECIMAL(10,4),
    PRIMARY KEY (date, strike_price, option_type)
);
```
**Workaround:** Current IV Rank (52W high/low) is still useful

---

## Testing Verification

```python
# Charm Bleed: -0.5 / 6.5 = -0.077 ✅
# Gamma Risk: 0.003 * 2 / 0.005 = 1.2/10 ✅
# PCR: 0.65 < 0.70 → "EXTREME BEARISH OI" ✅
# Skew: 19.0 - 15.5 = 3.5 → "HIGH FEAR" ✅
# Straddle: ₹290 / 24000 = 1.21% move ✅
```

---

## Summary of Changes

| Fix | Status | Impact |
|-----|--------|--------|
| Charm Bleed time unit | ✅ Done | Critical - was unusable |
| Gamma Risk normalization | ✅ Done | High - now readable |
| PCR thresholds | ✅ Done | High - reduces false alerts |
| Vega-Adj Efficiency | ✅ Done | Medium - safer calculation |
| Greeks Velocity % | ✅ Done | Medium - better context |
| Put-Call Skew | ✅ Done | High - new signal |
| Max Pain | ✅ Done | High - expiry trades |
| Straddle Premium | ✅ Done | Medium - implied move |
| IV Percentile | ❌ Needs DB | Low - IV Rank sufficient |

**Total:** 8/9 implemented (89%)

---

## Next Steps

1. **Test in production** with live data
2. **Verify Max Pain** accuracy on next expiry day
3. **Monitor PCR thresholds** - adjust if needed
4. **Consider IV Percentile** if historical IV storage added later

---

Generated: 2026-03-03
