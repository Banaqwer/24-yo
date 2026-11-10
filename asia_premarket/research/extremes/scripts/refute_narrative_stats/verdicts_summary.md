# Refuter (statistical) verdicts on lens "narrative" F1-F14

Scripts: common_r.py (independent loaders; two-sample Fisher / Mann-Whitney vs the complement, 90% bootstrap CI, H1/H2 split at 2025-09-01),
r1_extremes_claims.py (F2-F9, F14), r2_catalogue_panel_15m.py (F1, F10-F13, F8 bar check), r3_followups.py (F4 CMH by quarter, F10 per-DST, F12 opening print).
Outputs: r1_out.txt, r2_out.txt, r3_out.txt.

| id | verdict | one-line |
|---|---|---|
| F1 | downgrade | catalogue-vs-other reproduces (first-bar 64/37, Tokyo-bar 20/36, range 102/61); trend_close ns by Fisher (p=0.07); family cells are anecdotes/null |
| F2 | keep (minor downgrade) | Sunday low-in-bar-0 43% vs 28%, lo_after_tko 48% vs 67%: both halves, ES; drop the Sunday+pos combo increment |
| F3 | downgrade | bar-0 range x1.8 / session range x1.4-1.6 robust; late-extreme and early-extreme parts NQ-H2-only, fail ES |
| F4 | downgrade | Kospi nights 89% in H2; quarter-stratified CMH OR 1.9 p=0.02 (NQ) / 0.04 (ES); within 2026Q2-Q3 null; Kospi-not-SOX unsupported |
| F5 | keep (mechanical note) | 60% / 0/45 / 63 bp reproduce; mostly distance-to-RTH-low (distance control 51%) |
| F6 | keep | reproduces; sign adds beyond distance; close_loc>=0.7 part unstable |
| F7 | downgrade | range x1.3-1.5 holds (n=19, both symbols); timing rates are anecdotes that fail ES |
| F8 | REFUTED | 10/15 holiday sessions have 6 bars; 9-bar holiday nights 52 vs 63 (p=0.53) NQ, 38 vs 40 ES; bar-matched 6-bar 24 vs 51 (n=10) |
| F9 | downgrade | null range holds; later-low fails H2 (p=0.61) and ES |
| F10 | keep (minor downgrade) | 79%/80%/93%/85% reproduce, both halves, ES; Tokyo-open bar is a real jump in both DST regimes; rr<0.4 bins and Sunday +.1 are anecdotes |
| F11 | keep (minor downgrade) | 53% all, 56.5% at |move|>=20 (p=0.049, consistent sign in 6/6 cells) -> 'no usable momentum' |
| F12 | REFUTED (as stated) | opening print is the extreme 0/48; first-15-minute count reproduces (14/22) but one-quarter n<=22 anecdotes |
| F13 | keep as anecdote | 9/10 reproduces; 8/10 up-nights, vs up-night base p=0.056; control Wednesdays 1/17 |
| F14 | keep | all cont rates within CI of .469 |
