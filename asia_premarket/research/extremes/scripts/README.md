# Scripts behind `research/asia_extremes_report.md`

Every number in the report was produced by one of these scripts and then reproduced by at least one
independent refuter or verifier. They are kept here so the report can be re-derived; they are not
part of the daily pipeline. Run them from `asia_premarket/` (they read `research/extremes/*.csv`
and `data/*.csv`); most write their outputs next to themselves, so copy a directory out before
running it if you want to keep the tree clean. Large intermediate CSVs were not kept.

| Directory | What it did |
|---|---|
| `lens_timing/` | Q1 hour-of-extreme U-shape, Q2 hold rates by bar and condition, Q3 magnets / stop-runs, Q4-6 extreme-bar signature, Tokyo/China opens, NQ vs ES, Q7 supplements. |
| `lens_context/` | 18:00-knowable context: univariate screens (BH q-values), walk-forward logistic and quantile fits per feature, VIX / distance tables. |
| `lens_events/` | Calendar flags x statistics screen, event-bar tests (China / Japan data, BoJ, RBA), confound stratification (Sunday), 15-minute event anatomy. |
| `lens_narrative/` | The research catalogue's big nights, Kospi / SOX shocks, the US-origin vs Asia-origin rule, TSMC nights, headline vs no-news nights. |
| `lens_minute/` | 15-minute sub-study (48 sessions): within-hour slot of the extreme, first-15-minute levels, arcsine null. |
| `refute_<lens>_stats/` | Statistical refuters: reproduce each finding from the tables, multiple-testing and CI checks. |
| `refute_<lens>_leak/` | Knowability refuters: is every input available at the claimed decision time (18:00 or bar k), DST, partial bars, splices. |
| `refute_<lens>_regime/` | Regime refuters: half-splits, quarterly flips, leave-5-out, symbol replication, random-walk nulls. |
| `builder_a/` | Detector A (intra-session) build notes: OOS analysis, cross-variant tests, the first `predict_now` test. |
| `preasia/` | Detector B (pre-Asia) build: full walk-forward run logs and the tonight check. |
| `verify_0/` | Independent verification of Detector A: metric reproduction, label-permutation nulls, DST and oracle checks, splice / rule checks, wick scan. |
| `verify_1/` | Independent verification of Detector B: metric reproduction, leakage rows, DST, single-feature benchmarks, decomposition. |
| `critic/` | The completeness review (report section 8): recomputation of the headline cells, ES base rates by DST, the Europe-open analysis, the bridge to the mean-reversion engine, the live-mode check, hourly-bar ambiguity. |
