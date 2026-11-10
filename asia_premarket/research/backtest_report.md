# Asia-session mean-reversion engine — walk-forward backtest report

Decision at 18:00 ET on RTH date D; outcome = Asia session 18:00 D → 03:00 D+1. Every probability below is out-of-sample: models are retrained each month on data strictly before that month (expanding window, first 150 nights are training only). Isotonic calibration is fitted on the pooled OOS predictions.

## NQ

Data: hourly Globex bars 2024-06-18 → 2026-11-09, 588 RTH days, 506 nights with an RTH move ≥ 0.15%.

### Out-of-sample probability quality

| Outcome | description | OOS n | base rate | Brier base | Brier logit | Brier GBM | Brier calibrated | accuracy |
|---|---|---|---|---|---|---|---|---|
| reverted | Asia closes (03:00) on the opposite side of the 18:00 open vs the RTH move | 331 | 53% | 0.249 | 0.270 | 0.270 | **0.246** | 53% |
| hit_vwap_first | Asia touches RTH VWAP before the tight stop | 331 | 49% | 0.250 | 0.154 | 0.167 | **0.146** | 80% |
| hit_r382_first | Asia retraces 38.2% of the RTH move before the tight stop | 331 | 46% | 0.249 | 0.189 | 0.216 | **0.184** | 72% |
| hit_r500_first | Asia retraces 50% of the RTH move before the tight stop | 331 | 37% | 0.234 | 0.186 | 0.204 | **0.172** | 73% |
| stopped | Tight stop (RTH extreme + 10% of RTH range) is hit before any target | 331 | 37% | 0.233 | 0.201 | 0.207 | **0.183** | 72% |
| hit_vwap_first_w | Asia touches RTH VWAP before the wide stop | 331 | 51% | 0.250 | 0.186 | 0.200 | **0.175** | 75% |
| hit_r382_first_w | Asia retraces 38.2% of the RTH move before the wide stop | 331 | 48% | 0.250 | 0.218 | 0.242 | **0.210** | 67% |
| hit_r500_first_w | Asia retraces 50% of the RTH move before the wide stop | 331 | 40% | 0.239 | 0.216 | 0.234 | **0.200** | 68% |
| stopped_w | Wide stop (max(0.6x median Asia range, 0.3x today's RTH range) from 17:00 close) is hit first | 331 | 26% | 0.192 | 0.249 | 0.211 | **0.188** | 75% |

Calibration buckets (calibrated p vs realised):

| reverted bucket | n | realised | predicted |
|---|---|---|---|
| (0.35, 0.5] | 83.00 | 0.49 | 0.49 |
| (0.5, 0.65] | 228.00 | 0.53 | 0.53 |
| (0.65, 0.8] | 20.00 | 0.75 | 0.75 |

| hit_vwap_first bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 83.00 | 0.11 | 0.11 |
| (0.2, 0.35] | 75.00 | 0.27 | 0.27 |
| (0.35, 0.5] | 11.00 | 0.36 | 0.36 |
| (0.5, 0.65] | 45.00 | 0.64 | 0.64 |
| (0.65, 0.8] | 32.00 | 0.75 | 0.75 |
| (0.8, 1.0] | 85.00 | 0.91 | 0.90 |

| hit_r382_first bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 71.00 | 0.14 | 0.14 |
| (0.2, 0.35] | 57.00 | 0.30 | 0.30 |
| (0.35, 0.5] | 79.00 | 0.43 | 0.43 |
| (0.5, 0.65] | 32.00 | 0.53 | 0.53 |
| (0.65, 0.8] | 44.00 | 0.75 | 0.75 |
| (0.8, 1.0] | 48.00 | 0.88 | 0.87 |

| hit_r500_first bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 127.00 | 0.12 | 0.12 |
| (0.2, 0.35] | 43.00 | 0.30 | 0.30 |
| (0.35, 0.5] | 93.00 | 0.47 | 0.47 |
| (0.5, 0.65] | 13.00 | 0.62 | 0.62 |
| (0.65, 0.8] | 19.00 | 0.74 | 0.74 |
| (0.8, 1.0] | 36.00 | 0.83 | 0.83 |

| stopped bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 68.00 | 0.04 | 0.04 |
| (0.2, 0.35] | 115.00 | 0.28 | 0.28 |
| (0.35, 0.5] | 32.00 | 0.44 | 0.44 |
| (0.5, 0.65] | 91.00 | 0.60 | 0.60 |
| (0.65, 0.8] | 25.00 | 0.72 | 0.72 |

| hit_vwap_first_w bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 45.00 | 0.09 | 0.09 |
| (0.2, 0.35] | 101.00 | 0.30 | 0.30 |
| (0.35, 0.5] | 2.00 | 0.50 | 0.50 |
| (0.5, 0.65] | 33.00 | 0.52 | 0.52 |
| (0.65, 0.8] | 69.00 | 0.70 | 0.70 |
| (0.8, 1.0] | 81.00 | 0.85 | 0.85 |

| hit_r382_first_w bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 25.00 | 0.08 | 0.08 |
| (0.2, 0.35] | 46.00 | 0.26 | 0.26 |
| (0.35, 0.5] | 98.00 | 0.41 | 0.41 |
| (0.5, 0.65] | 66.00 | 0.55 | 0.55 |
| (0.65, 0.8] | 96.00 | 0.73 | 0.73 |

| hit_r500_first_w bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 43.00 | 0.05 | 0.05 |
| (0.2, 0.35] | 126.00 | 0.29 | 0.29 |
| (0.35, 0.5] | 36.00 | 0.47 | 0.47 |
| (0.5, 0.65] | 82.00 | 0.54 | 0.54 |
| (0.65, 0.8] | 44.00 | 0.70 | 0.70 |

| stopped_w bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 1.00 | 0.00 | 0.03 |
| (0.2, 0.35] | 328.00 | 0.26 | 0.26 |
| (0.8, 1.0] | 2.00 | 1.00 | 0.97 |

### Simulated decisions (OOS, first-hit resolution, no slippage)

- Nights evaluated: 331 · nights with a graded call: 212 (64%)
- Grade A: n=78, win rate 69%, avg +21.3 pts ($+426/contract), total +1662 pts, worst -337 pts
- Grade B: n=79, win rate 46%, avg -10.0 pts ($-199/contract), total -787 pts, worst -340 pts
- Grade C: n=39, win rate 49%, avg -14.3 pts ($-286/contract), total -558 pts, worst -228 pts
- MEAN REVERSION: n=111, win rate 57%, avg -0.6 pts, total -66 pts
- CONTINUATION: n=85, win rate 54%, avg +4.5 pts, total +384 pts
- Past year only (from 2025-11-01): n=139, win rate 54%, avg +2.8 pts, total +369 pts

| month | n | win | total_pts | avg_pts |
|---|---|---|---|---|
| 2025-04 | 12.00 | 0.50 | -310.00 | -28.18 |
| 2025-05 | 11.00 | 0.45 | -18.73 | -2.08 |
| 2025-06 | 6.00 | 0.33 | -30.43 | -5.07 |
| 2025-07 | 8.00 | 0.38 | -123.92 | -15.49 |
| 2025-08 | 11.00 | 0.45 | 165.63 | 16.56 |
| 2025-09 | 13.00 | 0.46 | 137.07 | 12.46 |
| 2025-10 | 12.00 | 0.58 | 129.42 | 11.77 |
| 2025-11 | 13.00 | 0.46 | -464.07 | -35.70 |
| 2025-12 | 9.00 | 0.44 | 86.18 | 10.77 |
| 2026-01 | 12.00 | 0.33 | -332.86 | -30.26 |
| 2026-02 | 6.00 | 0.17 | -247.88 | -41.31 |
| 2026-03 | 12.00 | 0.58 | 586.24 | 58.62 |
| 2026-04 | 12.00 | 0.50 | 80.59 | 7.33 |
| 2026-05 | 12.00 | 0.75 | 301.35 | 25.11 |
| 2026-06 | 9.00 | 0.22 | -864.44 | -108.05 |
| 2026-07 | 14.00 | 0.43 | -216.13 | -18.01 |
| 2026-08 | 13.00 | 0.69 | 287.34 | 22.10 |
| 2026-09 | 9.00 | 0.78 | 392.44 | 43.60 |
| 2026-10 | 14.00 | 0.79 | 767.06 | 59.00 |
| 2026-11 | 4.00 | 0.75 | -7.31 | -1.83 |

### Asymmetries and findings (full sample, nights with |RTH| ≥ 0.15%)

| Condition | n | reverted | avg rev (bp) | VWAP first | 38% first | stopped | med range (bp) |
|---|---|---|---|---|---|---|---|
| all | 506 | 52% | +2.0 | 48% | 44% | 35% | 62 |
| RTH down | 234 | 55% | +4.8 | 56% | 45% | 33% | 70 |
| RTH up | 272 | 49% | -0.3 | 42% | 43% | 38% | 55 |
| RTH down 0.1–0% | 77 | 55% | -0.8 | 74% | 66% | 22% | 57 |
| RTH down 0.5–1% | 76 | 49% | +0.5 | 56% | 44% | 38% | 69 |
| RTH down 1.0–2% | 54 | 67% | +19.7 | 44% | 35% | 37% | 74 |
| RTH down 2.0–100% | 27 | 52% | +2.0 | 26% | 7% | 41% | 95 |
| RTH up 0.1–0% | 105 | 55% | +4.1 | 62% | 63% | 28% | 52 |
| RTH up 0.5–1% | 95 | 47% | +0.8 | 35% | 39% | 38% | 53 |
| RTH up 1.0–2% | 62 | 40% | -6.3 | 23% | 23% | 52% | 60 |
| RTH up 2.0–100% | 10 | 40% | -22.1 | 0% | 0% | 44% | 105 |
| closed at extreme (trend close) | 241 | 53% | +2.8 | 23% | 31% | 49% | 61 |
| closed off the extreme | 106 | 50% | +1.1 | 89% | 62% | 12% | 64 |
| VIX confirmed move | 251 | 53% | +4.4 | 44% | 38% | 36% | 66 |
| VIX diverged | 74 | 39% | -9.3 | 54% | 57% | 32% | 72 |
| move extends >1.5 ATR stretch | 157 | 48% | +2.9 | 39% | 40% | 41% | 59 |
| move corrects >1.5 ATR stretch | 79 | 57% | +7.3 | 65% | 58% | 24% | 65 |
| Friday → Sunday reopen | 91 | 47% | +0.8 | 54% | 49% | 37% | 70 |
| FOMC day | 16 | 56% | +31.2 | 50% | 50% | 31% | 80 |
| CPI/NFP/PCE tomorrow | 76 | 45% | -0.6 | 45% | 44% | 37% | 60 |
| BoJ tonight | 13 | 62% | +9.2 | 46% | 54% | 38% | 66 |
| mega-cap earnings tonight | 52 | 54% | +6.5 | 50% | 50% | 44% | 83 |
| VIX > 25 | 37 | 41% | -16.3 | 19% | 28% | 64% | 130 |
| VIX < 15 | 71 | 48% | -3.6 | 37% | 36% | 31% | 36 |

### Full rule table (all history)

| rule | desc | n | rev_rate | avg_rev_ret_bp | vwap_first | r382_first | stopped | med_rng_bp | t_stat |
|---|---|---|---|---|---|---|---|---|---|
| prior_asia_reverted | Last night's Asia already reverted the prior RTH | 260 | 0.519 | 2.009 | 0.473 | 0.430 | 0.348 | 61.313 | 0.608 |
| close_at_extreme | Closed in outer 20% of range in the move's direction | 240 | 0.533 | 2.804 | 0.230 | 0.314 | 0.494 | 60.695 | 0.782 |
| broke_prev_high | Closed above prior RTH high | 185 | 0.476 | 1.797 | 0.397 | 0.402 | 0.370 | 50.117 | 0.590 |
| semis_confirm | Semis led in the direction of the move (>1%) | 179 | 0.514 | 2.813 | 0.388 | 0.354 | 0.371 | 69.246 | 0.590 |
| move_extends_stretch | Today's move extended an existing >1.5 ATR stretch from 20d SMA | 157 | 0.484 | 2.862 | 0.394 | 0.400 | 0.406 | 58.564 | 0.627 |
| rth_fought_overnight | RTH reversed the prior overnight move | 144 | 0.507 | -1.055 | 0.496 | 0.475 | 0.340 | 67.650 | -0.238 |
| us_diverged_from_asia | US moved > 1.5% opposite to Tokyo's session | 138 | 0.478 | -2.178 | 0.442 | 0.384 | 0.399 | 66.972 | -0.473 |
| broke_prev_low | Closed below prior RTH low | 135 | 0.570 | 6.860 | 0.466 | 0.376 | 0.338 | 76.250 | 1.261 |
| btc_confirms | BTC moved > 1.5% with the equity move in US hours | 119 | 0.521 | 4.893 | 0.350 | 0.350 | 0.385 | 72.514 | 1.009 |
| gap_reversed | Gapped then reversed the gap in RTH | 118 | 0.475 | -5.960 | 0.487 | 0.462 | 0.342 | 69.401 | -1.179 |
| close_near_vwap | Closed within 0.1 range-widths of RTH VWAP | 116 | 0.474 | -4.201 | 0.812 | 0.527 | 0.179 | 62.304 | -0.866 |
| cn_data_tonight | China data during tonight's Asia session | 114 | 0.482 | -1.460 | 0.434 | 0.372 | 0.425 | 60.472 | -0.304 |
| stretched_above_20 | More than 2 ATR above 20d SMA | 112 | 0.464 | 1.875 | 0.491 | 0.436 | 0.364 | 45.233 | 0.541 |
| gap_and_go | Gapped and extended in gap direction | 111 | 0.577 | 8.123 | 0.450 | 0.459 | 0.351 | 72.193 | 1.419 |
| thursday | Thursday | 104 | 0.529 | 2.656 | 0.408 | 0.447 | 0.340 | 55.990 | 0.559 |
| drawdown_5pct | More than 5% below 20d high | 103 | 0.515 | 3.635 | 0.431 | 0.441 | 0.382 | 92.539 | 0.507 |
| at_20d_high | Within 0.5% of 20d high | 100 | 0.500 | 1.832 | 0.404 | 0.394 | 0.394 | 39.312 | 0.525 |
| monday | Monday | 94 | 0.532 | 2.660 | 0.447 | 0.426 | 0.362 | 61.826 | 0.493 |
| prior_asia_same_dir | Last night's Asia moved > 0.4% in today's RTH direction | 91 | 0.604 | 12.066 | 0.516 | 0.429 | 0.374 | 76.250 | 2.013 |
| sunday_open | Friday close -> Sunday 18:00 reopen (weekend gap risk) | 91 | 0.473 | 0.767 | 0.540 | 0.494 | 0.368 | 69.866 | 0.110 |
| semis_led_up | SOX outperformed NQ by > 1.5% | 84 | 0.524 | 2.045 | 0.429 | 0.417 | 0.393 | 65.147 | 0.339 |
| semis_led_down | SOX underperformed NQ by > 1.5% | 82 | 0.549 | 8.036 | 0.481 | 0.383 | 0.309 | 78.141 | 1.039 |
| rth_down_big | RTH down more than 1% | 81 | 0.617 | 13.816 | 0.383 | 0.259 | 0.383 | 83.174 | 1.690 |
| close_mid_range | Closed in middle 40% of range (indecision) | 81 | 0.457 | -1.035 | 0.850 | 0.575 | 0.150 | 62.883 | -0.199 |
| move_corrects_stretch | Today's move corrected a >1.5 ATR stretch from 20d SMA | 78 | 0.577 | 7.336 | 0.654 | 0.577 | 0.244 | 65.076 | 1.309 |
| nikkei_up_big | Nikkei rose > 1.5% in the prior Tokyo session | 76 | 0.487 | -3.673 | 0.553 | 0.474 | 0.368 | 56.962 | -0.598 |
| up_streak_3 | 3+ consecutive up RTH sessions | 76 | 0.474 | -5.551 | 0.387 | 0.427 | 0.373 | 42.795 | -1.116 |
| tier1_tomorrow | CPI/NFP/PCE tomorrow (pre-event night) | 75 | 0.453 | -0.639 | 0.453 | 0.440 | 0.373 | 60.472 | -0.122 |
| prior_asia_big | Last night's Asia moved > 0.7% | 73 | 0.575 | 13.069 | 0.486 | 0.431 | 0.347 | 87.300 | 1.833 |
| range_expansion | RTH range > 1.5x 20d ATR | 73 | 0.507 | -4.282 | 0.384 | 0.219 | 0.274 | 78.661 | -0.497 |
| rth_up_big | RTH up more than 1% | 71 | 0.408 | -8.281 | 0.197 | 0.197 | 0.507 | 63.330 | -1.582 |
| nq_underperf_es | NQ underperformed ES by > 0.5% | 66 | 0.576 | 10.774 | 0.470 | 0.303 | 0.288 | 74.380 | 1.531 |
| nikkei_down_big | Nikkei fell > 1.5% in the prior Tokyo session | 65 | 0.492 | -4.534 | 0.431 | 0.415 | 0.415 | 85.740 | -0.537 |
| post_close_extends | Post-close move extended the RTH direction | 63 | 0.587 | 7.537 | 0.206 | 0.190 | 0.651 | 75.286 | 0.815 |
| tier1_today | CPI/NFP/PCE released today | 63 | 0.476 | -2.184 | 0.403 | 0.306 | 0.435 | 81.501 | -0.263 |
| vix_spike | VIX up more than 10% today | 62 | 0.516 | 2.257 | 0.339 | 0.290 | 0.484 | 90.060 | 0.234 |
| down_streak_3 | 3+ consecutive down RTH sessions | 60 | 0.517 | 8.802 | 0.542 | 0.492 | 0.390 | 84.040 | 1.166 |
| btc_down_rth | BTC fell > 2% during US hours | 56 | 0.571 | 8.015 | 0.364 | 0.309 | 0.455 | 85.857 | 1.039 |
| crude_spike | Crude up > 3% today | 53 | 0.491 | 6.247 | 0.481 | 0.462 | 0.327 | 75.930 | 0.890 |
| earnings_tonight | Mega-cap earnings after the close tonight | 52 | 0.538 | 6.526 | 0.500 | 0.500 | 0.442 | 83.037 | 0.803 |
| stretched_below_20 | More than 2 ATR below 20d SMA | 52 | 0.577 | 8.465 | 0.404 | 0.442 | 0.385 | 101.343 | 0.735 |
| nq_outperf_es | NQ outperformed ES by > 0.5% | 51 | 0.392 | -10.722 | 0.240 | 0.180 | 0.440 | 62.252 | -1.829 |
| range_contraction | RTH range < 0.6x 20d ATR | 49 | 0.612 | 6.872 | 0.562 | 0.562 | 0.354 | 44.852 | 1.070 |
| post_close_shock | Post-close (16-17h) move > 0.3% (earnings/news) | 49 | 0.510 | 5.736 | 0.429 | 0.469 | 0.429 | 102.872 | 0.629 |
| vix_z_high | VIX > 2 sigma above its 20d mean | 43 | 0.465 | -8.530 | 0.279 | 0.302 | 0.442 | 91.456 | -0.687 |
| vix_diverged | VIX moved AGAINST the equity move (>5%) | 41 | 0.390 | -11.842 | 0.525 | 0.575 | 0.325 | 72.803 | -1.146 |
| vix_crush | VIX down more than 10% today | 40 | 0.575 | 4.602 | 0.350 | 0.325 | 0.350 | 55.942 | 0.569 |
| yen_surge_5d | USDJPY down > 2% over 5d | 40 | 0.400 | -13.613 | 0.436 | 0.385 | 0.333 | 76.176 | -1.092 |
| dollar_up | DXY up > 0.5% today | 39 | 0.513 | 3.921 | 0.359 | 0.308 | 0.487 | 76.250 | 0.320 |
| vix_high | VIX above 25 | 37 | 0.405 | -16.301 | 0.194 | 0.278 | 0.639 | 130.324 | -0.977 |
| stretched_below_50 | More than 3 ATR below 50d SMA | 33 | 0.515 | 5.399 | 0.394 | 0.424 | 0.424 | 136.656 | 0.320 |
| fomc_within_2d | FOMC within next 2 trading days | 33 | 0.515 | -1.712 | 0.545 | 0.485 | 0.424 | 66.293 | -0.163 |
| heavy_volume | RTH volume > 1.4x 20d average | 28 | 0.571 | 4.706 | 0.429 | 0.286 | 0.250 | 77.345 | 0.294 |
| vol_regime_shift | 5d realised vol > 1.6x 20d (vol expanding) | 28 | 0.571 | 10.433 | 0.393 | 0.286 | 0.429 | 73.983 | 0.840 |
| yields_spike | US10Y up > 8bp today | 27 | 0.593 | -0.297 | 0.481 | 0.444 | 0.296 | 63.053 | -0.024 |
| rth_down_huge | RTH down more than 2% | 27 | 0.519 | 2.037 | 0.259 | 0.074 | 0.407 | 94.768 | 0.113 |
| yen_surge | USDJPY down > 1% today (yen bid / carry unwind) | 26 | 0.423 | -16.049 | 0.480 | 0.360 | 0.440 | 64.542 | -1.020 |
| yields_plunge | US10Y down > 8bp today | 26 | 0.500 | -0.875 | 0.346 | 0.423 | 0.385 | 76.746 | -0.093 |
| light_volume | RTH volume < 0.7x 20d average | 24 | 0.625 | 13.464 | 0.565 | 0.522 | 0.304 | 60.461 | 1.424 |
| month_end | Month-end rebalancing session | 23 | 0.478 | 0.854 | 0.381 | 0.571 | 0.524 | 62.037 | 0.088 |
| late_day_fade | Faded back toward VWAP into the close | 22 | 0.591 | 0.088 | 1.000 | 0.727 | 0.045 | 71.329 | 0.007 |
| vix_low | VIX below 14 | 22 | 0.500 | -3.689 | 0.227 | 0.273 | 0.318 | 31.302 | -0.867 |
| opex_today | Monthly opex today | 20 | 0.550 | 6.894 | 0.579 | 0.579 | 0.263 | 63.681 | 0.744 |
| fomc_tomorrow | FOMC decision tomorrow | 17 | 0.412 | -1.025 | 0.471 | 0.471 | 0.471 | 72.244 | -0.065 |
| fomc_today | FOMC decision was today | 16 | 0.562 | 31.151 | 0.500 | 0.500 | 0.312 | 80.479 | 2.311 |
| rth_move_2sig | RTH move > 2 sigma of 20d daily vol | 15 | 0.600 | 31.303 | 0.133 | 0.067 | 0.267 | 63.330 | 2.416 |
| boj_tonight | BoJ decision during tonight's Asia session | 13 | 0.615 | 9.203 | 0.462 | 0.538 | 0.385 | 66.293 | 0.509 |
| rth_up_huge | RTH up more than 2% | 9 | 0.444 | -22.102 | 0.000 | 0.000 | 0.444 | 105.409 | -1.086 |
| pre_holiday | US holiday tomorrow (thin Asia) | 9 | 0.556 | 23.623 | 0.429 | 0.143 | 0.286 | 54.751 | 1.718 |
| roll_week | Quarterly roll day today | 9 | 0.667 | 17.865 | 0.556 | 0.556 | 0.222 | 73.093 | 0.996 |
| close_far_from_vwap | Closed > 0.5 range-widths beyond RTH VWAP | 8 | 0.750 | 28.372 | 0.250 | 0.375 | 0.500 | 63.970 | 1.923 |
| witching_today | Quarterly witching today | 4 | 0.250 | -34.486 | 0.000 | 0.000 | 0.750 | 48.664 | -1.865 |

### Rule table — past 365 days only

| rule | desc | n | rev_rate | avg_rev_ret_bp | vwap_first | r382_first | stopped | med_rng_bp | t_stat |
|---|---|---|---|---|---|---|---|---|---|
| prior_asia_reverted | Last night's Asia already reverted the prior RTH | 104 | 0.510 | -0.919 | 0.529 | 0.461 | 0.392 | 80.425 | -0.144 |
| close_at_extreme | Closed in outer 20% of range in the move's direction | 95 | 0.547 | 5.921 | 0.255 | 0.340 | 0.500 | 70.479 | 0.972 |
| semis_confirm | Semis led in the direction of the move (>1%) | 88 | 0.500 | 4.220 | 0.398 | 0.364 | 0.409 | 85.698 | 0.624 |
| broke_prev_high | Closed above prior RTH high | 80 | 0.475 | 5.818 | 0.443 | 0.456 | 0.367 | 62.037 | 1.067 |
| rth_fought_overnight | RTH reversed the prior overnight move | 68 | 0.485 | 1.244 | 0.537 | 0.537 | 0.328 | 73.093 | 0.167 |
| us_diverged_from_asia | US moved > 1.5% opposite to Tokyo's session | 62 | 0.435 | -5.106 | 0.516 | 0.419 | 0.419 | 74.774 | -0.689 |
| broke_prev_low | Closed below prior RTH low | 62 | 0.565 | 10.244 | 0.525 | 0.443 | 0.344 | 88.311 | 1.413 |
| move_extends_stretch | Today's move extended an existing >1.5 ATR stretch from 20d SMA | 61 | 0.443 | 3.380 | 0.300 | 0.350 | 0.533 | 75.476 | 0.462 |
| gap_and_go | Gapped and extended in gap direction | 57 | 0.579 | 12.198 | 0.421 | 0.491 | 0.368 | 84.953 | 1.663 |
| gap_reversed | Gapped then reversed the gap in RTH | 56 | 0.500 | -2.589 | 0.554 | 0.554 | 0.286 | 73.038 | -0.308 |
| prior_asia_same_dir | Last night's Asia moved > 0.4% in today's RTH direction | 54 | 0.556 | 7.045 | 0.500 | 0.426 | 0.407 | 85.305 | 0.841 |
| btc_confirms | BTC moved > 1.5% with the equity move in US hours | 54 | 0.500 | 5.386 | 0.396 | 0.396 | 0.358 | 85.857 | 0.711 |
| close_near_vwap | Closed within 0.1 range-widths of RTH VWAP | 52 | 0.404 | -10.578 | 0.860 | 0.520 | 0.220 | 73.224 | -1.296 |
| semis_led_up | SOX outperformed NQ by > 1.5% | 47 | 0.489 | -3.112 | 0.404 | 0.340 | 0.489 | 80.091 | -0.320 |
| stretched_above_20 | More than 2 ATR above 20d SMA | 45 | 0.422 | -0.527 | 0.477 | 0.455 | 0.477 | 58.743 | -0.089 |
| cn_data_tonight | China data during tonight's Asia session | 45 | 0.533 | -1.536 | 0.444 | 0.311 | 0.467 | 62.037 | -0.221 |
| thursday | Thursday | 44 | 0.545 | 4.411 | 0.409 | 0.477 | 0.341 | 73.482 | 0.536 |
| drawdown_5pct | More than 5% below 20d high | 44 | 0.500 | 9.042 | 0.409 | 0.386 | 0.432 | 105.205 | 0.847 |
| semis_led_down | SOX underperformed NQ by > 1.5% | 43 | 0.605 | 14.976 | 0.535 | 0.442 | 0.326 | 97.288 | 1.621 |
| close_mid_range | Closed in middle 40% of range (indecision) | 41 | 0.415 | -4.926 | 0.878 | 0.585 | 0.195 | 67.740 | -0.701 |
| nikkei_down_big | Nikkei fell > 1.5% in the prior Tokyo session | 40 | 0.575 | 5.136 | 0.475 | 0.450 | 0.400 | 85.698 | 0.558 |
| prior_asia_big | Last night's Asia moved > 0.7% | 40 | 0.600 | 10.225 | 0.575 | 0.500 | 0.300 | 92.539 | 0.924 |
| monday | Monday | 40 | 0.550 | -0.190 | 0.500 | 0.450 | 0.400 | 77.448 | -0.019 |
| sunday_open | Friday close -> Sunday 18:00 reopen (weekend gap risk) | 37 | 0.432 | 5.705 | 0.571 | 0.543 | 0.371 | 86.566 | 0.583 |
| up_streak_3 | 3+ consecutive up RTH sessions | 36 | 0.528 | -6.244 | 0.429 | 0.486 | 0.343 | 61.686 | -0.643 |
| crude_spike | Crude up > 3% today | 36 | 0.583 | 14.334 | 0.583 | 0.583 | 0.250 | 86.632 | 1.617 |
| nikkei_up_big | Nikkei rose > 1.5% in the prior Tokyo session | 36 | 0.500 | -0.501 | 0.639 | 0.528 | 0.333 | 60.216 | -0.050 |
| at_20d_high | Within 0.5% of 20d high | 35 | 0.457 | 1.305 | 0.353 | 0.412 | 0.471 | 48.355 | 0.195 |
| down_streak_3 | 3+ consecutive down RTH sessions | 33 | 0.545 | 9.677 | 0.594 | 0.531 | 0.375 | 84.205 | 1.111 |
| rth_down_big | RTH down more than 1% | 33 | 0.576 | 16.706 | 0.394 | 0.212 | 0.455 | 101.050 | 1.448 |
| range_expansion | RTH range > 1.5x 20d ATR | 32 | 0.438 | -4.898 | 0.469 | 0.250 | 0.281 | 91.005 | -0.429 |
| nq_underperf_es | NQ underperformed ES by > 0.5% | 31 | 0.516 | 6.910 | 0.645 | 0.355 | 0.258 | 85.656 | 0.672 |
| tier1_tomorrow | CPI/NFP/PCE tomorrow (pre-event night) | 31 | 0.516 | 1.638 | 0.548 | 0.452 | 0.419 | 75.610 | 0.174 |
| rth_up_big | RTH up more than 1% | 29 | 0.414 | -8.044 | 0.241 | 0.172 | 0.448 | 67.650 | -0.870 |
| move_corrects_stretch | Today's move corrected a >1.5 ATR stretch from 20d SMA | 28 | 0.536 | 11.252 | 0.679 | 0.607 | 0.286 | 84.201 | 1.049 |
| tier1_today | CPI/NFP/PCE released today | 27 | 0.519 | 6.491 | 0.444 | 0.333 | 0.481 | 91.456 | 0.573 |
| vix_spike | VIX up more than 10% today | 26 | 0.577 | 15.550 | 0.308 | 0.385 | 0.500 | 97.164 | 1.226 |
| post_close_extends | Post-close move extended the RTH direction | 26 | 0.615 | 16.359 | 0.192 | 0.192 | 0.654 | 80.778 | 1.390 |
| nq_outperf_es | NQ outperformed ES by > 0.5% | 26 | 0.385 | -13.052 | 0.320 | 0.240 | 0.400 | 69.566 | -1.390 |
| btc_down_rth | BTC fell > 2% during US hours | 25 | 0.600 | 7.342 | 0.400 | 0.240 | 0.520 | 89.565 | 0.603 |
| stretched_below_20 | More than 2 ATR below 20d SMA | 25 | 0.680 | 30.639 | 0.400 | 0.440 | 0.400 | 101.635 | 2.459 |
| earnings_tonight | Mega-cap earnings after the close tonight | 22 | 0.545 | 4.409 | 0.500 | 0.545 | 0.455 | 101.343 | 0.375 |
| vix_diverged | VIX moved AGAINST the equity move (>5%) | 22 | 0.409 | -8.450 | 0.682 | 0.682 | 0.227 | 71.479 | -0.506 |
| post_close_shock | Post-close (16-17h) move > 0.3% (earnings/news) | 22 | 0.500 | 3.588 | 0.455 | 0.500 | 0.455 | 101.343 | 0.329 |
| vix_z_high | VIX > 2 sigma above its 20d mean | 18 | 0.556 | 11.983 | 0.222 | 0.333 | 0.500 | 126.919 | 0.654 |
| vix_high | VIX above 25 | 16 | 0.375 | -14.761 | 0.125 | 0.250 | 0.750 | 111.472 | -0.605 |
| vix_crush | VIX down more than 10% today | 16 | 0.625 | 6.905 | 0.312 | 0.312 | 0.375 | 55.610 | 0.527 |
| range_contraction | RTH range < 0.6x 20d ATR | 15 | 0.400 | -0.577 | 0.533 | 0.467 | 0.400 | 47.011 | -0.048 |
| dollar_up | DXY up > 0.5% today | 15 | 0.600 | 21.202 | 0.467 | 0.467 | 0.400 | 86.566 | 1.191 |
| fomc_within_2d | FOMC within next 2 trading days | 14 | 0.429 | -8.383 | 0.714 | 0.571 | 0.357 | 68.351 | -0.579 |
| yen_surge_5d | USDJPY down > 2% over 5d | 13 | 0.154 | -24.927 | 0.615 | 0.538 | 0.308 | 76.176 | -1.826 |
| rth_down_huge | RTH down more than 2% | 11 | 0.636 | 34.990 | 0.455 | 0.091 | 0.273 | 91.456 | 2.027 |
| heavy_volume | RTH volume > 1.4x 20d average | 10 | 0.700 | 40.194 | 0.500 | 0.400 | 0.200 | 98.614 | 2.355 |
| opex_today | Monthly opex today | 10 | 0.200 | -11.138 | 0.556 | 0.556 | 0.333 | 88.311 | -0.684 |
| late_day_fade | Faded back toward VWAP into the close | 9 | 0.778 | 23.127 | 1.000 | 0.889 | 0.000 | 89.556 | 1.062 |
| month_end | Month-end rebalancing session | 9 | 0.556 | 0.874 | 0.625 | 0.750 | 0.500 | 67.557 | 0.039 |
| yen_surge | USDJPY down > 1% today (yen bid / carry unwind) | 9 | 0.333 | -8.517 | 0.750 | 0.625 | 0.375 | 76.732 | -0.551 |
| vol_regime_shift | 5d realised vol > 1.6x 20d (vol expanding) | 9 | 0.556 | -4.675 | 0.556 | 0.333 | 0.444 | 97.288 | -0.176 |
| stretched_below_50 | More than 3 ATR below 50d SMA | 9 | 0.667 | 35.501 | 0.222 | 0.333 | 0.556 | 181.818 | 1.478 |
| fomc_today | FOMC decision was today | 8 | 0.625 | 41.743 | 0.625 | 0.625 | 0.375 | 109.090 | 2.392 |
| fomc_tomorrow | FOMC decision tomorrow | 7 | 0.286 | -15.571 | 0.571 | 0.571 | 0.429 | 78.943 | -0.746 |
| yields_spike | US10Y up > 8bp today | 7 | 0.429 | 0.459 | 0.714 | 0.714 | 0.286 | 73.093 | 0.017 |
| light_volume | RTH volume < 0.7x 20d average | 6 | 0.500 | 2.472 | 0.800 | 0.800 | 0.000 | 33.267 | 0.368 |
| rth_move_2sig | RTH move > 2 sigma of 20d daily vol | 6 | 0.833 | 47.899 | 0.167 | 0.000 | 0.167 | 79.553 | 2.396 |
| rth_up_huge | RTH up more than 2% | 5 | 0.600 | -23.456 | 0.000 | 0.000 | 0.400 | 71.699 | -0.809 |
| boj_tonight | BoJ decision during tonight's Asia session | 5 | 0.400 | -18.080 | 0.400 | 0.400 | 0.600 | 66.201 | -0.976 |
| yields_plunge | US10Y down > 8bp today | 5 | 0.600 | 13.035 | 0.400 | 0.600 | 0.200 | 88.321 | 0.755 |
| pre_holiday | US holiday tomorrow (thin Asia) | 5 | 0.600 | 40.374 | 0.500 | 0.250 | 0.000 | 64.401 | 2.361 |
| roll_week | Quarterly roll day today | 4 | 0.500 | -7.055 | 0.250 | 0.500 | 0.500 | 74.351 | -0.394 |
| witching_today | Quarterly witching today | 3 | 0.000 | -50.241 | 0.000 | 0.000 | 1.000 | 66.619 | -3.672 |
| close_far_from_vwap | Closed > 0.5 range-widths beyond RTH VWAP | 2 | 0.500 | 42.547 | 0.500 | 0.500 | 0.500 | 89.872 | nan |

### Average logistic coefficients (standardised features; + = toward outcome)

- **hit_vwap_first**: vwap_in_dir -0.85, post_in_dir -0.64, ext_in_dir -0.52, vix_z20 +0.29, rv_ratio -0.20, rth_range_atr -0.20, sunday_open +0.16, boj_tonight +0.15, mag -0.15, witching_today -0.14, sox_in_dir -0.14, is_down +0.14
- **stopped**: post_in_dir +0.75, ext_in_dir +0.42, vwap_in_dir +0.41, rth_range_atr -0.36, boj_tonight -0.25, rth_vol_rel -0.19, fomc_tomorrow +0.17, vix +0.16, mag +0.16, stretch50_in_dir +0.15, megacap_earnings_tonight +0.15, ret5_in_dir +0.12
- **reverted**: yen_in_dir +0.27, opex_today +0.25, tier1_data_tomorrow -0.19, n225_in_dir -0.15, is_down +0.15, prior_asia_in_dir +0.14, sox_in_dir -0.12, stretch50_in_dir -0.12, rth_vol_rel -0.11, boj_tonight +0.11, rth_range_atr -0.10, overnight_in_dir +0.10

## ES

Data: hourly Globex bars 2024-06-18 → 2026-11-09, 588 RTH days, 465 nights with an RTH move ≥ 0.15%.

### Out-of-sample probability quality

| Outcome | description | OOS n | base rate | Brier base | Brier logit | Brier GBM | Brier calibrated | accuracy |
|---|---|---|---|---|---|---|---|---|
| reverted | Asia closes (03:00) on the opposite side of the 18:00 open vs the RTH move | 301 | 57% | 0.245 | 0.262 | 0.269 | **0.240** | 57% |
| hit_vwap_first | Asia touches RTH VWAP before the tight stop | 301 | 51% | 0.250 | 0.185 | 0.186 | **0.166** | 74% |
| hit_r382_first | Asia retraces 38.2% of the RTH move before the tight stop | 301 | 44% | 0.246 | 0.210 | 0.215 | **0.194** | 67% |
| hit_r500_first | Asia retraces 50% of the RTH move before the tight stop | 301 | 37% | 0.233 | 0.216 | 0.219 | **0.193** | 68% |
| stopped | Tight stop (RTH extreme + 10% of RTH range) is hit before any target | 301 | 34% | 0.223 | 0.214 | 0.211 | **0.189** | 72% |
| hit_vwap_first_w | Asia touches RTH VWAP before the wide stop | 301 | 50% | 0.250 | 0.206 | 0.204 | **0.187** | 70% |
| hit_r382_first_w | Asia retraces 38.2% of the RTH move before the wide stop | 301 | 44% | 0.246 | 0.226 | 0.231 | **0.210** | 65% |
| hit_r500_first_w | Asia retraces 50% of the RTH move before the wide stop | 301 | 37% | 0.233 | 0.228 | 0.224 | **0.202** | 67% |
| stopped_w | Wide stop (max(0.6x median Asia range, 0.3x today's RTH range) from 17:00 close) is hit first | 301 | 25% | 0.189 | 0.218 | 0.196 | **0.176** | 75% |

Calibration buckets (calibrated p vs realised):

| reverted bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 1.00 | 0.00 | 0.03 |
| (0.35, 0.5] | 15.00 | 0.47 | 0.47 |
| (0.5, 0.65] | 278.00 | 0.57 | 0.57 |
| (0.65, 0.8] | 3.00 | 0.67 | 0.67 |
| (0.8, 1.0] | 4.00 | 1.00 | 0.97 |

| hit_vwap_first bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 50.00 | 0.12 | 0.12 |
| (0.2, 0.35] | 74.00 | 0.30 | 0.30 |
| (0.35, 0.5] | 66.00 | 0.48 | 0.48 |
| (0.5, 0.65] | 33.00 | 0.64 | 0.64 |
| (0.8, 1.0] | 78.00 | 0.92 | 0.92 |

| hit_r382_first bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 55.00 | 0.07 | 0.07 |
| (0.2, 0.35] | 40.00 | 0.25 | 0.25 |
| (0.35, 0.5] | 96.00 | 0.48 | 0.48 |
| (0.5, 0.65] | 71.00 | 0.56 | 0.56 |
| (0.65, 0.8] | 31.00 | 0.74 | 0.74 |
| (0.8, 1.0] | 8.00 | 1.00 | 0.97 |

| hit_r500_first bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 68.00 | 0.12 | 0.13 |
| (0.2, 0.35] | 79.00 | 0.28 | 0.28 |
| (0.35, 0.5] | 40.00 | 0.40 | 0.40 |
| (0.5, 0.65] | 101.00 | 0.52 | 0.52 |
| (0.8, 1.0] | 13.00 | 0.92 | 0.91 |

| stopped bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 48.00 | 0.08 | 0.09 |
| (0.2, 0.35] | 120.00 | 0.28 | 0.28 |
| (0.35, 0.5] | 95.00 | 0.37 | 0.37 |
| (0.65, 0.8] | 21.00 | 0.67 | 0.67 |
| (0.8, 1.0] | 17.00 | 0.82 | 0.82 |

| hit_vwap_first_w bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 31.00 | 0.10 | 0.10 |
| (0.2, 0.35] | 87.00 | 0.31 | 0.31 |
| (0.35, 0.5] | 78.00 | 0.49 | 0.49 |
| (0.5, 0.65] | 15.00 | 0.53 | 0.53 |
| (0.65, 0.8] | 26.00 | 0.73 | 0.73 |
| (0.8, 1.0] | 64.00 | 0.88 | 0.87 |

| hit_r382_first_w bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 53.00 | 0.13 | 0.13 |
| (0.2, 0.35] | 35.00 | 0.29 | 0.29 |
| (0.35, 0.5] | 146.00 | 0.47 | 0.47 |
| (0.5, 0.65] | 22.00 | 0.64 | 0.64 |
| (0.65, 0.8] | 41.00 | 0.68 | 0.68 |
| (0.8, 1.0] | 4.00 | 1.00 | 0.97 |

| hit_r500_first_w bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 36.00 | 0.08 | 0.10 |
| (0.2, 0.35] | 112.00 | 0.28 | 0.28 |
| (0.35, 0.5] | 46.00 | 0.37 | 0.37 |
| (0.5, 0.65] | 81.00 | 0.51 | 0.51 |
| (0.65, 0.8] | 22.00 | 0.68 | 0.68 |
| (0.8, 1.0] | 4.00 | 1.00 | 0.97 |

| stopped_w bucket | n | realised | predicted |
|---|---|---|---|
| (-0.001, 0.2] | 107.00 | 0.15 | 0.15 |
| (0.2, 0.35] | 125.00 | 0.25 | 0.25 |
| (0.35, 0.5] | 61.00 | 0.39 | 0.39 |
| (0.5, 0.65] | 8.00 | 0.62 | 0.62 |

### Simulated decisions (OOS, first-hit resolution, no slippage)

- Nights evaluated: 301 · nights with a graded call: 190 (63%)
- Grade A: n=73, win rate 62%, avg +2.7 pts ($+133/contract), total +194 pts, worst -38 pts
- Grade B: n=63, win rate 63%, avg +4.0 pts ($+201/contract), total +253 pts, worst -35 pts
- Grade C: n=41, win rate 46%, avg -2.1 pts ($-106/contract), total -87 pts, worst -39 pts
- MEAN REVERSION: n=156, win rate 58%, avg +1.8 pts, total +288 pts
- CONTINUATION: n=21, win rate 62%, avg +3.4 pts, total +72 pts
- Past year only (from 2025-11-01): n=112, win rate 60%, avg +4.8 pts, total +498 pts

| month | n | win | total_pts | avg_pts |
|---|---|---|---|---|
| 2025-04 | 10.00 | 0.40 | -57.38 | -6.38 |
| 2025-05 | 11.00 | 0.45 | -31.93 | -3.19 |
| 2025-06 | 14.00 | 0.57 | 2.49 | 0.18 |
| 2025-07 | 11.00 | 0.45 | 3.11 | 0.31 |
| 2025-08 | 12.00 | 0.42 | -31.46 | -2.86 |
| 2025-09 | 10.00 | 0.60 | 38.30 | 3.83 |
| 2025-10 | 10.00 | 0.40 | -60.58 | -6.73 |
| 2025-11 | 12.00 | 0.50 | -50.65 | -4.22 |
| 2025-12 | 5.00 | 0.40 | -12.59 | -2.52 |
| 2026-01 | 9.00 | 0.56 | 29.51 | 4.22 |
| 2026-02 | 5.00 | 0.80 | 79.31 | 19.83 |
| 2026-03 | 11.00 | 0.73 | 134.75 | 12.25 |
| 2026-04 | 13.00 | 0.54 | -1.15 | -0.09 |
| 2026-05 | 11.00 | 0.45 | 4.88 | 0.49 |
| 2026-06 | 11.00 | 0.73 | 165.47 | 16.55 |
| 2026-07 | 13.00 | 0.54 | 54.39 | 4.94 |
| 2026-08 | 12.00 | 0.67 | 30.57 | 2.55 |
| 2026-09 | 3.00 | 1.00 | 27.47 | 9.16 |
| 2026-10 | 6.00 | 0.67 | 52.92 | 10.58 |
| 2026-11 | 1.00 | 0.00 | -17.40 | -17.40 |

### Asymmetries and findings (full sample, nights with |RTH| ≥ 0.15%)

| Condition | n | reverted | avg rev (bp) | VWAP first | 38% first | stopped | med range (bp) |
|---|---|---|---|---|---|---|---|
| all | 465 | 54% | +2.6 | 47% | 43% | 30% | 41 |
| RTH down | 221 | 58% | +5.2 | 53% | 47% | 29% | 46 |
| RTH up | 244 | 50% | +0.2 | 41% | 38% | 31% | 36 |
| RTH down 0.1–0% | 108 | 57% | +2.5 | 63% | 59% | 22% | 37 |
| RTH down 0.5–1% | 67 | 57% | +5.9 | 56% | 47% | 32% | 52 |
| RTH down 1.0–2% | 39 | 67% | +19.5 | 31% | 23% | 41% | 73 |
| RTH down 2.0–100% | 7 | 43% | -41.4 | 14% | 14% | 43% | 129 |
| RTH up 0.1–0% | 124 | 56% | +3.1 | 56% | 53% | 33% | 36 |
| RTH up 0.5–1% | 88 | 44% | -1.4 | 28% | 25% | 27% | 30 |
| RTH up 1.0–2% | 31 | 39% | -8.9 | 17% | 20% | 37% | 56 |
| RTH up 2.0–100% | 1 | 100% | +64.1 | 0% | 0% | 0% | 159 |
| closed at extreme (trend close) | 225 | 53% | +2.4 | 25% | 33% | 42% | 40 |
| closed off the extreme | 87 | 54% | +1.6 | 85% | 59% | 8% | 42 |
| VIX confirmed move | 255 | 54% | +2.2 | 42% | 36% | 34% | 43 |
| VIX diverged | 54 | 50% | -3.0 | 52% | 56% | 29% | 48 |
| move extends >1.5 ATR stretch | 151 | 53% | +4.1 | 40% | 39% | 31% | 38 |
| move corrects >1.5 ATR stretch | 60 | 60% | +1.0 | 54% | 46% | 19% | 39 |
| Friday → Sunday reopen | 93 | 47% | -1.0 | 49% | 43% | 38% | 47 |
| FOMC day | 15 | 73% | +26.8 | 60% | 60% | 20% | 57 |
| CPI/NFP/PCE tomorrow | 61 | 52% | +1.6 | 43% | 40% | 30% | 43 |
| BoJ tonight | 15 | 73% | +13.0 | 53% | 53% | 33% | 51 |
| mega-cap earnings tonight | 47 | 60% | +8.8 | 51% | 49% | 43% | 51 |
| VIX > 25 | 35 | 43% | -14.7 | 24% | 29% | 50% | 103 |
| VIX < 15 | 62 | 55% | -1.2 | 33% | 37% | 23% | 21 |

### Full rule table (all history)

| rule | desc | n | rev_rate | avg_rev_ret_bp | vwap_first | r382_first | stopped | med_rng_bp | t_stat |
|---|---|---|---|---|---|---|---|---|---|
| prior_asia_reverted | Last night's Asia already reverted the prior RTH | 242 | 0.500 | 2.007 | 0.496 | 0.437 | 0.290 | 43.193 | 0.846 |
| close_at_extreme | Closed in outer 20% of range in the move's direction | 224 | 0.536 | 2.419 | 0.247 | 0.327 | 0.417 | 39.689 | 0.870 |
| semis_confirm | Semis led in the direction of the move (>1%) | 180 | 0.544 | 2.182 | 0.391 | 0.385 | 0.307 | 42.849 | 0.623 |
| broke_prev_high | Closed above prior RTH high | 173 | 0.503 | 2.379 | 0.419 | 0.395 | 0.273 | 32.576 | 1.015 |
| move_extends_stretch | Today's move extended an existing >1.5 ATR stretch from 20d SMA | 151 | 0.530 | 4.149 | 0.400 | 0.393 | 0.313 | 38.187 | 1.114 |
| at_20d_high | Within 0.5% of 20d high | 118 | 0.542 | 3.962 | 0.483 | 0.441 | 0.263 | 28.744 | 1.491 |
| us_diverged_from_asia | US moved > 1.5% opposite to Tokyo's session | 115 | 0.522 | 2.490 | 0.439 | 0.404 | 0.298 | 45.750 | 0.710 |
| btc_confirms | BTC moved > 1.5% with the equity move in US hours | 113 | 0.549 | 5.187 | 0.482 | 0.391 | 0.327 | 51.734 | 1.363 |
| cn_data_tonight | China data during tonight's Asia session | 111 | 0.495 | 0.523 | 0.459 | 0.394 | 0.321 | 42.772 | 0.139 |
| broke_prev_low | Closed below prior RTH low | 110 | 0.582 | 4.713 | 0.380 | 0.352 | 0.333 | 51.051 | 0.919 |
| close_near_vwap | Closed within 0.1 range-widths of RTH VWAP | 109 | 0.560 | 3.846 | 0.840 | 0.585 | 0.132 | 41.596 | 1.092 |
| semis_led_up | SOX outperformed NQ by > 1.5% | 103 | 0.534 | 3.276 | 0.455 | 0.465 | 0.287 | 37.243 | 1.001 |
| stretched_above_20 | More than 2 ATR above 20d SMA | 99 | 0.505 | 2.766 | 0.454 | 0.402 | 0.247 | 29.289 | 1.075 |
| sunday_open | Friday close -> Sunday 18:00 reopen (weekend gap risk) | 93 | 0.473 | -0.960 | 0.489 | 0.432 | 0.375 | 46.522 | -0.174 |
| monday | Monday | 91 | 0.516 | 2.288 | 0.484 | 0.385 | 0.308 | 45.552 | 0.574 |
| thursday | Thursday | 88 | 0.534 | 3.040 | 0.356 | 0.379 | 0.310 | 37.498 | 0.856 |
| rth_fought_overnight | RTH reversed the prior overnight move | 87 | 0.494 | -0.617 | 0.464 | 0.393 | 0.321 | 49.931 | -0.148 |
| semis_led_down | SOX underperformed NQ by > 1.5% | 87 | 0.586 | 2.715 | 0.419 | 0.372 | 0.314 | 50.293 | 0.456 |
| gap_and_go | Gapped and extended in gap direction | 79 | 0.544 | 3.672 | 0.367 | 0.392 | 0.380 | 45.552 | 0.597 |
| range_expansion | RTH range > 1.5x 20d ATR | 78 | 0.526 | -2.691 | 0.321 | 0.256 | 0.308 | 53.152 | -0.417 |
| close_mid_range | Closed in middle 40% of range (indecision) | 73 | 0.548 | 3.121 | 0.819 | 0.569 | 0.097 | 41.948 | 0.621 |
| nikkei_up_big | Nikkei rose > 1.5% in the prior Tokyo session | 69 | 0.507 | -1.295 | 0.529 | 0.368 | 0.309 | 37.476 | -0.277 |
| tier1_today | CPI/NFP/PCE released today | 67 | 0.507 | -0.244 | 0.400 | 0.354 | 0.400 | 46.064 | -0.036 |
| gap_reversed | Gapped then reversed the gap in RTH | 65 | 0.508 | -0.206 | 0.460 | 0.397 | 0.317 | 53.184 | -0.039 |
| nq_outperf_es | NQ outperformed ES by > 0.5% | 63 | 0.619 | 7.675 | 0.476 | 0.397 | 0.286 | 48.835 | 1.847 |
| vix_spike | VIX up more than 10% today | 60 | 0.550 | 0.325 | 0.250 | 0.267 | 0.500 | 63.505 | 0.039 |
| move_corrects_stretch | Today's move corrected a >1.5 ATR stretch from 20d SMA | 60 | 0.600 | 0.976 | 0.542 | 0.458 | 0.186 | 38.672 | 0.217 |
| tier1_tomorrow | CPI/NFP/PCE tomorrow (pre-event night) | 60 | 0.533 | 1.599 | 0.433 | 0.400 | 0.300 | 43.153 | 0.420 |
| up_streak_3 | 3+ consecutive up RTH sessions | 58 | 0.483 | -4.110 | 0.421 | 0.351 | 0.351 | 27.686 | -0.899 |
| nikkei_down_big | Nikkei fell > 1.5% in the prior Tokyo session | 58 | 0.448 | -6.232 | 0.397 | 0.379 | 0.362 | 50.575 | -0.798 |
| heavy_volume | RTH volume > 1.4x 20d average | 54 | 0.574 | -1.369 | 0.481 | 0.333 | 0.259 | 50.612 | -0.159 |
| btc_down_rth | BTC fell > 2% during US hours | 53 | 0.604 | 6.086 | 0.529 | 0.412 | 0.353 | 64.817 | 1.002 |
| down_streak_3 | 3+ consecutive down RTH sessions | 49 | 0.571 | 13.187 | 0.596 | 0.596 | 0.319 | 51.173 | 2.242 |
| earnings_tonight | Mega-cap earnings after the close tonight | 47 | 0.596 | 8.768 | 0.511 | 0.489 | 0.426 | 50.942 | 1.480 |
| prior_asia_same_dir | Last night's Asia moved > 0.4% in today's RTH direction | 46 | 0.609 | 8.533 | 0.522 | 0.500 | 0.283 | 53.207 | 1.014 |
| rth_down_big | RTH down more than 1% | 46 | 0.630 | 10.205 | 0.283 | 0.217 | 0.413 | 75.193 | 1.028 |
| stretched_below_20 | More than 2 ATR below 20d SMA | 44 | 0.614 | -1.533 | 0.364 | 0.432 | 0.364 | 77.803 | -0.142 |
| range_contraction | RTH range < 0.6x 20d ATR | 43 | 0.628 | 9.937 | 0.643 | 0.619 | 0.286 | 33.236 | 2.842 |
| nq_underperf_es | NQ underperformed ES by > 0.5% | 43 | 0.419 | -10.069 | 0.256 | 0.233 | 0.372 | 41.046 | -2.183 |
| light_volume | RTH volume < 0.7x 20d average | 41 | 0.659 | 11.526 | 0.575 | 0.525 | 0.175 | 37.332 | 2.611 |
| drawdown_5pct | More than 5% below 20d high | 41 | 0.463 | -6.845 | 0.425 | 0.525 | 0.300 | 88.049 | -0.582 |
| vix_crush | VIX down more than 10% today | 41 | 0.561 | 2.657 | 0.341 | 0.244 | 0.268 | 45.552 | 0.490 |
| vix_z_high | VIX > 2 sigma above its 20d mean | 40 | 0.500 | -12.333 | 0.250 | 0.300 | 0.475 | 65.110 | -1.118 |
| crude_spike | Crude up > 3% today | 39 | 0.513 | 10.152 | 0.421 | 0.474 | 0.368 | 56.026 | 1.510 |
| yen_surge_5d | USDJPY down > 2% over 5d | 38 | 0.447 | -16.939 | 0.222 | 0.222 | 0.333 | 50.987 | -1.431 |
| post_close_extends | Post-close move extended the RTH direction | 37 | 0.622 | -2.949 | 0.135 | 0.108 | 0.649 | 68.091 | -0.230 |
| dollar_up | DXY up > 0.5% today | 36 | 0.667 | 10.394 | 0.444 | 0.417 | 0.389 | 57.631 | 0.995 |
| vix_high | VIX above 25 | 35 | 0.429 | -14.699 | 0.235 | 0.294 | 0.500 | 103.000 | -1.023 |
| prior_asia_big | Last night's Asia moved > 0.7% | 33 | 0.606 | 7.772 | 0.406 | 0.344 | 0.375 | 74.837 | 0.702 |
| rth_up_big | RTH up more than 1% | 31 | 0.419 | -6.576 | 0.161 | 0.194 | 0.355 | 56.244 | -0.728 |
| vol_regime_shift | 5d realised vol > 1.6x 20d (vol expanding) | 30 | 0.633 | 6.129 | 0.400 | 0.333 | 0.333 | 50.290 | 0.593 |
| vix_diverged | VIX moved AGAINST the equity move (>5%) | 30 | 0.533 | -1.699 | 0.448 | 0.483 | 0.414 | 55.231 | -0.159 |
| fomc_within_2d | FOMC within next 2 trading days | 30 | 0.700 | 5.064 | 0.633 | 0.500 | 0.233 | 45.907 | 0.627 |
| post_close_shock | Post-close (16-17h) move > 0.3% (earnings/news) | 27 | 0.630 | 3.836 | 0.444 | 0.444 | 0.407 | 72.510 | 0.316 |
| yields_plunge | US10Y down > 8bp today | 26 | 0.462 | -5.971 | 0.385 | 0.346 | 0.346 | 50.688 | -0.607 |
| yen_surge | USDJPY down > 1% today (yen bid / carry unwind) | 25 | 0.400 | -15.302 | 0.333 | 0.333 | 0.417 | 47.391 | -1.168 |
| yields_spike | US10Y up > 8bp today | 25 | 0.600 | -3.322 | 0.320 | 0.280 | 0.320 | 47.505 | -0.324 |
| stretched_below_50 | More than 3 ATR below 50d SMA | 24 | 0.542 | -3.819 | 0.500 | 0.542 | 0.375 | 106.015 | -0.214 |
| month_end | Month-end rebalancing session | 23 | 0.478 | 2.212 | 0.333 | 0.476 | 0.381 | 42.849 | 0.310 |
| opex_today | Monthly opex today | 18 | 0.556 | 6.303 | 0.529 | 0.588 | 0.294 | 40.146 | 0.984 |
| vix_low | VIX below 14 | 17 | 0.765 | 4.830 | 0.294 | 0.412 | 0.118 | 17.725 | 1.891 |
| fomc_today | FOMC decision was today | 15 | 0.733 | 26.791 | 0.600 | 0.600 | 0.200 | 57.321 | 3.074 |
| boj_tonight | BoJ decision during tonight's Asia session | 15 | 0.733 | 12.956 | 0.533 | 0.533 | 0.333 | 50.942 | 1.331 |
| rth_move_2sig | RTH move > 2 sigma of 20d daily vol | 14 | 0.714 | 15.229 | 0.143 | 0.071 | 0.429 | 69.852 | 1.233 |
| fomc_tomorrow | FOMC decision tomorrow | 12 | 0.833 | 15.229 | 0.500 | 0.583 | 0.167 | 38.990 | 1.403 |
| close_far_from_vwap | Closed > 0.5 range-widths beyond RTH VWAP | 12 | 0.500 | 3.911 | 0.167 | 0.417 | 0.500 | 50.119 | 0.571 |
| late_day_fade | Faded back toward VWAP into the close | 9 | 0.556 | -11.913 | 1.000 | 0.667 | 0.000 | 66.343 | -0.581 |
| roll_week | Quarterly roll day today | 8 | 0.750 | 22.225 | 0.375 | 0.500 | 0.000 | 38.682 | 1.364 |
| pre_holiday | US holiday tomorrow (thin Asia) | 8 | 0.750 | 14.097 | 0.500 | 0.333 | 0.167 | 25.432 | 2.725 |
| rth_down_huge | RTH down more than 2% | 7 | 0.429 | -41.364 | 0.143 | 0.143 | 0.429 | 128.754 | -0.885 |
| witching_today | Quarterly witching today | 4 | 0.250 | -23.086 | 0.000 | 0.250 | 0.750 | 29.938 | -1.712 |
| rth_up_huge | RTH up more than 2% | 1 | 1.000 | 64.062 | 0.000 | 0.000 | 0.000 | 159.473 | nan |

### Rule table — past 365 days only

| rule | desc | n | rev_rate | avg_rev_ret_bp | vwap_first | r382_first | stopped | med_rng_bp | t_stat |
|---|---|---|---|---|---|---|---|---|---|
| prior_asia_reverted | Last night's Asia already reverted the prior RTH | 103 | 0.563 | 1.749 | 0.549 | 0.471 | 0.304 | 47.208 | 0.415 |
| close_at_extreme | Closed in outer 20% of range in the move's direction | 84 | 0.548 | 2.522 | 0.277 | 0.349 | 0.446 | 43.643 | 0.564 |
| semis_confirm | Semis led in the direction of the move (>1%) | 79 | 0.570 | 3.657 | 0.468 | 0.443 | 0.329 | 44.360 | 0.787 |
| broke_prev_high | Closed above prior RTH high | 71 | 0.507 | 4.510 | 0.486 | 0.414 | 0.314 | 36.106 | 1.209 |
| btc_confirms | BTC moved > 1.5% with the equity move in US hours | 53 | 0.566 | 5.095 | 0.549 | 0.412 | 0.314 | 46.980 | 0.982 |
| us_diverged_from_asia | US moved > 1.5% opposite to Tokyo's session | 52 | 0.558 | 8.543 | 0.510 | 0.431 | 0.314 | 53.184 | 1.552 |
| semis_led_up | SOX outperformed NQ by > 1.5% | 52 | 0.558 | 2.513 | 0.440 | 0.460 | 0.380 | 44.220 | 0.463 |
| move_extends_stretch | Today's move extended an existing >1.5 ATR stretch from 20d SMA | 51 | 0.549 | 8.751 | 0.373 | 0.373 | 0.412 | 41.307 | 1.885 |
| close_near_vwap | Closed within 0.1 range-widths of RTH VWAP | 49 | 0.551 | 2.894 | 0.854 | 0.604 | 0.146 | 42.374 | 0.642 |
| broke_prev_low | Closed below prior RTH low | 43 | 0.581 | 10.113 | 0.381 | 0.381 | 0.381 | 52.793 | 1.715 |
| cn_data_tonight | China data during tonight's Asia session | 41 | 0.585 | 5.355 | 0.525 | 0.425 | 0.325 | 38.766 | 1.104 |
| at_20d_high | Within 0.5% of 20d high | 41 | 0.512 | 3.234 | 0.463 | 0.366 | 0.317 | 30.521 | 0.846 |
| monday | Monday | 39 | 0.538 | 2.218 | 0.538 | 0.333 | 0.359 | 47.744 | 0.357 |
| thursday | Thursday | 35 | 0.571 | 3.641 | 0.343 | 0.371 | 0.286 | 41.867 | 0.710 |
| semis_led_down | SOX underperformed NQ by > 1.5% | 35 | 0.629 | 13.189 | 0.543 | 0.457 | 0.343 | 53.184 | 2.487 |
| stretched_above_20 | More than 2 ATR above 20d SMA | 35 | 0.514 | 2.843 | 0.412 | 0.412 | 0.353 | 34.316 | 0.699 |
| sunday_open | Friday close -> Sunday 18:00 reopen (weekend gap risk) | 34 | 0.471 | 7.997 | 0.581 | 0.484 | 0.387 | 43.975 | 1.173 |
| nikkei_up_big | Nikkei rose > 1.5% in the prior Tokyo session | 33 | 0.576 | 5.378 | 0.531 | 0.344 | 0.344 | 38.850 | 0.767 |
| nikkei_down_big | Nikkei fell > 1.5% in the prior Tokyo session | 33 | 0.576 | 7.677 | 0.485 | 0.424 | 0.333 | 50.218 | 1.144 |
| rth_fought_overnight | RTH reversed the prior overnight move | 32 | 0.562 | 8.444 | 0.613 | 0.452 | 0.226 | 49.644 | 1.199 |
| range_expansion | RTH range > 1.5x 20d ATR | 31 | 0.484 | 2.794 | 0.355 | 0.226 | 0.387 | 56.244 | 0.391 |
| gap_and_go | Gapped and extended in gap direction | 28 | 0.536 | 8.793 | 0.321 | 0.429 | 0.464 | 45.670 | 1.327 |
| nq_outperf_es | NQ outperformed ES by > 0.5% | 27 | 0.519 | 2.968 | 0.593 | 0.481 | 0.333 | 49.644 | 0.550 |
| up_streak_3 | 3+ consecutive up RTH sessions | 27 | 0.593 | -6.246 | 0.556 | 0.444 | 0.333 | 35.866 | -0.686 |
| close_mid_range | Closed in middle 40% of range (indecision) | 26 | 0.577 | 8.750 | 0.846 | 0.615 | 0.038 | 40.980 | 1.313 |
| tier1_today | CPI/NFP/PCE released today | 26 | 0.577 | 15.955 | 0.560 | 0.480 | 0.400 | 45.947 | 2.167 |
| down_streak_3 | 3+ consecutive down RTH sessions | 25 | 0.600 | 17.504 | 0.625 | 0.542 | 0.292 | 52.178 | 2.220 |
| btc_down_rth | BTC fell > 2% during US hours | 24 | 0.625 | 4.744 | 0.609 | 0.435 | 0.435 | 64.817 | 0.543 |
| vix_spike | VIX up more than 10% today | 23 | 0.565 | 10.008 | 0.348 | 0.391 | 0.565 | 64.817 | 1.185 |
| tier1_tomorrow | CPI/NFP/PCE tomorrow (pre-event night) | 23 | 0.652 | 3.128 | 0.565 | 0.435 | 0.261 | 46.775 | 0.541 |
| crude_spike | Crude up > 3% today | 23 | 0.609 | 13.402 | 0.565 | 0.609 | 0.217 | 57.893 | 1.417 |
| gap_reversed | Gapped then reversed the gap in RTH | 23 | 0.609 | 12.243 | 0.652 | 0.435 | 0.217 | 53.184 | 1.324 |
| nq_underperf_es | NQ underperformed ES by > 0.5% | 22 | 0.455 | -9.358 | 0.273 | 0.273 | 0.364 | 44.220 | -1.393 |
| prior_asia_same_dir | Last night's Asia moved > 0.4% in today's RTH direction | 21 | 0.571 | 7.699 | 0.667 | 0.619 | 0.238 | 50.349 | 0.646 |
| heavy_volume | RTH volume > 1.4x 20d average | 20 | 0.650 | 17.210 | 0.600 | 0.400 | 0.250 | 61.982 | 1.859 |
| earnings_tonight | Mega-cap earnings after the close tonight | 19 | 0.684 | 7.331 | 0.579 | 0.526 | 0.368 | 59.999 | 0.941 |
| move_corrects_stretch | Today's move corrected a >1.5 ATR stretch from 20d SMA | 16 | 0.688 | 11.366 | 0.400 | 0.467 | 0.267 | 38.672 | 1.741 |
| rth_down_big | RTH down more than 1% | 15 | 0.733 | 33.771 | 0.400 | 0.267 | 0.533 | 84.151 | 2.946 |
| post_close_extends | Post-close move extended the RTH direction | 15 | 0.933 | 24.433 | 0.200 | 0.200 | 0.533 | 54.963 | 5.954 |
| range_contraction | RTH range < 0.6x 20d ATR | 15 | 0.733 | 9.568 | 0.600 | 0.467 | 0.333 | 30.521 | 1.745 |
| stretched_below_20 | More than 2 ATR below 20d SMA | 15 | 0.800 | 30.307 | 0.267 | 0.400 | 0.533 | 95.424 | 2.877 |
| vix_crush | VIX down more than 10% today | 15 | 0.600 | 2.437 | 0.267 | 0.200 | 0.400 | 49.679 | 0.300 |
| vix_high | VIX above 25 | 14 | 0.429 | -7.383 | 0.214 | 0.286 | 0.571 | 94.793 | -0.353 |
| light_volume | RTH volume < 0.7x 20d average | 14 | 0.714 | 11.916 | 0.615 | 0.538 | 0.231 | 25.091 | 3.246 |
| vix_diverged | VIX moved AGAINST the equity move (>5%) | 14 | 0.643 | 4.306 | 0.643 | 0.571 | 0.357 | 48.550 | 0.227 |
| vix_z_high | VIX > 2 sigma above its 20d mean | 14 | 0.714 | 19.792 | 0.214 | 0.286 | 0.643 | 85.740 | 1.691 |
| fomc_within_2d | FOMC within next 2 trading days | 12 | 0.667 | 5.160 | 0.667 | 0.333 | 0.250 | 41.889 | 0.627 |
| yen_surge_5d | USDJPY down > 2% over 5d | 12 | 0.417 | -11.396 | 0.182 | 0.182 | 0.545 | 37.313 | -1.022 |
| rth_up_big | RTH up more than 1% | 11 | 0.545 | 4.345 | 0.182 | 0.091 | 0.364 | 49.355 | 0.302 |
| dollar_up | DXY up > 0.5% today | 10 | 0.700 | 32.366 | 0.700 | 0.700 | 0.300 | 77.286 | 2.293 |
| prior_asia_big | Last night's Asia moved > 0.7% | 10 | 0.800 | 22.796 | 0.700 | 0.600 | 0.100 | 52.055 | 1.270 |
| post_close_shock | Post-close (16-17h) move > 0.3% (earnings/news) | 9 | 0.778 | 9.134 | 0.444 | 0.444 | 0.444 | 46.146 | 1.016 |
| vol_regime_shift | 5d realised vol > 1.6x 20d (vol expanding) | 9 | 0.667 | 11.954 | 0.556 | 0.333 | 0.333 | 49.448 | 0.653 |
| month_end | Month-end rebalancing session | 8 | 0.625 | 8.131 | 0.571 | 0.571 | 0.429 | 44.079 | 0.472 |
| yen_surge | USDJPY down > 1% today (yen bid / carry unwind) | 8 | 0.375 | -9.995 | 0.429 | 0.286 | 0.571 | 45.947 | -1.067 |
| opex_today | Monthly opex today | 8 | 0.250 | -2.468 | 0.429 | 0.429 | 0.429 | 40.146 | -0.183 |
| fomc_today | FOMC decision was today | 7 | 0.857 | 34.325 | 0.714 | 0.714 | 0.286 | 75.874 | 3.008 |
| yields_spike | US10Y up > 8bp today | 6 | 0.500 | 6.316 | 0.333 | 0.500 | 0.500 | 55.141 | 0.273 |
| late_day_fade | Faded back toward VWAP into the close | 6 | 0.500 | -2.011 | 1.000 | 0.667 | 0.000 | 67.592 | -0.079 |
| rth_move_2sig | RTH move > 2 sigma of 20d daily vol | 6 | 0.833 | 26.896 | 0.167 | 0.000 | 0.500 | 83.806 | 3.222 |
| stretched_below_50 | More than 3 ATR below 50d SMA | 6 | 0.833 | 43.923 | 0.333 | 0.500 | 0.500 | 108.976 | 2.003 |
| drawdown_5pct | More than 5% below 20d high | 6 | 0.667 | 28.370 | 0.167 | 0.333 | 0.500 | 108.976 | 1.306 |
| yields_plunge | US10Y down > 8bp today | 5 | 0.400 | 10.234 | 0.800 | 0.800 | 0.000 | 46.146 | 0.621 |
| boj_tonight | BoJ decision during tonight's Asia session | 5 | 0.600 | 3.677 | 0.400 | 0.400 | 0.600 | 46.844 | 0.439 |
| fomc_tomorrow | FOMC decision tomorrow | 4 | 0.750 | 3.690 | 0.250 | 0.500 | 0.250 | 31.027 | 0.237 |
| pre_holiday | US holiday tomorrow (thin Asia) | 4 | 0.750 | 18.538 | 0.667 | 0.333 | 0.000 | 35.485 | 1.833 |
| witching_today | Quarterly witching today | 3 | 0.000 | -33.635 | 0.000 | 0.000 | 1.000 | 40.146 | -2.833 |
| close_far_from_vwap | Closed > 0.5 range-widths beyond RTH VWAP | 3 | 0.333 | 2.569 | 0.333 | 0.333 | 0.667 | 57.321 | 0.135 |
| roll_week | Quarterly roll day today | 3 | 0.667 | 0.520 | 0.333 | 0.333 | 0.000 | 49.679 | 0.043 |
| rth_down_huge | RTH down more than 2% | 2 | 0.500 | 11.903 | 0.000 | 0.000 | 0.500 | 106.107 | nan |

### Average logistic coefficients (standardised features; + = toward outcome)

- **hit_vwap_first**: post_in_dir -0.71, vwap_in_dir -0.68, ext_in_dir -0.48, rth_range_atr -0.29, vix_z20 +0.21, yield_in_dir +0.19, tier1_data_today -0.18, witching_today -0.16, vix_consistent -0.15, sox_in_dir -0.15, month_end -0.15, nqes_in_dir +0.15
- **stopped**: post_in_dir +0.82, ext_in_dir +0.39, vwap_in_dir +0.35, megacap_earnings_tonight +0.28, rth_range_atr -0.22, stretch50_in_dir +0.21, vix +0.18, sunday_open +0.18, stretch20_in_dir -0.15, pre_holiday -0.15, vix_z20 +0.14, prior_asia_in_dir +0.14
- **reverted**: yen_in_dir +0.25, is_down +0.25, pre_holiday +0.22, opex_today +0.21, ret5_in_dir -0.19, sox_in_dir -0.17, asia_rng_med20 +0.16, fomc_tomorrow +0.14, nqes_in_dir -0.14, boj_tonight +0.13, tier1_data_tomorrow -0.12, vwap_in_dir +0.11

## Caveats

- 17 months of hourly data; ~330 OOS nights. Rare calendar setups are anecdotes.
- First-hit resolution uses hourly bars: if target and stop are both inside one bar it counts as stopped (conservative).
- No slippage/commissions; Globex Asia liquidity is thin (NQ 1-2 tick spread but shallow depth), so size accordingly.
- The close-to-close reversion probability is close to coin-flip out of sample. The edge is in path outcomes and in sizing from the range model.
- Regime risk: the training window contains the Aug-2024 yen-carry unwind, the Apr-2025 tariff shock, the Mar-Apr 2026 and Jun-Jul 2026 stress episodes and Nov-2026 crash; a new regime can break the calibration.