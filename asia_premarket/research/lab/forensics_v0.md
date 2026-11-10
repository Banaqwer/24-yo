# Forensics v0 — why the NQ engine loses, and what the Grade-A wins are made of

Source: `research/backtest_trades_NQ.csv` (331 OOS nights, 196 graded, 87 losing graded nights) joined with `data/NQ_features.csv`, `data/NQ_targets.csv`, `data/NQ_sessions.csv`, hourly bars and the four `research/catalogue_*.csv`. Every graded trade's geometry (entry = 17:00 close, stop, target) was rebuilt from the session table and walked bar by bar; the rebuilt P&L matches the engine's `pnl_pts` on all 196 graded nights (max abs error 3.64e-12). Script: `/tmp/claude-0/-home-user-24-yo/0f4c1f58-9634-52a1-b9e3-d380ed906070/scratchpad/forensics.py`.

Reading guide: `res` = how the trade resolved (target / stop / scratch at 03:00); `decided_bar` = index of the hourly bar in which it resolved (0 = the 18:00 bar); `stop_vs_realised` = stop distance / realised Asia range; `whipsaw` = stopped and the target was reached later in the same Asia session; `same_bar` = target and stop first touched in the same hourly bar (the engine counts that as stopped for a fade and as a win for a continuation).

## 0. Headline numbers

| grade | n | win | avg | pts | avg_win | avg_loss | decided_bar0 |
|---|---|---|---|---|---|---|---|
| A | 78.00 | 0.69 | 21.31 | 1662.03 | 72.52 | -93.93 | 0.26 |
| B | 79.00 | 0.46 | -9.96 | -786.70 | 91.50 | -94.90 | 0.15 |
| C | 39.00 | 0.49 | -14.30 | -557.77 | 79.04 | -102.98 | 0.08 |

Resolution of every graded trade (how the loss happened matters more than the grade):

|  | n | avg | pts |
|---|---|---|---|
| ('A', 'scratch') | 23.00 | -49.80 | -1145.43 |
| ('A', 'stop') | 8.00 | -118.28 | -946.25 |
| ('A', 'target') | 47.00 | 79.87 | 3753.71 |
| ('B', 'scratch') | 26.00 | -12.73 | -330.92 |
| ('B', 'stop') | 27.00 | -117.67 | -3176.97 |
| ('B', 'target') | 26.00 | 104.66 | 2721.19 |
| ('C', 'scratch') | 18.00 | 25.07 | 451.28 |
| ('C', 'stop') | 14.00 | -130.78 | -1830.88 |
| ('C', 'target') | 7.00 | 117.40 | 821.83 |

Losses by grade / call / stop variant / resolution:

|  | n | pts | avg |
|---|---|---|---|
| ('A', 'CONTINUATION', 'tight', 'scratch') | 8.00 | -592.68 | -74.08 |
| ('A', 'CONTINUATION', 'tight', 'stop') | 3.00 | -309.60 | -103.20 |
| ('A', 'CONTINUATION', 'wide', 'scratch') | 4.00 | -591.16 | -147.79 |
| ('A', 'MEAN REVERSION', 'tight', 'scratch') | 4.00 | -124.21 | -31.05 |
| ('A', 'MEAN REVERSION', 'tight', 'stop') | 2.00 | -226.25 | -113.13 |
| ('A', 'MEAN REVERSION', 'wide', 'stop') | 3.00 | -410.40 | -136.80 |
| ('B', 'CONTINUATION', 'tight', 'scratch') | 7.00 | -334.09 | -47.73 |
| ('B', 'CONTINUATION', 'tight', 'stop') | 9.00 | -732.48 | -81.39 |
| ('B', 'CONTINUATION', 'wide', 'scratch') | 2.00 | -374.99 | -187.50 |
| ('B', 'CONTINUATION', 'wide', 'stop') | 1.00 | -155.51 | -155.51 |
| ('B', 'MEAN REVERSION', 'tight', 'scratch') | 3.00 | -74.48 | -24.83 |
| ('B', 'MEAN REVERSION', 'tight', 'stop') | 1.00 | -71.08 | -71.08 |
| ('B', 'MEAN REVERSION', 'wide', 'scratch') | 4.00 | -120.24 | -30.06 |
| ('B', 'MEAN REVERSION', 'wide', 'stop') | 16.00 | -2217.90 | -138.62 |
| ('C', 'CONTINUATION', 'tight', 'stop') | 5.00 | -440.01 | -88.00 |
| ('C', 'MEAN REVERSION', 'wide', 'scratch') | 6.00 | -228.64 | -38.11 |
| ('C', 'MEAN REVERSION', 'wide', 'stop') | 9.00 | -1390.88 | -154.54 |

## 1. Loss clusters (87 losing graded nights)

Each losing night gets every flag it satisfies (table 1a, overlapping) and one PRIMARY cluster by a fixed priority (table 1b, mutually exclusive): same-bar artefact > identified catalyst (catalogue driver or after-hours print) > geometry whipsaw > geometry (stop < 1/3 of realised range, target beyond realised range) > timing (target reached in Europe / next RTH) > ex-post Asia shock (KOSPI or N225 moved > 2% that night, not in catalogue) > calendar > regime > mid-band calibration > unexplained.

### 1a. Flag counts (overlapping) with the base rate of the same condition among the 109 winning graded nights

|  | n_losses | share | pts | A_losses | share_among_wins | lift_vs_wins |
|---|---|---|---|---|---|---|
| f_artefact_samebar | 0.00 | 0.00 | 0.00 | 0.00 |  |  |
| f_artefact_thin | 4.00 | 0.05 | -380.70 | 3.00 | 0.01 | 5.01 |
| f_calendar_sunday | 15.00 | 0.17 | -1570.60 | 0.00 | 0.20 | 0.85 |
| f_calendar_holiday | 4.00 | 0.05 | -473.06 | 2.00 | 0.00 | inf |
| f_catalyst_catalogue | 28.00 | 0.32 | -4157.77 | 10.00 | 0.26 | 1.25 |
| f_catalyst_ah | 7.00 | 0.08 | -1030.88 | 3.00 | 0.05 | 1.75 |
| f_catalyst_asia_expost | 37.00 | 0.43 | -4364.34 | 4.00 | 0.46 | 0.93 |
| f_geom_whipsaw | 2.00 | 0.02 | -367.12 | 0.00 |  |  |
| f_geom_stop_lt_third_range | 11.00 | 0.13 | -825.61 | 2.00 |  |  |
| f_geom_target_beyond_range | 12.00 | 0.14 | -550.25 | 3.00 |  |  |
| f_geom_stopped_before_move | 5.00 | 0.06 | -667.18 | 1.00 |  |  |
| f_timing_scratch_then_target | 5.00 | 0.06 | -203.68 | 3.00 |  |  |
| f_timing_eur_touch_any | 10.00 | 0.11 | -970.39 | 4.00 |  |  |
| f_timing_nextrth_touch_any | 37.00 | 0.43 | -3245.86 | 13.00 |  |  |
| f_regime_vol | 21.00 | 0.24 | -3208.30 | 9.00 | 0.22 | 1.10 |
| f_regime_form | 10.00 | 0.11 | -711.25 | 3.00 | 0.11 | 1.04 |
| f_calib_midband | 58.00 | 0.67 | -5796.23 | 0.00 | 0.47 | 1.42 |

### 1b. Primary cluster

| primary | n | pts | avg | A | B | C | share_n | share_pts |
|---|---|---|---|---|---|---|---|---|
| c) catalyst (catalogue driver / after-hours print) | 29.00 | -4245.84 | -146.41 | 10.00 | 14.00 | 5.00 | 0.33 | 0.51 |
| d) calibration: mid-band confidence only | 13.00 | -859.90 | -66.15 | 0.00 | 6.00 | 7.00 | 0.15 | 0.10 |
| a) geometry: stop < 1/3 of realised range or target beyond realised range | 12.00 | -573.04 | -47.75 | 2.00 | 6.00 | 4.00 | 0.14 | 0.07 |
| b) regime: VIX>25 / vix_z>1.5 / rv_ratio>1.5 / trailing form <45% | 11.00 | -999.57 | -90.87 | 5.00 | 5.00 | 1.00 | 0.13 | 0.12 |
| f) calendar: Sunday reopen / holiday / thin session | 8.00 | -691.98 | -86.50 | 1.00 | 5.00 | 2.00 | 0.09 | 0.08 |
| a) geometry: stopped, then the target was reached (Asia whipsaw or Europe target-first) | 5.00 | -667.18 | -133.44 | 1.00 | 3.00 | 1.00 | 0.06 | 0.08 |
| g) unexplained | 5.00 | -234.66 | -46.93 | 3.00 | 2.00 | 0.00 | 0.06 | 0.03 |
| e) timing: scratch at 03:00, target hit before stop in Europe / next RTH | 4.00 | -122.43 | -30.61 | 2.00 | 2.00 | 0.00 | 0.05 | 0.01 |

### 1b-i. Inside the catalyst cluster: what kind of driver, and was it knowable at 18:00 ET?

| knowable_at_18 | n | pts | A |
|---|---|---|---|
| Asia-origin, only visible at the 19:00-20:00 Seoul/Tokyo open | 11.00 | -1937.14 | 5.00 |
| after-hours print (known 16:05-17:00) | 13.00 | -1811.79 | 4.00 |
| after-hours print (known 16:05-17:00); scheduled event flag already in the model | 1.00 | -113.99 | 1.00 |
| intra-session headline (Trump/Iran/oil) or unflagged | 1.00 | -112.58 | 0.00 |
| weekend headline (known by Sunday 17:00) | 3.00 | -270.35 | 0.00 |

Driver kinds (keyword classification of the catalogue's `asia_driver`, overlapping):

| driver_kind | n |
|---|---|
| Asia-origin | 25 |
| headline | 17 |
| US macro/rates | 13 |
| after-hours print | 9 |
| not in catalogue (after-hours proxy only) | 2 |

Catalogue tags on the catalyst-cluster nights:

| tags | n |
|---|---|
| ai_capex | 16 |
| earnings_semis | 16 |
| continuation | 13 |
| geopolitics | 12 |
| oil | 10 |
| reversal | 9 |
| positioning_unwind | 8 |
| earnings_megacap | 6 |
| rates_yields | 6 |
| fed | 6 |
| yen_carry | 6 |
| fomc | 5 |
| holiday_thin | 4 |
| china_policy | 3 |
| nfp | 3 |
| boj | 3 |
| technical_level | 2 |
| fiscal | 2 |
| cpi | 2 |
| no_news | 2 |
| flows_rebalance | 2 |
| dollar | 1 |
| tariffs | 1 |
| bank_stress | 1 |
| opex | 1 |
| crypto | 1 |
| election | 1 |

### 1b-ii. Scratch nights: what happened after 03:00 (first touch of target vs stop over Europe + next RTH)

|  | n | engine_pts | hold_pts |
|---|---|---|---|
| ('A', 'none') | 1.00 | -21.74 | -9.75 |
| ('A', 'stop') | 12.00 | -1009.35 | -1830.66 |
| ('A', 'target') | 8.00 | -30.10 | 696.37 |
| ('B', 'none') | 1.00 | 52.79 | -99.83 |
| ('B', 'stop') | 18.00 | -709.38 | -1992.48 |
| ('B', 'target') | 7.00 | 325.66 | 768.40 |
| ('C', 'stop') | 10.00 | -17.26 | -1162.20 |
| ('C', 'target') | 8.00 | 468.54 | 1038.22 |

### a) geometry: stop < 1/3 of realised range or target beyond realised range — n=12, -573 pts

| date | grade | confidence | call | variant | best | pnl_pts | res | decided_bar | stop_dist | target_dist | asia_rng_pts | stop_vs_realised | whipsaw | hold_res | kospi_next | n225_next | vix | rv_ratio | trail20_wr | sunday_open | driver_kind | primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-14 | A | 79 | CONTINUATION | tight | stop_level | -136.26 | scratch |  | 212.41 | 192.30 | 186.75 | 1.14 |  | stop | -0.01 | -0.00 | 17.10 | 0.92 | 0.65 | 0 |  | a) |
| 2025-05-23 | B | 66 | MEAN REVERSION | wide | r500 | -97.88 | stop | 0.00 | 97.88 | 63.12 | 308.25 | 0.32 |  | stop | 0.02 | 0.01 | 22.29 | 0.69 | 0.56 | 1 |  | a) |
| 2025-08-22 | B | 64 | CONTINUATION | tight | stop_level | -79.64 | scratch |  | 59.08 | 124.70 | 88.50 | 0.67 |  | stop | 0.01 | 0.00 | 14.22 | 1.04 | 0.50 | 1 |  | a) |
| 2025-05-28 | B | 68 | CONTINUATION | tight | stop_level | -74.78 | stop | 0.00 | 74.78 | 52.60 | 344.50 | 0.22 |  | stop | 0.02 | 0.02 | 19.31 | 1.19 | 0.56 | 0 |  | a) |
| 2025-04-24 | C | 61 | MEAN REVERSION | wide | r382 | -56.83 | scratch |  | 154.20 | 206.51 | 145.25 | 1.06 |  | stop | 0.01 | 0.02 | 26.47 | 0.65 |  | 0 |  | a) |
| 2025-07-15 | C | 59 | MEAN REVERSION | wide | r382 | -47.00 | scratch |  | 86.40 | 102.70 | 79.00 | 1.09 |  | stop | -0.01 | -0.00 | 17.38 | 0.48 | 0.45 | 0 |  | a) |
| 2025-08-28 | B | 64 | CONTINUATION | tight | stop_level | -43.50 | scratch |  | 59.34 | 64.88 | 48.25 | 1.23 |  | stop | -0.00 | -0.00 | 14.43 | 0.73 | 0.50 | 0 |  | a) |
| 2025-09-30 | B | 68 | CONTINUATION | tight | stop_level | -24.91 | stop | 2.00 | 24.91 | 94.65 | 243.50 | 0.10 |  | stop | 0.01 | -0.01 | 16.28 | 0.98 | 0.55 | 0 |  | a) |
| 2025-09-29 | B | 72 | MEAN REVERSION | tight | vwap | -5.50 | scratch |  | 50.25 | 62.03 | 51.00 | 0.99 |  | stop | -0.00 | -0.00 | 16.12 | 0.98 | 0.55 | 0 |  | a) |
| 2025-06-03 | C | 63 | MEAN REVERSION | wide | r500 | -2.75 | scratch |  | 88.12 | 68.38 | 60.00 | 1.47 |  | stop | 0.03 | 0.01 | 17.69 | 0.44 | 0.55 | 0 |  | a) |
| 2026-04-14 | C | 59 | MEAN REVERSION | wide | r500 | -2.25 | scratch |  | 115.88 | 151.62 | 92.00 | 1.26 |  | stop | 0.02 | 0.00 | 18.36 | 0.64 | 0.55 | 0 |  | a) |
| 2025-08-26 | A | 72 | CONTINUATION | wide | stop_level | -1.75 | scratch |  | 85.17 | 62.78 | 37.25 | 2.29 |  | stop | 0.00 | 0.00 | 14.62 | 0.85 | 0.50 | 0 |  | a) |

### a) geometry: stopped, then the target was reached (Asia whipsaw or Europe target-first) — n=5, -667 pts

| date | grade | confidence | call | variant | best | pnl_pts | res | decided_bar | stop_dist | target_dist | asia_rng_pts | stop_vs_realised | whipsaw | hold_res | kospi_next | n225_next | vix | rv_ratio | trail20_wr | sunday_open | driver_kind | primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-04-10 | B | 70 | MEAN REVERSION | wide | r500 | -294.97 | stop | 2.00 | 294.97 | 150.75 | 727.75 | 0.41 | yes | target | -0.01 | -0.03 | 40.72 | 1.96 |  | 0 |  | a) |
| 2026-02-06 | C | 62 | MEAN REVERSION | wide | r500 | -150.75 | stop | 0.00 | 150.75 | 135.25 | 225.75 | 0.67 |  | target | 0.04 | 0.04 | 20.37 | 1.66 | 0.45 | 1 |  | a) |
| 2026-02-10 | A | 79 | CONTINUATION | tight | stop_level | -78.23 | stop | 4.00 | 78.23 | 83.90 | 92.75 | 0.84 |  | target | 0.01 | -0.00 | 17.79 | 1.57 | 0.40 | 0 |  | a) |
| 2025-10-13 | B | 69 | MEAN REVERSION | wide | r500 | -72.15 | stop | 2.00 | 72.15 | 50.38 | 393.75 | 0.18 | yes | target | -0.01 | -0.03 | 19.03 | 1.93 | 0.50 | 0 |  | a) |
| 2026-08-18 | B | 63 | MEAN REVERSION | tight | r500 | -71.08 | stop | 2.00 | 71.08 | 90.38 | 179.00 | 0.40 |  | target | -0.06 | -0.03 | 15.84 | 0.72 | 0.60 | 0 |  | a) |

### b) regime: VIX>25 / vix_z>1.5 / rv_ratio>1.5 / trailing form <45% — n=11, -1000 pts

| date | grade | confidence | call | variant | best | pnl_pts | res | decided_bar | stop_dist | target_dist | asia_rng_pts | stop_vs_realised | whipsaw | hold_res | kospi_next | n225_next | vix | rv_ratio | trail20_wr | sunday_open | driver_kind | primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-04-22 | A | 95 | MEAN REVERSION | tight | r500 | -196.08 | stop | 0.00 | 196.08 | 100.25 | 179.00 | 1.10 |  | stop | 0.02 | 0.02 | 30.57 | 0.66 |  | 0 |  | b) |
| 2025-10-16 | B | 71 | MEAN REVERSION | wide | vwap | -160.80 | stop | 7.00 | 160.80 | 141.24 | 288.50 | 0.56 |  | stop | 0.00 | -0.01 | 25.31 | 1.90 | 0.50 | 0 |  | b) |
| 2025-11-13 | C | 59 | MEAN REVERSION | wide | r500 | -152.10 | stop | 8.00 | 152.10 | 211.50 | 227.25 | 0.67 |  | stop | -0.04 | -0.02 | 20.00 | 1.25 | 0.60 | 0 |  | b) |
| 2026-01-15 | A | 86 | CONTINUATION | tight | stop_level | -103.95 | scratch |  | 137.90 | 58.12 | 133.75 | 1.03 |  | stop | 0.01 | -0.00 | 15.84 | 0.89 | 0.40 | 0 |  | b) |
| 2026-03-19 | B | 72 | CONTINUATION | tight | stop_level | -103.68 | scratch |  | 122.42 | 110.97 | 142.00 | 0.86 |  | stop | 0.00 | -0.03 | 24.06 | 1.17 | 0.40 | 0 |  | b) |
| 2025-11-10 | A | 72 | CONTINUATION | tight | stop_level | -70.25 | scratch |  | 112.37 | 70.60 | 122.75 | 0.92 |  | stop | 0.01 | -0.00 | 17.60 | 1.56 | 0.60 | 0 |  | b) |
| 2026-02-17 | B | 70 | MEAN REVERSION | tight | vwap | -60.99 | scratch |  | 165.55 | 85.80 | 146.25 | 1.13 |  | stop | 0.03 | 0.01 | 20.29 | 0.68 | 0.40 | 0 |  | b) |
| 2025-11-24 | A | 86 | CONTINUATION | tight | stop_level | -51.99 | scratch |  | 140.74 | 80.58 | 105.75 | 1.33 |  | stop | 0.00 | 0.00 | 20.52 | 1.58 | 0.50 | 0 |  | b) |
| 2025-07-29 | B | 68 | CONTINUATION | tight | stop_level | -47.25 | scratch |  | 61.75 | 53.60 | 61.25 | 1.01 |  | stop | 0.01 | -0.00 | 15.98 | 0.74 | 0.40 | 0 |  | b) |
| 2026-01-13 | A | 94 | MEAN REVERSION | tight | r500 | -38.00 | scratch |  | 118.95 | 38.75 | 90.25 | 1.32 |  | stop | 0.01 | 0.01 | 15.98 | 0.56 | 0.40 | 0 |  | b) |
| 2026-02-09 | B | 64 | CONTINUATION | tight | stop_level | -14.50 | scratch |  | 87.07 | 114.58 | 117.00 | 0.74 |  | stop | 0.00 | 0.02 | 17.36 | 1.72 | 0.40 | 0 |  | b) |

### c) catalyst (catalogue driver / after-hours print) — n=29, -4246 pts

| date | grade | confidence | call | variant | best | pnl_pts | res | decided_bar | stop_dist | target_dist | asia_rng_pts | stop_vs_realised | whipsaw | hold_res | kospi_next | n225_next | vix | rv_ratio | trail20_wr | sunday_open | driver_kind | primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-05 | B | 66 | CONTINUATION | wide | stop_level | -339.79 | scratch |  | 577.56 | 477.15 | 792.75 | 0.73 |  | stop | -0.06 | -0.06 | 28.18 | 1.57 | 0.85 | 0 | Asia-origin+headline+US macro/rates | c) |
| 2026-06-10 | A | 72 | CONTINUATION | wide | stop_level | -337.20 | scratch |  | 348.65 | 227.10 | 537.25 | 0.65 |  | stop | 0.00 | 0.00 | 22.22 | 1.56 | 0.60 | 0 | Asia-origin+headline | c) |
| 2026-06-25 | B | 70 | MEAN REVERSION | wide | r382 | -275.70 | stop | 3.00 | 275.70 | 163.24 | 732.25 | 0.38 |  | stop | -0.06 | -0.04 | 18.89 | 0.91 | 0.55 | 0 | Asia-origin+headline+US macro/rates | c) |
| 2026-06-16 | A | 81 | CONTINUATION | wide | stop_level | -237.95 | scratch |  | 261.52 | 176.03 | 239.25 | 1.09 |  | stop | 0.02 | 0.01 | 16.41 | 1.50 | 0.65 | 0 | Asia-origin+headline+US macro/rates | c) |
| 2026-07-27 | C | 58 | MEAN REVERSION | wide | r500 | -228.30 | stop | 3.00 | 228.30 | 231.75 | 388.50 | 0.59 |  | stop | -0.11 | -0.04 | 18.67 | 1.00 | 0.50 | 0 | after-hours print+Asia-origin+headline | c) |
| 2025-11-14 | C | 59 | MEAN REVERSION | wide | r500 | -200.17 | stop | 8.00 | 200.17 | 182.50 | 271.25 | 0.74 |  | stop | 0.02 | -0.00 | 19.83 | 1.25 | 0.55 | 1 | Asia-origin | c) |
| 2026-01-29 | B | 69 | MEAN REVERSION | wide | r500 | -198.22 | stop | 3.00 | 198.22 | 111.00 | 320.00 | 0.62 |  | stop | 0.00 | -0.00 | 16.88 | 0.88 | 0.45 | 0 | after-hours print+Asia-origin+headline+US macro/rates | c) |
| 2026-07-30 | C | 63 | MEAN REVERSION | wide | r382 | -181.65 | stop | 2.00 | 181.65 | 264.93 | 311.75 | 0.58 |  | stop | 0.18 | 0.04 | 17.09 | 1.42 | 0.45 | 0 | Asia-origin+US macro/rates | c) |
| 2026-07-02 | C | 58 | CONTINUATION | tight | stop_level | -179.08 | stop | 4.00 | 179.08 | 319.75 | 253.25 | 0.71 |  |  | 0.06 | 0.01 | 16.15 | 0.89 | 0.55 | 0 | Asia-origin+headline | c) |
| 2025-11-17 | B | 68 | MEAN REVERSION | wide | vwap | -156.67 | stop | 5.00 | 156.67 | 105.91 | 355.75 | 0.44 |  | stop | -0.03 | -0.03 | 22.38 | 0.74 | 0.55 | 0 | Asia-origin+US macro/rates | c) |
| 2026-05-20 | B | 70 | CONTINUATION | wide | stop_level | -155.51 | stop | 0.00 | 155.51 | 118.50 | 326.75 | 0.48 |  | stop | 0.08 | 0.03 | 17.44 | 1.11 | 0.65 | 0 | after-hours print | c) |
| 2025-11-19 | A | 73 | MEAN REVERSION | wide | r382 | -144.30 | stop | 0.00 | 144.30 | 256.92 | 253.75 | 0.57 |  | stop | 0.02 | 0.03 | 23.66 | 0.93 | 0.55 | 0 | after-hours print+Asia-origin | c) |
| 2026-10-29 | A | 73 | MEAN REVERSION | wide | vwap | -134.47 | stop | 0.00 | 134.47 | 327.65 | 358.50 | 0.38 |  | stop | -0.03 | -0.02 | 17.20 | 0.64 | 0.85 | 0 | Asia-origin+headline | c) |
| 2026-08-17 | A | 75 | MEAN REVERSION | wide | r382 | -131.62 | stop | 4.00 | 131.62 | 54.94 | 335.25 | 0.39 |  | stop | -0.02 | -0.03 | 15.19 | 0.48 | 0.60 | 0 | Asia-origin+headline+US macro/rates | c) |
| 2026-10-12 | B | 69 | MEAN REVERSION | wide | r382 | -125.10 | stop | 2.00 | 125.10 | 85.37 | 301.25 | 0.42 |  | stop | -0.05 | -0.02 | 15.21 | 0.76 | 0.70 | 0 | Asia-origin+headline | c) |
| 2026-06-18 | A | 79 | CONTINUATION | tight | stop_level | -117.38 | stop | 3.00 | 117.38 | 95.97 | 265.25 | 0.44 |  |  | -0.00 | 0.00 | 16.40 | 1.21 | 0.60 | 0 | Asia-origin | c) |
| 2025-12-10 | A | 79 | CONTINUATION | tight | stop_level | -113.99 | stop | 1.00 | 113.99 | 104.45 | 413.00 | 0.28 |  | stop | -0.01 | -0.01 | 15.77 | 0.26 | 0.55 | 0 | after-hours print+Asia-origin+US macro/rates | c) |
| 2026-08-28 | B | 69 | MEAN REVERSION | wide | vwap | -112.58 | stop | 1.00 | 112.58 | 83.58 | 255.00 | 0.44 |  | stop | 0.00 | -0.00 | 14.43 | 0.67 | 0.65 | 1 |  | c) |
| 2026-08-26 | B | 65 | MEAN REVERSION | wide | vwap | -112.42 | stop | 0.00 | 112.42 | 168.81 | 253.00 | 0.44 |  | stop | 0.02 | -0.00 | 15.21 | 0.51 | 0.65 | 0 | Asia-origin | c) |
| 2026-01-09 | B | 72 | CONTINUATION | tight | stop_level | -100.99 | stop | 1.00 | 100.99 | 84.25 | 243.25 | 0.42 |  | stop | 0.01 | 0.03 | 14.49 | 0.72 | 0.40 | 1 | Asia-origin+headline+US macro/rates | c) |
| 2026-07-10 | B | 68 | CONTINUATION | tight | stop_level | -100.70 | stop | 0.00 | 100.70 | 85.78 | 498.25 | 0.20 |  | stop | -0.09 | -0.02 | 15.03 | 0.73 | 0.50 | 1 | Asia-origin+headline+US macro/rates | c) |
| 2026-03-03 | B | 64 | CONTINUATION | tight | stop_level | -95.01 | stop | 3.00 | 95.01 | 190.05 | 304.50 | 0.31 |  | stop | -0.12 | -0.04 | 23.57 | 0.85 | 0.35 | 0 | Asia-origin+headline+US macro/rates | c) |
| 2025-04-30 | C | 59 | MEAN REVERSION | wide | r382 | -88.06 | scratch |  | 183.60 | 342.37 | 169.00 | 1.09 |  | stop | 0.00 | 0.01 | 24.70 | 0.29 | 0.60 | 0 |  | c) |
| 2026-03-26 | A | 79 | CONTINUATION | tight | stop_level | -81.24 | scratch |  | 193.69 | 93.75 | 170.00 | 1.14 |  | target | -0.00 | -0.00 | 27.44 | 1.13 | 0.45 | 0 | Asia-origin+headline | c) |
| 2025-11-03 | B | 70 | MEAN REVERSION | wide | r500 | -75.15 | stop | 1.00 | 75.15 | 40.75 | 369.00 | 0.20 |  | stop | -0.02 | -0.02 | 17.17 | 0.67 | 0.55 | 0 | after-hours print+Asia-origin | c) |
| 2026-01-27 | B | 66 | MEAN REVERSION | wide | r382 | -72.22 | stop | 1.00 | 72.22 | 66.97 | 237.75 | 0.30 |  | stop | 0.02 | 0.00 | 16.35 | 0.41 | 0.45 | 0 | after-hours print+Asia-origin+headline+US macro/rates | c) |
| 2026-02-27 | B | 68 | CONTINUATION | tight | stop_level | -68.66 | stop | 0.00 | 68.66 | 57.47 | 373.25 | 0.18 |  | stop | -0.07 | -0.01 | 19.86 | 0.98 | 0.40 | 1 | Asia-origin+headline+US macro/rates | c) |
| 2026-04-02 | A | 93 | CONTINUATION | tight | stop_level | -51.50 | scratch |  | 144.92 | 106.12 | 104.50 | 1.39 |  |  | 0.03 | 0.01 | 23.87 | 1.40 | 0.50 | 0 | after-hours print+headline | c) |
| 2026-06-03 | A | 75 | MEAN REVERSION | tight | r382 | -30.17 | stop | 0.00 | 30.17 | 171.69 | 182.50 | 0.17 |  | stop | -0.02 | -0.01 | 16.06 | 0.42 | 0.65 | 0 | after-hours print+Asia-origin | c) |

Catalogue drivers for these nights (truncated):

- **2026-11-05** (B, continuation, -340 pts, tags `election;ai_capex;earnings_semis;positioning_unwind;fed;geopolitics;oil;yen_carry;reversal`): NQ futures -0.4% at 18:00 ET; Kospi opened -8.52% to 4,924.61 at 09:03 KST (19:03 ET), sidecar + 20-min circuit breaker (11th level-1 halt this year), closed -6% at 5,059.69 (-11.7% wk); Nikkei -7% early, low 56,745.81 (>20% off June peak = bear market), close
- **2026-06-10** (A, continuation, -337 pts, tags `cpi;geopolitics;oil;reversal`): NQ Asia +1.18%: 18:00 ET NQ -0.6%, then Trump posted he had 'cancelled the scheduled strikes and bombings against Iran this evening' and said a deal would be signed soon - sharp V reversal; Nikkei opened -2.3% closed flat, Kospi -4.1% early closed +0.43%; oil 
- **2026-06-25** (B, mean reversion, -276 pts, tags `ai_capex;earnings_megacap;positioning_unwind;flows_rebalance;continuation`): NQ Asia -0.80%: OpenAI-IPO-delay report hit AI complex in Asia - SoftBank -11% to -13% intraday, Kospi -5.81% close (intraday -8%, 20-min circuit breaker, 2nd this week; Samsung -7.4%, SK Hynix -8.7%, reports of big Samsung/Hynix capex increases), Nikkei -4.15
- **2026-06-16** (A, continuation, -238 pts, tags `fomc;boj;oil;geopolitics;reversal`): NQ Asia +0.79%: pre-FOMC calm; Nikkei +0.72% to record 69,902 (eyeing 70k), Kospi +1.58%; crude plunged to 3-month low on US-Iran MoU progress (Trump: 'not final'); SOXQ +2.4% premarket as chips bounced; USD/JPY ~160.5 near intervention zone.
- **2026-07-27** (C, mean reversion, -228 pts, tags `china_policy;earnings_semis;ai_capex;positioning_unwind;fomc;continuation`): NQ Asia -0.93%: Korea memory crash on China-competition fears (DUV report, CXMT) plus AI-financing/valuation worries - Kospi -10.84% (sidecar then circuit breaker), Samsung -13.4% (worst day in ~20 yrs), SK Hynix -14.7%; Nikkei -3.95% (Advantest -10%, SoftBank
- **2025-11-14** (C, mean reversion, -200 pts, tags `earnings_semis;ai_capex;geopolitics;china_policy;continuation`): Sunday-open session (Nov 16 18:00 to Nov 17 03:00 ET): Nasdaq-100 futures +0.7% and S&P +0.4% through Asia; Kospi +1.9% on SK Hynix +8.2%/Samsung +3.5% (Nvidia AI collaboration plans); Nikkei -0.1% after Japan Q3 GDP -1.8% annualised; China warned citizens ove
- **2026-01-29** (B, mean reversion, -198 pts, tags `earnings_megacap;ai_capex;fed;tariffs;continuation`): Jan 30 Asia/Europe hours: Nasdaq-100 futures down ~1% by 03:30-05:25 ET: reports that Kevin Warsh (seen as hawkish) was the lead Fed-chair pick with an announcement due Friday; Trump threatened a 50% tariff on Canadian aircraft (Bombardier) on top of the 100% 
- **2026-07-30** (C, mean reversion, -182 pts, tags `earnings_megacap;boj;yen_carry;positioning_unwind;reversal`): Overnight Jul 30/31: NQ futures up on Amazon; BoJ held 1.00% (8-1, Takata for 1.25%) with upside inflation warning; MoF appeared to intervene (USD/JPY ~158, -3.3% wk); Kospi +17.9% best day on record, Nikkei +4%, Taiex +8%; Jul 31 RTH Nasdaq +1% despite 30y ~5
- **2026-07-02** (C, continuation, -179 pts, tags `nfp;earnings_semis;positioning_unwind;holiday_thin;geopolitics;reversal`): NQ Asia +0.68% (Thu-night/Fri Jul 3 session): Asia rebound - Kospi +5.76% (SK Hynix +10%, Samsung +8% on report Anthropic in talks for custom AI chips; sidecar halt), Nikkei +1.47% (Kioxia -12% then +7%); Trump: Iran 'agreed to just about everything we need', 
- **2025-11-17** (B, mean reversion, -157 pts, tags `ai_capex;earnings_semis;technical_level;rates_yields;fiscal;continuation`): Nov 18 Asia rout: Nikkei -3% to 48,835 (Tokyo Electron -5.4%, Advantest -4.6%), Kospi -3.1% to 3,961 (SK Hynix -5.7%), Taiex -2.3% (TSMC -2.4%), ASX -2.1%, Hang Seng -1.5%; AI-valuation fear ahead of NVDA plus 30y JGB at 3.31% on Takaichi spending plans; Nasda
- **2026-05-20** (B, continuation, -156 pts, tags `earnings_semis;ai_capex`): Overnight catalyst = NVDA print; after-hours reaction mixed/slightly negative per Kiplinger live blog (stock closed lower next day ~-1.8%); magnitude for NQ not verified.
- **2025-11-19** (A, mean reversion, -144 pts, tags `earnings_semis;ai_capex;fomc;continuation`): NVDA beat and raised (described as blowout; Q4 guide ~$65B): Nasdaq-100 futures +1.7% and S&P +1.2% by 21:16 ET; Nikkei +3.2% early (as much as +4.2%), Kospi and Taiex up, Hong Kong lagged; gains faded into the US open and fully reversed in RTH Nov 20 (Nasdaq 
- **2026-10-29** (A, mean reversion, -134 pts, tags `boj;yen_carry;earnings_megacap;ai_capex;crypto;flows_rebalance;continuation`): BoJ held 1.25% (8-1, Takata for 1.50%), said inflation 'generally consistent' with 2% (first since 2013), ETF sales accelerated; yen to 157.15 then pared; Katayama 'ready to act'; Nikkei -2.12% to 63,290, Kospi -3.48%, CSI300 -1.39%; SoftBank/TEL/SK Hynix down
- **2026-08-17** (A, mean reversion, -132 pts, tags `geopolitics;oil;rates_yields;yen_carry;continuation`): Overnight: Trump Truth Social 'no talks' with Iran, blockade in force; Brent >$91; 30y 5.32% (19-yr high); JGB 10y 3-decade high; yen ~159. Asia Aug 18: Nikkei -2.54% to 67,460, Kospi -1.55%, Kosdaq -3.5%; US memory names weak next day (WDC -7%, SNDK -9%). NQ 
- **2026-10-12** (B, mean reversion, -125 pts, tags `earnings_semis;ai_capex;china_policy;oil;geopolitics;holiday_thin;continuation`): Kospi sidecar at 20:53 ET (Kospi 200 futures -5%); Kospi -5.46% to lowest since Jul 31, Nikkei -1.82% to 67,777; SoftBank -6.7%, Kioxia -8.8%, Advantest -6.1%, SK Hynix -6.5%, Samsung -5.6% on AI-spend fears + CXMT competition; Brent >$106; NQ -0.63% (range 0.
- **2026-06-18** (A, continuation, -117 pts, tags `opex;holiday_thin;no_news`): NQ Asia -0.76%: unverified - no dated Asia wrap found for Fri Jun 19. Inferred from Jun 22 reports: Nikkei ~71,250 (+0.3%) and Kospi ~9,052 (-0.1%) on Jun 19, i.e. Asia cash flat; NQ drift lower most consistent with thin Juneteenth-eve/post-expiry positioning 
- **2025-12-10** (A, continuation, -114 pts, tags `fomc;fed;earnings_megacap;ai_capex;reversal`): Oracle FQ2 after the close: revenue miss, spending guide raised by $15B, RPO strong; ORCL -11% after hours. Reuters: Nasdaq-100 futures -1.3% and S&P -0.9% in Asia trade; Nikkei -0.9% to 50,149 (SoftBank, a Stargate partner, sold off), Taiwan -1.3%, Hang Seng 
- **2026-08-28** (B, mean reversion, -113 pts, tags `fed;rates_yields;no_news`): unverified (Friday).
- **2026-08-26** (B, mean reversion, -112 pts, tags `earnings_semis;ai_capex;continuation`): NQ futures +0.8% at Wed evening; Asia Aug 27: Kospi +1.53%, Nikkei -0.20%, BoK hiked 25bp to 3.00%; Kioxia +4%; NVDA +6% premarket, +8.7% close Aug 27 (SMH +3%).
- **2026-01-09** (B, continuation, -101 pts, tags `nfp;fed;yen_carry;fiscal;reversal`): Sunday-open session (Jan 11 18:00 to Jan 12 03:00 ET): Powell's Sunday video statement disclosed a DOJ criminal probe / indictment threat over his renovation testimony (Fed-independence shock); Nasdaq-100 E-mini -202 pts and S&P -34 at the open, reversing Frid
- **2026-07-10** (B, continuation, -101 pts, tags `geopolitics;oil;earnings_semis;positioning_unwind;rates_yields;reversal`): NQ Asia -0.88% (Sunday-night session Jul 12/13): weekend US-Iran exchange of strikes (CENTCOM hit 140 targets after Iran attacked a commercial vessel), Iran declared Hormuz closed (Trump disputed); Brent/WTI +4.1% by 23:30 ET; NQ -0.3% at 18:00; SK Hynix -15% 
- **2026-03-03** (B, continuation, -95 pts, tags `geopolitics;oil;earnings_semis;positioning_unwind;fed`): Futures -0.3% (NQ) at 18:06 ET; Kospi crashed >12% intraday Wed Mar 4 (circuit breakers; Kosdaq -13%; Samsung -7%, SK Hynix -5%) after EWY -14% Tuesday; Gulf bourses reopened -3 to -5%. Mar 4 RTH then rallied (Nasdaq +1.29%) as oil stalled, ADP 63k, ISM servic
- **2025-04-30** (C, mean reversion, -88 pts): not in catalogue; after-hours proxy post_ret=+105 bp, megacap_earnings_tonight=0, events `nan` / `nan`
- **2026-03-26** (A, continuation, -81 pts, tags `geopolitics;oil;earnings_semis;rates_yields;technical_level;continuation`): Asia had closed lower Thursday (Kospi -3%, HSI -1.9%, Nikkei -0.27%). No distinct overnight headline found for Mar 26 evening in sources retrieved (Mar 27 RTH then sold off further).
- **2025-11-03** (B, mean reversion, -75 pts, tags `ai_capex;positioning_unwind;earnings_megacap;earnings_semis;continuation`): Risk-off into Nov 4 Tokyo/HK hours: Palantir -7% to -8% after hours despite beat/raise (valuation), Michael Burry 13F puts on NVDA/PLTR disclosed, Wall St CEOs (Solomon/Pick/Gitlin) at HKMA summit (Tue HK morning = Mon evening ET) called 10-20% drawdowns norma
- **2026-01-27** (B, mean reversion, -72 pts, tags `earnings_semis;ai_capex;dollar;fomc;continuation`): Jan 28 Asia/Europe hours: Nasdaq-100 futures +0.9% by 04:44 ET as ASML (reported ~01:00 ET) posted record EUR13.2B bookings and a EUR12B buyback (shares +7%); Kospi +1.8%, Hang Seng +2.6%, Nikkei flat; DXY 96.0 near a 4-year low (Trump: weaker dollar is great)
- **2026-02-27** (B, continuation, -69 pts, tags `geopolitics;oil;earnings_semis;ai_capex;bank_stress;cpi;yen_carry;rates_yields`): [Sunday Mar 1 18:00 ET to Mon Mar 2 03:00 ET] US-Israeli strikes on Iran began Feb 28 ('Operation Epic Fury'), killing Supreme Leader Khamenei; Iran retaliated on Israel/Gulf/US bases and IRGC warned ships not to transit Hormuz (traffic -70%). NQ futures -1.5%
- **2026-04-02** (A, continuation, -51 pts, tags `holiday_thin;nfp;geopolitics;oil;reversal`): [Sunday Apr 5 18:00 ET; prior overnight session Thu Apr 2 was pre-holiday] Trump 18:09 ET post: 'Tuesday will be Power Plant Day, and Bridge Day' - strike power plants/bridges unless Hormuz open by 20:00 ET Tue Apr 7; crude rose; futures opened NQ -0.7%, ES -0
- **2026-06-03** (A, mean reversion, -30 pts, tags `earnings_semis;ai_capex`): Overnight catalyst = AVGO -12% to -14% after hours (closed -12.5% Jun 4, Micron -8%); start of the June AI/semis de-rating. Nikkei hit record Jun 3 on AI boom before the print.

### d) calibration: mid-band confidence only — n=13, -860 pts

| date | grade | confidence | call | variant | best | pnl_pts | res | decided_bar | stop_dist | target_dist | asia_rng_pts | stop_vs_realised | whipsaw | hold_res | kospi_next | n225_next | vix | rv_ratio | trail20_wr | sunday_open | driver_kind | primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05-18 | C | 63 | MEAN REVERSION | wide | r382 | -181.28 | stop | 7.00 | 181.28 | 140.98 | 303.50 | 0.60 |  | stop | -0.03 | -0.00 | 17.82 | 0.99 | 0.70 | 0 |  | d) |
| 2026-04-15 | C | 63 | MEAN REVERSION | wide | r382 | -119.55 | stop | 8.00 | 119.55 | 138.68 | 141.00 | 0.85 |  | stop | 0.02 | 0.02 | 18.17 | 0.37 | 0.50 | 0 |  | d) |
| 2026-06-30 | C | 59 | CONTINUATION | tight | stop_level | -87.63 | stop | 4.00 | 87.63 | 159.28 | 189.25 | 0.46 |  | stop | -0.02 | 0.01 | 16.45 | 0.81 | 0.55 | 0 |  | d) |
| 2025-06-11 | B | 69 | MEAN REVERSION | wide | vwap | -84.00 | stop | 2.00 | 84.00 | 61.98 | 140.00 | 0.60 |  | stop | 0.00 | -0.01 | 17.26 | 0.95 | 0.50 | 0 |  | d) |
| 2025-07-14 | B | 66 | MEAN REVERSION | wide | r500 | -84.00 | stop | 3.00 | 84.00 | 70.25 | 177.75 | 0.47 |  | stop | 0.00 | 0.01 | 17.20 | 0.48 | 0.50 | 0 |  | d) |
| 2026-05-05 | C | 63 | MEAN REVERSION | wide | r382 | -77.40 | stop | 0.00 | 77.40 | 133.63 | 179.00 | 0.43 |  | stop | 0.06 | 0.06 | 17.38 | 0.74 | 0.65 | 0 |  | d) |
| 2026-07-09 | C | 58 | CONTINUATION | tight | stop_level | -67.57 | stop | 2.00 | 67.57 | 100.15 | 189.00 | 0.36 |  | stop | 0.03 | 0.01 | 15.84 | 0.85 | 0.55 | 0 |  | d) |
| 2025-06-10 | C | 58 | CONTINUATION | tight | stop_level | -62.49 | stop | 3.00 | 62.49 | 66.15 | 136.75 | 0.46 |  | stop | 0.01 | 0.01 | 16.95 | 0.85 | 0.50 | 0 |  | d) |
| 2025-07-09 | C | 63 | CONTINUATION | tight | stop_level | -43.23 | stop | 3.00 | 43.23 | 87.70 | 88.75 | 0.49 |  | stop | 0.02 | -0.00 | 15.94 | 0.76 | 0.55 | 0 |  | d) |
| 2025-09-24 | B | 70 | MEAN REVERSION | wide | r500 | -18.75 | scratch |  | 81.67 | 63.25 | 74.25 | 1.10 |  | stop | -0.00 | 0.00 | 16.18 | 1.05 | 0.55 | 0 |  | d) |
| 2025-08-11 | B | 70 | CONTINUATION | tight | stop_level | -13.75 | scratch |  | 82.94 | 63.70 | 80.50 | 1.03 |  | stop | -0.01 | 0.02 | 16.25 | 1.07 | 0.50 | 0 |  | d) |
| 2025-08-13 | B | 66 | MEAN REVERSION | wide | r382 | -12.25 | scratch |  | 54.75 | 44.57 | 66.50 | 0.82 |  | stop | 0.00 | -0.01 | 14.49 | 0.71 | 0.45 | 0 |  | d) |
| 2025-06-24 | B | 70 | MEAN REVERSION | tight | vwap | -8.00 | scratch |  | 59.33 | 44.23 | 52.25 | 1.14 |  | stop | 0.00 | 0.00 | 17.48 | 1.14 | 0.50 | 0 |  | d) |

### e) timing: scratch at 03:00, target hit before stop in Europe / next RTH — n=4, -122 pts

| date | grade | confidence | call | variant | best | pnl_pts | res | decided_bar | stop_dist | target_dist | asia_rng_pts | stop_vs_realised | whipsaw | hold_res | kospi_next | n225_next | vix | rv_ratio | trail20_wr | sunday_open | driver_kind | primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-01-08 | A | 91 | MEAN REVERSION | tight | r500 | -52.22 | scratch |  | 167.20 | 29.25 | 99.75 | 1.68 |  | target | 0.01 | 0.02 | 15.45 | 0.72 | 0.45 | 0 |  | e) |
| 2026-04-30 | B | 70 | CONTINUATION | wide | stop_level | -35.21 | scratch |  | 191.49 | 137.62 | 118.25 | 1.62 |  | target | 0.05 | 0.00 | 16.89 | 1.19 | 0.65 | 0 |  | e) |
| 2025-07-17 | B | 68 | MEAN REVERSION | wide | r500 | -22.75 | scratch |  | 80.85 | 63.50 | 64.25 | 1.26 |  | target | -0.00 | -0.00 | 16.52 | 0.59 | 0.45 | 0 |  | e) |
| 2026-09-28 | A | 94 | MEAN REVERSION | tight | r382 | -12.25 | scratch |  | 240.25 | 76.09 | 243.75 | 0.99 |  | target | -0.00 | -0.01 | 16.07 | 0.81 | 0.75 | 0 |  | e) |

### f) calendar: Sunday reopen / holiday / thin session — n=8, -692 pts

| date | grade | confidence | call | variant | best | pnl_pts | res | decided_bar | stop_dist | target_dist | asia_rng_pts | stop_vs_realised | whipsaw | hold_res | kospi_next | n225_next | vix | rv_ratio | trail20_wr | sunday_open | driver_kind | primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-04-11 | B | 66 | MEAN REVERSION | wide | r500 | -181.05 | stop | 0.00 | 181.05 | 169.88 | 318.50 | 0.57 |  | stop | 0.01 | 0.01 | 37.56 | 1.73 |  | 1 |  | f) |
| 2026-07-24 | B | 68 | CONTINUATION | tight | stop_level | -133.53 | stop | 0.00 | 133.53 | 111.58 | 208.75 | 0.64 |  | stop | 0.01 | 0.00 | 18.58 | 0.99 | 0.55 | 1 |  | f) |
| 2025-10-17 | B | 68 | MEAN REVERSION | wide | r382 | -114.97 | stop | 6.00 | 114.97 | 94.23 | 172.00 | 0.67 |  | stop | 0.02 | 0.03 | 20.78 | 0.99 | 0.45 | 1 |  | f) |
| 2026-04-24 | C | 63 | MEAN REVERSION | wide | r500 | -99.67 | stop | 3.00 | 99.67 | 104.62 | 197.50 | 0.50 |  | target | 0.02 | 0.01 | 18.71 | 0.90 | 0.65 | 1 |  | f) |
| 2025-12-05 | B | 70 | MEAN REVERSION | wide | r500 | -66.48 | scratch |  | 107.40 | 62.12 | 121.00 | 0.89 |  | stop | 0.01 | 0.00 | 15.41 | 0.24 | 0.60 | 1 |  | f) |
| 2025-12-23 | A | 88 | CONTINUATION | tight | stop_level | -32.74 | scratch |  | 75.31 | 30.15 | 46.00 | 1.64 |  |  | -0.00 | -0.00 | 14.00 | 1.18 | 0.50 | 0 |  | f) |
| 2025-09-19 | B | 67 | CONTINUATION | tight | stop_level | -31.77 | scratch |  | 85.21 | 58.85 | 60.00 | 1.42 |  | stop | 0.01 | 0.01 | 15.45 | 0.20 | 0.45 | 1 |  | f) |
| 2025-09-12 | C | 63 | MEAN REVERSION | wide | r500 | -31.75 | scratch |  | 57.75 | 39.62 | 58.00 | 1.00 |  | stop | 0.00 | 0.00 | 14.76 | 0.39 | 0.50 | 1 |  | f) |

### g) unexplained — n=5, -235 pts

| date | grade | confidence | call | variant | best | pnl_pts | res | decided_bar | stop_dist | target_dist | asia_rng_pts | stop_vs_realised | whipsaw | hold_res | kospi_next | n225_next | vix | rv_ratio | trail20_wr | sunday_open | driver_kind | primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-05-19 | B | 72 | CONTINUATION | tight | stop_level | -88.30 | stop | 5.00 | 88.30 | 66.62 | 168.50 | 0.52 |  | stop | -0.00 | 0.00 | 18.14 | 0.45 | 0.57 | 0 |  | g) |
| 2026-01-06 | A | 86 | CONTINUATION | tight | stop_level | -64.75 | scratch |  | 100.08 | 31.03 | 80.00 | 1.25 |  | stop | 0.01 | -0.01 | 14.75 | 0.84 | 0.50 | 0 |  | g) |
| 2025-05-14 | B | 72 | CONTINUATION | tight | stop_level | -45.61 | stop | 7.00 | 45.61 | 34.33 | 94.75 | 0.48 |  | stop | -0.01 | -0.01 | 18.62 | 0.91 | 0.62 | 0 |  | g) |
| 2025-12-08 | A | 92 | MEAN REVERSION | tight | r500 | -21.74 | scratch |  | 171.60 | 32.88 | 82.75 | 2.07 |  | none | -0.00 | 0.00 | 16.66 | 0.31 | 0.60 | 0 |  | g) |
| 2025-10-08 | A | 81 | CONTINUATION | wide | stop_level | -14.25 | scratch |  | 123.07 | 86.85 | 87.00 | 1.41 |  | stop | 0.02 | 0.02 | 16.30 | 1.33 | 0.50 | 0 |  | g) |

### 1c. Quarter concentration

| quarter | n | win | pts | A_n | A_win | A_pts | losses | loss_pts |
|---|---|---|---|---|---|---|---|---|
| 2025Q2 | 26.00 | 0.50 | -359.16 | 6.00 | 0.83 | 104.08 | 13.00 | -1280.80 |
| 2025Q3 | 29.00 | 0.48 | 178.78 | 11.00 | 0.91 | 562.84 | 15.00 | -507.80 |
| 2025Q4 | 32.00 | 0.53 | -248.47 | 12.00 | 0.42 | -84.69 | 15.00 | -1447.77 |
| 2026Q1 | 27.00 | 0.44 | 5.50 | 11.00 | 0.45 | 155.05 | 15.00 | -1283.41 |
| 2026Q2 | 31.00 | 0.55 | -482.50 | 18.00 | 0.72 | 43.25 | 14.00 | -1808.41 |
| 2026Q3 | 34.00 | 0.65 | 463.64 | 14.00 | 0.79 | 596.87 | 12.00 | -1467.04 |
| 2026Q4 | 17.00 | 0.82 | 759.75 | 6.00 | 0.83 | 284.63 | 3.00 | -599.36 |

Primary cluster by quarter (n):

| primary | 2025Q2 | 2025Q3 | 2025Q4 | 2026Q1 | 2026Q2 | 2026Q3 | 2026Q4 |
|---|---|---|---|---|---|---|---|
| a) | 5 | 6 | 1 | 2 | 1 | 2 | 0 |
| b) | 1 | 1 | 4 | 5 | 0 | 0 | 0 |
| c) | 1 | 0 | 5 | 6 | 7 | 7 | 3 |
| d) | 3 | 5 | 0 | 0 | 4 | 1 | 0 |
| e) | 0 | 1 | 0 | 1 | 1 | 1 | 0 |
| f) | 1 | 2 | 3 | 0 | 1 | 1 | 0 |
| g) | 2 | 0 | 2 | 1 | 0 | 0 | 0 |

Primary cluster by quarter (pts):

| primary | 2025Q2 | 2025Q3 | 2025Q4 | 2026Q1 | 2026Q2 | 2026Q3 | 2026Q4 |
|---|---|---|---|---|---|---|---|
| a) | -527 | -202 | -72 | -229 | -2 | -207 |  |
| b) | -196 | -47 | -435 | -321 |  |  |  |
| c) | -88 |  | -690 | -616 | -1205 | -1046 | -599 |
| d) | -154 | -172 |  |  | -466 | -68 |  |
| e) |  | -23 |  | -52 | -35 | -12 |  |
| f) | -181 | -64 | -214 |  | -100 | -134 |  |
| g) | -134 |  | -36 | -65 |  |  |  |

Note: the catalogue starts 2025-11-03, so the 28 losses of 2025Q2-Q3 cannot fall into cluster c); their geometry / calibration / unexplained labels are upper bounds.

### 1e. Geometry vs the EX-ANTE expected range (target or stop distance / 20d median Asia range known at 18:00), all graded nights

| target/expected range | grade | n | win | avg | pts |
|---|---|---|---|---|
| (0.0, 0.3] | A | 18.00 | 0.72 | 18.00 | 324.00 |
| (0.0, 0.3] | B | 5.00 | 0.40 | -8.61 | -43.07 |
| (0.3, 0.5] | A | 26.00 | 0.73 | 25.65 | 666.84 |
| (0.3, 0.5] | B | 26.00 | 0.50 | 5.69 | 147.81 |
| (0.3, 0.5] | C | 6.00 | 0.33 | 6.16 | 36.99 |
| (0.5, 0.7] | A | 19.00 | 0.74 | 54.05 | 1026.98 |
| (0.5, 0.7] | B | 18.00 | 0.33 | -36.37 | -654.69 |
| (0.5, 0.7] | C | 9.00 | 0.56 | 5.26 | 47.38 |
| (0.7, 1.0] | A | 9.00 | 0.67 | -11.06 | -99.58 |
| (0.7, 1.0] | B | 19.00 | 0.63 | 37.44 | 711.41 |
| (0.7, 1.0] | C | 16.00 | 0.50 | -14.79 | -236.60 |
| (1.0, 10.0] | A | 6.00 | 0.33 | -42.70 | -256.21 |
| (1.0, 10.0] | B | 11.00 | 0.27 | -86.20 | -948.16 |
| (1.0, 10.0] | C | 8.00 | 0.50 | -50.69 | -405.54 |

| stop/expected range | grade | n | win | avg | pts |
|---|---|---|---|---|
| (0.0, 0.5] | A | 12.00 | 0.75 | 33.67 | 404.00 |
| (0.0, 0.5] | B | 17.00 | 0.41 | -3.63 | -61.68 |
| (0.0, 0.5] | C | 7.00 | 0.43 | -3.48 | -24.36 |
| (0.5, 0.75] | A | 24.00 | 0.71 | 20.02 | 480.38 |
| (0.5, 0.75] | B | 36.00 | 0.50 | 6.00 | 216.17 |
| (0.5, 0.75] | C | 21.00 | 0.48 | 0.41 | 8.70 |
| (0.75, 1.0] | A | 15.00 | 0.53 | -5.47 | -81.99 |
| (0.75, 1.0] | B | 9.00 | 0.44 | -33.53 | -301.73 |
| (0.75, 1.0] | C | 9.00 | 0.56 | -40.38 | -363.43 |
| (1.0, 1.5] | A | 23.00 | 0.78 | 30.86 | 709.74 |
| (1.0, 1.5] | B | 14.00 | 0.50 | 11.15 | 156.10 |
| (1.0, 1.5] | C | 2.00 | 0.50 | -89.34 | -178.68 |
| (1.5, 10.0] | A | 4.00 | 0.50 | 37.47 | 149.90 |
| (1.5, 10.0] | B | 3.00 | 0.00 | -265.19 | -795.56 |

### 1f. The tail: ten worst graded losses

| date | grade | confidence | call | variant | best | pnl_pts | res | decided_bar | move_18_20_in_dir | gap_18_in_dir | in_catalogue | driver_kind |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-05 | B | 66 | CONTINUATION | wide | stop_level | -339.79 | scratch |  | -234.50 | -36.25 | yes | Asia-origin+headline+US macro/rates |
| 2026-06-10 | A | 72 | CONTINUATION | wide | stop_level | -337.20 | scratch |  | 91.00 | 17.00 | yes | Asia-origin+headline |
| 2025-04-10 | B | 70 | MEAN REVERSION | wide | r500 | -294.97 | stop | 2.00 | -107.75 | -36.75 |  |  |
| 2026-06-25 | B | 70 | MEAN REVERSION | wide | r382 | -275.70 | stop | 3.00 | -35.00 | -17.25 | yes | Asia-origin+headline+US macro/rates |
| 2026-06-16 | A | 81 | CONTINUATION | wide | stop_level | -237.95 | scratch |  | -22.50 | -6.00 | yes | Asia-origin+headline+US macro/rates |
| 2026-07-27 | C | 58 | MEAN REVERSION | wide | r500 | -228.30 | stop | 3.00 | -47.25 | 0.50 | yes | after-hours print+Asia-origin+headline |
| 2025-11-14 | C | 59 | MEAN REVERSION | wide | r500 | -200.17 | stop | 8.00 | -159.25 | 21.00 | yes | Asia-origin |
| 2026-01-29 | B | 69 | MEAN REVERSION | wide | r500 | -198.22 | stop | 3.00 | -68.50 | 16.00 | yes | after-hours print+Asia-origin+headline+US macro/rates |
| 2025-04-22 | A | 95 | MEAN REVERSION | tight | r500 | -196.08 | stop | 0.00 | -114.75 | -287.00 |  |  |
| 2026-07-30 | C | 63 | MEAN REVERSION | wide | r382 | -181.65 | stop | 2.00 | -105.75 | 16.50 | yes | Asia-origin+US macro/rates |

### 1g. Ex-ante exclusion flags: P&L of the flagged nights vs the rest

|  | n_flagged | win_flagged | pts_flagged | n_rest | win_rest | pts_rest |
|---|---|---|---|---|---|---|
| after-hours shock (|post_ret|>0.3% or megacap earnings tonight) | all graded | 12.00 | 0.42 | -599.92 | 184.00 | 0.57 | 917.47 |
| after-hours shock (|post_ret|>0.3% or megacap earnings tonight) | A only | 4.00 | 0.25 | -183.70 | 74.00 | 0.72 | 1845.73 |
| pre-holiday / thin session (<9 Asia bars) | all graded | 5.00 | 0.20 | -234.85 | 191.00 | 0.57 | 552.41 |
| pre-holiday / thin session (<9 Asia bars) | A only | 3.00 | 0.00 | -201.62 | 75.00 | 0.72 | 1863.65 |
| Sunday reopen | all graded | 37.00 | 0.59 | 367.14 | 159.00 | 0.55 | -49.59 |
| Sunday reopen | A only | 12.00 | 1.00 | 868.06 | 66.00 | 0.64 | 793.97 |
| wide-stop variant | all graded | 90.00 | 0.50 | -1552.60 | 106.00 | 0.60 | 1870.15 |
| wide-stop variant | A only | 21.00 | 0.67 | 125.71 | 57.00 | 0.70 | 1536.32 |
| grade B or C | all graded | 118.00 | 0.47 | -1344.48 | 78.00 | 0.69 | 1662.03 |
| grade B or C | A only | 0.00 |  | 0.00 | 78.00 | 0.69 | 1662.03 |

### 1d. Calibration by stated confidence (all graded nights)

| confidence bucket | n | realised | stated | avg_pts |
|---|---|---|---|---|
| [55, 63) | 26.00 | 0.54 | 0.59 | -9.04 |
| [63, 72) | 83.00 | 0.45 | 0.67 | -15.45 |
| [72, 80) | 47.00 | 0.64 | 0.75 | 16.68 |
| [80, 90) | 16.00 | 0.62 | 0.85 | 19.16 |
| [90, 101) | 24.00 | 0.75 | 0.93 | 31.01 |

## 2. Hypothesis counterfactuals (IN-SAMPLE, exploratory; effect sizes are what a pre-registered test should expect, not results)

|  | n | engine_pts | cf_pts | engine_win | cf_win | converted | engine_pts_same_nights | resolved_before_20 | share_decided_bar0 | wins_decided_bar0 | losses_decided_bar0 | open_fill_pts | n_open_past_target | n_open_past_stop | avg_gap_in_dir | win | pts | avg | n_cont_wins | same_bar | A_same_bar | A_same_bar_pts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| wide_stop_all_tight_fades | 32.00 | 852.51 | 557.14 | 0.69 | 0.66 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| wide_stop_tight_fade_losses | 10.00 | -496.02 | -628.02 |  |  | 0.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| hold_eur_all_scratches | 65.00 | -940.84 | -2511.09 | 0.45 | 0.34 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| hold_nextRTH_all_scratches | 65.00 | -940.84 | -2591.93 | 0.45 | 0.35 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| hold_nextRTH scratches grade A | 21.00 | -1061.19 | -1144.04 | 0.33 | 0.38 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| hold_nextRTH scratches grade B | 26.00 | -330.92 | -1323.91 | 0.38 | 0.27 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| hold_nextRTH scratches grade C | 18.00 | 451.28 | -123.98 | 0.67 | 0.44 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| time-stop scratches at 20:00 (all) | 67.00 | -1025.08 | -361.71 | 0.43 | 0.48 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| time-stop scratches at 20:00 (A) | 23.00 | -1145.43 | -15.37 | 0.30 | 0.43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| time-stop scratches at 22:00 (all) | 67.00 | -1025.08 | -1042.11 | 0.43 | 0.40 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| time-stop scratches at 22:00 (A) | 23.00 | -1145.43 | -646.16 | 0.30 | 0.22 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| time-stop scratches at 00:00 (all) | 67.00 | -1025.08 | -1009.69 | 0.43 | 0.46 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| time-stop scratches at 00:00 (A) | 23.00 | -1145.43 | -1047.43 | 0.30 | 0.26 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| entry20_unconditional | 143.00 |  | 4.65 |  |  |  | -514.18 | 53.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| entry20 | 18-20 move WITH trade | 72.00 | 2099.44 | 91.85 |  | 0.62 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| entry20 | 18-20 move AGAINST trade | 71.00 | -2613.62 | -87.20 |  | 0.45 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| grade A: decided in 18:00 bar | 78.00 |  |  |  |  |  |  |  | 0.26 | 16.00 | 4.00 |  |  |  |  |  |  |  |  |  |  |  |
| grade A: fill at 18:00 open instead of 17:00 close | 78.00 | 1662.03 |  |  |  |  |  |  |  |  |  | 1701.69 | 3.00 | 2.00 | 0.59 |  |  |  |  |  |  |  |
| grade B: decided in 18:00 bar | 79.00 |  |  |  |  |  |  |  | 0.15 | 4.00 | 8.00 |  |  |  |  |  |  |  |  |  |  |  |
| grade B: fill at 18:00 open instead of 17:00 close | 79.00 | -786.70 |  |  |  |  |  |  |  |  |  | -358.07 | 3.00 | 5.00 | -6.87 |  |  |  |  |  |  |  |
| grade C: decided in 18:00 bar | 39.00 |  |  |  |  |  |  |  | 0.08 | 1.00 | 2.00 |  |  |  |  |  |  |  |  |  |  |  |
| grade C: fill at 18:00 open instead of 17:00 close | 39.00 | -557.77 |  |  |  |  |  |  |  |  |  | -603.50 | 1.00 | 0.00 | -0.77 |  |  |  |  |  |  |  |
| A | trail20_wr<0.45 | 6.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.50 | 93.73 | 15.62 |  |  |  |  |
| A | trail20_wr>=0.45 | 68.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.71 | 1571.25 | 23.11 |  |  |  |  |
| A | trail20 unknown | 4.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.75 | -2.95 | -0.74 |  |  |  |  |
| A | vix>25 | 9.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.78 | 508.96 | 56.55 |  |  |  |  |
| A | vix<=25 | 69.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.68 | 1153.07 | 16.71 |  |  |  |  |
| A | vix_z20>1.5 | 10.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.70 | 203.28 | 20.33 |  |  |  |  |
| A | rv_ratio>1.5 | 12.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.58 | -168.48 | -14.04 |  |  |  |  |
| A | ah_shock_proxy | 4.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.25 | -183.70 | -45.92 |  |  |  |  |
| A | no ah shock | 74.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.72 | 1845.73 | 24.94 |  |  |  |  |
| A | sunday_open | 12.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 1.00 | 868.06 | 72.34 |  |  |  |  |
| A | weeknight | 66.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.64 | 793.97 | 12.03 |  |  |  |  |
| A | in catalogue (big night) | 24.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.58 | 3.44 | 0.14 |  |  |  |  |
| A | not in catalogue | 54.00 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.74 | 1658.59 | 30.71 |  |  |  |  |
| continuation wins that were same-bar touches |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 46.00 | 1.00 | 1.00 | 133.12 |

### 2a. Full time-stop counterfactual (every graded trade: engine resolution if it happened by the 19:00 bar, otherwise flat at the 20:00 / 22:00 close)

|  | n | engine_pts | cf_pts | engine_win | cf_win | engine_avg | cf_avg | cf_worst |
|---|---|---|---|---|---|---|---|---|
| time-stop 20:00 | all graded | 196.00 | 317.55 | 398.23 | 0.56 | 0.54 | 1.62 | 2.03 | -234.18 |
| time-stop 20:00 | A | 78.00 | 1662.03 | 1807.79 | 0.69 | 0.65 | 21.31 | 23.18 | -196.08 |
| time-stop 20:00 | B | 79.00 | -786.70 | -1143.56 | 0.46 | 0.44 | -9.96 | -14.48 | -234.18 |
| time-stop 20:00 | C | 39.00 | -557.77 | -265.99 | 0.49 | 0.51 | -14.30 | -6.82 | -159.38 |
| time-stop 20:00 | A first half | 34.00 | 384.11 | 252.30 | 0.62 | 0.71 | 11.30 | 7.42 | -196.08 |
| time-stop 20:00 | A second half | 44.00 | 1277.92 | 1555.49 | 0.75 | 0.61 | 29.04 | 35.35 | -134.47 |
| time-stop 20:00 | A mean reversion | 37.00 | 963.77 | 477.08 | 0.76 | 0.68 | 26.05 | 12.89 | -196.08 |
| time-stop 20:00 | A continuation | 41.00 | 698.26 | 1330.71 | 0.63 | 0.63 | 17.03 | 32.46 | -113.99 |
| time-stop 22:00 | all graded | 196.00 | 317.55 | 281.49 | 0.56 | 0.54 | 1.62 | 1.44 | -460.62 |
| time-stop 22:00 | A | 78.00 | 1662.03 | 1882.94 | 0.69 | 0.64 | 21.31 | 24.14 | -196.08 |
| time-stop 22:00 | B | 79.00 | -786.70 | -961.76 | 0.46 | 0.47 | -9.96 | -12.17 | -460.62 |
| time-stop 22:00 | C | 39.00 | -557.77 | -639.70 | 0.49 | 0.49 | -14.30 | -16.40 | -228.30 |
| time-stop 22:00 | A first half | 34.00 | 384.11 | 551.83 | 0.62 | 0.62 | 11.30 | 16.23 | -196.08 |
| time-stop 22:00 | A second half | 44.00 | 1277.92 | 1331.11 | 0.75 | 0.66 | 29.04 | 30.25 | -186.36 |
| time-stop 22:00 | A mean reversion | 37.00 | 963.77 | 688.65 | 0.76 | 0.62 | 26.05 | 18.61 | -196.08 |
| time-stop 22:00 | A continuation | 41.00 | 698.26 | 1194.28 | 0.63 | 0.66 | 17.03 | 29.13 | -186.36 |

## 5. Hypotheses for the loop (candidates for pre-registration; every effect size above is in-sample and must be re-estimated on nights no agent has seen)

- **H-cat (catalyst)**: a night with an identifiable driver at 18:00 (|post_ret| > 0.3%, mega-cap/semis print after the close, or a narrative-agent 'Asia-origin / headline' flag) has no A-grade edge. Predicted: win rate on flagged A nights <= 50% vs ~72% on the rest; skipping them costs 0 and removes roughly a third of A loss points. Test: the daily narrative agent writes the flag to `catalogue_live.csv` BEFORE 18:00; score prospectively.
- **H-time (sub-session)**: what the engine wins, it wins early (66% of A target hits by the 20:00 bar) and A scratches lose -1145 pts between 20:00 and 03:00. But the FULL counterfactual (table 2a) is sober: a 20:00 time-stop lifts A continuation (+17 -> +32 pts/night, worst night -340 -> -114) and HURTS A mean reversion (+26 -> +13) and grade B; it is unstable across sample halves. Predicted (if real): +10-15 pts/night on A continuation only, ~0 on A overall. Low prior; pre-register for continuation trades only and evaluate on the next 60 graded nights.
- **H-geom (target cap)**: targets beyond 1.0 x the 20-day median Asia range (known at 18:00) resolve to target 30% of the time at every grade. Predicted: a max-target guard removes ~8% of graded nights and ~+1600 pts of in-sample losses; the wide-stop variant is NOT a fix (0 of 10 tight-fade losses convert, and they lose more).
- **H-calib (joint calibration)**: the mid band [63,72) realises 45% (n=83) against a stated 67%. Predicted: a single classifier for 'target before stop' of the chosen candidate, isotonic-calibrated, moves most B/C nights to NO EDGE and the realised-vs-stated gap in the mid band to < 5 points. Test: Brier/ECE on held-out months.
- **H-regime (narrative regime, not vol)**: VIX/rv/trailing-form flags have no lift (~1.0-1.1); the regime failure is a calendar cluster (2025Q4-2026Q1: A win rate 42-45%) that coincides with the catalogue's AI-capex/semis + Iran-oil driver regime. Predicted: a weekly narrative regime label ('Asia-origin continuation regime') gates A nights with ~0 cost in P&L and halves the quarterly drawdown. Test: label written weekly in advance by the pattern agent; compare gated vs ungated on the following weeks only.
- **H-cal (thin sessions)**: pre-holiday / 6-bar sessions: 0 wins in 5 graded nights (3 A). Predicted: skipping them is free (n is tiny; treat as a rule to pre-register, not a result).
- **H-hold (negative result)**: holding scratches through Europe or the next RTH makes them worse (-941 to -2592 pts); 'the target came later' explains only 4 losses. Do not spend loop budget here.

## 3. Grade-A anatomy

### 3a. Winners vs losers inside Grade A (t = Welch t-stat of the mean difference)

| feature | win_mean | win_med | loss_mean | loss_med | t |
|---|---|---|---|---|---|
| move_18_20_in_dir | 45.40 | 35.00 | -24.54 | -15.25 | 4.34 |
| stretch20_in_dir | 1.16 | 1.44 | 0.02 | -0.13 | 2.49 |
| gap_18_in_dir | 7.89 | 0.12 | -15.83 | -1.12 | 1.78 |
| n225_in_dir | 0.00 | 0.00 | -0.00 | -0.00 | 1.75 |
| target_dist | 81.09 | 70.93 | 107.84 | 85.38 | -1.61 |
| abs_streak | 2.22 | 1.00 | 1.75 | 1.00 | 1.48 |
| rr | 0.61 | 0.57 | 0.91 | 0.64 | -1.26 |
| vix_consistent | 0.03 | 0.02 | 0.04 | 0.05 | -1.24 |
| vwap_in_dir | 0.18 | 0.22 | 0.24 | 0.29 | -1.15 |
| prior_asia_in_dir | -0.00 | 0.00 | 0.00 | 0.00 | -1.07 |
| vix_z20 | -0.21 | -0.42 | 0.06 | 0.06 | -1.00 |
| post_in_dir | 0.00 | 0.00 | 0.00 | 0.00 | -0.99 |
| rth_vol_rel | 1.00 | 0.98 | 0.96 | 0.93 | 0.81 |
| ext_in_dir | 0.50 | 0.58 | 0.57 | 0.69 | -0.73 |
| stop_vs_expected | 0.84 | 0.80 | 0.88 | 0.85 | -0.51 |
| confidence | 83.24 | 80.50 | 82.25 | 80.00 | 0.51 |
| asia_rng_pts | 198.82 | 155.62 | 185.28 | 151.88 | 0.43 |
| vix | 18.67 | 16.98 | 18.23 | 16.40 | 0.41 |
| mag | 0.69 | 0.53 | 0.74 | 0.52 | -0.40 |
| stop_dist | 143.40 | 139.30 | 149.17 | 136.19 | -0.36 |
| trail20_wr | 0.55 | 0.55 | 0.55 | 0.55 | -0.32 |
| rv_ratio | 0.95 | 0.91 | 0.97 | 0.91 | -0.22 |
| rth_range_atr | 1.01 | 0.98 | 0.99 | 0.81 | 0.20 |
| sox_in_dir | 0.01 | 0.01 | 0.00 | 0.01 | 0.17 |

Same comparison inside Grade-A **MEAN REVERSION** trades only (28 wins vs 9 losses):

| feature | win_mean | win_med | loss_mean | loss_med | t |
|---|---|---|---|---|---|
| move_18_20_in_dir | 30.86 | 31.12 | -45.19 | -57.75 | 3.22 |
| abs_streak | 2.04 | 1.00 | 1.11 | 1.00 | 2.95 |
| rv_ratio | 0.83 | 0.77 | 0.61 | 0.64 | 2.20 |
| stretch20_in_dir | 0.00 | -0.05 | -1.18 | -1.08 | 1.84 |
| vix_consistent | 0.02 | 0.02 | 0.05 | 0.06 | -1.70 |
| sox_in_dir | 0.00 | 0.01 | -0.00 | -0.00 | 1.53 |
| gap_18_in_dir | 9.65 | 0.00 | -39.81 | -1.00 | 1.51 |
| trail20_wr | 0.53 | 0.55 | 0.61 | 0.60 | -1.42 |
| prior_asia_in_dir | -0.00 | -0.00 | 0.00 | 0.00 | -1.41 |
| target_dist | 69.91 | 65.19 | 120.93 | 76.09 | -1.40 |
| rr | 0.52 | 0.54 | 1.32 | 0.42 | -1.30 |
| post_in_dir | 0.00 | 0.00 | 0.00 | 0.00 | -1.30 |

Same comparison inside Grade-A **CONTINUATION** trades only (26 wins vs 15 losses):

| feature | win_mean | win_med | loss_mean | loss_med | t |
|---|---|---|---|---|---|
| stretch20_in_dir | 2.41 | 2.56 | 0.74 | 0.97 | 3.52 |
| move_18_20_in_dir | 61.06 | 35.12 | -12.15 | -8.00 | 2.96 |
| n225_in_dir | 0.01 | 0.00 | -0.00 | -0.00 | 1.89 |
| rth_vol_rel | 1.00 | 0.98 | 0.92 | 0.92 | 1.82 |
| vwap_in_dir | 0.32 | 0.31 | 0.35 | 0.35 | -1.19 |
| asia_rng_pts | 231.08 | 166.88 | 174.75 | 122.75 | 1.12 |
| trail20_wr | 0.56 | 0.55 | 0.53 | 0.50 | 1.12 |
| gap_18_in_dir | 6.00 | 0.88 | -1.45 | -1.25 | 1.00 |
| rv_ratio | 1.07 | 1.10 | 1.18 | 1.21 | -0.93 |
| rth_range_atr | 1.21 | 1.17 | 1.09 | 0.95 | 0.83 |
| abs_streak | 2.42 | 2.00 | 2.13 | 2.00 | 0.61 |
| post_in_dir | 0.00 | 0.00 | 0.00 | 0.00 | 0.56 |

### 3a-ii. Grade-A Sunday reopens (Friday rows): engine P&L vs a fill at the Sunday 18:00 open

| date | call | variant | best | confidence | pnl_pts | pnl_open_fill | gap_18_in_dir | res | decided_bar |
|---|---|---|---|---|---|---|---|---|---|
| 2025-05-02 | MEAN REVERSION | tight | r382 | 75 | 53.28 | 30.28 | 23.00 | target | 0.00 |
| 2025-08-01 | MEAN REVERSION | tight | r500 | 89 | 91.12 | 91.12 | 0.00 | target | 4.00 |
| 2025-08-08 | CONTINUATION | tight | stop_level | 79 | 30.53 | 0.00 | 50.25 | target | 0.00 |
| 2025-08-15 | MEAN REVERSION | tight | r500 | 91 | 51.25 | 60.25 | -9.00 | target | 1.00 |
| 2026-03-27 | CONTINUATION | wide | stop_level | 77 | 122.70 | 32.70 | 90.00 | target | 1.00 |
| 2026-04-17 | MEAN REVERSION | tight | r500 | 95 | 40.75 | 0.00 | 186.75 | target | 0.00 |
| 2026-05-08 | CONTINUATION | tight | stop_level | 88 | 56.65 | 107.40 | -50.75 | target | 2.00 |
| 2026-08-14 | MEAN REVERSION | wide | r500 | 75 | 64.62 | 14.12 | 50.50 | target | 0.00 |
| 2026-08-21 | MEAN REVERSION | tight | r500 | 95 | 65.75 | 132.50 | -66.75 | target | 1.00 |
| 2026-09-18 | CONTINUATION | wide | stop_level | 85 | 108.00 | 78.75 | 29.25 | target | 0.00 |
| 2026-10-09 | MEAN REVERSION | tight | r500 | 93 | 43.00 | 0.00 | 71.75 | target | 0.00 |
| 2026-11-06 | CONTINUATION | tight | stop_level | 75 | 140.40 | 159.65 | -19.25 | target | 0.00 |

### 3b. Grade A by `call`

| call | n | win | pts | avg |
|---|---|---|---|---|
| CONTINUATION | 41.00 | 0.63 | 698.26 | 17.03 |
| MEAN REVERSION | 37.00 | 0.76 | 963.77 | 26.05 |

### 3b. Grade A by `variant`

| variant | n | win | pts | avg |
|---|---|---|---|---|
| tight | 57.00 | 0.70 | 1536.32 | 26.95 |
| wide | 21.00 | 0.67 | 125.71 | 5.99 |

### 3b. Grade A by `best`

| best | n | win | pts | avg |
|---|---|---|---|---|
| r382 | 12.00 | 0.67 | 39.51 | 3.29 |
| r500 | 15.00 | 0.73 | 424.59 | 28.31 |
| stop_level | 41.00 | 0.63 | 698.26 | 17.03 |
| vwap | 10.00 | 0.90 | 499.68 | 49.97 |

### 3b. Grade A by `dow`

| dow | n | win | pts | avg |
|---|---|---|---|---|
| 0 | 18.00 | 0.67 | 411.52 | 22.86 |
| 1 | 15.00 | 0.53 | 37.47 | 2.50 |
| 2 | 18.00 | 0.72 | 206.22 | 11.46 |
| 3 | 15.00 | 0.60 | 138.75 | 9.25 |
| 4 | 12.00 | 1.00 | 868.06 | 72.34 |

### 3b. Grade A by `sunday_open`

| sunday_open | n | win | pts | avg |
|---|---|---|---|---|
| 0 | 66.00 | 0.64 | 793.97 | 12.03 |
| 1 | 12.00 | 1.00 | 868.06 | 72.34 |

### 3b. Grade A by `quarter`

| quarter | n | win | pts | avg |
|---|---|---|---|---|
| 2025Q2 | 6.00 | 0.83 | 104.08 | 17.35 |
| 2025Q3 | 11.00 | 0.91 | 562.84 | 51.17 |
| 2025Q4 | 12.00 | 0.42 | -84.69 | -7.06 |
| 2026Q1 | 11.00 | 0.45 | 155.05 | 14.10 |
| 2026Q2 | 18.00 | 0.72 | 43.25 | 2.40 |
| 2026Q3 | 14.00 | 0.79 | 596.87 | 42.63 |
| 2026Q4 | 6.00 | 0.83 | 284.63 | 47.44 |

### 3b. Grade A by `res`

| res | n | win | pts | avg |
|---|---|---|---|---|
| scratch | 23.00 | 0.30 | -1145.43 | -49.80 |
| stop | 8.00 | 0.00 | -946.25 | -118.28 |
| target | 47.00 | 1.00 | 3753.71 | 79.87 |

### 3c. Grade A by call / variant / target

|  | n | win | pts | avg | avg_win | avg_loss | rr |
|---|---|---|---|---|---|---|---|
| ('CONTINUATION', 'tight', 'stop_level') | 33.00 | 0.67 | 801.61 | 24.29 | 77.45 | -82.02 | 0.61 |
| ('CONTINUATION', 'wide', 'stop_level') | 8.00 | 0.50 | -103.36 | -12.92 | 121.95 | -147.79 | 0.66 |
| ('MEAN REVERSION', 'tight', 'r382') | 8.00 | 0.75 | 295.68 | 36.96 | 56.35 | -21.21 | 0.47 |
| ('MEAN REVERSION', 'tight', 'r500') | 13.00 | 0.69 | 293.46 | 22.57 | 66.83 | -77.01 | 0.36 |
| ('MEAN REVERSION', 'tight', 'vwap') | 3.00 | 1.00 | 145.57 | 48.52 | 48.52 |  | 0.30 |
| ('MEAN REVERSION', 'wide', 'r382') | 4.00 | 0.50 | -256.17 | -64.04 | 9.88 | -137.96 | 0.76 |
| ('MEAN REVERSION', 'wide', 'r500') | 2.00 | 1.00 | 131.12 | 65.56 | 65.56 |  | 0.44 |
| ('MEAN REVERSION', 'wide', 'vwap') | 7.00 | 0.86 | 354.11 | 50.59 | 81.43 | -134.47 | 0.70 |

### 3d. Fragility

- **A nights / wins / losses**: 78 / 54 / 24
- **avg pts (bootstrap 90% CI)**: +21.3 (+2.7 .. +38.0)
- **P(mean <= 0) bootstrap**: 0.027
- **avg win / avg loss / reward:risk (realised)**: +72.5 / -93.9 / 0.77
- **median planned target:stop**: 0.58
- **top-5 wins share of total**: 41% (2026-07-13, 2026-05-21, 2026-11-06, 2026-03-30, 2026-04-07)
- **total without top-5 wins**: +972
- **worst-5 losses share of loss pts**: 47%
- **share of A decided in the 18:00 bar**: 26%
- **A P&L if filled at the 18:00 open**: +1702 vs +1662 engine (3 nights open already past target, 2 past stop)
- **continuation A wins that were same-bar touches**: 1 of 26 (pts +133)
- **best quarter share of total**: 36% (2026Q3)
- **quarters with A win rate < 50%**: 2025Q4 (42%, n=12), 2026Q1 (45%, n=11)
- **continuation share of A pts**: 42%
- **A nights in the catalogue (big-move nights)**: 24 (58% win, +3 pts) vs 54 not (74% win, +1659 pts)
- **A Sunday reopens (Friday rows)**: 12 nights, 100% win, +868 pts engine, +707 pts if filled at the Sunday 18:00 open; 52% of all A pts
- **A losses by resolution**: scratch 16 (-1308 pts), stop 8 (-946 pts)
- **A wins by resolution**: target 47, scratch-but-positive 7
- **median hour of A target hits (ET)**: 19 (share hit by the 20:00 bar: 66%)

### 3e. Every Grade-A night

| date | grade | confidence | call | variant | best | pnl_pts | res | decided_bar | stop_dist | target_dist | asia_rng_pts | stop_vs_realised | whipsaw | hold_res | kospi_next | n225_next | vix | rv_ratio | trail20_wr | sunday_open | driver_kind | primary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-13 | A | 74 | MEAN REVERSION | wide | vwap | 142.99 | target | 7.00 | 172.50 | 142.99 | 346.25 | 0.50 |  | target | 0.01 | 0.01 | 17.16 | 0.87 | 0.45 | 0 |  | wi |
| 2026-05-21 | A | 85 | CONTINUATION | tight | stop_level | 141.20 | target | 2.00 | 145.20 | 141.20 | 162.25 | 0.89 |  | target | 0.00 | 0.03 | 16.76 | 1.12 | 0.60 | 0 |  | wi |
| 2026-11-06 | A | 75 | CONTINUATION | tight | stop_level | 140.40 | target | 0.00 | 118.23 | 140.40 | 567.75 | 0.21 |  | target | 0.05 | 0.05 | 25.64 | 1.72 | 0.80 | 1 | Asia-origin+headline+US macro/rates | wi |
| 2026-03-30 | A | 79 | CONTINUATION | tight | stop_level | 133.12 | target | 2.00 | 171.64 | 133.12 | 443.50 | 0.39 |  | stop | -0.04 | -0.02 | 30.61 | 0.82 | 0.45 | 0 | after-hours print+Asia-origin+headline | wi |
| 2026-04-07 | A | 81 | CONTINUATION | wide | stop_level | 131.85 | target | 0.00 | 239.95 | 131.85 | 847.00 | 0.28 |  | target | 0.07 | 0.05 | 25.78 | 0.96 | 0.45 | 0 | Asia-origin+headline | wi |
| 2026-03-31 | A | 92 | CONTINUATION | tight | stop_level | 131.58 | target | 1.00 | 242.18 | 131.58 | 296.75 | 0.82 |  | target | 0.08 | 0.05 | 25.25 | 1.55 | 0.45 | 0 | Asia-origin+headline | wi |
| 2026-02-05 | A | 75 | CONTINUATION | wide | stop_level | 125.25 | target | 0.00 | 304.21 | 125.25 | 374.00 | 0.81 |  | stop | -0.01 | 0.01 | 21.77 | 0.85 | 0.45 | 0 |  | wi |
| 2026-03-27 | A | 77 | CONTINUATION | wide | stop_level | 122.70 | target | 1.00 | 203.15 | 122.70 | 323.00 | 0.63 |  | stop | -0.03 | -0.03 | 31.05 | 1.08 | 0.40 | 1 | Asia-origin+headline+US macro/rates | wi |
| 2026-09-03 | A | 72 | CONTINUATION | tight | stop_level | 121.00 | target | 7.00 | 77.05 | 121.00 | 161.75 | 0.48 |  | target | 0.02 | 0.01 | 14.32 | 1.18 | 0.65 | 0 |  | wi |
| 2026-10-14 | A | 78 | CONTINUATION | tight | stop_level | 119.53 | target | 0.00 | 202.18 | 119.53 | 393.75 | 0.51 |  | target | -0.08 | -0.05 | 16.87 | 0.82 | 0.75 | 0 | Asia-origin | wi |
| 2025-04-21 | A | 94 | MEAN REVERSION | tight | r500 | 108.12 | target | 3.00 | 260.50 | 108.12 | 299.25 | 0.87 |  | target | -0.00 | -0.00 | 33.82 | 0.50 |  | 0 |  | wi |
| 2026-09-18 | A | 85 | CONTINUATION | wide | stop_level | 108.00 | target | 0.00 | 137.60 | 108.00 | 199.50 | 0.69 |  | target | 0.02 |  | 14.81 | 1.16 | 0.60 | 1 | Asia-origin+headline | wi |
| 2025-11-25 | A | 86 | CONTINUATION | tight | stop_level | 103.08 | target | 4.00 | 201.91 | 103.08 | 174.50 | 1.16 |  | target | 0.03 | 0.02 | 18.56 | 1.51 | 0.50 | 0 |  | wi |
| 2026-08-03 | A | 79 | CONTINUATION | tight | stop_level | 100.08 | target | 3.00 | 177.78 | 100.08 | 267.00 | 0.67 |  | target | 0.02 | 0.00 | 15.86 | 1.43 | 0.40 | 0 | Asia-origin+headline | wi |
| 2026-05-07 | A | 93 | MEAN REVERSION | tight | vwap | 94.11 | target | 2.00 | 131.28 | 94.11 | 297.50 | 0.44 |  | target | 0.00 | -0.00 | 17.08 | 0.99 | 0.60 | 0 | after-hours print+Asia-origin+headline | wi |
| 2025-08-01 | A | 89 | MEAN REVERSION | tight | r500 | 91.12 | target | 4.00 | 141.47 | 91.12 | 178.75 | 0.79 |  | target | 0.01 | -0.01 | 20.38 | 1.50 | 0.40 | 1 |  | wi |
| 2025-11-18 | A | 78 | MEAN REVERSION | wide | vwap | 88.91 | target | 0.00 | 136.20 | 88.91 | 210.50 | 0.65 |  | target | -0.01 | -0.00 | 24.69 | 0.73 | 0.55 | 0 |  | wi |
| 2026-08-12 | A | 74 | MEAN REVERSION | wide | vwap | 82.32 | target | 6.00 | 152.62 | 82.32 | 143.50 | 1.06 |  | target | 0.04 | 0.01 | 14.55 | 0.44 | 0.50 | 0 |  | wi |
| 2025-08-19 | A | 72 | CONTINUATION | tight | stop_level | 81.95 | target | 3.00 | 84.62 | 81.95 | 151.25 | 0.56 |  | target | -0.01 | -0.02 | 15.57 | 0.61 | 0.45 | 0 |  | wi |
| 2026-05-13 | A | 88 | CONTINUATION | tight | stop_level | 78.55 | target | 1.00 | 198.76 | 78.55 | 171.50 | 1.16 |  | target | 0.02 | -0.01 | 17.87 | 1.24 | 0.65 | 0 |  | wi |
| 2026-07-22 | A | 93 | MEAN REVERSION | tight | r500 | 76.50 | target | 0.00 | 209.72 | 76.50 | 260.75 | 0.80 |  | target | 0.04 | 0.00 | 16.64 | 0.97 | 0.50 | 0 | after-hours print+Asia-origin+headline | wi |
| 2026-05-06 | A | 92 | CONTINUATION | tight | stop_level | 74.88 | scratch |  | 170.63 | 52.47 | 111.75 | 1.53 |  | target | 0.01 | 0.06 | 17.39 | 0.91 | 0.60 | 0 |  | wi |
| 2026-08-19 | A | 91 | MEAN REVERSION | tight | r500 | 71.25 | target | 0.00 | 222.50 | 71.25 | 133.25 | 1.67 |  | target | 0.06 | 0.01 | 14.89 | 0.68 | 0.60 | 0 |  | wi |
| 2026-06-15 | A | 73 | MEAN REVERSION | tight | r382 | 70.60 | target | 0.00 | 118.25 | 70.60 | 113.00 | 1.05 |  | stop | 0.02 | 0.00 | 16.20 | 1.47 | 0.65 | 0 | Asia-origin+headline | wi |
| 2026-10-05 | A | 79 | CONTINUATION | tight | stop_level | 69.75 | target | 3.00 | 104.39 | 69.75 | 102.00 | 1.02 |  | target | -0.01 | 0.01 | 15.52 | 0.44 | 0.70 | 0 |  | wi |
| 2025-11-12 | A | 90 | MEAN REVERSION | tight | r382 | 67.45 | target | 2.00 | 167.47 | 67.45 | 220.00 | 0.76 |  | stop | 0.00 | 0.00 | 17.51 | 1.30 | 0.55 | 0 |  | wi |
| 2025-04-29 | A | 75 | MEAN REVERSION | wide | r500 | 66.50 | target | 1.00 | 153.00 | 66.50 | 126.50 | 1.21 |  | target | -0.00 | 0.01 | 24.17 | 0.31 |  | 0 |  | wi |
| 2026-08-21 | A | 95 | MEAN REVERSION | tight | r500 | 65.75 | target | 1.00 | 197.35 | 65.75 | 360.00 | 0.55 |  | stop | -0.03 | -0.01 | 15.13 | 0.53 | 0.60 | 1 |  | wi |
| 2026-08-14 | A | 75 | MEAN REVERSION | wide | r500 | 64.62 | target | 0.00 | 143.70 | 64.62 | 141.75 | 1.01 |  | target | -0.02 | 0.01 | 14.25 | 0.49 | 0.55 | 1 |  | wi |
| 2025-08-06 | A | 83 | CONTINUATION | tight | stop_level | 61.67 | target | 0.00 | 100.98 | 61.67 | 126.75 | 0.80 |  | target | 0.01 | 0.01 | 16.77 | 2.00 | 0.45 | 0 |  | wi |
| 2025-09-10 | A | 74 | MEAN REVERSION | wide | vwap | 61.18 | target | 8.00 | 69.00 | 61.18 | 70.25 | 0.98 |  | target | 0.01 | 0.01 | 15.35 | 0.56 | 0.45 | 0 |  | wi |
| 2026-01-22 | A | 94 | MEAN REVERSION | tight | r382 | 60.79 | target | 4.00 | 113.47 | 60.79 | 156.00 | 0.73 |  | target | 0.01 | 0.00 | 15.64 | 1.63 | 0.45 | 0 |  | wi |
| 2025-10-01 | A | 92 | CONTINUATION | tight | stop_level | 58.53 | target | 3.00 | 99.17 | 58.53 | 74.75 | 1.33 |  | target | 0.03 | 0.01 | 16.29 | 0.95 | 0.50 | 0 |  | wi |
| 2025-09-25 | A | 74 | MEAN REVERSION | wide | vwap | 57.76 | target | 7.00 | 82.28 | 57.76 | 94.75 | 0.87 |  | target | -0.02 | -0.01 | 16.74 | 0.92 | 0.55 | 0 |  | wi |
| 2026-05-08 | A | 88 | CONTINUATION | tight | stop_level | 56.65 | target | 2.00 | 148.02 | 56.65 | 174.00 | 0.85 |  | target | 0.04 | -0.00 | 17.19 | 1.20 | 0.65 | 1 |  | wi |
| 2026-04-09 | A | 79 | CONTINUATION | tight | stop_level | 55.92 | target | 5.00 | 105.27 | 55.92 | 110.75 | 0.95 |  | target | 0.01 | 0.02 | 19.49 | 0.69 | 0.50 | 0 |  | wi |
| 2025-07-07 | A | 78 | MEAN REVERSION | wide | vwap | 55.44 | target | 2.00 | 83.03 | 55.44 | 144.00 | 0.58 |  | target | 0.02 | 0.00 | 17.79 | 0.73 | 0.50 | 0 |  | wi |
| 2025-06-16 | A | 91 | MEAN REVERSION | tight | r500 | 53.75 | target | 0.00 | 84.17 | 53.75 | 170.00 | 0.50 |  | target | 0.00 | 0.01 | 19.11 | 1.04 | 0.50 | 0 |  | wi |
| 2025-05-02 | A | 75 | MEAN REVERSION | tight | r382 | 53.28 | target | 0.00 | 97.92 | 53.28 | 210.25 | 0.47 |  | target |  |  | 22.68 | 0.24 | 0.58 | 1 |  | wi |
| 2025-08-15 | A | 91 | MEAN REVERSION | tight | r500 | 51.25 | target | 1.00 | 88.47 | 51.25 | 110.50 | 0.80 |  | none | -0.01 | 0.01 | 15.09 | 0.75 | 0.45 | 1 |  | wi |
| 2026-05-04 | A | 95 | MEAN REVERSION | tight | vwap | 48.21 | target | 2.00 | 162.80 | 48.21 | 155.25 | 1.05 |  | target | 0.06 | 0.06 | 18.29 | 1.00 | 0.60 | 0 |  | wi |
| 2025-11-05 | A | 94 | MEAN REVERSION | tight | r382 | 46.61 | target | 1.00 | 190.20 | 46.61 | 157.75 | 1.21 |  | target | 0.01 | 0.01 | 18.01 | 0.86 | 0.55 | 0 |  | wi |
| 2026-10-07 | A | 79 | CONTINUATION | tight | stop_level | 46.42 | target | 1.00 | 107.66 | 46.42 | 218.00 | 0.49 |  | stop | -0.03 | -0.01 | 15.08 | 0.57 | 0.70 | 0 |  | wi |
| 2026-09-22 | A | 72 | CONTINUATION | tight | stop_level | 43.74 | scratch |  | 61.20 | 95.17 | 112.00 | 0.55 |  | stop | 0.01 | 0.01 | 14.21 | 1.16 | 0.70 | 0 |  | wi |
| 2026-10-09 | A | 93 | MEAN REVERSION | tight | r500 | 43.00 | target | 0.00 | 141.00 | 43.00 | 133.25 | 1.06 |  | target | -0.04 | -0.02 | 14.84 | 0.91 | 0.70 | 1 |  | wi |
| 2026-04-17 | A | 95 | MEAN REVERSION | tight | r500 | 40.75 | target | 0.00 | 84.78 | 40.75 | 106.50 | 0.80 |  | target | 0.00 | 0.01 | 17.48 | 0.30 | 0.55 | 1 |  | wi |
| 2025-07-01 | A | 86 | MEAN REVERSION | tight | r382 | 39.37 | target | 4.00 | 122.62 | 39.37 | 105.75 | 1.16 |  | target | -0.00 | -0.01 | 16.83 | 0.78 | 0.45 | 0 |  | wi |
| 2025-09-15 | A | 79 | CONTINUATION | tight | stop_level | 34.33 | target | 4.00 | 34.84 | 34.33 | 77.00 | 0.45 |  | target | 0.01 | 0.00 | 15.69 | 0.46 | 0.45 | 0 |  | wi |
| 2025-08-08 | A | 79 | CONTINUATION | tight | stop_level | 30.53 | target | 0.00 | 46.80 | 30.53 | 72.00 | 0.65 |  | target | -0.00 | 0.02 | 15.15 | 1.23 | 0.45 | 1 |  | wi |
| 2026-05-28 | A | 92 | CONTINUATION | tight | stop_level | 20.24 | scratch |  | 131.02 | 73.92 | 145.50 | 0.90 |  | target | 0.04 | 0.03 | 15.74 | 0.68 | 0.65 | 0 |  | wi |
| 2025-04-14 | A | 75 | MEAN REVERSION | wide | r382 | 18.50 | scratch |  | 155.55 | 131.44 | 141.00 | 1.10 |  | target | 0.01 | 0.01 | 30.89 | 1.74 |  | 0 |  | wi |
| 2026-04-16 | A | 93 | MEAN REVERSION | tight | vwap | 3.25 | scratch |  | 128.60 | 32.72 | 57.75 | 2.23 |  | stop | -0.01 | -0.02 | 17.94 | 0.42 | 0.50 | 0 |  | wi |
| 2026-04-08 | A | 75 | MEAN REVERSION | wide | r382 | 1.25 | scratch |  | 135.22 | 91.65 | 84.50 | 1.60 |  | target | -0.02 | -0.01 | 21.04 | 0.70 | 0.45 | 0 | Asia-origin+headline+US macro/rates | wi |
| 2026-09-21 | A | 80 | CONTINUATION | tight | stop_level | 0.75 | scratch |  | 183.21 | 147.80 | 150.00 | 1.22 |  | target | 0.00 | 0.01 | 14.87 | 1.44 | 0.65 | 0 |  | wi |
| 2025-08-26 | A | 72 | CONTINUATION | wide | stop_level | -1.75 | scratch |  | 85.17 | 62.78 | 37.25 | 2.29 |  | stop | 0.00 | 0.00 | 14.62 | 0.85 | 0.50 | 0 |  | a) |
| 2026-09-28 | A | 94 | MEAN REVERSION | tight | r382 | -12.25 | scratch |  | 240.25 | 76.09 | 243.75 | 0.99 |  | target | -0.00 | -0.01 | 16.07 | 0.81 | 0.75 | 0 |  | e) |
| 2025-10-08 | A | 81 | CONTINUATION | wide | stop_level | -14.25 | scratch |  | 123.07 | 86.85 | 87.00 | 1.41 |  | stop | 0.02 | 0.02 | 16.30 | 1.33 | 0.50 | 0 |  | g) |
| 2025-12-08 | A | 92 | MEAN REVERSION | tight | r500 | -21.74 | scratch |  | 171.60 | 32.88 | 82.75 | 2.07 |  | none | -0.00 | 0.00 | 16.66 | 0.31 | 0.60 | 0 |  | g) |
| 2026-06-03 | A | 75 | MEAN REVERSION | tight | r382 | -30.17 | stop | 0.00 | 30.17 | 171.69 | 182.50 | 0.17 |  | stop | -0.02 | -0.01 | 16.06 | 0.42 | 0.65 | 0 | after-hours print+Asia-origin | c) |
| 2025-12-23 | A | 88 | CONTINUATION | tight | stop_level | -32.74 | scratch |  | 75.31 | 30.15 | 46.00 | 1.64 |  |  | -0.00 | -0.00 | 14.00 | 1.18 | 0.50 | 0 |  | f) |
| 2026-01-13 | A | 94 | MEAN REVERSION | tight | r500 | -38.00 | scratch |  | 118.95 | 38.75 | 90.25 | 1.32 |  | stop | 0.01 | 0.01 | 15.98 | 0.56 | 0.40 | 0 |  | b) |
| 2026-04-02 | A | 93 | CONTINUATION | tight | stop_level | -51.50 | scratch |  | 144.92 | 106.12 | 104.50 | 1.39 |  |  | 0.03 | 0.01 | 23.87 | 1.40 | 0.50 | 0 | after-hours print+headline | c) |
| 2025-11-24 | A | 86 | CONTINUATION | tight | stop_level | -51.99 | scratch |  | 140.74 | 80.58 | 105.75 | 1.33 |  | stop | 0.00 | 0.00 | 20.52 | 1.58 | 0.50 | 0 |  | b) |
| 2026-01-08 | A | 91 | MEAN REVERSION | tight | r500 | -52.22 | scratch |  | 167.20 | 29.25 | 99.75 | 1.68 |  | target | 0.01 | 0.02 | 15.45 | 0.72 | 0.45 | 0 |  | e) |
| 2026-01-06 | A | 86 | CONTINUATION | tight | stop_level | -64.75 | scratch |  | 100.08 | 31.03 | 80.00 | 1.25 |  | stop | 0.01 | -0.01 | 14.75 | 0.84 | 0.50 | 0 |  | g) |
| 2025-11-10 | A | 72 | CONTINUATION | tight | stop_level | -70.25 | scratch |  | 112.37 | 70.60 | 122.75 | 0.92 |  | stop | 0.01 | -0.00 | 17.60 | 1.56 | 0.60 | 0 |  | b) |
| 2026-02-10 | A | 79 | CONTINUATION | tight | stop_level | -78.23 | stop | 4.00 | 78.23 | 83.90 | 92.75 | 0.84 |  | target | 0.01 | -0.00 | 17.79 | 1.57 | 0.40 | 0 |  | a) |
| 2026-03-26 | A | 79 | CONTINUATION | tight | stop_level | -81.24 | scratch |  | 193.69 | 93.75 | 170.00 | 1.14 |  | target | -0.00 | -0.00 | 27.44 | 1.13 | 0.45 | 0 | Asia-origin+headline | c) |
| 2026-01-15 | A | 86 | CONTINUATION | tight | stop_level | -103.95 | scratch |  | 137.90 | 58.12 | 133.75 | 1.03 |  | stop | 0.01 | -0.00 | 15.84 | 0.89 | 0.40 | 0 |  | b) |
| 2025-12-10 | A | 79 | CONTINUATION | tight | stop_level | -113.99 | stop | 1.00 | 113.99 | 104.45 | 413.00 | 0.28 |  | stop | -0.01 | -0.01 | 15.77 | 0.26 | 0.55 | 0 | after-hours print+Asia-origin+US macro/rates | c) |
| 2026-06-18 | A | 79 | CONTINUATION | tight | stop_level | -117.38 | stop | 3.00 | 117.38 | 95.97 | 265.25 | 0.44 |  |  | -0.00 | 0.00 | 16.40 | 1.21 | 0.60 | 0 | Asia-origin | c) |
| 2026-08-17 | A | 75 | MEAN REVERSION | wide | r382 | -131.62 | stop | 4.00 | 131.62 | 54.94 | 335.25 | 0.39 |  | stop | -0.02 | -0.03 | 15.19 | 0.48 | 0.60 | 0 | Asia-origin+headline+US macro/rates | c) |
| 2026-10-29 | A | 73 | MEAN REVERSION | wide | vwap | -134.47 | stop | 0.00 | 134.47 | 327.65 | 358.50 | 0.38 |  | stop | -0.03 | -0.02 | 17.20 | 0.64 | 0.85 | 0 | Asia-origin+headline | c) |
| 2026-09-14 | A | 79 | CONTINUATION | tight | stop_level | -136.26 | scratch |  | 212.41 | 192.30 | 186.75 | 1.14 |  | stop | -0.01 | -0.00 | 17.10 | 0.92 | 0.65 | 0 |  | a) |
| 2025-11-19 | A | 73 | MEAN REVERSION | wide | r382 | -144.30 | stop | 0.00 | 144.30 | 256.92 | 253.75 | 0.57 |  | stop | 0.02 | 0.03 | 23.66 | 0.93 | 0.55 | 0 | after-hours print+Asia-origin | c) |
| 2025-04-22 | A | 95 | MEAN REVERSION | tight | r500 | -196.08 | stop | 0.00 | 196.08 | 100.25 | 179.00 | 1.10 |  | stop | 0.02 | 0.02 | 30.57 | 0.66 |  | 0 |  | b) |
| 2026-06-16 | A | 81 | CONTINUATION | wide | stop_level | -237.95 | scratch |  | 261.52 | 176.03 | 239.25 | 1.09 |  | stop | 0.02 | 0.01 | 16.41 | 1.50 | 0.65 | 0 | Asia-origin+headline+US macro/rates | c) |
| 2026-06-10 | A | 72 | CONTINUATION | wide | stop_level | -337.20 | scratch |  | 348.65 | 227.10 | 537.25 | 0.65 |  | stop | 0.00 | 0.00 | 22.22 | 1.56 | 0.60 | 0 | Asia-origin+headline | c) |

## 4. Caveats

- All counterfactuals in section 2 are evaluated on the same 331 nights that produced the grades: they size hypotheses, they do not confirm them.
- The catalogue covers Nov 2025 → Nov 2026 and only the big Asia nights, so `in_catalogue` is itself a proxy for 'big move happened' (selection on the outcome).
- `asia_shock_expost` uses the next KOSPI/N225 daily close: ex post by construction.
- Hourly bars: a bar that touches both levels is ambiguous; 'whipsaw' and 'same_bar' depend on that granularity.
- P&L is booked from the 17:00 close; the first tradable price is the 18:00 open. See the `fill at 18:00 open` rows.