# OTE Indicator Validation Report

Generated 2026-11-10 08:28 UTC by `ote_validation_pipeline.py`. Rules under test: `ote_indicator.py` defaults (swing 5, leg ≥ 1.5 ATR, structure break required, consolidation 2 bars, stop beyond origin, target −0.27 expansion, HTF structure bias). 1% of equity risked per trade, costs per side as configured, no slippage beyond costs.

Pass thresholds are the same as `hurst_validation_pipeline.py` (Sharpe ≥ 0.6, Sortino ≥ 0.8, win rate ≥ 42%, PF ≥ 1.4, max DD ≥ −35%, positive expectancy, ≥ 12 trades, DD at least 5 pts better than buy-and-hold, MC ≥ 70% profitable, ≥ 2 of 4 OOS periods positive, optimised walk-forward OOS positive in all but one window).

## Summary

| Market | TF | Bars | Trades | Win % | Avg R | Total R | PF | Sharpe | Max DD | B&H | MC prof % | MC p(R≤0) | WF +/n | WFO +/n (ΣR opt / default) | Score | Grade |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NQ=F | hourly | 13683 | 118 | 33.9 | -0.16 | -18.9 | 0.76 | -0.79 | -29.4% | +40% | 10.1 | 0.874 | 1/4 | 1/2 (-0.3 / +4.6) | 3/11 | F |
| ES=F | hourly | 13683 | 123 | 33.3 | -0.15 | -18.6 | 0.77 | -0.80 | -19.9% | +38% | 9.8 | 0.887 | 1/4 | 0/2 (-15.7 / -6.3) | 2/11 | F |
| GC=F | hourly | 13718 | 133 | 40.6 | -0.04 | -5.7 | 0.93 | -0.24 | -13.7% | +75% | 33.1 | 0.641 | 1/4 | 2/2 (+10.2 / -5.9) | 3/11 | F |
| CL=F | hourly | 13542 | 152 | 32.9 | -0.28 | -42.5 | 0.60 | -1.95 | -38.2% | +5% | 0.0 | 0.999 | 0/4 | 1/2 (-0.8 / -16.5) | 2/11 | F |
| EURUSD=X | hourly | 17252 | 173 | 37.6 | -0.03 | -5.7 | 0.95 | -0.18 | -18.8% | +4% | 34.9 | 0.618 | 1/4 | 2/2 (+9.2 / +2.1) | 4/11 | D |
| GBPUSD=X | hourly | 17255 | 180 | 34.4 | -0.14 | -25.0 | 0.80 | -0.82 | -28.7% | +6% | 6.3 | 0.918 | 0/4 | 0/2 (-19.1 / -20.0) | 3/11 | F |
| USDJPY=X | hourly | 17157 | 165 | 38.8 | -0.11 | -18.4 | 0.82 | -0.65 | -24.0% | +7% | 11.4 | 0.862 | 1/4 | 0/2 (-30.7 / -24.0) | 3/11 | F |
| BTC-USD | hourly | 17472 | 199 | 39.7 | +0.05 | +10.0 | 1.07 | 0.22 | -21.3% | -7% | 53.4 | 0.42 | 2/4 | 1/2 (-16.1 / +18.6) | 6/11 | C |
| ETH-USD | hourly | 17469 | 186 | 33.3 | -0.21 | -38.5 | 0.73 | -1.37 | -36.6% | -34% | 1.3 | 0.981 | 0/4 | 2/2 (+9.5 / -27.3) | 2/11 | F |
| SPY | daily | 3770 | 41 | 46.3 | +0.22 | +8.9 | 1.39 | 0.21 | -5.5% | +505% | 75.0 | 0.239 | 1/4 | 1/2 (-2.1 / -4.3) | 7/11 | C |
| QQQ | daily | 3770 | 42 | 45.2 | +0.06 | +2.6 | 1.11 | 0.07 | -10.8% | +1096% | 60.2 | 0.386 | 2/4 | 0/2 (-7.5 / -10.5) | 6/11 | C |
| GLD | daily | 3770 | 48 | 35.4 | -0.21 | -10.2 | 0.68 | -0.31 | -16.5% | +122% | 9.8 | 0.887 | 1/4 | 1/2 (+3.0 / +3.4) | 3/11 | F |
| TLT | daily | 3770 | 45 | 37.8 | -0.06 | -2.8 | 0.91 | -0.08 | -5.9% | -30% | 34.1 | 0.646 | 1/4 | 1/2 (+0.8 / -2.7) | 3/11 | F |
| NVDA | daily | 3770 | 41 | 36.6 | -0.05 | -1.9 | 0.93 | -0.06 | -9.1% | +49290% | 38.2 | 0.599 | 2/4 | 1/2 (+8.4 / +3.6) | 4/11 | D |
| AAPL | daily | 3770 | 38 | 34.2 | -0.21 | -8.0 | 0.69 | -0.28 | -11.7% | +2449% | 15.3 | 0.841 | 1/4 | 0/2 (-8.7 / -5.8) | 2/11 | F |
| BTC-USD | daily | 4438 | 33 | 36.4 | +0.05 | +1.5 | 1.07 | 0.04 | -8.4% | +16204% | 52.1 | 0.466 | 2/4 | 0/2 (-9.5 / -3.5) | 5/11 | D |

**0 of 16 markets pass all criteria.** Total net R across all markets with default rules: -173.3 R over 1717 trades.

## Pooled view

- Average net R per trade across all markets (trade-weighted): -0.101 R
- Markets with positive expectancy: 4 of 16
- Markets where the optimised walk-forward beat the defaults out of sample: 9 of 16
- Share of marked legs that were tapped: 55%; share of tapped legs that were traps (ran through the origin before confirming): 22%

## Per-market detail

### NQ=F (INDEX_FUT, hourly)  —  FAIL 3/11 grade F

Range 2024-06-20 → 2026-11-10, 13683 bars, 2.39 years. Legs marked 354, tapped 181, traps 55, trades 118 (49.4/yr, 48.3% long).

- Backtest: return -18.1% (B&H +39.7%), win rate 33.9%, PF 0.76, avg R -0.160 (gross -0.146, cost 0.013), Sharpe -0.79, Sortino -16.75, max DD -29.4% (B&H -25.9%), max consecutive losses 8, avg hold 27.8 bars
- Monte Carlo (1000 bootstraps): profitable 10.1%, median return -18.4%, worst 5% -35.2%, median max DD -24.3%, worst-5% DD -37.5%, p(mean R ≤ 0) = 0.874
- Walk-forward, default rules: 1/4 periods positive, avg -5.0 R per period
    - 2024-06-20 → 2025-01-28: 26 trades, -9.3 R, win 35%, B&H +7%
    - 2025-01-28 → 2025-08-29: 28 trades, -15.2 R, win 18%, B&H +11%
    - 2025-08-29 → 2026-04-09: 27 trades, -5.3 R, win 30%, B&H +6%
    - 2026-04-09 → 2026-11-10: 36 trades, +9.9 R, win 47%, B&H +12%
- Walk-forward optimisation (144 parameter sets): 1/2 OOS windows positive, Σ OOS -0.3 R vs defaults +4.6 R
    - train 2024-06-20 → 2025-08-29 (18 trades, +3.7 R, 8.3% of grid positive) → test 2025-08-29 → 2026-04-09: 9 trades, +1.7 R (defaults -5.3 R); chosen swing=4 confirm=reclaim tp=2 leg≥1.5ATR sweep=True
    - train 2025-01-28 → 2026-04-09 (19 trades, -2.3 R, 0.0% of grid positive) → test 2026-04-09 → 2026-11-10: 8 trades, -2.0 R (defaults +9.9 R); chosen swing=4 confirm=consolidation tp=2 leg≥1.5ATR sweep=True
- Failed criteria: Sharpe -0.79 < 0.6; Sortino -16.75 < 0.8; WinRate 33.9% < 42.0%; PF 0.76 < 1.4; Expectancy -0.16R <= 0; DD not reduced: -29.4% vs B&H -25.9%; MC profitable 10.1% < 70.0%; WF: 1/4 OOS periods positive

### ES=F (INDEX_FUT, hourly)  —  FAIL 2/11 grade F

Range 2024-06-20 → 2026-11-10, 13683 bars, 2.39 years. Legs marked 357, tapped 184, traps 50, trades 123 (51.5/yr, 48.8% long).

- Backtest: return -18.0% (B&H +37.8%), win rate 33.3%, PF 0.77, avg R -0.152 (gross -0.128, cost 0.024), Sharpe -0.80, Sortino -8.16, max DD -19.9% (B&H -21.1%), max consecutive losses 7, avg hold 32.4 bars
- Monte Carlo (1000 bootstraps): profitable 9.8%, median return -17.4%, worst 5% -35.4%, median max DD -23.8%, worst-5% DD -37.6%, p(mean R ≤ 0) = 0.887
- Walk-forward, default rules: 1/4 periods positive, avg -4.4 R per period
    - 2024-06-20 → 2025-01-28: 23 trades, -5.5 R, win 35%, B&H +10%
    - 2025-01-28 → 2025-08-28: 37 trades, -5.6 R, win 32%, B&H +7%
    - 2025-08-29 → 2026-04-09: 30 trades, +1.6 R, win 40%, B&H +4%
    - 2026-04-09 → 2026-11-10: 33 trades, -8.0 R, win 30%, B&H +12%
- Walk-forward optimisation (144 parameter sets): 0/2 OOS windows positive, Σ OOS -15.7 R vs defaults -6.3 R
    - train 2024-06-20 → 2025-08-28 (50 trades, +5.9 R, 8.3% of grid positive) → test 2025-08-29 → 2026-04-09: 24 trades, -4.3 R (defaults +1.6 R); chosen swing=10 confirm=consolidation tp=2 leg≥1.5ATR sweep=False
    - train 2025-01-28 → 2026-04-09 (28 trades, +10.3 R, 16.0% of grid positive) → test 2026-04-09 → 2026-11-10: 20 trades, -11.4 R (defaults -8.0 R); chosen swing=4 confirm=touch tp=2 leg≥2.5ATR sweep=True
- Failed criteria: Sharpe -0.80 < 0.6; Sortino -8.16 < 0.8; WinRate 33.3% < 42.0%; PF 0.77 < 1.4; Expectancy -0.15R <= 0; DD not reduced: -19.9% vs B&H -21.1%; MC profitable 9.8% < 70.0%; WF: 1/4 OOS periods positive; WFO: 0/2 optimised OOS windows positive

### GC=F (METALS, hourly)  —  FAIL 3/11 grade F

Range 2024-06-20 → 2026-11-10, 13718 bars, 2.39 years. Legs marked 343, tapped 180, traps 40, trades 133 (55.6/yr, 59.4% long).

- Backtest: return -6.6% (B&H +75.4%), win rate 40.6%, PF 0.93, avg R -0.043 (gross -0.017, cost 0.026), Sharpe -0.24, Sortino -12.39, max DD -13.7% (B&H -30.4%), max consecutive losses 7, avg hold 28.7 bars
- Monte Carlo (1000 bootstraps): profitable 33.1%, median return -6.5%, worst 5% -26.8%, median max DD -17.3%, worst-5% DD -31.2%, p(mean R ≤ 0) = 0.641
- Walk-forward, default rules: 1/4 periods positive, avg -1.8 R per period
    - 2024-06-20 → 2025-01-27: 31 trades, -0.8 R, win 45%, B&H +16%
    - 2025-01-27 → 2025-08-28: 36 trades, -0.5 R, win 36%, B&H +26%
    - 2025-08-28 → 2026-04-08: 33 trades, +0.8 R, win 48%, B&H +37%
    - 2026-04-08 → 2026-11-10: 30 trades, -6.7 R, win 30%, B&H -13%
- Walk-forward optimisation (144 parameter sets): 2/2 OOS windows positive, Σ OOS +10.2 R vs defaults -5.9 R
    - train 2024-06-20 → 2025-08-28 (75 trades, +17.4 R, 32.6% of grid positive) → test 2025-08-28 → 2026-04-08: 33 trades, +8.3 R (defaults +0.8 R); chosen swing=4 confirm=touch tp=2 leg≥2.5ATR sweep=False
    - train 2025-01-27 → 2026-04-08 (85 trades, +19.7 R, 38.9% of grid positive) → test 2026-04-08 → 2026-11-10: 37 trades, +1.9 R (defaults -6.7 R); chosen swing=4 confirm=touch tp=2 leg≥1.5ATR sweep=False
- Failed criteria: Sharpe -0.24 < 0.6; Sortino -12.39 < 0.8; WinRate 40.6% < 42.0%; PF 0.93 < 1.4; Expectancy -0.04R <= 0; DD not reduced: -13.7% vs B&H -30.4%; MC profitable 33.1% < 70.0%; WF: 1/4 OOS periods positive

### CL=F (ENERGY, hourly)  —  FAIL 2/11 grade F

Range 2024-06-20 → 2026-11-10, 13542 bars, 2.39 years. Legs marked 355, tapped 200, traps 41, trades 152 (63.6/yr, 52.6% long).

- Backtest: return -35.3% (B&H +4.8%), win rate 32.9%, PF 0.60, avg R -0.280 (gross -0.250, cost 0.029), Sharpe -1.95, Sortino -75.02, max DD -38.2% (B&H -42.3%), max consecutive losses 15, avg hold 27.2 bars
- Monte Carlo (1000 bootstraps): profitable 0.0%, median return -35.3%, worst 5% -48.9%, median max DD -37.7%, worst-5% DD -49.9%, p(mean R ≤ 0) = 0.999
- Walk-forward, default rules: 0/4 periods positive, avg -10.7 R per period
    - 2024-06-20 → 2025-01-29: 38 trades, -7.6 R, win 34%, B&H -10%
    - 2025-01-29 → 2025-09-03: 35 trades, -18.6 R, win 23%, B&H -13%
    - 2025-09-03 → 2026-04-10: 43 trades, -16.2 R, win 30%, B&H +55%
    - 2026-04-10 → 2026-11-10: 32 trades, -0.3 R, win 44%, B&H -14%
- Walk-forward optimisation (144 parameter sets): 1/2 OOS windows positive, Σ OOS -0.8 R vs defaults -16.5 R
    - train 2024-06-20 → 2025-09-03 (15 trades, -5.1 R, 0.0% of grid positive) → test 2025-09-03 → 2026-04-10: 8 trades, -3.6 R (defaults -16.2 R); chosen swing=7 confirm=consolidation tp=2 leg≥1.5ATR sweep=True
    - train 2025-01-29 → 2026-04-10 (16 trades, -2.2 R, 0.0% of grid positive) → test 2026-04-10 → 2026-11-10: 5 trades, +2.8 R (defaults -0.3 R); chosen swing=10 confirm=touch tp=0 leg≥1.5ATR sweep=True
- Failed criteria: Sharpe -1.95 < 0.6; Sortino -75.02 < 0.8; WinRate 32.9% < 42.0%; PF 0.60 < 1.4; MaxDD -38.2% worse than -35.0%; Expectancy -0.28R <= 0; DD not reduced: -38.2% vs B&H -42.3%; MC profitable 0.0% < 70.0%; WF: 0/4 OOS periods positive

### EURUSD=X (FX, hourly)  —  FAIL 4/11 grade D

Range 2024-01-24 → 2026-11-10, 17252 bars, 2.8 years. Legs marked 429, tapped 236, traps 50, trades 173 (61.9/yr, 47.4% long).

- Backtest: return -7.3% (B&H +3.5%), win rate 37.6%, PF 0.95, avg R -0.033 (gross +0.014, cost 0.047), Sharpe -0.18, Sortino -8.23, max DD -18.8% (B&H -9.0%), max consecutive losses 7, avg hold 31.6 bars
- Monte Carlo (1000 bootstraps): profitable 34.9%, median return -8.0%, worst 5% -31.6%, median max DD -21.2%, worst-5% DD -37.0%, p(mean R ≤ 0) = 0.618
- Walk-forward, default rules: 1/4 periods positive, avg -5.0 R per period
    - 2024-01-24 → 2024-10-03: 37 trades, -20.2 R, win 22%, B&H +2%
    - 2024-10-03 → 2025-06-16: 40 trades, -1.8 R, win 38%, B&H +5%
    - 2025-06-16 → 2026-02-27: 42 trades, +5.9 R, win 45%, B&H +2%
    - 2026-02-27 → 2026-11-10: 44 trades, -3.8 R, win 36%, B&H -5%
- Walk-forward optimisation (144 parameter sets): 2/2 OOS windows positive, Σ OOS +9.2 R vs defaults +2.1 R
    - train 2024-01-24 → 2025-06-16 (84 trades, -0.6 R, 0.0% of grid positive) → test 2025-06-16 → 2026-02-27: 39 trades, +8.7 R (defaults +5.9 R); chosen swing=7 confirm=touch tp=1 leg≥1.5ATR sweep=False
    - train 2024-10-03 → 2026-02-27 (66 trades, +37.6 R, 69.4% of grid positive) → test 2026-02-27 → 2026-11-10: 30 trades, +0.5 R (defaults -3.8 R); chosen swing=10 confirm=touch tp=2 leg≥1.5ATR sweep=False
- Failed criteria: Sharpe -0.18 < 0.6; Sortino -8.23 < 0.8; WinRate 37.6% < 42.0%; PF 0.95 < 1.4; Expectancy -0.03R <= 0; MC profitable 34.9% < 70.0%; WF: 1/4 OOS periods positive

### GBPUSD=X (FX, hourly)  —  FAIL 3/11 grade F

Range 2024-01-24 → 2026-11-10, 17255 bars, 2.8 years. Legs marked 448, tapped 251, traps 54, trades 180 (64.4/yr, 49.4% long).

- Backtest: return -23.4% (B&H +6.0%), win rate 34.4%, PF 0.80, avg R -0.139 (gross -0.095, cost 0.044), Sharpe -0.82, Sortino -32.64, max DD -28.7% (B&H -9.8%), max consecutive losses 9, avg hold 26.2 bars
- Monte Carlo (1000 bootstraps): profitable 6.3%, median return -23.7%, worst 5% -42.7%, median max DD -29.9%, worst-5% DD -45.6%, p(mean R ≤ 0) = 0.918
- Walk-forward, default rules: 0/4 periods positive, avg -8.5 R per period
    - 2024-01-24 → 2024-10-03: 49 trades, -0.1 R, win 41%, B&H +4%
    - 2024-10-03 → 2025-06-16: 50 trades, -14.0 R, win 28%, B&H +3%
    - 2025-06-17 → 2026-02-27: 39 trades, -17.3 R, win 26%, B&H -1%
    - 2026-02-27 → 2026-11-10: 40 trades, -2.7 R, win 35%, B&H -0%
- Walk-forward optimisation (144 parameter sets): 0/2 OOS windows positive, Σ OOS -19.1 R vs defaults -20.0 R
    - train 2024-01-24 → 2025-06-16 (84 trades, +14.3 R, 8.3% of grid positive) → test 2025-06-17 → 2026-02-27: 37 trades, -17.1 R (defaults -17.3 R); chosen swing=7 confirm=touch tp=2 leg≥1.5ATR sweep=False
    - train 2024-10-03 → 2026-02-27 (16 trades, -4.8 R, 0.0% of grid positive) → test 2026-02-27 → 2026-11-10: 9 trades, -2.0 R (defaults -2.7 R); chosen swing=10 confirm=consolidation tp=2 leg≥1.5ATR sweep=True
- Failed criteria: Sharpe -0.82 < 0.6; Sortino -32.64 < 0.8; WinRate 34.4% < 42.0%; PF 0.80 < 1.4; Expectancy -0.14R <= 0; MC profitable 6.3% < 70.0%; WF: 0/4 OOS periods positive; WFO: 0/2 optimised OOS windows positive

### USDJPY=X (FX, hourly)  —  FAIL 3/11 grade F

Range 2024-01-24 → 2026-11-10, 17157 bars, 2.8 years. Legs marked 417, tapped 229, traps 53, trades 165 (59.0/yr, 57.0% long).

- Backtest: return -18.0% (B&H +6.7%), win rate 38.8%, PF 0.82, avg R -0.112 (gross -0.076, cost 0.036), Sharpe -0.65, Sortino -14.68, max DD -24.0% (B&H -13.6%), max consecutive losses 7, avg hold 30.8 bars
- Monte Carlo (1000 bootstraps): profitable 11.4%, median return -18.3%, worst 5% -38.1%, median max DD -25.6%, worst-5% DD -41.0%, p(mean R ≤ 0) = 0.862
- Walk-forward, default rules: 1/4 periods positive, avg -4.9 R per period
    - 2024-01-24 → 2024-10-03: 42 trades, -7.5 R, win 40%, B&H -1%
    - 2024-10-03 → 2025-06-16: 40 trades, +12.1 R, win 45%, B&H -1%
    - 2025-06-16 → 2026-02-27: 44 trades, -10.7 R, win 34%, B&H +8%
    - 2026-02-27 → 2026-11-10: 40 trades, -13.3 R, win 35%, B&H +1%
- Walk-forward optimisation (144 parameter sets): 0/2 OOS windows positive, Σ OOS -30.7 R vs defaults -24.0 R
    - train 2024-01-24 → 2025-06-16 (85 trades, +25.4 R, 55.6% of grid positive) → test 2025-06-16 → 2026-02-27: 43 trades, -12.1 R (defaults -10.7 R); chosen swing=5 confirm=touch tp=2 leg≥2.5ATR sweep=False
    - train 2024-10-03 → 2026-02-27 (86 trades, +6.7 R, 16.0% of grid positive) → test 2026-02-27 → 2026-11-10: 33 trades, -18.6 R (defaults -13.3 R); chosen swing=4 confirm=consolidation tp=2 leg≥2.5ATR sweep=False
- Failed criteria: Sharpe -0.65 < 0.6; Sortino -14.68 < 0.8; WinRate 38.8% < 42.0%; PF 0.82 < 1.4; Expectancy -0.11R <= 0; MC profitable 11.4% < 70.0%; WF: 1/4 OOS periods positive; WFO: 0/2 optimised OOS windows positive

### BTC-USD (CRYPTO, hourly)  —  FAIL 6/11 grade C

Range 2024-11-11 → 2026-11-10, 17472 bars, 2.0 years. Legs marked 449, tapped 265, traps 53, trades 199 (99.7/yr, 46.7% long).

- Backtest: return +5.4% (B&H -7.3%), win rate 39.7%, PF 1.07, avg R +0.050 (gross +0.258, cost 0.208), Sharpe 0.22, Sortino 2.64, max DD -21.3% (B&H -54.0%), max consecutive losses 6, avg hold 29.7 bars
- Monte Carlo (1000 bootstraps): profitable 53.4%, median return +2.8%, worst 5% -35.4%, median max DD -24.6%, worst-5% DD -43.4%, p(mean R ≤ 0) = 0.42
- Walk-forward, default rules: 2/4 periods positive, avg +1.9 R per period
    - 2024-11-11 → 2025-05-12: 46 trades, -11.7 R, win 35%, B&H +30%
    - 2025-05-12 → 2025-11-10: 49 trades, +0.8 R, win 41%, B&H +2%
    - 2025-11-10 → 2026-05-12: 53 trades, +26.6 R, win 42%, B&H -24%
    - 2026-05-12 → 2026-11-10: 47 trades, -8.0 R, win 40%, B&H -8%
- Walk-forward optimisation (144 parameter sets): 1/2 OOS windows positive, Σ OOS -16.1 R vs defaults +18.6 R
    - train 2024-11-11 → 2025-11-10 (23 trades, +7.0 R, 22.9% of grid positive) → test 2025-11-10 → 2026-05-12: 8 trades, +1.6 R (defaults +26.6 R); chosen swing=7 confirm=reclaim tp=1 leg≥1.5ATR sweep=True
    - train 2025-05-12 → 2026-05-12 (94 trades, +49.9 R, 58.3% of grid positive) → test 2026-05-12 → 2026-11-10: 40 trades, -17.8 R (defaults -8.0 R); chosen swing=5 confirm=consolidation tp=2 leg≥2.5ATR sweep=False
- Failed criteria: Sharpe 0.22 < 0.6; WinRate 39.7% < 42.0%; PF 1.07 < 1.4; DD not reduced: -21.3% vs B&H -54.0%; MC profitable 53.4% < 70.0%

### ETH-USD (CRYPTO, hourly)  —  FAIL 2/11 grade F

Range 2024-11-11 → 2026-11-10, 17469 bars, 2.0 years. Legs marked 423, tapped 244, traps 49, trades 186 (93.1/yr, 53.8% long).

- Backtest: return -33.3% (B&H -33.9%), win rate 33.3%, PF 0.73, avg R -0.207 (gross -0.077, cost 0.130), Sharpe -1.37, Sortino -23.34, max DD -36.6% (B&H -69.2%), max consecutive losses 11, avg hold 31.8 bars
- Monte Carlo (1000 bootstraps): profitable 1.3%, median return -33.6%, worst 5% -51.9%, median max DD -38.1%, worst-5% DD -54.3%, p(mean R ≤ 0) = 0.981
- Walk-forward, default rules: 0/4 periods positive, avg -10.4 R per period
    - 2024-11-11 → 2025-05-11: 50 trades, -7.8 R, win 34%, B&H -21%
    - 2025-05-12 → 2025-11-10: 44 trades, -6.5 R, win 39%, B&H +42%
    - 2025-11-10 → 2026-05-12: 43 trades, -12.0 R, win 30%, B&H -37%
    - 2026-05-12 → 2026-11-10: 44 trades, -15.3 R, win 27%, B&H -8%
- Walk-forward optimisation (144 parameter sets): 2/2 OOS windows positive, Σ OOS +9.5 R vs defaults -27.3 R
    - train 2024-11-11 → 2025-11-10 (15 trades, +6.2 R, 16.7% of grid positive) → test 2025-11-10 → 2026-05-12: 7 trades, +6.5 R (defaults -12.0 R); chosen swing=10 confirm=reclaim tp=2 leg≥1.5ATR sweep=True
    - train 2025-05-12 → 2026-05-12 (17 trades, +7.6 R, 31.2% of grid positive) → test 2026-05-12 → 2026-11-10: 13 trades, +2.9 R (defaults -15.3 R); chosen swing=7 confirm=reclaim tp=2 leg≥1.5ATR sweep=True
- Failed criteria: Sharpe -1.37 < 0.6; Sortino -23.34 < 0.8; WinRate 33.3% < 42.0%; PF 0.73 < 1.4; MaxDD -36.6% worse than -35.0%; Expectancy -0.21R <= 0; DD not reduced: -36.6% vs B&H -69.2%; MC profitable 1.3% < 70.0%; WF: 0/4 OOS periods positive

### SPY (ETF, daily)  —  FAIL 7/11 grade C

Range 2011-11-10 → 2026-11-09, 3770 bars, 15.0 years. Legs marked 109, tapped 54, traps 11, trades 41 (2.7/yr, 65.9% long).

- Backtest: return +8.6% (B&H +505.4%), win rate 46.3%, PF 1.39, avg R +0.217 (gross +0.261, cost 0.044), Sharpe 0.21, Sortino 10.12, max DD -5.5% (B&H -34.1%), max consecutive losses 4, avg hold 18.5 bars
- Monte Carlo (1000 bootstraps): profitable 75.0%, median return +7.8%, worst 5% -9.8%, median max DD -7.0%, worst-5% DD -14.1%, p(mean R ≤ 0) = 0.239
- Walk-forward, default rules: 1/4 periods positive, avg +0.9 R per period
    - 2011-11-10 → 2015-08-11: 11 trades, -0.5 R, win 45%, B&H +68%
    - 2015-08-12 → 2019-05-10: 9 trades, +8.3 R, win 67%, B&H +38%
    - 2019-05-13 → 2023-02-06: 11 trades, -0.2 R, win 45%, B&H +46%
    - 2023-02-07 → 2026-11-09: 4 trades, -4.2 R, win 0%, B&H +81%
- Walk-forward optimisation (144 parameter sets): 1/2 OOS windows positive, Σ OOS -2.1 R vs defaults -4.3 R
    - train 2011-11-10 → 2019-05-10 (24 trades, +23.4 R, 81.9% of grid positive) → test 2019-05-13 → 2023-02-06: 10 trades, +1.3 R (defaults -0.2 R); chosen swing=4 confirm=touch tp=1 leg≥1.5ATR sweep=False
    - train 2015-08-12 → 2023-02-06 (20 trades, +19.1 R, 79.2% of grid positive) → test 2023-02-07 → 2026-11-06: 8 trades, -3.4 R (defaults -4.2 R); chosen swing=5 confirm=touch tp=2 leg≥1.5ATR sweep=False
- Failed criteria: Sharpe 0.21 < 0.6; PF 1.39 < 1.4; DD not reduced: -5.5% vs B&H -34.1%; WF: 1/4 OOS periods positive

### QQQ (ETF, daily)  —  FAIL 6/11 grade C

Range 2011-11-10 → 2026-11-09, 3770 bars, 15.0 years. Legs marked 112, tapped 59, traps 13, trades 42 (2.8/yr, 66.7% long).

- Backtest: return +2.2% (B&H +1096.5%), win rate 45.2%, PF 1.11, avg R +0.062 (gross +0.096, cost 0.034), Sharpe 0.07, Sortino 3.46, max DD -10.8% (B&H -35.6%), max consecutive losses 4, avg hold 13.7 bars
- Monte Carlo (1000 bootstraps): profitable 60.2%, median return +2.3%, worst 5% -11.1%, median max DD -7.6%, worst-5% DD -14.4%, p(mean R ≤ 0) = 0.386
- Walk-forward, default rules: 2/4 periods positive, avg +1.1 R per period
    - 2011-11-10 → 2015-08-11: 5 trades, +3.6 R, win 60%, B&H +94%
    - 2015-08-12 → 2019-05-10: 12 trades, +11.2 R, win 75%, B&H +67%
    - 2019-05-13 → 2023-02-06: 8 trades, -6.6 R, win 12%, B&H +70%
    - 2023-02-07 → 2026-11-09: 9 trades, -3.9 R, win 33%, B&H +119%
- Walk-forward optimisation (144 parameter sets): 0/2 OOS windows positive, Σ OOS -7.5 R vs defaults -10.5 R
    - train 2011-11-10 → 2019-05-10 (24 trades, +20.1 R, 80.6% of grid positive) → test 2019-05-13 → 2023-02-06: 12 trades, -5.3 R (defaults -6.6 R); chosen swing=4 confirm=touch tp=1 leg≥1.5ATR sweep=False
    - train 2015-08-12 → 2023-02-06 (25 trades, +12.1 R, 86.8% of grid positive) → test 2023-02-07 → 2026-11-06: 11 trades, -2.2 R (defaults -3.9 R); chosen swing=5 confirm=touch tp=2 leg≥1.5ATR sweep=False
- Failed criteria: Sharpe 0.07 < 0.6; PF 1.11 < 1.4; DD not reduced: -10.8% vs B&H -35.6%; MC profitable 60.2% < 70.0%; WFO: 0/2 optimised OOS windows positive

### GLD (ETF, daily)  —  FAIL 3/11 grade F

Range 2011-11-10 → 2026-11-09, 3770 bars, 15.0 years. Legs marked 107, tapped 65, traps 13, trades 48 (3.2/yr, 50.0% long).

- Backtest: return -10.1% (B&H +121.8%), win rate 35.4%, PF 0.68, avg R -0.213 (gross -0.173, cost 0.040), Sharpe -0.31, Sortino -14.72, max DD -16.5% (B&H -42.2%), max consecutive losses 7, avg hold 24.9 bars
- Monte Carlo (1000 bootstraps): profitable 9.8%, median return -10.2%, worst 5% -20.8%, median max DD -14.0%, worst-5% DD -22.6%, p(mean R ≤ 0) = 0.887
- Walk-forward, default rules: 1/4 periods positive, avg -1.6 R per period
    - 2011-11-10 → 2015-08-11: 12 trades, -3.5 R, win 33%, B&H -38%
    - 2015-08-12 → 2019-05-10: 13 trades, -6.2 R, win 23%, B&H +13%
    - 2019-05-13 → 2023-02-06: 13 trades, -5.4 R, win 31%, B&H +42%
    - 2023-02-07 → 2026-11-09: 5 trades, +8.8 R, win 80%, B&H +118%
- Walk-forward optimisation (144 parameter sets): 1/2 OOS windows positive, Σ OOS +3.0 R vs defaults +3.4 R
    - train 2011-11-10 → 2019-05-10 (20 trades, +3.9 R, 23.6% of grid positive) → test 2019-05-13 → 2023-02-06: 9 trades, -4.3 R (defaults -5.4 R); chosen swing=7 confirm=touch tp=2 leg≥1.5ATR sweep=False
    - train 2015-08-12 → 2023-02-06 (16 trades, +10.9 R, 23.6% of grid positive) → test 2023-02-07 → 2026-11-06: 3 trades, +7.3 R (defaults +8.8 R); chosen swing=10 confirm=touch tp=2 leg≥1.5ATR sweep=False
- Failed criteria: Sharpe -0.31 < 0.6; Sortino -14.72 < 0.8; WinRate 35.4% < 42.0%; PF 0.68 < 1.4; Expectancy -0.21R <= 0; DD not reduced: -16.5% vs B&H -42.2%; MC profitable 9.8% < 70.0%; WF: 1/4 OOS periods positive

### TLT (ETF, daily)  —  FAIL 3/11 grade F

Range 2011-11-10 → 2026-11-09, 3770 bars, 15.0 years. Legs marked 97, tapped 59, traps 12, trades 45 (3.0/yr, 37.8% long).

- Backtest: return -3.1% (B&H -29.6%), win rate 37.8%, PF 0.91, avg R -0.061 (gross -0.018, cost 0.044), Sharpe -0.08, Sortino -3.92, max DD -5.9% (B&H -55.1%), max consecutive losses 4, avg hold 24.0 bars
- Monte Carlo (1000 bootstraps): profitable 34.1%, median return -3.8%, worst 5% -16.9%, median max DD -10.4%, worst-5% DD -18.9%, p(mean R ≤ 0) = 0.646
- Walk-forward, default rules: 1/4 periods positive, avg -1.2 R per period
    - 2011-11-10 → 2015-08-11: 10 trades, -2.0 R, win 30%, B&H +7%
    - 2015-08-12 → 2019-05-10: 9 trades, +0.1 R, win 44%, B&H +1%
    - 2019-05-13 → 2023-02-06: 12 trades, -0.8 R, win 42%, B&H -16%
    - 2023-02-07 → 2026-11-09: 10 trades, -1.9 R, win 40%, B&H -22%
- Walk-forward optimisation (144 parameter sets): 1/2 OOS windows positive, Σ OOS +0.8 R vs defaults -2.7 R
    - train 2011-11-10 → 2019-05-10 (22 trades, +3.3 R, 42.4% of grid positive) → test 2019-05-13 → 2023-02-06: 14 trades, -3.8 R (defaults -0.8 R); chosen swing=4 confirm=reclaim tp=0 leg≥1.5ATR sweep=False
    - train 2015-08-12 → 2023-02-06 (22 trades, +14.2 R, 38.9% of grid positive) → test 2023-02-07 → 2026-11-06: 14 trades, +4.6 R (defaults -1.9 R); chosen swing=4 confirm=touch tp=2 leg≥2.5ATR sweep=False
- Failed criteria: Sharpe -0.08 < 0.6; Sortino -3.92 < 0.8; WinRate 37.8% < 42.0%; PF 0.91 < 1.4; Expectancy -0.06R <= 0; DD not reduced: -5.9% vs B&H -55.1%; MC profitable 34.1% < 70.0%; WF: 1/4 OOS periods positive

### NVDA (STOCK, daily)  —  FAIL 4/11 grade D

Range 2011-11-10 → 2026-11-09, 3770 bars, 15.0 years. Legs marked 104, tapped 54, traps 8, trades 41 (2.7/yr, 70.7% long).

- Backtest: return -2.2% (B&H +49290.5%), win rate 36.6%, PF 0.93, avg R -0.046 (gross -0.032, cost 0.014), Sharpe -0.06, Sortino -9.51, max DD -9.1% (B&H -66.4%), max consecutive losses 7, avg hold 23.0 bars
- Monte Carlo (1000 bootstraps): profitable 38.2%, median return -2.9%, worst 5% -15.2%, median max DD -9.2%, worst-5% DD -17.8%, p(mean R ≤ 0) = 0.599
- Walk-forward, default rules: 2/4 periods positive, avg -0.6 R per period
    - 2011-11-10 → 2015-08-11: 10 trades, -8.2 R, win 10%, B&H +64%
    - 2015-08-12 → 2019-05-10: 9 trades, +2.2 R, win 56%, B&H +612%
    - 2019-05-13 → 2023-02-06: 11 trades, +5.0 R, win 55%, B&H +432%
    - 2023-02-07 → 2026-11-09: 9 trades, -1.4 R, win 22%, B&H +706%
- Walk-forward optimisation (144 parameter sets): 1/2 OOS windows positive, Σ OOS +8.4 R vs defaults +3.6 R
    - train 2011-11-10 → 2019-05-10 (21 trades, +7.5 R, 36.1% of grid positive) → test 2019-05-13 → 2023-02-06: 12 trades, +9.3 R (defaults +5.0 R); chosen swing=5 confirm=touch tp=2 leg≥1.5ATR sweep=False
    - train 2015-08-12 → 2023-02-06 (20 trades, +14.7 R, 48.6% of grid positive) → test 2023-02-07 → 2026-11-06: 10 trades, -0.9 R (defaults -1.4 R); chosen swing=5 confirm=touch tp=2 leg≥1.5ATR sweep=False
- Failed criteria: Sharpe -0.06 < 0.6; Sortino -9.51 < 0.8; WinRate 36.6% < 42.0%; PF 0.93 < 1.4; Expectancy -0.05R <= 0; DD not reduced: -9.1% vs B&H -66.4%; MC profitable 38.2% < 70.0%

### AAPL (STOCK, daily)  —  FAIL 2/11 grade F

Range 2011-11-10 → 2026-11-09, 3770 bars, 15.0 years. Legs marked 97, tapped 52, traps 14, trades 38 (2.5/yr, 60.5% long).

- Backtest: return -7.9% (B&H +2449.0%), win rate 34.2%, PF 0.69, avg R -0.210 (gross -0.192, cost 0.018), Sharpe -0.28, Sortino -39.38, max DD -11.7% (B&H -44.4%), max consecutive losses 7, avg hold 20.4 bars
- Monte Carlo (1000 bootstraps): profitable 15.3%, median return -7.7%, worst 5% -17.7%, median max DD -11.1%, worst-5% DD -19.5%, p(mean R ≤ 0) = 0.841
- Walk-forward, default rules: 1/4 periods positive, avg -2.0 R per period
    - 2011-11-10 → 2015-08-11: 7 trades, +1.5 R, win 57%, B&H +106%
    - 2015-08-12 → 2019-05-10: 12 trades, -3.7 R, win 25%, B&H +71%
    - 2019-05-13 → 2023-02-06: 8 trades, -0.4 R, win 38%, B&H +227%
    - 2023-02-07 → 2026-11-09: 7 trades, -5.5 R, win 14%, B&H +127%
- Walk-forward optimisation (144 parameter sets): 0/2 OOS windows positive, Σ OOS -8.7 R vs defaults -5.8 R
    - train 2011-11-10 → 2019-05-10 (15 trades, +4.2 R, 30.6% of grid positive) → test 2019-05-13 → 2023-02-06: 8 trades, -1.9 R (defaults -0.4 R); chosen swing=7 confirm=touch tp=1 leg≥1.5ATR sweep=False
    - train 2015-08-12 → 2023-02-06 (16 trades, +0.2 R, 2.8% of grid positive) → test 2023-02-07 → 2026-11-06: 8 trades, -6.8 R (defaults -5.5 R); chosen swing=7 confirm=consolidation tp=1 leg≥1.5ATR sweep=False
- Failed criteria: Sharpe -0.28 < 0.6; Sortino -39.38 < 0.8; WinRate 34.2% < 42.0%; PF 0.69 < 1.4; Expectancy -0.21R <= 0; DD not reduced: -11.7% vs B&H -44.4%; MC profitable 15.3% < 70.0%; WF: 1/4 OOS periods positive; WFO: 0/2 optimised OOS windows positive

### BTC-USD (CRYPTO, daily)  —  FAIL 5/11 grade D

Range 2014-09-17 → 2026-11-10, 4438 bars, 12.15 years. Legs marked 93, tapped 46, traps 12, trades 33 (2.7/yr, 78.8% long).

- Backtest: return +1.1% (B&H +16204.4%), win rate 36.4%, PF 1.07, avg R +0.046 (gross +0.072, cost 0.025), Sharpe 0.04, Sortino 4.24, max DD -8.4% (B&H -83.4%), max consecutive losses 6, avg hold 33.1 bars
- Monte Carlo (1000 bootstraps): profitable 52.1%, median return +0.3%, worst 5% -13.3%, median max DD -8.1%, worst-5% DD -15.8%, p(mean R ≤ 0) = 0.466
- Walk-forward, default rules: 2/4 periods positive, avg +0.5 R per period
    - 2014-09-17 → 2017-09-29: 7 trades, +8.9 R, win 57%, B&H +810%
    - 2017-09-30 → 2020-10-13: 8 trades, -3.4 R, win 25%, B&H +163%
    - 2020-10-14 → 2023-10-27: 6 trades, +2.5 R, win 50%, B&H +197%
    - 2023-10-28 → 2026-11-10: 10 trades, -6.0 R, win 20%, B&H +119%
- Walk-forward optimisation (144 parameter sets): 0/2 OOS windows positive, Σ OOS -9.5 R vs defaults -3.5 R
    - train 2014-09-17 → 2020-10-13 (17 trades, +10.3 R, 33.3% of grid positive) → test 2020-10-14 → 2023-10-27: 6 trades, -1.7 R (defaults +2.5 R); chosen swing=5 confirm=consolidation tp=2 leg≥1.5ATR sweep=False
    - train 2017-09-30 → 2023-10-27 (17 trades, +2.1 R, 19.4% of grid positive) → test 2023-10-28 → 2026-11-09: 10 trades, -7.8 R (defaults -6.0 R); chosen swing=4 confirm=reclaim tp=1 leg≥1.5ATR sweep=False
- Failed criteria: Sharpe 0.04 < 0.6; WinRate 36.4% < 42.0%; PF 1.07 < 1.4; DD not reduced: -8.4% vs B&H -83.4%; MC profitable 52.1% < 70.0%; WFO: 0/2 optimised OOS windows positive
