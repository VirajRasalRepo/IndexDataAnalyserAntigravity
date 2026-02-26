# Volume Measurement Explained

## What is Volume in Options Trading?

**Volume** = Total number of option contracts **traded** (bought + sold) during the day.

---

## How It's Measured

### Example:
If you see **Vol(K): 309** for strike 25300 CE:
- **309K** = **309,000 contracts**
- This means 309,000 option contracts of this strike were traded since market open

### Volume Difference (ΔVol):
**ΔVol(K)** = Change in volume since last measurement (3 minutes ago)

If you see **ΔVol(K): +309**:
- **+309K** = **+309,000 contracts**
- This means 309,000 additional contracts were traded in the last 3 minutes

---

## Reading the Dashboard

Looking at your screenshot for **Strike 25300 CE at 09:15:00**:

| Column | Value | Meaning |
|--------|-------|---------|
| **OI(L)** | 6.66 | 666,000 contracts are currently **open** (not closed yet) |
| **ΔOI(K)** | +13.8 | Open Interest increased by 13,800 contracts |
| **Vol(K)** | 309 | 309,000 contracts were **traded** today |
| **ΔVol(K)** | +309 | 309,000 contracts traded in last 3 minutes |

---

## Key Differences

### Open Interest (OI) vs Volume

| Metric | What It Measures | Resets? |
|--------|-----------------|---------|
| **Open Interest (OI)** | How many contracts are **currently open** (not expired/closed) | ❌ Accumulates throughout contract life |
| **Volume** | How many contracts were **traded today** | ✅ Resets to 0 every day at market open |

### Example Timeline:

**Day 1:**
- 1000 contracts traded → Volume = 1000
- 800 remain open → OI = 800

**Day 2 (Next trading day):**
- Volume resets to 0
- OI carries forward = 800
- If 500 new contracts traded → Volume = 500
- If 300 of old contracts closed → OI = 1000 (800 + 200 new - 300 closed)

---

## Why Volume Matters

### High Volume = High Activity
- **High Volume + Increasing OI** → New positions being built (bullish/bearish interest)
- **High Volume + Decreasing OI** → Positions being closed (profit booking or stop loss)
- **Low Volume** → Less liquidity, harder to enter/exit positions

### Volume Spike Signals:
1. **Large ΔVol(K)** → Sudden interest in this strike (potential breakout/support)
2. **Volume > OI** → Heavy intraday trading (scalpers active)
3. **Volume < OI** → Long-term positions (swing traders holding)

---

## Dashboard Units

| Unit | Multiplier | Example |
|------|-----------|---------|
| **L** (Lakhs) | ÷ 100,000 | 666,000 → 6.66L |
| **K** (Thousands) | ÷ 1,000 | 309,000 → 309K |

---

## Real-World Example from Your Dashboard

**Strike 25400 CE at 09:15:00:**

```
OI(L):    18.34    (1,834,000 contracts open)
ΔOI(K):   -671     (67,100 contracts closed in last 3 min)
Vol(K):   1234     (1,234,000 contracts traded today so far)
ΔVol(K):  +1234    (1,234,000 traded in last 3 min)
```

**Interpretation:**
- **Negative ΔOI**: Traders are closing positions (profit booking or stop loss)
- **High ΔVol**: Very active trading happening right now
- **ΔVol ≈ Total Vol**: Most of today's trading happened in last 3 minutes (market just opened at 9:15!)

---

## Quick Reference

| You See | It Means |
|---------|----------|
| `Vol(K): 309` | 309,000 contracts traded today |
| `ΔVol(K): +309` | 309,000 traded in last 3 min |
| `ΔVol(K): 0` | No new trading in last 3 min |
| `Vol >> OI` | Heavy intraday churn |
| `Vol << OI` | Mostly position holding |

---

**Bottom Line**: Volume tells you **how active** the trading is. High volume = high liquidity = easier to buy/sell at fair prices.
