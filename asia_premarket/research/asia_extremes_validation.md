# Walk-forward validation of the Asia high / low detectors (signal level)

Scope. CME Globex NQ and ES, Asia session 18:00-02:59 ET (hourly bars k = 0..8, k = 0 is the 18:00 bar), Europe 03:00-08:59 ET. Hourly data 2024-06-18 to 2026-11-06 (579 sessions per symbol in the session table). Detector A (intra-session) out-of-sample window 2024-12-19 to 2026-11-06: 439 NQ / 438 ES sessions, 3,951 / 3,942 bar closes, of which 3,512 / 3,504 at k <= 7 carry a non-definitional Asia label; overnight labels exist for 438 / 437 of these sessions. Detector B (pre-Asia) out-of-sample window 2025-01-02 to 2026-11-06: 434 NQ / 433 ES nights. "Last 12 months" is 2025-11-07 to 2026-11-06 (233 sessions per symbol); H1 is before 2025-09-01 (160 NQ / 160 ES sessions for Detector A, 155 / 155 nights for Detector B), H2 from 2025-09-01 (279 NQ / 278 ES for both detectors). Every probability evaluated here was produced out of sample by the walk-forward described in `research/asia_extremes_report.md`, sections 5 and 8.7 (expanding window, monthly refits, first 120 sessions training only, isotonic calibration fitted only on prior out-of-sample rows, models fitted only on dates strictly before the prediction date). This document does not retrain anything: it reads the stored predictions (`research/extremes/oos_intrasession_{NQ,ES}.csv`, `oos_preasia_{NQ,ES}.csv`), turns them into flags and measures the flags against the realised labels as trading signals. Decision time of each signal: the intra-session flags are read at the close of Asia bar k (19:00 ET for k = 0, through 02:00 ET for k = 7 and 03:00 ET for k = 8); the pre-Asia calls are read at 17:xx ET, after the 17:00 reference close and before the 18:00 reopen. All numbers below were written by `research/extremes/signal_backtest.py` into `research/extremes/validation/` (section 10). Dates are ISO, CIs are 90 %.

## 1. Summary verdict

One row per signal and symbol; n events = first firings per session for the intra-session flags, nights called for the pre-Asia calls. Base = the k-matched k-only baseline for the intra-session flags (mean of the expanding bar-k base rate over the fired rows), the expanding base rate of the label for the pre-Asia calls. Lift = hit rate minus base.

| signal | sym | decision time | claim | n events | share of sessions | hit rate [90% CI] | base | lift | last 12 months hit rate [90% CI] (n) |
|---|---|---|---|---|---|---|---|---|---|
| HI_IN@0.90 | NQ | bar close, k<=7 (median first firing 23:00 ET) | Asia high already in | 267 | 0.608 | 0.888 [0.852, 0.916] | 0.580 | +0.308 | 0.904 [0.856, 0.937] (n=146) |
| HI_IN@0.90 | ES | bar close, k<=7 (median first firing 00:00 ET) | Asia high already in | 238 | 0.543 | 0.916 [0.882, 0.941] | 0.604 | +0.312 | 0.922 [0.875, 0.953] (n=129) |
| LO_IN@0.90 | NQ | bar close, k<=7 (median first firing 00:00 ET) | Asia low already in | 200 | 0.456 | 0.910 [0.871, 0.938] | 0.661 | +0.249 | 0.931 [0.882, 0.961] (n=116) |
| LO_IN@0.90 | ES | bar close, k<=7 (median first firing 00:00 ET) | Asia low already in | 238 | 0.543 | 0.929 [0.896, 0.951] | 0.649 | +0.279 | 0.946 [0.904, 0.971] (n=130) |
| HI_IN@0.95 | NQ | bar close, k<=7 (median first firing 00:00 ET) | Asia high already in | 188 | 0.428 | 0.947 [0.913, 0.968] | 0.637 | +0.310 | 0.956 [0.912, 0.978] (n=113) |
| HI_IN@0.95 | ES | bar close, k<=7 (median first firing 00:00 ET) | Asia high already in | 171 | 0.390 | 0.965 [0.934, 0.982] | 0.637 | +0.328 | 0.951 [0.904, 0.976] (n=103) |
| LO_IN@0.95 | NQ | bar close, k<=7 (median first firing 00:00-01:00 ET) | Asia low already in | 154 | 0.351 | 0.948 [0.910, 0.970] | 0.678 | +0.270 | 0.966 [0.917, 0.986] (n=87) |
| LO_IN@0.95 | ES | bar close, k<=7 (median first firing 00:00 ET) | Asia low already in | 176 | 0.402 | 0.949 [0.914, 0.970] | 0.675 | +0.274 | 0.967 [0.919, 0.987] (n=90) |
| HI_AHEAD@0.10 | NQ | bar close, k<=7 (median first firing 19:00 ET) | new Asia high before 03:00 | 183 | 0.417 | 0.940 [0.904, 0.963] | 0.702 | +0.238 | 0.928 [0.877, 0.959] (n=111) |
| HI_AHEAD@0.10 | ES | bar close, k<=7 (median first firing 20:00 ET) | new Asia high before 03:00 | 160 | 0.365 | 0.925 [0.883, 0.953] | 0.658 | +0.267 | 0.925 [0.871, 0.957] (n=106) |
| LO_AHEAD@0.10 | NQ | bar close, k<=7 (median first firing 19:00-20:00 ET) | new Asia low before 03:00 | 164 | 0.374 | 0.890 [0.844, 0.924] | 0.590 | +0.300 | 0.878 [0.810, 0.924] (n=90) |
| LO_AHEAD@0.10 | ES | bar close, k<=7 (median first firing 20:00 ET) | new Asia low before 03:00 | 187 | 0.427 | 0.920 [0.881, 0.947] | 0.589 | +0.331 | 0.897 [0.839, 0.936] (n=107) |
| OVN_HI_IN@0.90 | NQ | bar close, k<=8 (median first firing 00:00 ET) | 18:00-08:59 high already in | 13 | 0.030 | 0.769 [0.542, 0.904] | 0.331 | +0.438 | 0.800 [0.541, 0.931] (n=10) |
| OVN_HI_IN@0.90 | ES | bar close, k<=8 (median first firing 21:00 ET) | 18:00-08:59 high already in | 3 | 0.007 | 0.667 [0.254, 0.922] | 0.208 | +0.459 | no firings (n=0) |
| OVN_LO_IN@0.90 | NQ | bar close, k<=8 (median first firing 00:00 ET) | 18:00-08:59 low already in | 40 | 0.091 | 0.850 [0.735, 0.920] | 0.441 | +0.409 | 0.875 [0.684, 0.958] (n=16) |
| OVN_LO_IN@0.90 | ES | bar close, k<=8 (median first firing 00:00 ET) | 18:00-08:59 low already in | 38 | 0.087 | 0.868 [0.753, 0.934] | 0.425 | +0.443 | 0.870 [0.715, 0.947] (n=23) |
| BREAK_HI@0.70 | NQ | 17:xx ET | Asia trades above RTH high | 66 | 0.152 | 0.864 [0.780, 0.919] | 0.295 | +0.569 | 0.838 [0.716, 0.914] (n=37) |
| BREAK_HI@0.70 | ES | 17:xx ET | Asia trades above RTH high | 55 | 0.127 | 0.855 [0.760, 0.916] | 0.277 | +0.577 | 0.750 [0.598, 0.858] (n=28) |
| BREAK_LO@0.70 | NQ | 17:xx ET | Asia trades below RTH low | 43 | 0.099 | 0.791 [0.673, 0.874] | 0.227 | +0.564 | 0.769 [0.612, 0.876] (n=26) |
| BREAK_LO@0.70 | ES | 17:xx ET | Asia trades below RTH low | 34 | 0.079 | 0.912 [0.799, 0.964] | 0.247 | +0.665 | 0.920 [0.785, 0.973] (n=25) |
| HOLD_HI@0.10 | NQ | 17:xx ET | RTH high holds through Asia | 154 | 0.355 | 0.981 [0.952, 0.992] | 0.704 | +0.277 | 0.966 [0.919, 0.986] (n=89) |
| HOLD_HI@0.10 | ES | 17:xx ET | RTH high holds through Asia | 182 | 0.420 | 0.940 [0.904, 0.963] | 0.721 | +0.218 | 0.959 [0.912, 0.982] (n=98) |
| HOLD_LO@0.10 | NQ | 17:xx ET | RTH low holds through Asia | 171 | 0.394 | 0.936 [0.898, 0.960] | 0.774 | +0.161 | 0.900 [0.831, 0.943] (n=80) |
| HOLD_LO@0.10 | ES | 17:xx ET | RTH low holds through Asia | 139 | 0.321 | 0.942 [0.901, 0.967] | 0.758 | +0.185 | 0.938 [0.868, 0.972] (n=64) |

Verdict. Four signals are usable as stated: HI_IN@0.90 and LO_IN@0.90, read at the first firing of the night on the calibrated p_high_done / p_low_done that predict_now prints first, as claims that the Asia extreme is in; and HOLD_HI@0.10 and HOLD_LO@0.10 at 17:xx as claims that the RTH level holds through Asia (every threshold in this document is on the calibrated column the tool prints first; on the raw column HI_IN@0.90 is 0.928 on 222 NQ sessions and 0.940 on 215 ES sessions, LO_IN@0.90 0.901 on 252 and 0.916 on 262). The first HI_IN@0.90 / LO_IN@0.90 firing of a session is right 0.888-0.929 of the time over the full window (n = 200-267 per cell) against k-matched bases of 0.580-0.661, with every full-window lower CI bound at or above 0.852; in H2 (n = 133-173) it is 0.896-0.946 and in the last 12 months (n = 116-146) 0.904-0.946, with lower bounds at or above 0.851; in H1 (n = 67-94) it is 0.866-0.916 with lower bounds of 0.783-0.851. Every one of those sixteen cells has a lower bound at least 0.15 above its k-matched base. The 0.95 versions are the same two intra-session signals at a stricter threshold: closer to their nominal level (0.947-0.965) and firing in 35-43 % of sessions instead of 46-61 %. HOLD_HI@0.10 and HOLD_LO@0.10 are right 0.936-0.981 of the time against bases of 0.704-0.774 on 139-182 nights per symbol; their lift is modest (+0.16 to +0.28) because the RTH levels hold on most nights anyway. BREAK_HI@0.70 and BREAK_LO@0.70 carry the largest lift (+0.56 to +0.66 over bases of 0.23-0.29) but are usable only as a prior sized on 34-66 nights of evidence, not as a standalone call: their full-window CIs are 14-20 points wide and they contain the only degradations in the set (NQ BREAK_LO@0.70 0.929 in H1 to 0.724 [0.573, 0.837] (n = 29) in H2; ES BREAK_HI@0.70 0.750 (n = 28) in the last 12 months; BREAK_HI@0.70 0.600 (n = 10) in NQ and 0.667 (n = 6) in ES on Sunday reopens; section 7). OVN_LO_IN@0.90 is usable at 0.850-0.868 (n = 38-40) and fires in 9 % of sessions; OVN_HI_IN is not usable (13 NQ / 3 ES firings). The still-ahead flags HI_AHEAD / LO_AHEAD@0.10 fire almost only at the 19:00-20:00 closes and are right 0.890-0.940 (n = 160-187) against k-only bases of 0.589-0.702; the +0.24 to +0.33 lift has CIs that exclude the base, but no baseline that also conditions on where the first bar closed in its range was run here, the research report (section 5) finds that such a baseline absorbs most of the ensemble's skill at k = 0-2, and the flags are therefore not cleared as a sized signal. The mechanical translation of section 8 (an evaluation device, not a strategy: long at the first LO_IN@0.90 firing with the running low as stop and the running high as target, and the mirror short) reaches its target first in 0.69-0.82 of entries by 02:00 and is stopped first in 0.05-0.08, against 0.36-0.42 and 0.36-0.44 k-matched, but its mean P&L at exit is -1.0 to +3.4 bp per entry before costs with 90 % CIs that include zero in 7 of the 8 cells, because the target is 4-9 bp away and the stop 29-56 bp. The flags locate the extreme; they do not by themselves make a trade. The single most important caveat is that an Asia extreme is not an overnight extreme: at the first HI_IN@0.90 firing the running high survives Europe in only 0.541 (NQ) / 0.515 (ES) of sessions (overnight k-matched base 0.303 / 0.288), at the first LO_IN@0.90 firing the running low survives in 0.715 / 0.684 (base 0.442 / 0.416). Any use of these flags beyond 03:00 ET has to be sized on those numbers, not on the Asia hit rates.

## 2. Method

Data. The stored out-of-sample prediction files of the two detectors; the hourly panel (`{NQ,ES}_hourly_panel.csv`, running extremes and the bar of each extreme); the session table (`{NQ,ES}_extremes.csv`, reference close, levels, VIX, calendar flags); the raw hourly bars (`data/{NQ,ES}_1h.csv`, loaded through `sessions.load_hourly`) for the trade translation. The night of RTH date d consists of the 18:00-23:00 bars of the calendar day before the Globex date and the 00:00-02:00 bars of the Globex date; Europe is 03:00-08:00 of the Globex date. The running extremes implied by the panel (`run_hi_bp`, `run_lo_bp` applied to `ref_close`) were checked against the cumulative extremes of the raw bars on every out-of-sample session; the script stops if they disagree.

Walk-forward and why these numbers are out of sample. Each stored probability was emitted for a (session, bar) from models fitted on sessions strictly before that session, refitted monthly on an expanding window, with the first 120 sessions used for training only, and with the isotonic calibrator fitted only on earlier out-of-sample rows (calibrator active from 2025-04-01 for Detector A, 377 / 376 of the 439 / 438 sessions, and from 2025-06-02 for Detector B, 336 / 335 of the 434 / 433 nights; before those dates the shipped probability equals the raw ensemble). This document adds no fitting of any kind. The flags are fixed thresholds on the shipped probability columns (`p_high_done`, `p_low_done`, `p_ovn_high_done`, `p_ovn_low_done`; `high_above_rth_high__full__p_cal`, `low_below_rth_low__full__p_cal`); the raw-ensemble columns are evaluated beside them as a secondary version. Every threshold in this document applies to the calibrated column, which predict_now prints first (p=...); the raw ensemble is printed beside it in parentheses. The research report's advice to prefer the raw column (section 5) is a Brier statement; as a flag the two columns differ mainly in firing frequency (section 3). Among the "already in" flags the only cells where the raw column is more precise and outside the calibrated CI are NQ HI_IN@0.90 (raw 0.928 [0.894, 0.952] on 222 first firings against 0.888 [0.852, 0.916] on 267) and NQ HI_IN@0.95 (0.969 on 162 against 0.947 on 188); the one further such cell, ES LO_AHEAD@0.05, is in section 3. A desk that reads the raw number must use the raw rows of the tables. No threshold was chosen after looking at the outcomes; the thresholds are the ones named in the signal specification.

Flags, first firings and outcomes. HI_IN@p fires at a bar close when p_high_done >= p and claims that the Asia high is already in; the outcome is `high_done` at that row (1 if the running high at bar k equals the session high). LO_IN@p likewise with `low_done`. HI_AHEAD@q fires when p_high_done <= q and claims a new Asia high will print before 03:00; outcome 1 - `high_done`. OVN_HI_IN@p / OVN_LO_IN@p fire on p_ovn_high_done / p_ovn_low_done >= p and claim the 18:00-08:59 extreme is already in; outcome `overnight_high_done` / `overnight_low_done`. The Asia flags are evaluated at k = 0..7 (at k = 8 the label is 1 by definition), the overnight flags at k = 0..8. Two populations are reported: row level (every bar close at which the flag fires; a session can contribute up to eight rows for the Asia flags and nine for the overnight flags) and first firing (the first bar k at which the flag fires in a session; one event per session; sessions that never fire are counted in the denominator and reported as the share that fires). The median first-firing bar is the ordinary median of the first-firing k values; when it falls between two observed bars the table prints both bar closes (for example "5.5 (00:00-01:00)"). BREAK_HI@p fires at 17:xx when the calibrated P(high > RTH high) >= p; HOLD_HI@q when it is <= q; outcomes `high_above_rth_high__y` and its complement; BREAK_LO / HOLD_LO likewise. Secondary outcomes: for every Asia flag the overnight label of the same row ("hold through Europe"), for every overnight flag the Asia label.

Statistics. Session-level proportions (first firings, pre-Asia calls, stability cuts) carry Wilson 90 % intervals with sessions as the unit. Row-level proportions carry a session-block bootstrap interval (sessions resampled with replacement, 1,000 draws, seed 0, 5th and 95th percentiles of the pooled rate), because the rows of one session are not independent. The matched baselines of section 8 use the same bootstrap for the matched rates and for the difference conditional minus matched. The k-matched base of an intra-session flag is the mean over its fired rows of the k-only expanding baseline (`kbase_*`: the base rate of the label at the same bar index, computed from prior sessions only); the base of a pre-Asia call is the mean over the called nights of the expanding base rate of the label. Lift = hit rate minus base. Failure excess for an "already in" flag is measured from the raw bars as the eventual extreme relative to the running extreme at the firing bar (eventual / running - 1 for the high, in bp of the running high; running / eventual - 1 for the low, in bp of the eventual low) and relative to the firing bar's close, close-denominated on both sides (eventual / close - 1 for the high, which equals `remaining_up_bp`; 1 - eventual / close for the low, which equals -`remaining_down_bp`).

Exclusions, with counts. The out-of-sample files already exclude the roll and splice sessions (`asia_extremes.SPLICE_SESSIONS`: NQ 2024-06-21, 2024-12-20, 2025-03-21, 2025-09-16, 2025-09-17, 2025-12-16, 2025-12-17; ES 2025-09-16, 2025-09-17, 2025-12-16, 2025-12-17) and the nights with fewer than nine Asia bars. Within the Detector A window the session table holds 455 sessions per symbol; 16 (NQ) / 17 (ES) of them are absent from the prediction file: 12 / 13 short nights and the four roll sessions. Ten of the short nights per symbol are holiday eves whose 00:00-02:00 bars are absent from the feed (2024-12-23, 2025-01-17, 2025-02-14, 2025-07-02, 2025-11-26, 2025-12-23, 2026-02-13, 2026-04-02, 2026-06-18, 2026-07-02); the others are feed gaps: 2025-07-25 without its 18:00 and 19:00 bars (both symbols), 2026-07-16 without its 01:00-02:00 bars (NQ) / 02:00 bar (ES), and ES 2025-09-15 without its 19:00 bar (the per-night list is in `summary.json` under `_meta.populations`). One session per symbol (2026-04-17) has an incomplete Europe window and therefore no overnight label; its 9 rows are excluded from every overnight outcome and from the overnight-flag populations (438 / 437 sessions). The Detector B window starts 2025-01-02, so its population is the Detector A population less the five sessions of December 2024. Horizon B of the trade translation drops the one session per symbol without six Europe bars.

Leakage controls specific to this evaluation. Only decision-time columns define the flags (the probabilities at or before bar k; nothing from later bars). The k-only baseline, the base rates and the calibrators are expanding and strictly prior. The cuts (halves, last 12 months, Sunday reopen, VIX terciles, DST, calendar month) are descriptive partitions of the evaluation population, not inputs to any flag. The raw-bar race of section 8 starts at the close of the firing bar and uses only later bars. Nothing in `signal_backtest.py` writes back into the prediction files.

## 3. Intra-session "extreme already in" flags

Row level: every bar close at k <= 7 where the flag fires. The hit rates at 0.90 and 0.95 reproduce the cells of section 5 of the research report (NQ HI_IN@0.90: n = 842, 0.941; ES 708, 0.951; NQ LO_IN@0.90: 576, 0.944).

| flag | sym | n bar closes | n sessions | hit rate [90% CI] | k-matched base | lift | overnight label at the same rows [CI] (n) | raw ensemble: hit [CI] (n) |
|---|---|---|---|---|---|---|---|---|
| HI_IN@0.80 | NQ | 1041 | 312 | 0.914 [0.887, 0.935] | 0.624 | +0.290 | 0.580 [0.523, 0.633] (n=1040) | 0.925 [0.901, 0.946] (n=991) |
| HI_IN@0.80 | ES | 899 | 280 | 0.923 [0.897, 0.948] | 0.633 | +0.291 | 0.541 [0.481, 0.598] (n=898) | 0.926 [0.903, 0.951] (n=919) |
| LO_IN@0.80 | NQ | 1214 | 320 | 0.892 [0.863, 0.920] | 0.661 | +0.231 | 0.686 [0.637, 0.732] (n=1212) | 0.894 [0.866, 0.920] (n=1250) |
| LO_IN@0.80 | ES | 1226 | 317 | 0.908 [0.883, 0.931] | 0.667 | +0.241 | 0.684 [0.639, 0.731] (n=1220) | 0.911 [0.887, 0.934] (n=1297) |
| HI_IN@0.90 | NQ | 842 | 267 | 0.941 [0.919, 0.961] | 0.636 | +0.304 | 0.621 [0.567, 0.671] (n=841) | 0.962 [0.943, 0.978] (n=625) |
| HI_IN@0.90 | ES | 708 | 238 | 0.951 [0.929, 0.970] | 0.641 | +0.310 | 0.586 [0.527, 0.647] (n=707) | 0.967 [0.949, 0.982] (n=574) |
| LO_IN@0.90 | NQ | 576 | 200 | 0.944 [0.916, 0.968] | 0.688 | +0.256 | 0.792 [0.735, 0.839] (n=576) | 0.930 [0.902, 0.953] (n=814) |
| LO_IN@0.90 | ES | 753 | 238 | 0.952 [0.930, 0.972] | 0.688 | +0.264 | 0.751 [0.701, 0.801] (n=751) | 0.945 [0.923, 0.965] (n=871) |
| HI_IN@0.95 | NQ | 454 | 188 | 0.969 [0.948, 0.985] | 0.661 | +0.308 | 0.706 [0.645, 0.768] (n=453) | 0.984 [0.969, 0.995] (n=367) |
| HI_IN@0.95 | ES | 438 | 171 | 0.977 [0.959, 0.993] | 0.661 | +0.316 | 0.642 [0.567, 0.705] (n=438) | 0.984 [0.969, 0.997] (n=308) |
| LO_IN@0.95 | NQ | 405 | 154 | 0.965 [0.941, 0.985] | 0.694 | +0.272 | 0.857 [0.807, 0.902] (n=405) | 0.965 [0.940, 0.985] (n=514) |
| LO_IN@0.95 | ES | 486 | 176 | 0.973 [0.957, 0.989] | 0.698 | +0.275 | 0.800 [0.743, 0.853] (n=486) | 0.967 [0.947, 0.984] (n=551) |

First firing per session. This is what a user who acts on the first flag of the night experiences. It is lower than the row-level rate because the first firing is the earliest and least confident crossing (mean shipped probability at the first HI_IN@0.90 / LO_IN@0.90 firing: NQ 0.934 / 0.947, ES 0.937 / 0.938) and because later rows of the same session, which are mostly confirmations, no longer count.

| flag | sym | n fired / sessions | share | median first k (close ET) | hit rate [90% CI] | k-matched base | lift | hold through Europe [CI] (n) | overnight k-base | raw ensemble: hit [CI] (n) |
|---|---|---|---|---|---|---|---|---|---|---|
| HI_IN@0.80 | NQ | 312 / 439 | 0.711 | 4.0 (23:00) | 0.843 [0.806, 0.874] | 0.559 | +0.284 | 0.489 [0.442, 0.535] (n=311) | 0.290 | 0.866 [0.831, 0.895] (n=307) |
| HI_IN@0.80 | ES | 280 / 438 | 0.639 | 4.0 (23:00) | 0.875 [0.839, 0.904] | 0.582 | +0.293 | 0.455 [0.407, 0.504] (n=279) | 0.277 | 0.875 [0.839, 0.904] (n=288) |
| LO_IN@0.80 | NQ | 320 / 439 | 0.729 | 3.0 (22:00) | 0.838 [0.801, 0.869] | 0.593 | +0.245 | 0.589 [0.543, 0.634] (n=319) | 0.407 | 0.837 [0.801, 0.868] (n=331) |
| LO_IN@0.80 | ES | 317 / 438 | 0.724 | 3.0 (22:00) | 0.849 [0.813, 0.879] | 0.595 | +0.254 | 0.611 [0.565, 0.655] (n=316) | 0.389 | 0.848 [0.813, 0.878] (n=330) |
| HI_IN@0.90 | NQ | 267 / 439 | 0.608 | 4.0 (23:00) | 0.888 [0.852, 0.916] | 0.580 | +0.308 | 0.541 [0.491, 0.591] (n=266) | 0.303 | 0.928 [0.894, 0.952] (n=222) |
| HI_IN@0.90 | ES | 238 / 438 | 0.543 | 5.0 (00:00) | 0.916 [0.882, 0.941] | 0.604 | +0.312 | 0.515 [0.462, 0.568] (n=237) | 0.288 | 0.940 [0.907, 0.961] (n=215) |
| LO_IN@0.90 | NQ | 200 / 439 | 0.456 | 5.0 (00:00) | 0.910 [0.871, 0.938] | 0.661 | +0.249 | 0.715 [0.660, 0.764] (n=200) | 0.442 | 0.901 [0.865, 0.928] (n=252) |
| LO_IN@0.90 | ES | 238 / 438 | 0.543 | 5.0 (00:00) | 0.929 [0.896, 0.951] | 0.649 | +0.279 | 0.684 [0.632, 0.731] (n=237) | 0.416 | 0.916 [0.883, 0.940] (n=262) |
| HI_IN@0.95 | NQ | 188 / 439 | 0.428 | 5.0 (00:00) | 0.947 [0.913, 0.968] | 0.637 | +0.310 | 0.647 [0.588, 0.702] (n=187) | 0.328 | 0.969 [0.938, 0.985] (n=162) |
| HI_IN@0.95 | ES | 171 / 438 | 0.390 | 5.0 (00:00) | 0.965 [0.934, 0.982] | 0.637 | +0.328 | 0.579 [0.516, 0.639] (n=171) | 0.303 | 0.971 [0.936, 0.987] (n=136) |
| LO_IN@0.95 | NQ | 154 / 439 | 0.351 | 5.5 (00:00-01:00) | 0.948 [0.910, 0.970] | 0.678 | +0.270 | 0.805 [0.748, 0.852] (n=154) | 0.450 | 0.947 [0.913, 0.968] (n=187) |
| LO_IN@0.95 | ES | 176 / 438 | 0.402 | 5.0 (00:00) | 0.949 [0.914, 0.970] | 0.675 | +0.274 | 0.750 [0.693, 0.800] (n=176) | 0.427 | 0.942 [0.907, 0.964] (n=189) |

By bar of the first firing (calibrated, 0.90 flags). The k-matched base climbs from 0.33-0.43 at k = 1 to 0.76-0.80 at k = 7. In every cell with n >= 17 the hit rate is 0.82-1.00 except NQ LO_IN@0.90 at k = 4 (0.818 [0.685, 0.903], n = 33); the k = 0-1 cells (n = 2-16) range from 0.000 to 1.000 and are listed for completeness only. The lift is +0.24 to +0.65 at k = 1-2 and +0.12 to +0.20 at k = 7 (02:00 close, one bar left). The weakest cells with n >= 25 are NQ LO_IN@0.90 at k = 4 (0.818, n = 33), ES LO_IN@0.90 at k = 3 (0.821 [0.676, 0.910], n = 28), ES HI_IN@0.90 at k = 4 (0.833 [0.709, 0.911], n = 36) and NQ HI_IN@0.90 at k = 4 (0.837 [0.725, 0.909], n = 43).

| first-firing k | close ET | NQ HI_IN@0.90: n / hit [CI] / base | NQ LO_IN@0.90 | ES HI_IN@0.90 | ES LO_IN@0.90 |
|---|---|---|---|---|---|
| 0 | 19:00 | 0 / n/a / n/a | 7 / 0.857 [0.548, 0.967] / 0.333 | 2 / 0.000 [0.000, 0.575] / 0.277 | 8 / 1.000 [0.747, 1.000] / 0.340 |
| 1 | 20:00 | 16 / 0.750 [0.545, 0.882] / 0.331 | 6 / 0.667 [0.347, 0.883] / 0.429 | 11 / 1.000 [0.803, 1.000] / 0.352 | 11 / 0.727 [0.480, 0.885] / 0.404 |
| 2 | 21:00 | 40 / 0.950 [0.860, 0.983] / 0.416 | 17 / 0.941 [0.774, 0.987] / 0.508 | 34 / 0.941 [0.837, 0.980] / 0.442 | 25 / 0.880 [0.735, 0.951] / 0.497 |
| 3 | 22:00 | 49 / 0.898 [0.805, 0.949] / 0.505 | 24 / 0.917 [0.777, 0.972] / 0.576 | 33 / 1.000 [0.924, 1.000] / 0.525 | 28 / 0.821 [0.676, 0.910] / 0.588 |
| 4 | 23:00 | 43 / 0.837 [0.725, 0.909] / 0.563 | 33 / 0.818 [0.685, 0.903] / 0.643 | 36 / 0.833 [0.709, 0.911] / 0.586 | 46 / 0.913 [0.820, 0.960] / 0.643 |
| 5 | 00:00 | 32 / 0.906 [0.787, 0.962] / 0.627 | 28 / 0.929 [0.806, 0.976] / 0.669 | 35 / 0.857 [0.734, 0.929] / 0.629 | 37 / 0.946 [0.849, 0.982] / 0.683 |
| 6 | 01:00 | 39 / 0.897 [0.790, 0.953] / 0.685 | 33 / 0.939 [0.832, 0.980] / 0.708 | 25 / 0.960 [0.839, 0.991] / 0.674 | 34 / 1.000 [0.926, 1.000] / 0.719 |
| 7 | 02:00 | 48 / 0.896 [0.801, 0.948] / 0.773 | 52 / 0.962 [0.890, 0.987] / 0.796 | 62 / 0.935 [0.864, 0.971] / 0.759 | 49 / 1.000 [0.948, 1.000] / 0.800 |

Failure analysis (first firings whose claim failed: the Asia extreme printed later). The new extreme printed a median 3-4 bars after the firing, in the very next bar in 12-23 % of the failures, and a median 7.7-14.1 bp beyond the running extreme at 0.90 (p90 23.7-53.0 bp); measured from the firing bar's close, which is typically well away from the running extreme, the median excess is 32-60 bp. The failures are larger in NQ than in ES in bp terms, as its ranges are. Every failed first-firing event of every flag and both probability versions is written to `research/extremes/validation/failures.csv` (872 rows, 440 for the calibrated version) with sym, date, flag, version, k, p, k-matched base, excess beyond the bar close (close-denominated on both sides, section 2), excess beyond the running extreme, the bar of the new extreme, bars until it and the secondary outcome (`secondary_outcome`, named in `secondary_outcome_label`: the overnight label for the Asia flags, the Asia label for the overnight flags, since at an overnight-flag failure the overnight label is 0 by construction); for the still-ahead flags the excess fields are empty because their failure is the absence of a new extreme.

| flag | sym | failures / firings | excess beyond bar close, bp (p50 / p75 / p90) | excess beyond running extreme, bp (p50 / p75 / p90) | bars until new extreme (p50 / p75 / p90) | share in the next bar |
|---|---|---|---|---|---|---|
| HI_IN@0.90 | NQ | 30 / 267 | 54.5 / 67.4 / 90.6 | 14.1 / 30.2 / 38.3 | 3.0 / 5.0 / 6.0 | 0.233 |
| HI_IN@0.90 | ES | 20 / 238 | 32.3 / 45.3 / 50.4 | 7.8 / 15.9 / 23.7 | 3.0 / 4.0 / 6.0 | 0.200 |
| LO_IN@0.90 | NQ | 18 / 200 | 60.0 / 103.9 / 166.6 | 10.2 / 28.0 / 53.0 | 3.5 / 4.0 / 5.6 | 0.167 |
| LO_IN@0.90 | ES | 17 / 238 | 51.1 / 75.1 / 99.7 | 7.7 / 20.7 / 46.9 | 4.0 / 5.0 / 6.4 | 0.118 |
| HI_IN@0.95 | NQ | 10 / 188 | 56.5 / 72.0 / 97.7 | 8.3 / 18.5 / 32.2 | 2.0 / 4.8 / 5.1 | 0.200 |
| HI_IN@0.95 | ES | 6 / 171 | 31.6 / 43.0 / 69.3 | 6.2 / 7.2 / 11.7 | 3.5 / 4.0 / 4.5 | 0.000 |
| LO_IN@0.95 | NQ | 8 / 154 | 110.1 / 166.3 / 187.2 | 27.7 / 36.3 / 53.0 | 3.5 / 4.2 / 5.6 | 0.000 |
| LO_IN@0.95 | ES | 9 / 176 | 62.3 / 91.0 / 122.3 | 20.0 / 21.7 / 48.5 | 3.0 / 4.0 / 6.0 | 0.222 |

Raw versus calibrated, in one line: at the same threshold the raw ensemble fires less often on the high side and more often on the low side (row level, NQ HI_IN@0.90: raw 0.962 on 625 rows against calibrated 0.941 on 842; NQ LO_IN@0.90: raw 0.930 on 814 against 0.944 on 576), and at the first firing of the six "already in" flags the raw rate differs from the calibrated one by -0.013 to +0.040 and lies inside the calibrated CI except for NQ HI_IN@0.90 and NQ HI_IN@0.95 (raw 0.928 and 0.969 against calibrated upper bounds of 0.916 and 0.968); for the still-ahead and overnight flags the differences run from -0.011 to +0.133 on small cells (ES LO_AHEAD@0.05: raw 1.000 on 22 sessions against calibrated 0.913 [0.856, 0.948]; ES OVN_HI_IN@0.90: raw 0.800 on 10 against 0.667 on 3). The two columns are calibrated differently rather than one being better, and the choice between them is a choice of firing frequency.

## 4. "Still ahead" flags

HI_AHEAD@q / LO_AHEAD@q claim that a new Asia extreme will print before 03:00. They fire almost exclusively at the first one or two bar closes (median first firing k = 0-1, 19:00-20:00 ET), where the base rate of "still ahead" is already 0.59-0.71; the hit rates of 0.88-0.95 therefore carry lifts of +0.21 to +0.33, lower than the "already in" flags despite the higher nominal confidence, and every first-firing CI of the 0.10 flags excludes its base. The k-matched base conditions on the bar index only, so the lift is not a statement that the session is early; what has not been done is to measure these flags against a baseline that also conditions on where the first bar closed in its range, which the research report (section 5) finds absorbs most of the ensemble's skill at k = 0-2. Until that is done the lift over the k-only base is an upper bound on what the flags add for a reader who already looks at the first bar's close location, and the flags are not cleared as a sized signal. HI_AHEAD@0.05 fires in only 9 ES sessions because the ES isotonic step rarely maps below 0.05. Whenever an Asia extreme is still ahead the overnight extreme is still ahead by construction, so the overnight outcome of these flags is at least their Asia outcome and is not reported separately.

| flag | sym | row level: n / hit [CI] / base | first firings (share) | median first k (close ET) | first-firing hit [90% CI] | k-matched base | lift |
|---|---|---|---|---|---|---|---|
| HI_AHEAD@0.10 | NQ | 305 / 0.938 [0.913, 0.960] / 0.649 | 183 (0.417) | 0.0 (19:00) | 0.940 [0.904, 0.963] | 0.702 | +0.238 |
| HI_AHEAD@0.10 | ES | 266 / 0.917 [0.888, 0.944] / 0.607 | 160 (0.365) | 1.0 (20:00) | 0.925 [0.883, 0.953] | 0.658 | +0.267 |
| LO_AHEAD@0.10 | NQ | 263 / 0.909 [0.875, 0.938] / 0.538 | 164 (0.374) | 0.5 (19:00-20:00) | 0.890 [0.844, 0.924] | 0.590 | +0.300 |
| LO_AHEAD@0.10 | ES | 303 / 0.931 [0.907, 0.956] / 0.537 | 187 (0.427) | 1.0 (20:00) | 0.920 [0.881, 0.947] | 0.589 | +0.331 |
| HI_AHEAD@0.05 | NQ | 103 / 0.951 [0.915, 0.982] / 0.676 | 73 (0.166) | 0.0 (19:00) | 0.945 [0.883, 0.975] | 0.708 | +0.237 |
| HI_AHEAD@0.05 | ES | 15 / 0.933 [0.800, 1.000] / 0.639 | 9 (0.021) | 0.0 (19:00) | 0.889 [0.623, 0.975] | 0.676 | +0.213 |
| LO_AHEAD@0.05 | NQ | 40 / 0.875 [0.775, 0.951] / 0.576 | 33 (0.075) | 1.0 (20:00) | 0.879 [0.756, 0.944] | 0.598 | +0.281 |
| LO_AHEAD@0.05 | ES | 173 / 0.919 [0.884, 0.953] / 0.549 | 103 (0.235) | 0.0 (19:00) | 0.913 [0.856, 0.948] | 0.606 | +0.307 |

## 5. Overnight flags

The overnight-high flag is rare because a running Asia high rarely survives the Europe session: the overnight k-matched base is 0.21-0.34 at the bars where the flag fires, and the walk-forward model reaches 0.90 in 13 NQ / 3 ES sessions (0.80 in 47 / 8). Those counts do not support a statement about its hit rate; the row-level CIs span 0.29-1.00 in ES. The overnight-low flag fires in 38-40 sessions at 0.90 (83-97 at 0.80), median first firing at the 00:00 close, and is right 0.850 (NQ) / 0.868 (ES) of the time against bases of 0.441 / 0.425; at 0.80 it is right 0.794 / 0.795. When it fires, the Asia low is in 0.918-0.952 of the time, so it is a stricter version of LO_IN that trades frequency for the Europe hold.

| flag | sym | row level: n / hit [CI] / base | first firings / sessions (share) | median first k (close ET) | first-firing hit [90% CI] | k-matched base | lift | Asia label at the same events [CI] |
|---|---|---|---|---|---|---|---|---|
| OVN_HI_IN@0.80 | NQ | 127 / 0.827 [0.724, 0.926] / 0.349 | 47 / 438 (0.107) | 6.0 (01:00) | 0.787 [0.675, 0.868] | 0.340 | +0.448 | 0.979 [0.910, 0.995] |
| OVN_HI_IN@0.80 | ES | 28 / 0.714 [0.333, 1.000] / 0.265 | 8 / 437 (0.018) | 3.0 (21:00-23:00) | 0.750 [0.460, 0.913] | 0.244 | +0.506 | 1.000 [0.747, 1.000] |
| OVN_HI_IN@0.90 | NQ | 30 / 0.833 [0.636, 0.975] / 0.342 | 13 / 438 (0.030) | 5.0 (00:00) | 0.769 [0.542, 0.904] | 0.331 | +0.438 | 1.000 [0.828, 1.000] |
| OVN_HI_IN@0.90 | ES | 14 / 0.643 [0.286, 1.000] / 0.264 | 3 / 437 (0.007) | 2.0 (21:00) | 0.667 [0.254, 0.922] | 0.208 | +0.459 | 1.000 [0.526, 1.000] |
| OVN_LO_IN@0.80 | NQ | 331 / 0.843 [0.772, 0.908] / 0.465 | 97 / 438 (0.221) | 5.0 (00:00) | 0.794 [0.719, 0.853] | 0.442 | +0.352 | 0.918 [0.859, 0.953] |
| OVN_LO_IN@0.80 | ES | 291 / 0.869 [0.801, 0.926] / 0.444 | 83 / 437 (0.190) | 5.0 (00:00) | 0.795 [0.714, 0.858] | 0.418 | +0.378 | 0.952 [0.897, 0.978] |
| OVN_LO_IN@0.90 | NQ | 133 / 0.865 [0.758, 0.952] / 0.459 | 40 / 438 (0.091) | 5.0 (00:00) | 0.850 [0.735, 0.920] | 0.441 | +0.409 | 0.925 [0.827, 0.970] |
| OVN_LO_IN@0.90 | ES | 119 / 0.916 [0.835, 0.976] / 0.441 | 38 / 437 (0.087) | 5.0 (00:00) | 0.868 [0.753, 0.934] | 0.425 | +0.443 | 0.947 [0.853, 0.982] |

The bridge from the Asia flags to the overnight label, at the first firing: the Asia high flagged at 0.90 holds through Europe only about half of the time, the Asia low about two thirds; the 0.95 flags add 6-11 points. These are the numbers that govern any position kept open past 03:00 ET.

| flag (first firing) | sym | n | Asia label hit [CI] | Asia k-base | overnight label hit [CI] (n) | overnight k-base |
|---|---|---|---|---|---|---|
| HI_IN@0.90 | NQ | 267 | 0.888 [0.852, 0.916] | 0.580 | 0.541 [0.491, 0.591] (n=266) | 0.303 |
| HI_IN@0.90 | ES | 238 | 0.916 [0.882, 0.941] | 0.604 | 0.515 [0.462, 0.568] (n=237) | 0.288 |
| HI_IN@0.95 | NQ | 188 | 0.947 [0.913, 0.968] | 0.637 | 0.647 [0.588, 0.702] (n=187) | 0.328 |
| HI_IN@0.95 | ES | 171 | 0.965 [0.934, 0.982] | 0.637 | 0.579 [0.516, 0.639] (n=171) | 0.303 |
| LO_IN@0.90 | NQ | 200 | 0.910 [0.871, 0.938] | 0.661 | 0.715 [0.660, 0.764] (n=200) | 0.442 |
| LO_IN@0.90 | ES | 238 | 0.929 [0.896, 0.951] | 0.649 | 0.684 [0.632, 0.731] (n=237) | 0.416 |
| LO_IN@0.95 | NQ | 154 | 0.948 [0.910, 0.970] | 0.678 | 0.805 [0.748, 0.852] (n=154) | 0.450 |
| LO_IN@0.95 | ES | 176 | 0.949 [0.914, 0.970] | 0.675 | 0.750 [0.693, 0.800] (n=176) | 0.427 |

## 6. Pre-Asia level calls, envelope coverage and the joint map call

Level calls at 17:xx ET (one per night). The BREAK calls are rare (8-15 % of nights at 0.70, 4-9 % at 0.90) and right 0.78-1.00 of the time against bases of 0.23-0.30; the HOLD calls are frequent (22-42 % of nights) and right 0.94-0.98 of the time against bases of 0.70-0.77. The raw ensemble is at least as accurate as the calibrated column on every BREAK call and fires less often (NQ BREAK_HI@0.70: 0.914 on 58 nights against 0.864 on 66), which is consistent with the research report's note that the isotonic step never helped Detector B.

| call | sym | n called / nights | share | hit rate [90% CI] | base (expanding rate) | lift | raw ensemble: hit [CI] (n) |
|---|---|---|---|---|---|---|---|
| BREAK_HI@0.70 | NQ | 66 / 434 | 0.152 | 0.864 [0.780, 0.919] | 0.295 | +0.569 | 0.914 [0.833, 0.957] (n=58) |
| BREAK_HI@0.70 | ES | 55 / 433 | 0.127 | 0.855 [0.760, 0.916] | 0.277 | +0.577 | 0.900 [0.808, 0.950] (n=50) |
| BREAK_HI@0.80 | NQ | 58 / 434 | 0.134 | 0.897 [0.812, 0.946] | 0.294 | +0.603 | 0.927 [0.830, 0.970] (n=41) |
| BREAK_HI@0.80 | ES | 49 / 433 | 0.113 | 0.857 [0.756, 0.921] | 0.280 | +0.577 | 0.939 [0.832, 0.980] (n=33) |
| BREAK_HI@0.90 | NQ | 37 / 434 | 0.085 | 0.892 [0.780, 0.951] | 0.298 | +0.594 | 0.957 [0.827, 0.990] (n=23) |
| BREAK_HI@0.90 | ES | 32 / 433 | 0.074 | 0.906 [0.787, 0.962] | 0.282 | +0.624 | 1.000 [0.863, 1.000] (n=17) |
| BREAK_LO@0.70 | NQ | 43 / 434 | 0.099 | 0.791 [0.673, 0.874] | 0.227 | +0.564 | 0.879 [0.756, 0.944] (n=33) |
| BREAK_LO@0.70 | ES | 34 / 433 | 0.079 | 0.912 [0.799, 0.964] | 0.247 | +0.665 | 1.000 [0.895, 1.000] (n=23) |
| BREAK_LO@0.80 | NQ | 27 / 434 | 0.062 | 0.778 [0.624, 0.880] | 0.229 | +0.549 | 1.000 [0.847, 1.000] (n=15) |
| BREAK_LO@0.80 | ES | 30 / 433 | 0.069 | 0.967 [0.864, 0.993] | 0.247 | +0.720 | 1.000 [0.847, 1.000] (n=15) |
| BREAK_LO@0.90 | NQ | 17 / 434 | 0.039 | 0.941 [0.774, 0.987] | 0.232 | +0.709 | 1.000 [0.747, 1.000] (n=8) |
| BREAK_LO@0.90 | ES | 22 / 433 | 0.051 | 1.000 [0.890, 1.000] | 0.250 | +0.750 | 1.000 [0.721, 1.000] (n=7) |
| HOLD_HI@0.10 | NQ | 154 / 434 | 0.355 | 0.981 [0.952, 0.992] | 0.704 | +0.277 | 0.979 [0.948, 0.991] (n=140) |
| HOLD_HI@0.10 | ES | 182 / 433 | 0.420 | 0.940 [0.904, 0.963] | 0.721 | +0.218 | 0.974 [0.943, 0.988] (n=154) |
| HOLD_HI@0.05 | NQ | 140 / 434 | 0.323 | 0.979 [0.948, 0.991] | 0.702 | +0.277 | 0.987 [0.943, 0.997] (n=76) |
| HOLD_HI@0.05 | ES | 113 / 433 | 0.261 | 0.973 [0.935, 0.989] | 0.720 | +0.254 | 0.979 [0.938, 0.993] (n=94) |
| HOLD_LO@0.10 | NQ | 171 / 434 | 0.394 | 0.936 [0.898, 0.960] | 0.774 | +0.161 | 0.937 [0.901, 0.960] (n=189) |
| HOLD_LO@0.10 | ES | 139 / 433 | 0.321 | 0.942 [0.901, 0.967] | 0.758 | +0.185 | 0.940 [0.902, 0.964] (n=167) |
| HOLD_LO@0.05 | NQ | 138 / 434 | 0.318 | 0.957 [0.918, 0.977] | 0.773 | +0.183 | 0.983 [0.950, 0.994] (n=118) |
| HOLD_LO@0.05 | ES | 93 / 433 | 0.215 | 0.946 [0.894, 0.974] | 0.757 | +0.189 | 0.967 [0.921, 0.987] (n=92) |

Envelope coverage (full Detector B window; realised value against the shipped q20 / q50 / q80 and against the unconditional expanding quantiles). The range envelope is not better calibrated than the unconditional one: both cover 0.55-0.60 of nights (nominal 0.60) and both under-cover the upper tail (0.24-0.31 of nights above q80, nominal 0.20), the model slightly more so in NQ. The model's median is more accurate (MAE 28.2 against 35.9 bp in NQ, 19.1 against 25.2 bp in ES). For hi_bp and lo_bp the model and base envelopes are indistinguishable (coverage 0.54-0.59 for both, MAE within 1.4 bp), as the research report's near-zero quantile skills implied. In the last 12 months (n = 233) the NQ range envelope covered 0.549 with 0.356 of nights above q80 (base 0.609 and 0.330), the ES one 0.648 with 0.206 above (base 0.652 and 0.215): the under-coverage of the upper tail is a feature of the recent regime, not of the model alone. The shipped quantiles are fitted separately per level and are not monotone on every night: q20 > q50 or q50 > q80 on 9 (NQ) / 14 (ES) rng_bp nights, 13 / 11 lo_bp nights and 2 / 2 hi_bp nights, and on one rng_bp night per symbol q20 > q80, so that night cannot fall "inside"; the base quantiles are monotone on every night. Coverage is computed on the quantiles as shipped (the counts are in `envelope_coverage.csv`), and the three shares of every row sum to one.

| sym | quantity | source | n | below q20 [CI] (nominal 0.200) | inside [q20, q80] [CI] (nominal 0.600) | above q80 [CI] (nominal 0.200) | MAE of q50, bp |
|---|---|---|---|---|---|---|---|
| NQ | rng_bp | model | 434 | 0.136 [0.111, 0.165] | 0.553 [0.514, 0.592] | 0.311 [0.276, 0.349] | 28.2 |
| NQ | rng_bp | base | 434 | 0.136 [0.111, 0.165] | 0.569 [0.530, 0.608] | 0.295 [0.260, 0.332] | 35.9 |
| NQ | hi_bp | model | 434 | 0.184 [0.156, 0.217] | 0.592 [0.553, 0.630] | 0.224 [0.192, 0.258] | 29.8 |
| NQ | hi_bp | base | 434 | 0.177 [0.149, 0.210] | 0.558 [0.518, 0.596] | 0.265 [0.232, 0.301] | 30.4 |
| NQ | lo_bp | model | 434 | 0.260 [0.227, 0.296] | 0.541 [0.502, 0.580] | 0.198 [0.169, 0.231] | 35.2 |
| NQ | lo_bp | base | 434 | 0.260 [0.227, 0.296] | 0.567 [0.527, 0.605] | 0.173 [0.145, 0.205] | 36.6 |
| ES | rng_bp | model | 433 | 0.152 [0.126, 0.183] | 0.603 [0.564, 0.641] | 0.245 [0.212, 0.280] | 19.1 |
| ES | rng_bp | base | 433 | 0.143 [0.118, 0.173] | 0.591 [0.552, 0.629] | 0.266 [0.232, 0.302] | 25.2 |
| ES | hi_bp | model | 433 | 0.208 [0.178, 0.242] | 0.561 [0.522, 0.600] | 0.231 [0.199, 0.266] | 20.7 |
| ES | hi_bp | base | 433 | 0.180 [0.152, 0.212] | 0.580 [0.540, 0.618] | 0.240 [0.208, 0.276] | 20.9 |
| ES | lo_bp | model | 433 | 0.256 [0.223, 0.292] | 0.550 [0.510, 0.589] | 0.194 [0.165, 0.227] | 24.2 |
| ES | lo_bp | base | 433 | 0.254 [0.221, 0.290] | 0.554 [0.515, 0.593] | 0.192 [0.163, 0.225] | 25.2 |

Joint map call. On the 7-14 % of nights where BREAK_HI@0.70 and HOLD_LO@0.10 coincide, exactly "extends up, low holds" happened 0.900 (NQ, 60 nights) and 0.843 (ES, 51) of the time against unconditional rates of 0.329 / 0.284; the mirror call happened 0.800 (NQ, 40) and 0.906 (ES, 32) of the time against 0.267 / 0.247. In NQ no joint call extended and also broke the other side (one night in ES). Of the remaining failures, 4 NQ / 6 ES nights (up call) and 8 NQ / 3 ES nights (down call) extended in neither direction, and 2 NQ / 1 ES nights (up call) did the opposite of the call: the low that was called to hold broke and the high did not extend.

| joint call | sym | n called / nights | exactly that [90% CI] | extended, other side also broke | neither broke | only the other side broke | unconditional rate of the exact outcome |
|---|---|---|---|---|---|---|---|
| BREAK_HI@0.70 & HOLD_LO@0.10: extends up, low holds | NQ | 60 / 434 | 0.900 [0.818, 0.947] | 0 | 4 | 2 | 0.329 |
| BREAK_LO@0.70 & HOLD_HI@0.10: extends down, high holds | NQ | 40 / 434 | 0.800 [0.679, 0.883] | 0 | 8 | 0 | 0.267 |
| BREAK_HI@0.70 & HOLD_LO@0.10: extends up, low holds | ES | 51 / 433 | 0.843 [0.742, 0.909] | 1 | 6 | 1 | 0.284 |
| BREAK_LO@0.70 & HOLD_HI@0.10: extends down, high holds | ES | 32 / 433 | 0.906 [0.787, 0.962] | 0 | 3 | 0 | 0.247 |

## 7. Stability

Headline flags, calibrated version, first firing for the intra-session flags; cells are hit rate [90 % CI] (n fired). VIX terciles are terciles of VIX over the out-of-sample population of each detector (NQ cut points 16.41 and 18.67 for Detector A, 16.41 and 18.68 for Detector B; ES 16.41 / 18.68 and 16.41 / 18.69; the overnight flags, whose population lacks the one session without an overnight label, cut at 16.41 / 18.68 in both symbols). The second table gives the base rate (and the number of sessions in the cut) beside each window cell; the per-k view is in section 3 and `first_firing_by_k.csv`; DST cuts and every other cell are in `stability_cuts.csv`.

| flag | sym | full | last 12m | H1 | H2 | Sunday reopen | weeknight | VIX T1 (low) | VIX T2 | VIX T3 (high) |
|---|---|---|---|---|---|---|---|---|---|---|
| HI_IN@0.90 | NQ | 0.888 [0.852, 0.916] (267) | 0.904 [0.856, 0.937] (146) | 0.872 [0.805, 0.919] (94) | 0.896 [0.851, 0.928] (173) | 0.891 [0.793, 0.946] (46) | 0.887 [0.847, 0.917] (221) | 0.926 [0.863, 0.961] (81) | 0.890 [0.825, 0.933] (91) | 0.853 [0.783, 0.903] (95) |
| HI_IN@0.90 | ES | 0.916 [0.882, 0.941] (238) | 0.922 [0.875, 0.953] (129) | 0.916 [0.851, 0.954] (83) | 0.916 [0.872, 0.946] (155) | 0.923 [0.822, 0.969] (39) | 0.915 [0.876, 0.942] (199) | 0.910 [0.842, 0.951] (78) | 0.923 [0.858, 0.960] (78) | 0.915 [0.850, 0.953] (82) |
| LO_IN@0.90 | NQ | 0.910 [0.871, 0.938] (200) | 0.931 [0.882, 0.961] (116) | 0.866 [0.783, 0.920] (67) | 0.932 [0.887, 0.960] (133) | 0.958 [0.882, 0.986] (48) | 0.895 [0.847, 0.929] (152) | 0.915 [0.836, 0.958] (59) | 0.919 [0.843, 0.960] (62) | 0.899 [0.829, 0.942] (79) |
| LO_IN@0.90 | ES | 0.929 [0.896, 0.951] (238) | 0.946 [0.904, 0.971] (130) | 0.901 [0.837, 0.942] (91) | 0.946 [0.906, 0.969] (147) | 0.942 [0.864, 0.977] (52) | 0.925 [0.886, 0.951] (186) | 0.945 [0.883, 0.975] (73) | 0.935 [0.873, 0.968] (77) | 0.909 [0.846, 0.948] (88) |
| OVN_LO_IN@0.90 | NQ | 0.850 [0.735, 0.920] (40) | 0.875 [0.684, 0.958] (16) | 0.824 [0.631, 0.927] (17) | 0.870 [0.715, 0.947] (23) | 0.875 [0.684, 0.958] (16) | 0.833 [0.676, 0.923] (24) | 1.000 [0.649, 1.000] (5) | 0.900 [0.652, 0.977] (10) | 0.800 [0.642, 0.899] (25) |
| OVN_LO_IN@0.90 | ES | 0.868 [0.753, 0.934] (38) | 0.870 [0.715, 0.947] (23) | 0.889 [0.623, 0.975] (9) | 0.862 [0.726, 0.937] (29) | 0.941 [0.774, 0.987] (17) | 0.810 [0.637, 0.911] (21) | 0.857 [0.548, 0.967] (7) | 0.750 [0.460, 0.913] (8) | 0.913 [0.768, 0.971] (23) |
| BREAK_HI@0.70 | NQ | 0.864 [0.780, 0.919] (66) | 0.838 [0.716, 0.914] (37) | 0.900 [0.738, 0.966] (20) | 0.848 [0.742, 0.915] (46) | 0.600 [0.352, 0.806] (10) | 0.911 [0.828, 0.956] (56) | 0.806 [0.667, 0.896] (31) | 1.000 [0.895, 1.000] (23) | 0.750 [0.513, 0.895] (12) |
| BREAK_HI@0.70 | ES | 0.855 [0.760, 0.916] (55) | 0.750 [0.598, 0.858] (28) | 0.950 [0.804, 0.989] (20) | 0.800 [0.669, 0.888] (35) | 0.667 [0.347, 0.883] (6) | 0.878 [0.780, 0.935] (49) | 0.857 [0.691, 0.941] (21) | 0.833 [0.648, 0.931] (18) | 0.875 [0.684, 0.958] (16) |
| BREAK_LO@0.70 | NQ | 0.791 [0.673, 0.874] (43) | 0.769 [0.612, 0.876] (26) | 0.929 [0.734, 0.984] (14) | 0.724 [0.573, 0.837] (29) | 0.750 [0.460, 0.913] (8) | 0.800 [0.669, 0.888] (35) | 0.667 [0.347, 0.883] (6) | 0.818 [0.573, 0.938] (11) | 0.808 [0.654, 0.903] (26) |
| BREAK_LO@0.70 | ES | 0.912 [0.799, 0.964] (34) | 0.920 [0.785, 0.973] (25) | 0.875 [0.589, 0.972] (8) | 0.923 [0.792, 0.974] (26) | 1.000 [0.649, 1.000] (5) | 0.897 [0.768, 0.958] (29) | 1.000 [0.689, 1.000] (6) | 0.800 [0.541, 0.931] (10) | 0.944 [0.785, 0.988] (18) |
| HOLD_HI@0.10 | NQ | 0.981 [0.952, 0.992] (154) | 0.966 [0.919, 0.986] (89) | 1.000 [0.948, 1.000] (49) | 0.971 [0.931, 0.989] (105) | 0.929 [0.806, 0.976] (28) | 0.992 [0.965, 0.998] (126) | 0.974 [0.890, 0.994] (38) | 0.979 [0.912, 0.995] (48) | 0.985 [0.937, 0.997] (68) |
| HOLD_HI@0.10 | ES | 0.940 [0.904, 0.963] (182) | 0.959 [0.912, 0.982] (98) | 0.906 [0.829, 0.951] (64) | 0.958 [0.916, 0.979] (118) | 0.921 [0.818, 0.968] (38) | 0.944 [0.904, 0.968] (144) | 0.957 [0.879, 0.986] (47) | 0.900 [0.818, 0.947] (60) | 0.960 [0.904, 0.984] (75) |
| HOLD_LO@0.10 | NQ | 0.936 [0.898, 0.960] (171) | 0.900 [0.831, 0.943] (80) | 0.986 [0.938, 0.997] (69) | 0.902 [0.843, 0.940] (102) | 0.889 [0.752, 0.955] (27) | 0.944 [0.904, 0.968] (144) | 0.931 [0.855, 0.969] (58) | 0.950 [0.881, 0.980] (60) | 0.925 [0.842, 0.966] (53) |
| HOLD_LO@0.10 | ES | 0.942 [0.901, 0.967] (139) | 0.938 [0.868, 0.972] (64) | 0.933 [0.860, 0.970] (60) | 0.949 [0.892, 0.977] (79) | 0.929 [0.806, 0.976] (28) | 0.946 [0.899, 0.972] (111) | 0.936 [0.851, 0.974] (47) | 0.915 [0.823, 0.961] (47) | 0.978 [0.906, 0.995] (45) |

| flag | sym | full | last 12m | H1 | H2 | Sunday reopen | weeknight |
|---|---|---|---|---|---|---|---|
| HI_IN@0.90 | NQ | 0.580 (439) | 0.556 (233) | 0.603 (160) | 0.567 (279) | 0.554 (79) | 0.585 (360) |
| HI_IN@0.90 | ES | 0.604 (438) | 0.575 (233) | 0.642 (160) | 0.584 (278) | 0.574 (79) | 0.610 (359) |
| LO_IN@0.90 | NQ | 0.661 (439) | 0.681 (233) | 0.624 (160) | 0.679 (279) | 0.612 (79) | 0.676 (360) |
| LO_IN@0.90 | ES | 0.649 (438) | 0.665 (233) | 0.621 (160) | 0.667 (278) | 0.621 (79) | 0.657 (359) |
| OVN_LO_IN@0.90 | NQ | 0.441 (438) | 0.454 (232) | 0.426 (160) | 0.452 (278) | 0.418 (78) | 0.457 (360) |
| OVN_LO_IN@0.90 | ES | 0.425 (437) | 0.437 (232) | 0.421 (160) | 0.427 (277) | 0.402 (78) | 0.444 (359) |
| BREAK_HI@0.70 | NQ | 0.295 (434) | 0.305 (233) | 0.278 (155) | 0.302 (279) | 0.298 (78) | 0.294 (356) |
| BREAK_HI@0.70 | ES | 0.277 (433) | 0.289 (233) | 0.258 (155) | 0.288 (278) | 0.280 (78) | 0.277 (355) |
| BREAK_LO@0.70 | NQ | 0.227 (434) | 0.229 (233) | 0.222 (155) | 0.229 (279) | 0.219 (78) | 0.229 (356) |
| BREAK_LO@0.70 | ES | 0.247 (433) | 0.251 (233) | 0.236 (155) | 0.250 (278) | 0.238 (78) | 0.249 (355) |
| HOLD_HI@0.10 | NQ | 0.704 (434) | 0.693 (233) | 0.722 (155) | 0.695 (279) | 0.705 (78) | 0.703 (356) |
| HOLD_HI@0.10 | ES | 0.721 (433) | 0.710 (233) | 0.742 (155) | 0.710 (278) | 0.721 (78) | 0.721 (355) |
| HOLD_LO@0.10 | NQ | 0.774 (434) | 0.770 (233) | 0.780 (155) | 0.770 (279) | 0.777 (78) | 0.774 (356) |
| HOLD_LO@0.10 | ES | 0.758 (433) | 0.749 (233) | 0.769 (155) | 0.749 (278) | 0.758 (78) | 0.757 (355) |

Where a signal degraded. (i) NQ BREAK_LO@0.70: 0.929 (n = 14) in H1 to 0.724 (n = 29) in H2 and 0.769 (n = 26) in the last 12 months; the H2 CI [0.573, 0.837] still excludes the base of 0.229, but the call is now right about three times in four, not nine in ten. (ii) ES BREAK_HI@0.70: 0.950 (n = 20) in H1 to 0.800 (n = 35) in H2 and 0.750 (n = 28) in the last 12 months. (iii) NQ HOLD_LO@0.10: 0.986 (n = 69) in H1 to 0.902 (n = 102) in H2 and 0.900 (n = 80) in the last 12 months, against a base of 0.770: the lift fell from +0.21 to +0.13. (iv) BREAK_HI@0.70 on Sunday reopens is 0.600 (n = 10) in NQ and 0.667 (n = 6) in ES against 0.911 / 0.878 on weeknights; the counts are small but the direction is the same in both symbols. (v) NQ HI_IN@0.90 in the high-VIX tercile is 0.853 (n = 95) against 0.926 in the low tercile, with overlapping CIs; the overnight-low flag in NQ shows the same pattern (0.800 on 25 high-VIX sessions). The intra-session 0.90 flags did not degrade: H2 and the last 12 months lie inside the full-window CIs in both symbols, the only half outside a full-window CI is NQ LO_IN@0.90 in H1 (0.866 against a lower bound of 0.871), which improved from 0.866 in H1 to 0.932 in H2, and the Sunday reopens are at least as good as the weeknights. Per calendar month (counts hits/n fired; an asterisk marks n fired < 5; sessions per month are given so the firing frequency is visible; the Wilson CI of every cell is in `monthly.csv`): the month cells of HI_IN@0.90 and LO_IN@0.90 with at least five firings are at or above 4 hits in 5 in 79 of the 85 month cells, and the lowest is NQ LO_IN@0.90 in 2026-04 at 8/11.

| month | sessions NQ / ES | NQ HI_IN@0.90 | ES HI_IN@0.90 | NQ LO_IN@0.90 | ES LO_IN@0.90 | NQ OVN_LO_IN@0.90 | ES OVN_LO_IN@0.90 |
|---|---|---|---|---|---|---|---|
| 2024-12 | 5 / 5 | 3/3* | 3/3* | 1/1* | 2/2* | 1/1* | 0/0* |
| 2025-01 | 19 / 19 | 6/7 | 10/12 | 11/12 | 9/9 | 3/3* | 1/1* |
| 2025-02 | 18 / 18 | 4/5 | 6/6 | 11/13 | 10/12 | 3/3* | 2/2* |
| 2025-03 | 20 / 20 | 8/9 | 8/10 | 9/12 | 9/11 | 2/5 | 1/2* |
| 2025-04 | 20 / 20 | 15/18 | 9/9 | 7/8 | 9/10 | 2/2* | 0/0* |
| 2025-05 | 21 / 21 | 14/16 | 11/11 | 7/7 | 10/10 | 0/0* | 2/2* |
| 2025-06 | 19 / 19 | 11/12 | 11/11 | 6/7 | 11/12 | 2/2* | 2/2* |
| 2025-07 | 18 / 18 | 9/11 | 8/9 | 3/3* | 13/13 | 0/0* | 0/0* |
| 2025-08 | 20 / 20 | 12/13 | 10/12 | 3/4* | 9/12 | 1/1* | 0/0* |
| 2025-09 | 19 / 18 | 8/10 | 9/11 | 4/4* | 4/4* | 1/1* | 1/1* |
| 2025-10 | 23 / 23 | 11/13 | 10/11 | 10/11 | 10/11 | 5/6 | 4/5 |
| 2025-11 | 17 / 17 | 10/11 | 10/10 | 8/8 | 9/9 | 1/1* | 2/3* |
| 2025-12 | 17 / 17 | 9/9 | 9/10 | 6/6 | 6/6 | 0/0* | 0/0* |
| 2026-01 | 18 / 18 | 8/9 | 7/8 | 9/9 | 10/10 | 3/3* | 2/2* |
| 2026-02 | 17 / 17 | 9/10 | 8/10 | 5/5 | 8/10 | 1/1* | 1/1* |
| 2026-03 | 22 / 22 | 14/15 | 14/16 | 10/10 | 11/12 | 3/3* | 4/4* |
| 2026-04 | 20 / 20 | 11/12 | 12/12 | 8/11 | 7/9 | 1/2* | 1/2* |
| 2026-05 | 18 / 18 | 10/11 | 6/8 | 11/11 | 12/12 | 0/0* | 0/0* |
| 2026-06 | 20 / 20 | 13/15 | 11/11 | 13/13 | 12/12 | 1/1* | 3/3* |
| 2026-07 | 20 / 20 | 14/16 | 13/14 | 11/14 | 10/11 | 1/1* | 0/0* |
| 2026-08 | 21 / 21 | 10/11 | 10/10 | 9/9 | 11/11 | 0/0* | 0/0* |
| 2026-09 | 20 / 20 | 9/11 | 6/6 | 10/10 | 13/14 | 0/0* | 4/5 |
| 2026-10 | 22 / 22 | 14/15 | 13/14 | 8/9 | 13/13 | 1/1* | 0/0* |
| 2026-11 | 5 / 5 | 5/5 | 4/4* | 2/3* | 3/3* | 2/3* | 3/3* |

The sessions column counts the Asia-flag population; the overnight-flag population of 2026-04 is 19 / 19 (2026-04-17 has no overnight label, section 2) and equals the sessions column in every other month.

| month | nights NQ / ES | NQ BREAK_HI@0.70 | ES BREAK_HI@0.70 | NQ BREAK_LO@0.70 | ES BREAK_LO@0.70 | NQ HOLD_HI@0.10 | ES HOLD_HI@0.10 | NQ HOLD_LO@0.10 | ES HOLD_LO@0.10 |
|---|---|---|---|---|---|---|---|---|---|
| 2025-01 | 19 / 19 | 2/2* | 3/3* | 1/1* | 0/0* | 6/6 | 7/7 | 10/10 | 8/9 |
| 2025-02 | 18 / 18 | 3/3* | 4/4* | 0/1* | 0/0* | 4/4* | 4/4* | 10/10 | 9/9 |
| 2025-03 | 20 / 20 | 1/1* | 0/0* | 1/1* | 1/1* | 10/10 | 9/9 | 8/8 | 7/7 |
| 2025-04 | 20 / 20 | 2/4* | 3/4* | 3/3* | 2/2* | 9/9 | 11/11 | 9/9 | 10/10 |
| 2025-05 | 21 / 21 | 1/1* | 2/2* | 1/1* | 1/1* | 4/4* | 8/11 | 8/8 | 8/10 |
| 2025-06 | 19 / 19 | 1/1* | 2/2* | 4/4* | 0/1* | 3/3* | 7/10 | 7/8 | 6/7 |
| 2025-07 | 18 / 18 | 3/3* | 2/2* | 2/2* | 2/2* | 5/5 | 3/3* | 8/8 | 2/2* |
| 2025-08 | 20 / 20 | 5/5 | 3/3* | 1/1* | 1/1* | 8/8 | 9/9 | 8/8 | 6/6 |
| 2025-09 | 19 / 18 | 5/6 | 4/4* | 0/1* | 0/0* | 6/6 | 7/7 | 12/13 | 8/8 |
| 2025-10 | 23 / 23 | 3/3* | 3/3* | 0/1* | 0/0* | 7/7 | 9/10 | 8/9 | 7/7 |
| 2025-11 | 17 / 17 | 2/3* | 1/2* | 3/3* | 3/3* | 8/8 | 8/8 | 7/7 | 7/7 |
| 2025-12 | 17 / 17 | 2/4* | 2/2* | 2/2* | 0/1* | 4/4* | 7/7 | 2/3* | 2/3* |
| 2026-01 | 18 / 18 | 2/3* | 1/2* | 0/2* | 0/0* | 8/8 | 7/7 | 8/8 | 3/3* |
| 2026-02 | 17 / 17 | 1/1* | 1/1* | 2/4* | 1/1* | 8/8 | 9/9 | 7/8 | 6/6 |
| 2026-03 | 22 / 22 | 1/1* | 3/3* | 4/5 | 4/5 | 11/11 | 13/13 | 8/8 | 6/6 |
| 2026-04 | 20 / 20 | 6/6 | 5/5 | 0/1* | 0/0* | 2/2* | 2/2* | 13/15 | 7/7 |
| 2026-05 | 18 / 18 | 6/6 | 3/4* | 0/0* | 1/1* | 5/5 | 5/5 | 9/12 | 7/9 |
| 2026-06 | 20 / 20 | 2/2* | 0/1* | 2/2* | 5/5 | 9/9 | 10/10 | 5/5 | 3/3* |
| 2026-07 | 20 / 20 | 2/3* | 2/3* | 3/3* | 3/3* | 7/8 | 8/9 | 3/4* | 4/4* |
| 2026-08 | 21 / 21 | 2/2* | 2/2* | 3/3* | 2/2* | 7/7 | 11/11 | 3/3* | 3/3* |
| 2026-09 | 20 / 20 | 1/2* | 0/0* | 0/0* | 1/1* | 7/8 | 9/12 | 3/3* | 5/5 |
| 2026-10 | 22 / 22 | 4/4* | 1/3* | 1/1* | 2/2* | 9/10 | 6/6 | 4/4* | 6/7 |
| 2026-11 | 5 / 5 | 0/0* | 0/0* | 1/1* | 2/2* | 4/4* | 2/2* | 0/0* | 1/1* |

## 8. Trade translation

This section is a mechanical evaluation device on hourly bars with conservative stop priority, not a strategy, and no slippage, commissions or fills are modelled. Rule: at the first LO_IN@0.90 firing of a session with k <= 6 (at least two Asia bars left), a hypothetical long at that bar's close; stop = the running Asia low at that bar (exact level from the raw bars), target = the running Asia high; horizon A = the 02:00 bar close, horizon B = the 08:00 bar close. From the next bar on, bar by bar: a bar that touches the stop counts as a stop even if it also touches the target; otherwise a touch of the target counts as a target; if neither is touched by the horizon the position is marked at the horizon close. MFE and MAE are the best and worst excursions, in bp of the entry, over the bars held. The mirror is a short at the first HI_IN@0.90 firing with stop = running high and target = running low. Baselines: the same rule at every bar close k <= 6 of every session (unconditional); the per-k unconditional rates weighted by the firing k distribution (k-matched, the baseline of the specification); and the per-cell unconditional rates over cells of k x quintile of the stop distance in units of the 20-session median range, weighted by the firing cell distribution (k x stop-distance matched). The last baseline is added because the flag fires when price has moved away from the extreme it protects: at the firing the stop is 29-56 bp away and the target 4-9 bp away (medians; the stop distance is expressed in bp of the stop level, the target distance and every other bp figure of this section in bp of the entry close, a difference of at most 0.3 bp at these distances), against 11-25 bp and 11-25 bp at the k-matched baseline, so a large part of the conditional target / stop asymmetry is geometry rather than information. Two tight-stop variants are raced beside the running-extreme stop, both placed beyond the running extreme: 0.10 x the 20-session median Asia range, as specified for this evaluation (med20 = the rolling median of the session table's `rng_bp`, the Asia range in bp of the 17:00 reference close, over the 20 prior sessions), and 0.10 x today's RTH range (`lvl_rth_high` - `lvl_rth_low`), which is the distance the mean-reversion engine uses. Neither is the engine's stop: the engine places its tight stop 0.10 x the RTH range beyond the RTH extreme (`sessions.path_outcomes`), and its Asia-range stop is the wide stop, 0.6 x the 20-day median of (asia_high - asia_low) in points (`features.wide_stop_distance`). The med20 series used here also differs from the codebase's `asia_rng_med20` (the median of (asia_high - asia_low) / asia_open) by more than 1 bp on 87 NQ / 66 ES of the 439 / 438 sessions, spread over eleven months of the window (median absolute difference 0.05 / 0.03 bp; above 5 bp on 10 / 14 sessions, maximum 15.2 / 13.7 bp, the ES ones all in April-May 2025), so the tight-stop rates in this section are not comparable with the engine-bridge numbers of the research report (section 8.3C). Rates carry Wilson CIs for the flagged entries and session-bootstrap CIs otherwise; differences and means carry the session-bootstrap CI.

| signal | sym | horizon | n flagged | P(target first): flagged [90% CI] | k-matched [CI] | k x stop-distance-matched [CI] | unconditional, all k<=6 [CI] (n) | flagged minus k-matched [CI] | flagged minus distance-matched [CI] |
|---|---|---|---|---|---|---|---|---|---|
| LO_IN@0.90 long | NQ | A: 02:00 | 148 | 0.736 [0.673, 0.791] | 0.409 [0.376, 0.440] | 0.590 [0.547, 0.637] | 0.436 [0.406, 0.464] (n=3073) | +0.328 [0.271, 0.384] | +0.146 [0.096, 0.195] |
| LO_IN@0.90 long | NQ | B: 08:00 | 148 | 0.845 [0.789, 0.887] | 0.530 [0.496, 0.564] | 0.762 [0.723, 0.804] | 0.526 [0.497, 0.556] (n=3066) | +0.315 [0.268, 0.365] | +0.083 [0.041, 0.125] |
| LO_IN@0.90 long | ES | A: 02:00 | 189 | 0.778 [0.724, 0.823] | 0.421 [0.388, 0.451] | 0.618 [0.574, 0.658] | 0.439 [0.408, 0.466] (n=3066) | +0.357 [0.310, 0.401] | +0.160 [0.116, 0.199] |
| LO_IN@0.90 long | ES | B: 08:00 | 188 | 0.867 [0.821, 0.903] | 0.540 [0.507, 0.573] | 0.785 [0.748, 0.819] | 0.531 [0.500, 0.558] (n=3059) | +0.327 [0.282, 0.370] | +0.082 [0.046, 0.117] |
| HI_IN@0.90 short | NQ | A: 02:00 | 219 | 0.694 [0.641, 0.743] | 0.357 [0.324, 0.391] | 0.555 [0.512, 0.602] | 0.366 [0.339, 0.395] (n=3073) | +0.337 [0.292, 0.380] | +0.139 [0.095, 0.178] |
| HI_IN@0.90 short | NQ | B: 08:00 | 219 | 0.785 [0.736, 0.827] | 0.420 [0.387, 0.454] | 0.645 [0.603, 0.690] | 0.417 [0.388, 0.446] (n=3066) | +0.366 [0.322, 0.409] | +0.141 [0.098, 0.178] |
| HI_IN@0.90 short | ES | A: 02:00 | 176 | 0.818 [0.766, 0.861] | 0.367 [0.335, 0.399] | 0.600 [0.558, 0.647] | 0.377 [0.349, 0.406] (n=3066) | +0.452 [0.405, 0.498] | +0.218 [0.169, 0.261] |
| HI_IN@0.90 short | ES | B: 08:00 | 176 | 0.875 [0.828, 0.910] | 0.428 [0.397, 0.462] | 0.685 [0.645, 0.730] | 0.427 [0.399, 0.457] (n=3059) | +0.447 [0.405, 0.488] | +0.190 [0.143, 0.231] |

| signal | sym | horizon | n flagged | P(stop first): flagged [90% CI] | k-matched [CI] | k x stop-distance-matched [CI] | unconditional, all k<=6 [CI] (n) | flagged minus k-matched [CI] | flagged minus distance-matched [CI] |
|---|---|---|---|---|---|---|---|---|---|
| LO_IN@0.90 long | NQ | A: 02:00 | 148 | 0.074 [0.046, 0.118] | 0.359 [0.325, 0.391] | 0.109 [0.082, 0.136] | 0.392 [0.364, 0.420] (n=3073) | -0.284 [-0.326, -0.243] | -0.035 [-0.068, -0.004] |
| LO_IN@0.90 long | NQ | B: 08:00 | 148 | 0.101 [0.067, 0.150] | 0.431 [0.398, 0.464] | 0.173 [0.139, 0.207] | 0.444 [0.416, 0.474] (n=3066) | -0.330 [-0.376, -0.287] | -0.072 [-0.112, -0.034] |
| LO_IN@0.90 long | ES | A: 02:00 | 189 | 0.048 [0.028, 0.080] | 0.370 [0.339, 0.403] | 0.120 [0.095, 0.148] | 0.400 [0.372, 0.430] (n=3066) | -0.323 [-0.360, -0.285] | -0.073 [-0.098, -0.045] |
| LO_IN@0.90 long | ES | B: 08:00 | 188 | 0.112 [0.079, 0.155] | 0.436 [0.405, 0.470] | 0.181 [0.151, 0.213] | 0.450 [0.423, 0.481] (n=3059) | -0.324 [-0.368, -0.283] | -0.069 [-0.101, -0.034] |
| HI_IN@0.90 short | NQ | A: 02:00 | 219 | 0.078 [0.053, 0.113] | 0.431 [0.397, 0.463] | 0.140 [0.111, 0.170] | 0.462 [0.431, 0.490] (n=3073) | -0.353 [-0.390, -0.317] | -0.063 [-0.093, -0.031] |
| HI_IN@0.90 short | NQ | B: 08:00 | 219 | 0.178 [0.140, 0.224] | 0.544 [0.510, 0.578] | 0.293 [0.251, 0.335] | 0.553 [0.525, 0.583] (n=3066) | -0.366 [-0.409, -0.323] | -0.115 [-0.153, -0.075] |
| HI_IN@0.90 short | ES | A: 02:00 | 176 | 0.051 [0.030, 0.086] | 0.436 [0.402, 0.467] | 0.122 [0.091, 0.152] | 0.462 [0.431, 0.490] (n=3066) | -0.385 [-0.424, -0.346] | -0.071 [-0.103, -0.040] |
| HI_IN@0.90 short | ES | B: 08:00 | 176 | 0.114 [0.080, 0.159] | 0.550 [0.516, 0.582] | 0.279 [0.235, 0.319] | 0.554 [0.524, 0.584] (n=3059) | -0.436 [-0.477, -0.391] | -0.165 [-0.205, -0.122] |

| signal | sym | horizon | flagged: median distance to stop (bp of the stop level) / target (bp of the entry) | k-matched | k x distance-matched | flagged MFE median (p25, p75), bp | flagged MAE median (p25, p75), bp | unconditional MFE / MAE median, bp | P(neither) flagged (n) | P&L at horizon when neither, median bp | mean P&L at exit, bp [90% CI]: flagged | unconditional |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LO_IN@0.90 long | NQ | A: 02:00 | 55.7 / 5.7 | 24.8 / 16.7 | 51.3 / 10.7 | 12.6 (5.5, 20.2) | -7.6 (-21.1, -2.2) | 10.6 / -10.9 | 0.189 (n=28) | -5.0 | -1.0 [-5.6, +3.5] | -0.9 [-2.1, +0.2] |
| LO_IN@0.90 long | NQ | B: 08:00 | 55.7 / 5.7 | 24.7 / 16.8 | 51.3 / 10.8 | 13.8 (7.4, 27.0) | -8.1 (-24.5, -2.6) | 11.7 / -11.8 | 0.054 (n=8) | -6.8 | +3.4 [-0.6, +7.3] | +0.7 [-0.8, +2.1] |
| LO_IN@0.90 long | ES | A: 02:00 | 35.3 / 3.7 | 16.4 / 11.1 | 32.7 / 7.3 | 7.3 (3.5, 12.4) | -4.6 (-11.3, -1.7) | 6.8 / -7.1 | 0.175 (n=33) | -4.4 | +0.3 [-2.1, +2.8] | -0.7 [-1.6, +0.1] |
| LO_IN@0.90 long | ES | B: 08:00 | 35.5 / 3.6 | 16.4 / 11.1 | 32.8 / 7.3 | 7.8 (3.9, 13.3) | -4.6 (-13.7, -1.6) | 7.4 / -7.5 | 0.021 (n=4) | -8.5 | +1.8 [-0.8, +4.8] | +0.8 [-0.2, +1.8] |
| HI_IN@0.90 short | NQ | A: 02:00 | 43.9 / 9.4 | 16.5 / 24.6 | 40.9 / 17.1 | 12.9 (6.5, 24.8) | -10.6 (-25.2, -5.0) | 10.9 / -10.6 | 0.228 (n=50) | -7.4 | +2.5 [-0.4, +5.4] | +0.3 [-0.9, +1.4] |
| HI_IN@0.90 short | NQ | B: 08:00 | 43.9 / 9.4 | 16.6 / 24.5 | 41.1 / 17.1 | 15.2 (7.3, 29.4) | -11.9 (-31.9, -5.0) | 11.8 / -11.7 | 0.037 (n=8) | -22.4 | -0.1 [-3.3, +2.9] | -1.4 [-2.7, +0.0] |
| HI_IN@0.90 short | ES | A: 02:00 | 29.2 / 4.2 | 11.1 / 16.5 | 29.4 / 10.8 | 8.3 (4.7, 17.3) | -6.0 (-13.6, -2.6) | 7.1 / -6.8 | 0.131 (n=23) | -7.2 | +3.1 [+1.3, +4.9] | +0.3 [-0.5, +1.2] |
| HI_IN@0.90 short | ES | B: 08:00 | 29.2 / 4.2 | 11.1 / 16.5 | 29.3 / 10.8 | 9.2 (4.9, 18.4) | -6.0 (-15.5, -2.6) | 7.5 / -7.4 | 0.011 (n=2) | -14.7 | +1.3 [-1.2, +3.5] | -1.2 [-2.2, -0.2] |

Next-bar statistic, target proximity and the two tight stops (the tight-stop P&L columns are the mean P&L at exit of the same entries when the tight stop replaces the running-extreme stop):

| signal | sym | horizon | target hit in the next bar: flagged [CI] | unconditional / k-matched / distance-matched | target within 2 bp of entry: flagged [CI] | k-matched / distance-matched | 0.10 x med20 stop hit first: flagged [CI] | k-matched [CI] | distance-matched [CI] | mean P&L at exit with it, bp [CI] | 0.10 x RTH-range stop hit first: flagged [CI] | k-matched [CI] | distance-matched [CI] | mean P&L at exit with it, bp [CI] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LO_IN@0.90 long | NQ | A: 02:00 | 0.554 [0.486, 0.620] | 0.291 / 0.251 / 0.386 | 0.189 [0.142, 0.248] | 0.067 / 0.115 | 0.047 [0.026, 0.085] | 0.268 [0.237, 0.298] | 0.085 [0.061, 0.110] | -0.9 [-5.6, +3.7] | 0.041 [0.021, 0.076] | 0.186 [0.160, 0.213] | 0.055 [0.037, 0.075] | -0.3 [-4.7, +4.0] |
| LO_IN@0.90 long | NQ | B: 08:00 | 0.554 [0.486, 0.620] | 0.291 / 0.251 / 0.387 | 0.189 [0.142, 0.248] | 0.067 / 0.115 | 0.081 [0.051, 0.126] | 0.366 [0.332, 0.398] | 0.153 [0.123, 0.185] | +3.6 [-0.6, +7.6] | 0.074 [0.046, 0.118] | 0.310 [0.279, 0.341] | 0.128 [0.099, 0.155] | +4.9 [+0.9, +8.6] |
| LO_IN@0.90 long | ES | A: 02:00 | 0.624 [0.565, 0.680] | 0.298 / 0.269 / 0.423 | 0.312 [0.260, 0.370] | 0.111 / 0.181 | 0.042 [0.024, 0.074] | 0.268 [0.240, 0.299] | 0.098 [0.075, 0.122] | +0.1 [-2.3, +2.6] | 0.016 [0.006, 0.039] | 0.185 [0.161, 0.213] | 0.063 [0.043, 0.085] | +0.1 [-2.7, +2.8] |
| LO_IN@0.90 long | ES | B: 08:00 | 0.628 [0.568, 0.683] | 0.299 / 0.269 / 0.423 | 0.314 [0.261, 0.372] | 0.111 / 0.181 | 0.112 [0.079, 0.155] | 0.362 [0.331, 0.397] | 0.164 [0.134, 0.195] | +1.3 [-1.3, +4.4] | 0.085 [0.057, 0.125] | 0.304 [0.274, 0.338] | 0.131 [0.104, 0.159] | +1.7 [-1.3, +4.9] |
| HI_IN@0.90 short | NQ | A: 02:00 | 0.511 [0.456, 0.566] | 0.227 / 0.202 / 0.356 | 0.142 [0.107, 0.185] | 0.036 / 0.073 | 0.041 [0.024, 0.069] | 0.322 [0.291, 0.353] | 0.106 [0.081, 0.135] | +2.8 [-0.0, +5.7] | 0.023 [0.011, 0.046] | 0.203 [0.175, 0.231] | 0.048 [0.033, 0.066] | +2.7 [-0.2, +5.6] |
| HI_IN@0.90 short | NQ | B: 08:00 | 0.511 [0.456, 0.566] | 0.228 / 0.202 / 0.356 | 0.142 [0.107, 0.185] | 0.036 / 0.073 | 0.155 [0.119, 0.200] | 0.484 [0.448, 0.519] | 0.267 [0.225, 0.308] | -0.3 [-3.6, +2.9] | 0.146 [0.111, 0.190] | 0.393 [0.359, 0.428] | 0.213 [0.176, 0.251] | -1.5 [-5.3, +2.1] |
| HI_IN@0.90 short | ES | A: 02:00 | 0.653 [0.592, 0.710] | 0.243 / 0.217 / 0.401 | 0.273 [0.221, 0.331] | 0.064 / 0.121 | 0.023 [0.010, 0.050] | 0.316 [0.284, 0.347] | 0.092 [0.066, 0.119] | +3.5 [+1.6, +5.2] | 0.006 [0.001, 0.025] | 0.193 [0.166, 0.218] | 0.045 [0.027, 0.067] | +3.4 [+1.6, +5.2] |
| HI_IN@0.90 short | ES | B: 08:00 | 0.653 [0.592, 0.710] | 0.243 / 0.218 / 0.401 | 0.273 [0.221, 0.331] | 0.065 / 0.121 | 0.080 [0.052, 0.120] | 0.468 [0.434, 0.504] | 0.239 [0.196, 0.278] | +1.6 [-0.9, +3.8] | 0.062 [0.039, 0.100] | 0.383 [0.350, 0.415] | 0.190 [0.152, 0.224] | +1.2 [-1.5, +3.7] |

Reading. Conditional on the flag, the running extreme is revisited before 02:00 in 0.048-0.078 of entries and before 08:00 in 0.101-0.178, against 0.359-0.550 at the k-matched baseline; the target (the opposite running extreme) is reached first in 0.694-0.818 by 02:00 and 0.785-0.875 by 08:00, against 0.357-0.540. Most of the target-first column is a next-bar statistic: the target is hit in the very next bar in 0.511-0.653 of flagged entries (0.227-0.299 unconditionally, 0.202-0.269 k-matched), and it lies within 2 bp of the entry close in 0.142-0.314 of them (0.036-0.111 k-matched), because the flag fires when price has just moved away from the extreme it protects. The stop-first reduction is the informative number. Against the k x stop-distance-matched baseline most of the gap closes: the stop is hit 0.035-0.073 less often by 02:00 and 0.069-0.165 less often by 08:00 (every CI excludes zero, but the differences are a fraction of the k-matched ones), and the target is reached 0.082-0.218 more often, with the target still about twice as close in the flagged rows as in the matched rows. The tight stop at 0.10 x the 20-session median range beyond the running extreme is hit first in 0.023-0.047 of flagged entries by 02:00 and 0.080-0.155 by 08:00, against 0.268-0.322 and 0.362-0.484 k-matched; the engine-distance stop at 0.10 x the RTH range is hit first in 0.006-0.041 by 02:00 and 0.062-0.146 by 08:00, against 0.185-0.203 and 0.304-0.393 k-matched (neither is the engine's own stop, see above). Because the target is 4-9 bp away and the stop 29-56 bp away, the mean P&L at exit of the flagged entries is -1.0 to +3.4 bp before costs (the 90 % CI includes zero in 7 of the 8 cells; unconditional -1.4 to +0.8 bp), and the tight-stop variants are the same (-0.9 to +3.6 bp with the med20 stop, -1.5 to +4.9 bp with the RTH-range stop; zero inside the CI in 7 and 6 of the 8 cells). The flag locates the extreme; it does not by itself make a positive-expectancy trade against the running extremes. The honest summary is that the flag selects bars where the running extreme is already far away and a small target is near; the information beyond that geometry is a 4-17 point reduction in stop risk and an 8-22 point increase in target probability, and the Europe horizon roughly doubles the stop rate.

## 9. Limitations and what is not claimed

Hourly bars: a stop and a target touched inside the same hour are resolved as a stop by convention, and the running extreme is the hourly bar extreme; nothing is claimed about intra-hour sequencing. Fifteen-minute data exist for 48 sessions only and were not used here. About 440 out-of-sample sessions per symbol, 24 month blocks, within a 23-month window; the 0.70 BREAK calls rest on 34-66 nights (17-66 across all thresholds, with full-window CIs of 11-26 points) and their sub-cuts on 5-56 nights, which is why the 0.70 full-window CIs are 14-20 points wide and the sub-cut CIs 10-54 points wide, and why the degradations in section 7 cannot be separated from sampling noise with confidence. The isotonic step was fitted on prior out-of-sample rows and is active for 86 % of the Detector A sessions and 77 % of the Detector B nights; the shipped column is therefore a mixture of raw and calibrated probabilities over time, and the raw column is reported beside it. The overnight caveat of section 5 applies to every intra-session flag: the hit rates are statements about the Asia session, and the probability that the extreme survives Europe is 0.46-0.81 at the first firing. There is no live track record: this is a simulation on stored predictions, and the live tool's inputs (the as-delivered hourly file, the complete-bar guard, the per-date refit) were validated separately in section 8.7 of the research report. Holiday nights with fewer than nine Asia bars and the roll sessions are excluded, so nothing is claimed about them. The k-matched base is a k-only baseline; a baseline that conditions on the position in the running range (the research report's histogram) would be higher and the lifts correspondingly smaller. The envelope outputs are not better calibrated than unconditional quantiles and should not be presented as probability envelopes. The tight stops of section 8 are placed beyond the running Asia extreme and are not the mean-reversion engine's stop, which sits beyond the RTH extreme; nothing in section 8 is comparable with the engine-bridge numbers of the research report. No claim is made about direction, about the bar in which an extreme will print, or about the 15-minute structure of the extremes.

## 10. Reproduction

Commands, from the project root (the script also runs from `research/extremes`):

    OMP_NUM_THREADS=1 python research/extremes/signal_backtest.py

Inputs read: `research/extremes/oos_intrasession_{NQ,ES}.csv`, `oos_preasia_{NQ,ES}.csv`, `{NQ,ES}_hourly_panel.csv`, `{NQ,ES}_extremes.csv`, `data/{NQ,ES}_1h.csv`. Outputs written to `research/extremes/validation/`: `signals_rowlevel.csv`, `signals_first_firing.csv`, `first_firing_by_k.csv`, `failures.csv`, `overnight_flags.csv`, `preasia_calls.csv`, `envelope_coverage.csv`, `joint_calls.csv`, `stability_cuts.csv` (one long table: flag, sym, cut_name, cut_value, n_sessions_in_cut, n_fired, hits, hit_rate, ci_lo, ci_hi, base_rate), `monthly.csv`, `trade_translation.csv` (flagged, unconditional, k-matched, distance-matched and per-k rows with the target / stop / next-bar / tight-stop rates, their CIs and the mean P&L at exit) and `summary.json` (the headline dictionary, with the population counts of section 2, the short-night bar layout and the med20 convention of section 8 under `_meta.populations`). The script retrains nothing, is deterministic (bootstrap seed 0, 1,000 draws), caches the hourly bars in memory, prints a compact summary and exits 0. Runtime about 15 s on one core. Every table in this document was rendered from those CSVs and re-checked against a clean re-run before the document was finalised. The input files are the ones committed in revision 7b2b8c9 (the regeneration described in section 8.7 of the research report); their md5 prefixes at the time of this run were oos_intrasession NQ 4d590d09 / ES 3c19d29a, oos_preasia 8e26d56a / b92f6ba4, hourly panel cfa6387a / 819191da, extremes table 04392af2 / 374bff84, raw bars 22a44ff6 / 5bf195af, so a later re-run on regenerated prediction files can be told apart from a reproduction of this one.
