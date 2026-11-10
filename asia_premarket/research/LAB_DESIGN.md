# Research Lab design: turning the Asia pre-market engine into a looped, multi-agent research process

**Status:** design, not yet implemented. Nothing in `model.py`, `backtest.py` or `run_daily.py` has been changed by this document.

**Question this answers.** How to (1) turn the engine's failures into a research mode that finds out *why* it loses edge when it does, (2) turn Grade A into a research mode that refines the edge in the same way, and (3) run both as a loop of agents that share findings until the edge is "perfected to its maximum", with "maximum" defined as a goal the loop can actually reach and recognise.

**How it was produced.** One forensics agent re-derived every graded NQ night in `research/backtest_trades_NQ.csv` bar by bar (P&L reproduced to 1e-6 on all 196 graded nights) and classified the 87 losing nights into cause clusters with lift against the 109 winners (`research/lab/forensics_v0.md`, `forensics_graded_NQ.csv`, `forensics_losses_NQ.csv`). Four designers then wrote independent lab designs from different lenses (quant methodology, multi-agent systems, overnight microstructure, ML experimentation); three judges scored them; the winner was merged with the others' kept ideas into sections 1–11; a completeness critic then audited the merged design against the repository and wrote section 12, which supersedes anything it conflicts with. Appendix A lists the critic's findings in full.

**Verified against the repository after the critic reported them** (so they are facts, not agent claims):

- Contract-splice artefacts in `data/NQ_1h.csv` and `data/ES_1h.csv`. Hourly log-return divergences between NQ and ES outside regular hours that no index move explains: NQ 2024-06-23 18:00 (+1.31% vs +0.02%), NQ 2024-12-22 18:00 (+3.34% vs +0.41%), NQ 2025-03-21 16:00 (+2.64% vs +1.85%), NQ 2025-09-16 16:00 and 18:00 (−0.95% then +1.04% with ES flat), and ES alternating roughly ±0.8% every bar from 2025-12-16 04:00 to 2025-12-17 13:00 with NQ flat. Two of these are Sunday reopens in the training prefix; the 2025-09-16 one creates a fake after-hours shock in `post_ret`.
- Outcome-label overlap. `sessions.path_outcomes` keeps walking after a target is hit, so `stopped` means "stop touched before the *farthest* target", not "before this target". Recomputing `features.path_targets` for NQ: `stopped=1` co-occurs with `hit_vwap_first=1` on 13 of 588 sessions (15 for the 38.2% target, 6 for the 50% target); with the wide stop, 22 / 13 / 6. The classifiers for P(target) and P(stop) therefore do not model complementary events for the chosen target, which is one mechanical reason the confidence ratio p_t/(p_t+p_s) is over-confident in the middle band.

**Scope tags.** Every number in this document carries a tag: **[FULL]** all 331 out-of-sample nights (already seen by the forensics agent and therefore by this design), **[DISC]** discovery split only, **[VH]** historical vault, **[VF]** forward nights. Nothing tagged [FULL] or [DISC] is a result. It is a prior that sizes a pre-registered test.

**The honest expectation, stated first.** Roughly 330 out-of-sample nights with a per-night standard deviation near 90 points support a handful of decisions, not a search. The most likely end state of this loop is: calibration fixed, Grades B and C retired or demoted, far targets and wide continuation pruned, costs and fills applied, splices repaired, and a smaller, cleaner Grade A whose edge is **unconfirmed** at the six-month forward horizon because confirming a +15 point per night edge needs about 100 Grade-A nights, which is roughly two years. The loop is built to say that rather than manufacture a number.

---

## Contents

1. Goal and stopping rule
2. Data discipline and anti-overfitting controls
3. Agent roles
4. Shared-memory protocol
5. One iteration step by step
6. Why-it-fails research mode
7. Grade-A research mode
8. First-iteration backlog
9. Metrics and acceptance tests
10. Cost and cadence
11. Risks and what would make us abandon the project
12. Completeness patch (supersedes conflicting text above)

Appendix A: completeness critic's findings

---

This document merges the winning blackboard/orchestrator design with the orchestrator's baseline and the ideas the judges asked to keep (global trial ledger and deflated Sharpe, independent replicator, placebo trio and random-filter null, DST-aware Tokyo hours, cost schedule, pre-period pseudo-vault, deterministic Judge, known_at_1800 table and target-shift test, entry-reference fix, scope tags, small-n ban, complexity budget, prospective labeller, forward ledger hashed before 18:00 ET). Every number below carries a scope tag: **[FULL]** = all 331 OOS nights (contaminated: `research/lab/forensics_v0.md` read them all), **[DISC]** = discovery split only, **[VH]** = historical vault aggregate the designer has already seen (disclosed in 2.2), **[VF]** = forward nights. Nothing tagged [FULL] or [DISC] is a result; it is a prior that sizes a pre-registration.

The one-sentence honesty: ~330 OOS nights with a per-night standard deviation of ~90 pts support a handful of decisions, not a search. The loop is built to make those decisions on data no proposer has seen, to say "unconfirmed" when the sample cannot say more, and then to stop.

---

## 1 Goal and stopping rule (measurable)

### 1.1 What is optimised

`S` = the engine specification, a versioned record (`research/lab/board/versions/spec_vN.json`) consumed by a `Spec` dataclass in `lab/decision.py` that drives `trade_plan`, `_candidates`, `confidence_from_plan` and `simulate` through one code path shared by `run_daily.py` and the lab:

| Spec field | Today (spec_v0) | Source line |
|---|---|---|
| `calibration_mode` | pooled isotonic on all OOS predictions | model.py L275-277 |
| `range_mode` | rng_q50/q80/exp_rev fitted on the full sample | model.py L287-324, backtest.py L31-33 |
| `entry_ref`, `fill` | 17:00 `post_close`, filled at that price | model.py L428, sessions.py L190 |
| `scratch_ref` | `rev_ret` from the 18:00 `asia_open` (mixed with the 17:00 entry) | backtest.py L48/L55, features.py L214 |
| `costs` | none | — |
| guard constants | 0.25 / 1.0 / 0.03, no max-target guard | model.py L481-483, L529-536 |
| candidate set | 2 variants x (3 fade targets + continuation) | model.py L486-510 |
| confidence | p_win/(p_win+p_loss) of the chosen candidate | model.py L526, L545 |
| grade cutoffs | 72 / 63 / 56 | model.py L552-559 |
| `veto_fns`, `exit_rules`, `playbook_rules` | none | new: `lab/playbook.py` |
| `tokyo_open_hour` | 20 (DST-naive) | sessions.py L25 |
| `feature_cols` | `FEATURE_COLS_COMPACT` | features.py L261-268 |

`spec_v0` must reproduce `research/backtest_trades_NQ.csv` rows to 1e-9 on discovery dates before any agent runs (forensics already matched the engine's P&L to 3.6e-12 [FULL], so this is feasible). `spec_v0.1` = `spec_v0` + the iteration-0 integrity fixes (2.3) + the cost schedule. **spec_v0.1 is the honest baseline every effect is measured against**, and it may already be weaker than the published +21.3 pts/night [FULL].

### 1.2 Definition of "perfected to its maximum"

`S*` is the spec such that:

1. **Provenance.** Every element of `S*` that differs from `spec_v0.1` passed exactly one pre-registered test on data its proposer never saw: Vault-H (2026-06-01 to 2026-11-06, 96 nights) or Vault-F (forward nights, spec frozen and hypotheses hash-registered before the month began).
2. **Exhaustion.** The registry holds no untested hypothesis whose pre-registered predicted effect is >= the minimum detectable effect (MDE, 2.5) for its population at the remaining vault size, and two consecutive iterations produced no proposal that cleared the Referee with predicted effect >= MDE.
3. **Forward confirmation band.** Under the frozen `S*`, Vault-F shows, after costs: (a) all-night paired P&L of `S*` vs `spec_v0.1` with a 90% weekly-block-bootstrap lower bound > 0 on >= 80 nights (this is the powered test: paired all-night differences have sd ~45-70 pts, so +8 pts/night is detectable at n=80); (b) Grade-A net expectancy inside the band pre-registered from discovery (point estimate >= +10 pts, trimmed mean > 0) on >= 25 A nights; (c) pooled graded ECE <= 10 points (n >= 60 graded; per-bucket ECE reported, gated only where bucket n >= 30); (d) no issued grade with negative net expectancy (a grade may be eliminated by converting its nights to NO EDGE); (e) >= 2.5 A nights/month.
4. **Accounting.** Family-wise alpha <= 0.10 (Holm) over all Vault-H tests ever run; FDR <= 10% (BH) over all Vault-F tests; the deflated Sharpe ratio of the Grade-A series with `N_trials` = total registry entries including dead ones and the pre-charged informal looks (2.2) is reported with every iteration report.

Power arithmetic is stated up front: Grade-A P&L has sd ~76-124 pts [DISC]/[VH]. For a +15 pt/night edge the 90% lower bound clears zero only at n ≈ (1.645·90/15)² ≈ 100 A nights, i.e. ~2 years at 3.9 A nights/month [FULL]. So "confirmed Grade-A edge" is a calendar outcome. Condition 3(a) is the test that can actually be passed in six months; 3(b)-(e) are band checks that can fail (and stop the project) but cannot alone confirm.

Three terminal states are legitimate and the loop must be allowed to reach any of them:

| State | Meaning |
|---|---|
| **CONVERGED-CONFIRMED** | 1, 2, 3 and 4 all hold |
| **CONVERGED-UNCONFIRMED** | 1, 2 and 4 hold; 3(a) passes but 3(b) has < 25 A nights or its CI includes zero; `S*` is frozen, paper-trading continues, no further mining |
| **FAILED** | 3(a) lower bound < 0 on >= 80 nights, or the kill switch fires; revert to the last spec that passed, report "edge not confirmed at this sample size" |

ES is a replication arm (same-sign check for every NQ pass), not a search space; the loop may conclude ES is NO TRADE (H10).

### 1.3 Stopping rule

**Historical phase** (Vault-H): at most 4 iterations. Stop early when (i) the Vault-H wallet is spent (12 lifetime tests, max 3 per iteration), or (ii) two consecutive iterations with no proposal clearing the Referee at >= MDE, or (iii) three consecutive iterations with no Vault-H pass. Then freeze `S_k` and enter the forward phase.

**Forward phase** (Vault-F): monthly iterations for at most 6 months. On the last trading day of month m the spec is frozen and forward hypotheses for month m+1 are hash-registered; at month start the previous month is scored (BH 10% over all forward tests) and steps 3-10 of the iteration run once. Stop with CONVERGED-* when conditions 1-4 are met, or at the 6-month cap with whatever state holds.

**Kill switch** (any time, checked weekly on Vault-F): rolling 40-night Grade-A net expectancy < 0 with bootstrap P(mean <= 0) > 0.5, or any confidence bucket with n >= 30 off by > 15 points. Effect: demote to research-only, no new hypotheses (PAUSE), Pathologist post-mortem; resume only if the post-mortem names a mechanism and the band is re-entered within 20 nights, else FAILED.

**Re-open after stop**: rolling 20-night A win rate < 45% or pooled ECE > 15 on Vault-F starts a new historical phase with the vault cutoff moved forward; the old Vault-F joins discovery and the previous Vault-H joins discovery too (the rolling-vault rule).

---

## 2 Data discipline and anti-overfitting controls

### 2.1 Splits

| Split | Dates | Nights | Graded | A / B / C | Who sees it |
|---|---|---|---|---|---|
| Training prefix | 2024-06-18 to 2025-03-31 | 150 training-only nights | — | — | models only |
| **Discovery** | 2025-04-01 to 2026-05-31 | 235 | 137 (+12 NO TRADE) | 53 / 55 / 29 | every agent, freely |
| **Vault-H** | 2026-06-01 to 2026-11-06 | 96 | 59 (+4 NO TRADE) | 25 / 24 / 10 | Judge script only |
| **Vault-F** | 2026-11-10 onward, monthly blocks | ~17/month, ~4 A/month | — | — | Judge script; agents see PASS/FAIL + sign + CI |
| Pre-period pseudo-vault | 2024-10 to 2025-03 graded by `walk_forward_target(min_train=80)` | ~100 | — | — | replication arm only, sign checks |
| ES (same windows) | as above | 301 OOS | 177 | 73 / 63 / 41 | replication arm only |
| Backward holdout (stretch) | 2022-06 to 2024-06 hourly NQ/ES from a vendor, validated bar-by-bar on the 2024-06..08 overlap | ~500 | — | — | Judge only; acquire only if budget allows; holdout failure = rejection, fixed in advance |

Discovery Grade A [DISC]: n=53, 70% win, +27.0 avg, sd 76; continuation 28 / mean reversion 25; wide 13; Sunday reopens 7 (7/7); after-hours-shock A nights 2; pre-holiday A nights 1. Mid band [63,72) [DISC]: n=58, realised 36% vs 67% stated. B avg -18.8, C avg -15.1 [DISC].

The split is in time, not interleaved, because the monthly expanding-window retrain would otherwise let vault outcomes shape discovery predictions.

### 2.2 Sealing and contamination disclosure

`orchestrator.py seal --cutoff 2026-06-01` (iteration 0, once):

- Archives the full `data/*.csv` outside the repo and writes `research/lab/vault/vault_H.tar.enc` (openssl, key only in the orchestrator's environment) containing vault-period rows of `NQ/ES_features`, `_targets`, `_sessions`, `_1h`, `BTC_1h`, `daily_*.csv`, `research/backtest_trades_*.csv`, the >= 2026-06-01 rows of `catalogue_2026Q2_Jul.csv` (it spans 2026-05-07 to 07-30), all of `catalogue_2026Q3_Nov.csv`, `narrative_2026Q2_Jul.md`, `narrative_2026Q3_Nov.md`, and `research/lab/forensics_v0.md` plus its two CSVs (they tabulate vault-era nights by date).
- Writes `research/lab/discovery/*.parquet` (truncated at the cutoff) with a SHA256 manifest. `harness.load_discovery()` is the only data entry point; the static checker rejects any experiment that opens a path outside `research/lab/discovery/`, and agents' tool permissions deny `research/lab/vault/`.
- Vault-F nights are never written anywhere agents read; the Judge emits aggregates only.

**Disclosure.** `forensics_v0.md` and the four design drafts were produced on the full sample, so the designer of this document has seen Vault-H aggregates (A n=25, win 68%, avg +9.2, sd 124; B n=24; C n=10; the forensics calibration table pools both eras) and the agents may remember 2026 market narratives (LLM-prior contamination). Vault-H is therefore **semi-clean**. Two consequences: (a) the alpha ledger starts pre-charged: every first-iteration hypothesis in section 8 is logged as one informal full-sample look, so the DSR `N_trials` starts at 15 and the Vault-H wallet still allows 12 formal tests but reports the pre-charge; (b) the goal and stopping rule are defined on Vault-F, the only fully clean data.

### 2.3 Iteration-0 integrity fixes (all before any agent proposes anything; logged as trials H0a-H0h, not charged to the wallet)

| id | Defect | Fix | Touchpoint |
|---|---|---|---|
| H0a | Isotonic calibrator fitted on pooled OOS (night t's p_cal uses outcomes from t+1..T); honesty-box buckets matching to two decimals is the signature | causal calibrator: refit monthly on OOS predictions strictly before the month, min 60 nights, raw before that | model.py L275-277; `FitResult.calibrator` becomes a per-month dict |
| H0b | rng_q50/q80/exp_rev fitted on the full sample and used by the guard and EV cap in `simulate` (comment at L30 admits it) | monthly walk-forward refits, same hyper-parameters | model.py L287-324, backtest.py L31-33 |
| H0c | Mixed entry reference: scratch P&L = `rev_ret*entry` where `rev_ret = asia_ret` is measured from the 18:00 `asia_open`, while targets/stops are measured from the 17:00 `post_close` | `scratch_ref='post_close'` using `t["asia_ret_vs_settle"]` (features.py L215, already computed) | backtest.py L48, L55; model.py L151 |
| H0d | Fill at the 17:00 close; first tradeable print is the 18:00 open (49 hours later on Sundays); `already_past` evaluated at 17:00 | `fill='asia_open'`, `already_past` re-evaluated at the open; realism variant kept alongside | model.py L428, L452, L462; sessions.py L190; backtest.py L34 |
| H0e | `TOKYO_HOURS = 20..02` is DST-naive: Seoul/Tokyo cash opens 09:00 KST/JST = 19:00 ET in EST, 20:00 ET in EDT | `tokyo_open_hour(date)` from `America/New_York` DST; `tokyo_*` session stats and any checkpoint hypothesis use it | sessions.py L25, L91 |
| H0f | `refresh_data` overwrites `data/*_1h.csv` with yfinance's rolling 730-day window; a refresh today would start the file at ~2024-11 and silently move the OOS start from 2025-04-01 | append-only merge; SHA256 of every `data/*.csv` recorded per spec version; harness refuses an unknown hash; nightly 15-minute archive (`NQ_15m_archive.csv`) started now | run_daily.py L27-48 |
| H0g | `data/NQ_features.csv` on disk is stale (114 columns, lacks `mag`, `ext_in_dir` and the other direction-framed columns the models use) | features regenerated from code at every seal/bundle; CSVs never read as model inputs | features.py L292-301 |
| H0h | No transaction costs; hourly first-hit ambiguity (both levels in one bar = stopped for fades, win for continuation) | cost schedule (2.8); 15m re-resolution of the vault era as a Referee-only measurement (disagreement rate reported, not a spec change) | `lab/harness.apply_costs`; sessions.py L148-222 on `NQ_15m.csv` (2026-08-31 to 11-09) |

Pre-registered alarm for H0a+H0b+H0c+H0d+costs jointly: Grade-A discovery avg falls from +27.0 [DISC] to +12..+22; if it falls below +5 the baseline is declared reset and the first objective becomes recovering honest edge.

### 2.4 Knowability

- `features.KNOWN_AT_1800`: a table mapping every column to its timestamp source (RTH bar, 16:00 post bar, daily close with exchange close time, calendar). The harness asserts every entry of any `feature_cols` is in it. `dchg()` (features.py L119-126) forward-fills daily closes, so KOSPI/N225/HSI closes are the *prior* session's, correctly; USDJPY and DXY close timing is audited explicitly.
- `harness.assert_knowable(col)`: recompute the column from data truncated at 17:00 ET of date D for 20 random D; equality required.
- Target-shift test: shift all outcome columns by +1 night; every classifier's calibrated Brier must go to base rate ± 0.01, else the candidate is rejected.
- Catalogue text and tags are never features (written ex post; `in_catalogue` selects on the outcome). Narrative claims become prospective tests through labels written to `research/catalogue_live.csv` before 17:50 ET (section 3, Prospective Labeller).

### 2.5 Pre-registration and MDE

A hypothesis is an append-only JSON record (schema in 4.2), hash-locked at registration; the orchestrator refuses to run a record whose hash changed; a modified hypothesis is a new id. Each record declares: mechanism, population (grade/kind/variant/flag it touches), exactly one primary metric, predicted effect with direction and magnitude, the number of nights it touches on discovery, at most **one free parameter with its value written before the test** (a grid is allowed only with <= 3 values, CPCV/PBO, and the grid counts as 3 trials in the DSR ledger), the placebo, the falsifier, and the arms (ES, pseudo-vault).

MDE table (minimum mean improvement per *touched* night, one-sided, power 0.8, from the touched population's P&L sd; the orchestrator recomputes it per registered population):

| Population | n | sd (pts) | MDE at alpha 0.05 | MDE at the Holm first-test alpha (0.10/12) |
|---|---|---|---|---|
| Vault-H, rule touching 20 nights | 20 | 134 | 75 | 97 |
| Vault-H, rule touching 40 nights | 40 | 134 | 53 | 69 |
| Vault-H, all graded | 59 | 134 | 42 | 55 |
| Vault-H, Grade A only | 25 | 124 | 62 | 80 |
| Vault-H, all nights paired (untraded = 0) | 96 | 105 | 27 | 35 |
| Discovery, all graded (gate) | 137 | 91 | 20 | — |
| Discovery, Grade A (gate) | 53 | 76 | 26 | — |
| ECE, one bucket | 15 / 30 / 59 | binomial | 32 / 23 / 16 points | — |

Reading: only broad decision-layer changes (calibration, grade demotion, candidate pruning, stop sizing) are Vault-H-testable on P&L; A-only refinements (MDE 62-80 pts on 25 nights) are routed to the forward track **by construction** and never charge the wallet; calibration hypotheses are tested on pooled ECE (59 graded vault nights detect a 16-point gap).

### 2.6 Multiple testing

- **Vault-H alpha wallet**: Holm family-wise 0.10 over all Vault-H tests ever run; max 3 per iteration, 12 lifetime; single-shot per hypothesis; a hypothesis still contested after the Referee ruling never charges the wallet (forward track or dead).
- **Vault-F**: Benjamini-Hochberg 10% FDR over all forward tests; a forward hypothesis is *confirmed* only with >= 25 affected forward nights and the predicted sign.
- **Global trial ledger**: every registry entry (dead, deferred, duplicate, revised, pre-charged informal look, grid value) increments `N_trials`; the deflated Sharpe ratio of the Grade-A series (Bailey and Lopez de Prado, skew/kurtosis from the per-night series) is reported every iteration and must be > 0 at 95% on Vault-F for CONVERGED-CONFIRMED.
- **Random-filter null** (every filter/veto/gate hypothesis): must beat the 95th percentile of 1000 random same-size filters on the test split.
- **Placebo trio** (orchestrator-run): sign-flipped rule; rule applied to NO-EDGE nights (must not help); outcome labels shuffled within calendar month for any new feature (200 draws). A hypothesis whose placebo reproduces >= 50% of the claimed effect is dead.
- **Sign consistency**: the discovery effect must carry the same sign in >= 3 of the 4 discovery quarters (2025Q2, Q3, Q4, 2026Q1) and in the Apr-May 2026 stub.
- **CPCV/PBO**: for any grid, 8 month-blocks, 1-week purge, PBO < 0.4 required.
- **Replication arms**: every NQ vault pass must show the same effect sign on ES (same window) or on the pre-period pseudo-vault; a pass with neither is flagged NQ-idiosyncratic and demoted to forward track.
- **Independent replicator**: every vault-queued hypothesis is re-implemented from the registry text alone in a clean worktree; MISMATCH (> 10% effect difference or sign flip) or AMBIGUOUS rejects before the vault is touched.

### 2.7 Structural guards

- **Parsimony / complexity budget**: <= 1 new parameter per passed hypothesis; the incumbent may not exceed `spec_v0.1`'s tunable constants + 4; a rule added must remove one unless its vault gain exceeds 2x MDE.
- **Degeneracy**: a spec must keep >= 2.5 A nights/month on discovery and >= 60% of discovery Grade-A P&L; "skip everything that lost" is rejected automatically.
- **Small-n ban**: no feature, gate or guard built on a discovery subgroup with < 30 graded nights; such slices (Sunday reopens 7 A nights, thin sessions, after-hours A nights) may only be *free rules* with a no-harm criterion or *forward bands*.
- **Regression guards on integration**: path-model calibrated Brier not worse by > 0.005; every previously passed effect must persist under the joint spec (interaction check) or the merge is refused; ES no-harm (paired lower 90% bound >= -1 pt).
- **Visibility**: vault results reach agents as PASS/FAIL, sign and CI only.
- **Graveyard + dedup**: dead hypotheses carry a cause of death; a proposal with token-set Jaccard >= 0.6 to any registry or graveyard entry (title + spec_delta) is rejected by the orchestrator; the Skeptic additionally blocks cosmetic re-submissions (a "VIX > 25 gate" after a "vix_z20 > 1.5 gate" died).

### 2.8 Costs and fills (`harness.apply_costs`)

NQ: 2 ticks per side (1.0 pt round trip) + commission (~0.15 pt) on weeknights = 1.5 pts/RT; 4 pts/RT at Sunday 18:00 opens and on nights with |post_ret| > 0.3% or a mega-cap print; sensitivity line at 4 pts/RT everywhere. ES: 0.75 / 2.0 pts. Sunday P&L is booked from the Sunday `asia_open`, not the Friday 17:00 close. No hypothesis is promoted on pre-cost P&L.

### 2.9 Raw-data freeze

`data/*.csv` are git-tracked; every spec version records their SHA256; `--refresh` appends only; the seal manifest is re-verified monthly; the yfinance 730-day cap is the reason the archive is outside the repo as well.

---

## 3 Agent roles

Agents are stateless per iteration (fresh spawn), fed orchestrator-built bundles capped at ~25k tokens, and write only to their own iteration-scoped files. "Count" is runs per historical iteration.

| Role | Lens | Count | Inputs | Outputs |
|---|---|---|---|---|
| **Pathologist** | Why each losing graded night lost: one primary cause from the fixed taxonomy (6.1), flags with lift vs winners, re-coded whenever the spec changes a night's P&L | 1 | `discovery/trades_NQ.parquet` joined to features/targets/sessions/hourly bars via `harness.forensics` (the scratchpad `forensics.py` moved into the lab); discovery-era catalogue rows; `KNOWLEDGE.md`; prior `pathologist.json` | `findings/<iter>/pathologist.json` (one record per losing night), `failures.csv` (baseline file, regenerated), `pathologist.md` <= 1200 words with the three costliest clusters as testable mechanism statements |
| **Anatomist** | What Grade-A wins are made of: sub-populations, reward:risk, resolution bar, Welch-t separators (ex-ante vs ex-post listed separately), geometry vs ex-ante expected range, top-k dependence, fragility battery (7.2) | 1 | Same bundle restricted to A and to candidate sets that would become A; `KNOWLEDGE.md` | `findings/<iter>/anatomist.json` + `anatomist.md` <= 1000 words with an explicit "anecdote" section (slices n < 30) |
| **Validity Auditor** | Measurement validity: fills, bar resolution, pooled calibration, in-sample fits, roll artefacts, entry reference, DST, data-hash drift | 1 at iteration 0; on demand after any integration | model.py / backtest.py / sessions.py / features.py, harness acceptance-test log, data manifest | `findings/<iter>/validity.md` + VALIDITY alerts (halt the iteration if upheld) |
| **Theorist: geometry / execution** | Stops, targets, entry time, time-stops and checkpoints, scratch handling, wide-stop sizing, hourly first-hit artefacts | 1 | `KNOWLEDGE.md` (<= 3k tokens), latest digest (<= 1.5k), both findings md, registry one-liners, GRAVEYARD titles, harness API doc, one rotation partner's prior proposals | `proposals/<iter>/geometry.jsonl` (<= 3 hypotheses in registry schema) |
| **Theorist: statistics / calibration** | The ratio p_t/(p_t+p_s), winner's-curse selection among 8 candidates, causal vs pooled calibrators, guard thresholds, EV formula, grade cutoffs, range coverage | 1 | Theorist bundle + orchestrator-generated calibration and coverage tables (stated vs realised by bucket, P50/P80 coverage by quarter, discovery only) | `proposals/<iter>/stats.jsonl` |
| **Theorist: regime / cross-asset** | Ex-ante regime features from `daily_close.csv` (KOSPI, N225, HSI, USDJPY, CRUDE, VIX, VVIX) and NQ hourly bars; demotion gates rather than new model inputs | 1 | Theorist bundle + feature-availability sheet (column, source, last-observation timestamp relative to 18:00 ET, coverage) | `proposals/<iter>/regime.jsonl`, each with the exact column formula so `assert_knowable` can run |
| **Theorist: catalyst / narrative** (web-enabled) | Converts narrative patterns into 18:00-knowable encodings; verifies catalogue facts with primary sources; declares what is unfalsifiable with current data; files data requests | 1 | Theorist bundle, discovery-era catalogue and narratives only, `event_calendar.csv`, web search | `proposals/<iter>/catalyst.jsonl` + `catalyst_notes.md` (verified/unverified claims with URLs) + data requests |
| **Skeptic** (two seats: statistical; market/knowability) | Kill hypotheses: look-ahead, ex-post conditioning disguised as a filter, implicit multiplicity, power vs MDE, single-quarter effects, implementation realism (18:00 fill, gap through stop, same-bar ambiguity, DST), duplicates of dead ideas | 2 | `proposals/<iter>/*.jsonl`, harness API, knowability rubric, GRAVEYARD, registry, MDE table | `disputes/<iter>.jsonl`: one challenge per hypothesis {hyp_id, category, severity 1-3, objection, required fix or kill} |
| **Theorist cross-read + rebuttal** (same four theorists, second short call) | Each theorist answers the other three lenses' proposals with harness-computed tables (agree / challenge / extend; no prose-only disagreement) and rebuts once the challenges to its own | 4 (<= 400 words out each) | Own proposals, the other lenses' proposals, disputes against own, harness | `responses/<iter>/<lens>.md` |
| **Referee** | Rules with a fixed rubric; sets the exact test; never invents hypotheses | 1 | proposals, disputes, responses, MDE table, harness test catalogue | `rulings/<iter>.jsonl`: scores (knowability 0-2 must be 2; mechanism, power, parsimony, novelty 0-2), decision approved / revise once / dead, test_spec, population, vault_eligible, placebo_spec |
| **Experimenter** | Implements one approved hypothesis against the harness; interprets the orchestrator-run result against the pre-registered prediction | <= 5 | One hypothesis + ruling, harness API, relevant source, `load_discovery()` only | `experiments/H<id>/variant.py` exposing `apply(spec)->spec` and optionally `feature(f,s,h)`, `veto(row)`, `exit_rule(bars, entry, side)`; later `interpretation.md` <= 300 words |
| **Replicator** | Re-implements each vault-queued hypothesis from the registry text only, in a clean worktree, without reading the experimenter's code | <= 3 | Registry record + ruling, clean checkout at the iteration's git SHA, `load_discovery()` | `experiments/H<id>/replication.json` MATCH / MISMATCH / AMBIGUOUS |
| **Integrator** | Folds vault passes into `lab/decision.py` / `lab/playbook.py` / model.py behind Spec flags, one code path for `run_daily.py` and the lab | 0-1 | Vault PASS records, current spec, `variant.py`, regression suite | Code diff + `versions/spec_v<N+1>.json` + CHANGELOG citing hypothesis ids; `report.py` honesty box shows spec version and Vault-F status |
| **Librarian** | The only agent that reads every artefact; compresses within hard caps; writes the human report | 1 | All findings / proposals / disputes / rulings / experiments / ledgers of the iteration; previous `KNOWLEDGE.md`, `GRAVEYARD.md` | `KNOWLEDGE.md` (<= 3k tokens), `GRAVEYARD.md`, `digest.md` (<= 800 words, baseline file) + `digest/<iter>.md`, `iteration_report_<iter>.md` |
| **Prospective Labeller** (daily, outside the iteration) | Writes catalyst/regime labels before 18:00 ET so narrative hypotheses become prospective tests | 1 per trading day | `reports/<date>_<SYM>_agent_brief.md`, web search, `agent_prompts/daily_narrative.md` (extended) | Row in `research/catalogue_live.csv` by 17:50 ET: `asia_origin_risk`, `ah_shock`, `headline_regime` in {us_macro, ai_capex_asia, geopolitics_oil, calm}, sources; hashed into `forward_chain.txt`; `asia_driver` filled next morning; never edited after 18:00 |
| **Regime Labeller** (weekly, Friday) | Writes the coming week's regime label ("Asia-origin continuation", "US-origin fade", "headline-gap", "quiet") before the nights it applies to; proposes an 18:00-knowable proxy that must reproduce >= 70% of weeks | 1 per week | Last week's reports and outcomes, `agent_prompts/weekly_patterns.md` (extended) | `narrative_live.md` regime line + `regime_labels.csv` (date_written, week, label, sources) |
| **Data Scout** (on demand) | Finds and validates additional 18:00-knowable data (CL=F, JPY=X, NKD=F hourly; VIX term structure; vendor 2022-24 hourly if budgeted); timestamp audits | 0-1 | Data requests filed by theorists, `refresh_data`, manifest | `data/<new>_1h.csv` + `lab/data_audit_<name>.md`; never computes outcomes or touches vault dates |
| **Judge** (not an agent) | `lab/judge.py`: one paired comparison per registered id on the sealed split, verdict by pre-stated rule; no LLM ever writes a vault verdict | script | registry record, incumbent spec, sealed split, null distribution | `vault_ledger.jsonl` aggregates only |

---

## 4 Shared-memory protocol

### 4.1 Directory (merges the orchestrator's baseline file names)

```
research/lab/
  discovery/           *.parquet + MANIFEST.sha256          [script writes; agents read]
  vault/               vault_H.tar.enc                       [orchestrator only]
  harness/             decision.py playbook.py harness.py forensics.py judge.py
                       null_distribution.py ledger.py acceptance_tests.py schemas/
  board/
    registry/hypotheses.jsonl   append-only, hash-locked (CSV view hypotheses.csv exported for humans)
    results.jsonl               one record per harness run (discovery / replication metrics only)
    failures.csv                pathologist's per-night cause table (baseline file)
    findings/<iter>/{pathologist,anatomist}.{json,md} validity.md
    proposals/<iter>/<lens>.jsonl
    disputes/<iter>.jsonl
    responses/<iter>/<lens>.md
    rulings/<iter>.jsonl
    experiments/H<id>/{variant.py,results.json,placebo.json,replication.json,interpretation.md}
    vault_ledger.jsonl          every Vault-H / Vault-F evaluation; aggregates only   [judge.py only]
    referee_log.md              human-readable render of vault_ledger (baseline file) [script only]
    forward/<date>_<SYM>.json   frozen-spec call logged 17:20 ET + resolved outcome   [run_daily + ledger.py]
    forward_chain.txt           sha256 chain of every forward call and every pre-18:00 label, git-committed
    versions/spec_v<N>.json     accepted spec + data hashes + git sha + pip freeze (baseline: versions/)
    KNOWLEDGE.md GRAVEYARD.md digest.md digest/<iter>.md iteration_report_<iter>.md
```

### 4.2 Record schemas (validated by `harness/schemas/*.json`; the orchestrator rejects any record that fails)

```json
// registry/hypotheses.jsonl (append-only; status transitions applied only by orchestrator.py)
{"id":"H12","iteration":1,"author":"theorist.geometry","title":"...",
 "mechanism":"when X (knowable at 18:00) the trade loses because Y",
 "population":{"grade":["A","B","C"],"kind":"CONTINUATION","variant":null,"flag":null},
 "spec_delta":{"Spec.time_stop_hour":"tokyo_open+1","Spec.checkpoint_frac":0.25},
 "free_parameter":{"name":"checkpoint_frac","value":0.25,"grid":null},
 "primary_metric":"paired_pnl_per_night|ece_pooled|coverage_p50|stopped_rate",
 "predicted_effect":{"direction":"+","magnitude":10,"units":"pts/touched night","touched_nights_disc":28},
 "mde":{"population":"VH.cont_all","value":53},"vault_eligible":false,"route":"forward",
 "placebo":"sign_flip|random_nights|label_shuffle|hsi_gate","falsifier":"...",
 "arms":["ES","pseudo_vault"],"graveyard_jaccard":0.21,
 "status":"proposed|challenged|approved|revise|dead|discovery_pass|discovery_fail|vault_queued|forward_track|vault_pass|vault_fail|integrated",
 "hash":"sha256(of all fields above at registration)"}

// findings/<iter>/pathologist.json (one per losing graded night)
{"date":"2026-01-15","grade":"A","call":"CONTINUATION","variant":"tight","res":"scratch","decided_bar":null,
 "pts":-103.95,"flags":["regime_vol","midband"],"primary":"b","knowable_at_1800":"no","scope":"DISC"}

// disputes/<iter>.jsonl
{"hyp_id":"H12","seat":"market","category":"leakage|expost|multiplicity|power|regime|implementation|duplicate",
 "severity":3,"objection":"...names the column, the night count, the bar...","required":"fix|kill"}

// rulings/<iter>.jsonl
{"hyp_id":"H12","scores":{"knowability":2,"mechanism":2,"power":1,"parsimony":2,"novelty":1},"total":8,
 "decision":"approved","test_spec":{"metric":"paired_pnl_per_night","population":"cont_all","block":"week",
 "one_sided":"+","placebo":"sign_flip"},"vault_eligible":false,"route":"forward"}

// results.jsonl (discovery / replication only)
{"hyp_id":"H12","split":"DISC","effect":9.1,"ci90":[1.2,17.3],"quarters_sign":[1,1,-1,1],"pbo":null,
 "placebo_effect":-0.4,"random_filter_pctile":97,"guards":{"brier_delta":0.001,"a_per_month":3.4,"es_lower":-0.3},"gate":"pass"}

// vault_ledger.jsonl (aggregates only)
{"hyp_id":"H3","vault":"H","test_no":2,"alpha_holm":0.05,"effect":4.1,"ci90":[-2.0,10.2],"p":0.14,"verdict":"FAIL",
 "es_sign":"+","pseudo_vault_sign":"+","wallet_remaining":10}

// forward/<date>_<SYM>.json
{"date":"2026-11-10","sym":"NQ","spec":"v0.1","logged_at":"17:20:04 ET","call":"MEAN REVERSION: LONG ...","grade":"B",
 "confidence":68,"geometry":{...},"playbook_call":"NO EDGE (veto: after-hours print)","data_sha":"...",
 "labels":{"asia_origin_risk":0,"ah_shock":1,"headline_regime":"ai_capex_asia"},
 "resolved":{"res":"stop","pnl_pts":-61.0,"pnl_net":-62.5,"resolved_at":"03:05 ET"}}
```

### 4.3 Who writes what, who reads what

| Artefact | Writer | Readers |
|---|---|---|
| discovery bundle, MANIFEST | orchestrator | all agents (only through `load_discovery`) |
| findings/* | Pathologist, Anatomist, Validity Auditor | Theorists, Skeptics, Librarian |
| proposals/* | the four Theorists | Skeptics, other Theorists (cross-read), Referee, Librarian |
| disputes/* | Skeptics | authoring Theorist, Referee, Librarian |
| responses/* | Theorists | Referee, Librarian |
| rulings/* | Referee | orchestrator (applies statuses), Experimenters, Librarian |
| registry, results, vault_ledger, referee_log, forward_chain, versions | orchestrator / judge.py / ledger.py only | everyone (vault_ledger: PASS/FAIL + sign + CI) |
| experiments/H<id>/* | one Experimenter, one Replicator | orchestrator, Integrator, Librarian |
| KNOWLEDGE.md, GRAVEYARD.md, digest.md, iteration_report | Librarian | every agent at start (KNOWLEDGE + digest + GRAVEYARD titles); the human reads iteration_report |
| catalogue_live.csv, regime_labels.csv | Prospective / Regime Labeller (before 18:00 ET / Friday) | ledger.py; Catalyst theorist (discovery-era rows only) |

### 4.4 Digest and memory rules

- `KNOWLEDGE.md` (<= 3k tokens): confirmed facts each with an evidence id (H-id, vault ledger line, findings file), current spec diff vs v0.1, open questions (<= 10), alpha wallet and MDE table, Vault-F status. If over cap, drop the weakest open question, never a confirmed fact or a wallet entry.
- `digest.md` (baseline file, <= 800 words, rewritten every iteration): settled / open / failed / next focus. Every number carries a scope tag `[DISC]`, `[VH]`, `[VF]`; the completeness script rejects a digest with an untagged number or a DEV prior promoted to a result.
- `GRAVEYARD.md`: id, title, cause of death (leakage / ex-post / power / placebo / replication / vault fail / worse than control), one line each. Seeded at iteration 0 with the forensics negative results: hold-through-Europe (-941 -> -2511 pts on 65 scratch nights [FULL]), hold-to-next-RTH (-941 -> -2592 [FULL]), widening the stop on tight-fade losses (0 of 10 converted, -496 -> -628 [FULL]), catalogue-tag filters (ex post), ex-post KOSPI/N225 > 2% flag (lift 0.93 [FULL]), VIX > 25 / vix_z20 / rv_ratio / trailing-form gates as A filters (lift 1.0-1.1; VIX > 25 A nights were the best [FULL]).
- **Disagreement**: Skeptic challenge -> one Theorist rebuttal (in the cross-read call) -> Referee rubric. Empirical disputes become deterministic checks the orchestrator runs (count the nights, recompute the table), never votes. Two unresolved competing claims are both registered in the same mechanism family (<= 2 per family per iteration) and the vault decides. The Judge's verdict is final; the Librarian records it.
- **Herding control**: the four lenses are distinct by construction; <= 2 registrations per mechanism family per iteration; Jaccard dedup; the rotation-partner obligation (each theorist must extend or refute one claim from another lens) is checked by the Referee (novelty score 0 if absent).

---

## 5 One iteration step by step

Legend: **[S]** deterministic script, **[A]** agent judgment, **[S+H]** script with a human-visible diff.

0. **[S] Iteration 0 only.** `orchestrator.py seal`; refactor `confidence_from_plan` / `trade_plan` / `simulate` behind `Spec`; assert spec_v0 reproduces `backtest_trades_NQ.csv` discovery rows to 1e-9; run H0a-H0h; publish `spec_v0.1` and the honest discovery scoreboard; precompute walk-forward OOS probability caches per `(calibration_mode, range_mode, feature_cols)` so decision-layer experiments never retrain the 9 classifiers; compute the MDE table; seed the registry (section 8, pre-charged) and the graveyard; start the forward ledger and the 15m archive; **[A]** Validity Auditor reviews the harness.
1. **[S] Bundle build.** Regenerate features from code, verify the manifest, regenerate discovery forensics for the incumbent spec, build per-role bundles (<= 25k tokens, truncate with a warning), print the calibration/coverage tables and the feature-availability sheet.
2. **[A, parallel] Forensics.** Pathologist + Anatomist (+ Validity Auditor after any integration). **[S]** schema validation; reject and respawn once.
3. **[A, parallel] Hypothesize.** Four Theorists, <= 3 proposals each. **[S] Register**: Jaccard dedup against registry and graveyard, assign ids, compute MDE and `vault_eligible`, hash-lock.
4. **[A, parallel] Challenge.** Two Skeptics, one severity-scored challenge per hypothesis.
5. **[A, parallel] Cross-read and rebut.** Each Theorist responds to the other lenses' proposals with harness tables and rebuts challenges to its own, once.
6. **[A] Rule.** Referee scores the rubric (knowability must be 2/2; >= 8/10 approved, 6-7 one revision, < 6 dead), fixes the exact test (metric, population, block length, direction, placebo), sets the route. **[S]** apply statuses; a hypothesis still contested is routed to forward track or dies.
7. **[A -> S pipeline, per approved hypothesis] Test.** Experimenter writes `variant.py` -> **[S]** static checks (import whitelist, no path outside discovery, `assert_knowable`, target-shift test, DoF declaration matches the config diff, incumbent reproduction when switched off) -> **[S]** `harness.run` with fixed seeds: paired weekly-block bootstrap on the registered metric, quarter sign-consistency, CPCV/PBO if a grid, random-filter null if a filter, placebo trio, regression guards -> **[S] discovery gate**: 90% lower bound > 0 AND effect >= 0.5 x predicted AND same sign in >= 3 of 4 quarters AND PBO < 0.4 AND placebo fails AND guards pass -> `vault_queued` if `vault_eligible` else `forward_track`; otherwise dead (reason logged) or one revision -> **[A]** Experimenter writes `interpretation.md` against the pre-registered prediction.
8. **[A, parallel] Replicate.** Replicator per vault-queued hypothesis (<= 3) from the registry text; **[S]** MATCH required, else rejected before the vault.
9. **[S] Vault-H.** `judge.py` runs each queued hypothesis once: one-sided paired test on the registered population and metric against a weekly-block-bootstrap null (5000 resamples), Holm-adjusted within the running family, trimmed mean as co-primary, ES and pseudo-vault sign checks; charges the wallet; writes PASS/FAIL + CI to `vault_ledger.jsonl`; the id can never be re-submitted.
10. **[A -> S+H] Integrate.** Integrator folds passes into Spec flags (<= 1 new parameter each); **[S]** re-run discovery under the joint spec; assert every previously passed effect persists, Brier not worse by > 0.005, degeneracy and ES guards hold; two passes touching the same population are registered as a joint candidate for the next iteration (no untested stacking); on success bump `versions/spec_v<N+1>.json`, show the human the diff; `run_daily.py` uses the new spec from the next night.
11. **[A] Digest.** Librarian updates `KNOWLEDGE.md`, `GRAVEYARD.md`, `digest.md`, writes `iteration_report_<iter>.md` (scoreboard, wallet, DSR, MDE, Vault-F status, escalations). **[S]** completeness check (every approved id has a result; every result a status; every number a scope tag).
12. **[S] Control.** Stopping rule (1.3); historical: loop to step 1 while < 4 iterations and the wallet is open; forward: freeze, hash-register forward hypotheses, wait for the month.

```python
# orchestrator.py (workflow pseudo-code; every agent call is a fresh spawn with a bundle)
def iteration(k, phase):
    bundles   = script.build_bundles(k)                                   # [S]
    findings  = parallel(agent("pathologist", bundles.path),
                         agent("anatomist",   bundles.anat),
                        *([agent("validity", bundles.valid)] if script.spec_changed_since(k-1) else []))
    script.validate_or_respawn(findings, schemas.findings, max_retries=1)
    proposals = parallel(agent(f"theorist.{lens}", bundles.theorist[lens]) for lens in LENSES)
    registry  = script.register(proposals)                                # dedup, ids, MDE, vault_eligible, hash-lock
    disputes  = parallel(agent(f"skeptic.{seat}", registry, bundles.skeptic) for seat in ("stats", "market"))
    responses = parallel(agent(f"theorist.{lens}.crossread", registry, disputes, bundles.theorist[lens]) for lens in LENSES)
    rulings   = agent("referee", registry, disputes, responses, MDE_TABLE)
    script.apply_statuses(rulings)
    for h in registry.approved():                                          # pipeline per hypothesis
        variant = agent("experimenter", h, bundles.exp(h))
        if not script.static_checks(variant, h): script.kill(h, "static"); continue
        res = script.harness_run(variant, h, seeds=FIXED); script.placebo_and_null(variant, h, res)
        h.status = script.discovery_gate(h, res)                          # vault_queued | forward_track | dead | revise
        agent("experimenter.interpret", h, res.public())
    queued = registry.vault_queued()[:3]
    reps   = parallel(agent("replicator", h.record_text(), clean_worktree()) for h in queued)
    queued = [h for h, r in zip(queued, reps) if script.replication_match(h, r)]
    judge.run(queued, vault="H", holm_family=registry.vault_tests_so_far())   # [S] aggregates only
    passes = registry.vault_pass(k)
    if passes:
        diff = agent("integrator", passes, current_spec())
        if script.joint_regression(diff): script.bump_spec(diff, human_diff=True)
        else: script.log_interaction(passes)
    agent("librarian", board.everything(k)); script.completeness_check(k)
    return script.control(k, phase)                                        # continue | freeze | stop(state)

def forward_month(m):                                                      # [S], runs daily / weekly / monthly
    nightly_1720_ET:  run_daily.log_call(spec=frozen, path="board/forward/", chain="forward_chain.txt")
    nightly_0310_ET:  ledger.resolve(last_night, bars=NQ_15m_archive or NQ_1h)
    friday:           agent("regime_labeller"); ledger.score_week(); check_kill_switch()
    month_start:      judge.run(registry.forward_registered(m-1), vault="F", bh_fdr=0.10)
                      script.update_vault_f_metrics(); iteration(k+1, phase="forward")
```

---

## 6 Why-it-fails research mode

### 6.1 Taxonomy (fixed; one primary cause per losing graded night, priority order)

same-bar artefact > catalyst (catalogue driver / after-hours print) > stopped-then-target (whipsaw, Europe target-first) > geometry (stop < 1/3 realised range, target beyond realised range) > timing (scratch, target hit in Europe / next RTH) > calendar (Sunday / holiday / < 9 bars) > regime (VIX > 25, vix_z20 > 1.5, rv_ratio > 1.5, trailing 20-trade win rate < 45%) > mid-band calibration > unexplained. The ex-post Asia-shock flag (KOSPI/N225 > 2% that night) is recorded but never a cause (lift 0.93 [FULL]).

Rules the Pathologist must obey: (i) a flag counts as a cause only if its lift vs winning nights is > 1.2 (the base rate of every flag among winners is computed each iteration); (ii) the taxonomy is re-applied whenever an integrated spec changes a night's P&L, so clusters shrink or move as fixes land; (iii) every cluster statement is written as a testable mechanism: "when X (knowable at 18:00), the trade loses because Y; a fix of type Z changes N nights by ~P pts"; (iv) cluster g (unexplained) is the noise floor: a 70%-win trade loses 30% of the time for no reason, and any rule that "fixes" cluster-g nights on history is overfitting by construction.

### 6.2 From cluster to hypothesis (the forensic clusters as they stand, [FULL] priors)

| Cluster | n / pts [FULL] | Knowable at 18:00? | Mechanism as registered | Test type | Hypotheses |
|---|---|---|---|---|---|
| c) catalyst | 29 / -4246 (51% of loss pts; 10 A); 14 nights were after-hours prints visible by 17:00, 11 Asia-origin shocks visible only at the Seoul/Tokyo open, 3 weekend headlines | partly: `post_ret`, `megacap_earnings_tonight` yes; Asia-origin only via labels written before 18:00 or Kospi-stress proxies | after-hours print nights have no A edge (A 1 of 4, -184 [FULL]; discovery has only 2 A nights); Asia-origin regime demotes mean reversion | veto (random-filter null + no-harm); prospective label test on the ledger; Kospi-stress gate with HSI placebo | H5, H6, H13 |
| d) mid-band calibration | 13 primary / 58 of 87 losses in [63,72) (lift 1.42); discovery mid band realises 36% vs 67% stated (n=58) [DISC] | yes (it is the meter itself) | the ratio of two independently calibrated marginals, selected as the max-EV of 8 candidates, is biased upward (winner's curse) | pooled ECE on graded nights (powered on 59 vault nights) + no-worse all-night P&L | H1 |
| a) geometry | 17 / -1240; targets > 1.0 x ex-ante 20d median Asia range resolve to target ~30% at every grade (25 nights, -1610); widening stops converts 0 of 10 | yes (`asia_rng_med20`, features.py L114) | the target, not the stop, is the lever | guard change evaluated by re-calling nights (`rerun_confidence_with_candidates`), random-filter null on the removed set | H2, H3, H7 |
| b) regime | 11 / -1000 primary; vol flags have lift 1.0-1.1; the real failure is calendar (2025Q4-2026Q1 A win 42-45%) coinciding with the Kospi/semis unwind | VIX/rv gates: yes but dead (graveyard); driver regime: only via Friday labels or KOSPI drawdown proxies | regime = driver regime, not VIX level | weekly label written forward; proxy must reproduce the label >= 70% of weeks; gate tested on the ledger | H6, Regime Labeller |
| f) calendar / thin | 8 / -692; pre-holiday or < 9-bar sessions 0 of 5 graded (3 A); Sunday reopens are NOT a loss cause (lift 0.85) | yes (`pre_holiday`, expected bar count) | thin book turns every headline into a stop run | free rule (no-harm, n too small for MDE) | H9 |
| e) timing | 4 / -122; holding scratches longer makes them worse on all 65 scratch nights | yes | negative result; A continuation scratches are the largest A loss mode (16 nights, -1044 net; 12 losers -1184 [FULL]) | continuation-only checkpoint at the DST-aware Tokyo open, applied to ALL continuation calls (not ex-post scratches) | H4, H11 |
| g) unexplained | 5 / -235 | — | binomial noise | none; used as the null for sizing | — |

### 6.3 How the mode runs each iteration

1. Pathologist re-codes every losing graded night under the incumbent spec (discovery only) and reports cluster x grade x quarter x stop variant, with lifts.
2. The three costliest clusters get mechanism statements; the Theorist whose lens owns the cluster must either propose the encoding or declare it unfalsifiable with current data and file a data request (e.g. Kospi futures, a news feed).
3. The Skeptic checks that each mechanism is not ex-post conditioning (a time-stop applied only to nights that scratched is dead on arrival; a filter that needs the night's own driver is not a feature).
4. A cluster is **closed** when (a) a vault-passed rule removes it from the primary-cause table on discovery without creating a new cluster of equal size, or (b) two pre-registered attempts died, in which case the cluster is re-labelled "accepted loss" in `KNOWLEDGE.md` and no further budget goes to it.
5. Vault-era and forward-era nights are never coded by any agent; the Judge reports cluster counts for Vault-F in aggregate only (the human sees them in the iteration report).

---

## 7 Grade-A research mode

### 7.1 From anatomy to playbook

The Anatomist characterises A on discovery every iteration (n=53 [DISC]; the [FULL] anatomy: 47 of 54 wins resolve to target, median target hour 19:00 ET, 66% hit by the 20:00 bar; continuation winners extend a stretch, stretch20_in_dir 2.41 vs 0.74, t=3.5; mean-reversion winners follow streaks, abs_streak 2.0 vs 1.1, t=3.0; winners have smaller targets, 81 vs 108 pts; confidence, mag, ext_in_dir, VIX level, trailing form do not separate). Findings become playbook rules through `lab/playbook.py`: a rule layer applied *after* `confidence_from_plan` that produces `playbook_call` with reasons (veto, demotion, size multiplier, exit rule), logged side by side with the engine call by `run_daily.py`, so model.py stays stable and every rule cites the hypothesis id that passed. The playbook has three sections: Select (vetoes, demotions, target cap), Timing (entry/checkpoint/exit rules), Size (multipliers from 18:00-knowable inputs only; a sizing rule is registrable only if it improves pts/sigma by >= 10% at <= 5% P&L cost).

"Perfecting A" is allowed to mean: fewer A nights with the same points (pruning wide continuation, far targets, print nights), or the same A nights with a smaller average loss (checkpoint, scratch cap). It is not allowed to mean a rule built on fewer than 30 graded discovery nights, and it is not allowed to reduce A below 2.5 nights/month or below 60% of discovery A P&L.

### 7.2 Fragility battery (run by the harness on every Grade-A slice and every candidate spec; all reported in `anatomist.json`)

| Test | Current reading [FULL] | What it guards against |
|---|---|---|
| Weekly-block bootstrap 90% CI of A avg | +21.3 (+2.7 .. +38.0), P(mean <= 0) = 2.7% | the whole edge being noise |
| Top-k dependence | top-5 wins = 41% of A points; +972 without them; worst-5 losses = 47% of loss points | a few nights carrying the result |
| Quarter concentration | best quarter 36% of total; two consecutive quarters net flat; A win < 50% in 2025Q4 and 2026Q1 | single-regime edge |
| Sunday share | 12 Sunday A nights = 52% of A points (7/7 in discovery) | a 12-night slice masquerading as structure (forward band H8, never a feature) |
| Fill sensitivity | 18:00-open fill +1702 vs +1662; Sunday A +707 vs +868; 3 A nights open past the target, 2 past the stop | the 17:00 reference being unfillable |
| Cost sensitivity | not yet applied; at 1.5 / 4 pts RT | gross edges that die net |
| Same-bar ambiguity | 1 of 26 continuation A wins is a same-bar touch | hourly first-hit artefacts |
| 15-minute re-resolution | vault era only (Referee); disagreement rate reported | hourly conservatism / mislabels |
| Reward:risk | 0.77 (avg win +72.5 vs avg loss -93.9); edge is the 69% hit rate alone | a hit-rate edge that one regime shift erases |
| Scratch share | 23 of 78 A nights (-1145); A losses are scratches 16 (-1308) more than stops 8 (-946) | slow bleeds the stop never catches |
| Random-filter null | for every A-slice claim | "any 10% skip looks good" |
| Replication arms | ES same window; pseudo-vault 2024-10..2025-03 | NQ-idiosyncratic or era-specific structure |
| Deflated Sharpe | `N_trials` = registry size incl. pre-charge | selection among many looks |

### 7.3 Subgroup policy

| Discovery graded n in the slice | Allowed outcome |
|---|---|
| >= 30 | may become a registered hypothesis (gate / guard / rule) |
| 15-29 | "prior to watch": registered with a forward band only; no spec change until >= 25 affected forward nights |
| < 15 | free rule with a no-harm criterion (flagged nights' net P&L <= 0 on discovery and on the vault) or nothing |

---

## 8 First-iteration backlog (ranked by expected value of information = points at stake x probability the test changes the spec / cost; all effects are pre-registrations sized on [FULL]/[DISC] priors and are pre-charged to the ledger)

| # | id | Hypothesis | Test | Predicted effect | Code touchpoint | Route |
|---|---|---|---|---|---|---|
| 1 | **H0** | Integrity bundle H0a-H0h (2.3): the published Grade-A edge contains look-ahead from the pooled calibrator and the in-sample range/EV models, a mixed entry reference, an unfillable 17:00 fill, DST-naive Tokyo hours, no costs | Paired discovery re-simulation spec_v0 vs spec_v0.1; A n/win/avg, ECE by bucket, P50/P80 coverage by quarter, fraction of nights whose guard decision changes | A changes membership 15-25%; A avg +27.0 [DISC] -> +12..+22 net; calibration buckets stop matching to two decimals; mid-band gap persists (it is not caused by the leak); 10-20% of nights change guard outcome; P50 coverage on the last discovery quarter rises from ~25% toward 40%; alarm if A avg < +5 | model.py L275-277, L287-324, L428, L452; backtest.py L31-33, L48, L55; sessions.py L25, L190; run_daily.py L27-48; features.py L215 | iteration 0, not charged |
| 2 | **H1** | Winner's-curse calibration: replace conf = p_win/(p_win+p_loss) of the max-EV candidate with a walk-forward isotonic second stage of "won on resolution" against the raw ratio of the chosen candidate (fit on prior graded nights, min 40), or a direct walk-forward classifier of target-before-stop per (kind, variant) with the candidate's own geometry as features | Primary: pooled ECE on graded nights (bootstrap CI); secondary: B/C counts, paired all-night P&L (must not worsen); Vault-H on ECE (59 graded nights detect a 16-point gap) | Discovery mid band 36% realised vs 67% stated (n=58) -> gap within 10 points; ~40% of B and ~50% of C nights -> NO EDGE (B -18.8, C -15.1 avg [DISC]); A membership changes <= 20%; paired P&L +3..+5 pts/night (below the P&L MDE, hence ECE) | model.py L526 (`win_rate_on_resolution`), L545 (`conf`), L552-559; new `RatioCalibrator` fitted in `Engine.train` by replaying prior months; `_candidates` emits geometry features | Vault-H (ECE) |
| 3 | **H2** | Target cap: targets farther than 1.0 x `asia_rng_med20` x entry are lottery tickets at every grade (25 nights, ~30% win, -1610 [FULL]); add `MAX_TARGET_FRAC_OF_RANGE = 1.0` and re-select the best candidate | `harness.rerun_confidence_with_candidates` (nights are re-called, not dropped); paired graded P&L; random-filter null on the removed set; placebo = cap at 1.0 x a random night's med20 | Removes ~8% of graded nights that win <= 40%; graded pts/night +6 after costs; A count -8%, A avg +4..+6; single free parameter 1.0 (no grid) | model.py constants after L481, guard block L529-536 (new reason "target beyond expected range"); backtest.py passes `asia_rng_med20` into `pred` | Vault-H (graded) |
| 4 | **H3** | Dead-weight candidates: wide CONTINUATION (A 8 nights, 50%, -103 [FULL]) and wide fades below confidence 80 (wide variant across grades 90 nights, 50%, -1553 [FULL]) add nights without expectancy; remove wide continuation from `_candidates`, require conf >= 80 for wide fades | Re-call nights with the candidates removed; paired graded and A P&L; degeneracy guard; Skeptic checks replacement candidates are not worse | Graded count -35%; A count -15%; A avg +21 -> >= +26 [FULL prior]; total A pts within -5%; worst A loss -337 -> >= -200 | model.py L491-509 (variant loop), per-variant grade floor in `confidence_from_plan` | Vault-H (graded) |
| 5 | **H11** | Scratch cap: A losses are mostly scratches (16 of 24 [FULL]); the scratch is valued by `exp_rev_bp` whose OOS R^2 is -0.04, so a candidate with p_scratch > 0.30 is a coin flip; add "scratch too likely" to the guard | Paired A and graded P&L; single free parameter 0.30; placebo = cap on p_scratch of a random candidate | A scratch share 29% -> <= 20%; A avg loss -94 -> ~-70; n(A) -20%; A avg +4..+8 | model.py L450 (`scratch`), L529-536 guard, L437-438 shrink | forward track (A-only MDE unreachable) unless the graded effect >= 42 |
| 6 | **H4** | Continuation-only checkpoint at the DST-aware Seoul/Tokyo open: a continuation needs the cash open to extend the US move; if at the close of the first Tokyo-cash hour bar the position is adverse by > 0.25 x stop_dist, exit there; mean reversion untouched (the same rule hurts it: +26 -> +13 [FULL]) | Applied to ALL continuation calls (never ex-post scratches); P&L at that bar's close from hourly bars; paired per-night on continuation nights; quarter sign-consistency; requires H0e | A continuation avg +17 -> +25..+32 (full 20:00 time-stop analogue +17 -> +32, worst night -340 -> -114 [FULL]); MR null; low prior because the analogue flips sign between sample halves | sessions.py `path_outcomes` gains `exit_hour`/`pnl_at_exit`; backtest.py L49-55; `Spec.checkpoint_frac`; `_candidates` EV for continuation (L505) values scratch at the checkpoint P&L | forward track by MDE |
| 7 | **H10** | ES is not tradeable after costs at any grade (A +2.7, B +4.0, C -2.1 gross, sd ~18 [FULL]) and is a replication set only | One-sample weekly-block bootstrap of ES net expectancy by grade vs a +3 pts/night floor; ES sign check for every NQ pass | ES A and C fail the floor; B marginal and fails at 1 extra tick; `report.py` header states "replication set, not traded"; expected ES sign agreement with NQ passes ~70% | report.py ES header; `judge.py` replication check on `discovery/trades_ES.parquet`; `Spec.costs` | discovery-only decision, no wallet |
| 8 | **H6** | Kospi-stress gate: when KOSPI 20-day drawdown < -8% or prior-session \|kospi_ret\| > 2.5% (daily_close.csv, knowable at 18:00), demote MEAN REVERSION one grade (continuation unchanged); the 2025Q4-2026Q1 A failure coincides with the Korea/Japan chip unwind | Add `kospi_dd20`, `kospi_ret` via `assert_knowable`; veto_fn; paired P&L on gate-active nights (~40 on discovery) and all nights; placebo = the same gate on HSI | Fade stopped rate on gate-active nights 45% -> 30%; A avg +2..+3; B avg -19 -> -12; all-night +4..+6 pts (forward track); the forward track is where the gate matters most | features.py `build_feature_table` X block (L143), `KNOWN_AT_1800`; `Spec.veto_fns`; `RULES` entry for the report | forward track; Vault-H only if the all-night discovery effect >= 27 |
| 9 | **H7** | Wide stops from 0.6 x 20d median Asia range are too tight when vol expands and the P80 model under-covers; size the wide stop as 0.6 x walk-forward q80 (needs H0b) | Primary: stopped_w rate on wide-fade graded nights; secondary paired P&L on those nights; placebo = med20 scaled by the same constant (if the gain is "a wider stop" the placebo matches and H7 dies); single free parameter 0.6 | stopped_w on wide fades 35% -> ~25%; B wide-fade avg -12 -> -4; A wide fades unchanged within 5 pts | features.py L241-250 `wide_stop_distance`; sessions.py `stop_dist`; model.py L432; `Spec.wide_stop_rule` | forward track |
| 10 | **H5** | After-hours print veto: \|post_ret\| > 0.3% or `megacap_earnings_tonight` = 1 -> NO EDGE (12 graded nights, 42%, -600; A 1 of 4 [FULL]; only 2 A nights in discovery) | Free rule: flagged nights' net P&L <= 0 on discovery and on the vault; random-filter null; the Catalyst theorist verifies each flagged night's print with sources | Flagged discovery nights ~8-10 at mean -40..-50; +1.5..+2 pts/night over all nights; A nights lost <= 3; retained only if Vault-F flagged nights (~1-2/month) average below zero over 60 nights | `Spec.veto_fns` on `post_ret`, `megacap_earnings_tonight` (calendar_features.py L96); report.py section 1 prints the veto reason | free rule + forward band |
| 11 | **H9** | Thin sessions: `pre_holiday` = 1 or an expected Asia session < 9 bars has no edge (5 graded, 0 wins, -235; A 0 of 3 [FULL]) | Free rule, no-harm only; affected nights counted on the ledger | ~0 cost (< 1 A night/month); affected A nights win <= 40% | calendar_features.py L173-174; sessions.py expected bar count from `US_HOLIDAYS`; `playbook.py` THIN_SESSION_SKIP | free rule |
| 12 | **H8** | Sunday-reopen A record (7/7 [DISC], 12/12 [FULL], +72 avg) is a selection artefact of n=12; the true win rate is <= 75%; fills at the Sunday 18:00 open with 4 pts cost and a stand-down when the opening gap is already past the stop (`open_past_stop`) | No vault test; forward band on the first 12 Sunday A nights (reject the artefact reading only if win >= 75% and avg >= +30 net); stand-down evaluated with a random-filter null among Sunday nights | Forward Sunday A win 65-75%, avg +15..+30 net; no spec change either way until 12 forward observations | `judge.py`/`ledger.py` monitor keyed on `sunday_open == 1 & grade == A`; `playbook.py` SUNDAY_STANDDOWN using the 18:00:00 print (known at execution, not at grading) | forward band |
| 13 | **H14** | ES-agreement confirmation: NQ A nights where the ES engine issues the same call average +43 (n=28) vs -8.5 when ES graded the opposite call (n=21) [FULL]; index-wide vs NQ-idiosyncratic move | Join `trades_ES`; paired A P&L with the filter; placebo = the filter on NO-EDGE NQ nights (must not help); CPCV on the filter; 50% prior of noise | Filtered A avg >= +30, disagreeing nights <= +5 on discovery; n(A) 78 -> ~45; admissible only if the gap holds in CPCV | backtest.py join of the ES sim by date; `Spec.require_es_agree`; `run_daily.py` builds both engines before grading | forward track |
| 14 | **H13** | Print-override direction frame: when \|post_ret\| > 0.2% and sign(post_ret) != sign(rth_ret), the overnight trades relative to the 16:00-17:00 print, not the RTH move; use d = sign(post_close - rth_open) on those nights | Primary: OOS Brier of `stopped` and `hit_vwap_first` (target-shift test mandatory); secondary: graded P&L on the re-framed nights | Brier improves >= 0.01 on re-framed nights; re-framed graded nights win >= 55% vs < 45% under the old frame | features.py L176 (`d`), L70 (`post_ret`); FEATURE_COLS unchanged | forward track (model-input change; Referee may hold it to iteration 2) |
| 15 | **H12** | Two-stage execution for MEAN REVERSION: decide at 18:00, fill at the 20:00 open only if the 18-20 move against the call is <= 0.25 x q50, else cancel (the move_18_20 separator, t=4.3 [FULL], is partly mechanical) | P&L from the 20:00 open with registered levels, bars 20:00-02:59, nights whose target was already touched count as 0; paired vs baseline; dies if the effect disappears when 18:00-bar resolutions are excluded; needs a 19:55 ET production pass | Fills drop 35-45%; A MR win 76% -> >= 82%; per fill +26 -> +30..+36; all-night +3..+6 | sessions.py `path_outcomes(start_hour=20)` suffix `_e20`; `Spec.entry_hour`, `Spec.cancel_frac` | forward track; lowest prior |

Budget note: H0 is run first; H1, H2, H3 are the only first-iteration candidates whose predicted effects can clear the Vault-H MDE (they touch 40-120 nights), which is exactly the 3-per-iteration cap; everything A-specific waits for the forward track as the MDE table dictates.

---

## 9 Metrics and acceptance tests

### 9.1 Metrics (every one reported per spec version, per split, with scope tags)

| Metric | Definition | Target / gate |
|---|---|---|
| `net_exp_A` | mean A P&L after costs, 18:00-open fill, first-hit resolution; 90% weekly-block-bootstrap CI; trimmed mean co-primary | Vault-F: inside the pre-registered band, point >= +10, trimmed mean > 0; candidate acceptance on Vault-H requires the paired improvement >= MDE |
| `paired_all_night` | mean of (candidate - incumbent) P&L over all nights, untraded = 0 | the powered test: lower 90% bound > 0 for any claimed gain; `S*` vs spec_v0.1 on >= 80 Vault-F nights |
| `win_A`, quarter floor | share of A nights > 0; min win rate across quarters with n >= 8 | >= 65%; no quarter < 50% |
| `rr_A` | avg win / \|avg loss\| on A | >= 0.9 (0.77 now [FULL]) |
| `ece_pooled`, `ece_bucket` | \|realised - stated\| over graded nights, buckets [56,63) [63,72) [72,80) [80,90) [90,100] | pooled <= 10 on Vault-F; bucket <= 8 where n >= 30 |
| `grade_exp` | net expectancy of every issued grade | >= 0 for every grade still issued |
| `scratch_share_A` | A nights unresolved at 03:00 | <= 20% (29% now [FULL]) |
| `coverage_p50/p80` | walk-forward range-model coverage, trailing 60 nights | 45-55% / 75-85% (P50 ~23% now in the recent regime) |
| `coverage_A` | A nights per month | >= 2.5 |
| `brier_guard` | calibrated Brier of hit_vwap_first / stopped / stopped_w under the joint spec vs spec_v0.1 | not worse by > 0.005 |
| `dsr_A` | deflated Sharpe with `N_trials` = registry size incl. pre-charge | > 0 at 95% on Vault-F for CONVERGED-CONFIRMED |
| `alpha_ledger` | Vault-H tests used of 12, Holm FWER; Vault-F BH FDR; hypotheses by status | FWER <= 0.10; FDR <= 10%; in every report |
| `tracking_error` | realised Vault-F A expectancy minus the pre-registered band | inside; 20 rolling nights below triggers the regime re-open, never a tweak |
| `ledger_n` | forward nights whose call hash was committed before 18:00 and scored after 03:00 | >= 80 nights, >= 25 A before any CONVERGED-* state |
| `resolution_fidelity` | hourly vs 15-minute first-hit disagreement on the archive | known within ±5 points; path resolution moves to 15m if > 10% |

### 9.2 Acceptance tests (`harness/acceptance_tests.py`, run on every candidate before any result counts)

1. Determinism: two runs with fixed seeds give identical `results.json`.
2. Incumbent reproduction: the candidate with its flag off reproduces the incumbent's trades to 1e-9; spec_v0 reproduces `backtest_trades_NQ.csv` discovery rows to 1e-9 (re-run after every integration).
3. Data hash: every `data/*.csv` SHA256 is in the manifest for the spec version.
4. Path whitelist: no file access outside `research/lab/discovery/` and the harness; import whitelist.
5. Knowability: every feature column in `KNOWN_AT_1800`; `assert_knowable` on new columns; catalogue/narrative columns absent.
6. Target-shift: outcomes shifted +1 night drive every classifier's Brier to base rate ± 0.01.
7. No full-sample fits inside `simulate`: every `fit()` call is keyed by month and sees only earlier data.
8. Degrees of freedom: declared free parameter(s) match the config diff; grid <= 3 values.
9. Guard sanity: candidate changes no grade count by > 40% unless registered; A nights >= 2.5/month; >= 60% of discovery A P&L retained.
10. ES no-harm: paired ES lower 90% bound >= -1 pt.
11. Runtime: < 10 minutes on cached probabilities (retraining candidates flagged and scheduled).
12. Production path: `run_daily.py --sym NQ --date <discovery date>` still runs and prints the spec version and playbook call.

---

## 10 Cost and cadence

**Agent runs per historical iteration**: 2-3 forensics + 4 theorists + 2 skeptics + 4 cross-read/rebuttal + 1 referee + <= 5 experimenters (x2 calls: implement, interpret) + <= 3 replicators + 0-1 integrator + 1 librarian ≈ 19-25 bounded calls, each <= 25k tokens in and <= 5k out, i.e. roughly 0.5-0.7M input tokens per iteration. Forward phase adds 1 short labeller call per trading day (~17/month) and 1 regime call per week.

**Wall-clock**: iteration 0 (seal, Spec refactor, 1e-9 reproduction, H0a-H0h, OOS caches) is the engineering lift: 3-5 working days. A historical iteration is ~4-6 hours: forensics and theorists in parallel (~30 min), skeptic/cross-read/referee (~30 min), experiments on cached OOS probabilities (seconds each; a retraining candidate takes ~10 min for 9 classifiers x monthly refits; CPCV only when a grid exists), replication and vault (~30 min), librarian (~15 min). The historical phase (4 iterations) runs in 2-3 weeks, paced by the human reading each `iteration_report` rather than by compute.

**Weekly live cadence** (forward phase, 6 months max):

| When (ET) | What | Who |
|---|---|---|
| 17:20 every trading day | `run_daily.py --refresh` (append-only), engine call + playbook call logged to `board/forward/`, hash appended to `forward_chain.txt` | script |
| by 17:50 | `asia_origin_risk`, `ah_shock`, `headline_regime` row hashed | Prospective Labeller |
| 03:10 next day | outcome resolved from the 15m archive (hourly fallback); `asia_driver` filled | script; Labeller |
| Friday after 17:00 | regime label for the coming week; weekly ledger scoring; kill-switch check; calibration drift check | Regime Labeller; script |
| nightly | 15m bars appended to `data/NQ_15m_archive.csv`, `ES_15m_archive.csv` | script |
| 1st trading day of the month | previous month's forward hypotheses judged (BH 10%); Vault-F metrics updated; one iteration; spec frozen and next month's forward hypotheses hash-registered | script + agents |
| monthly | seal manifest re-verified; DSR and alpha ledger in the report | script |

---

## 11 Risks and what would make us abandon the project

**Risks**

- H0 may show the honest baseline is materially weaker than +21.3 [FULL]; the loop must then conclude the maximum is a smaller, rarer edge rather than manufacture one.
- Power is the binding constraint: Vault-H has 25 A nights (MDE 62-80 pts/night); most A-specific refinements will die unconfirmed when the forward phase ends. The likely honest end state is "calibration fixed, B/C retired, far targets and wide continuation pruned, costs applied, Grade-A edge unconfirmed at this sample size". The user should expect that.
- Contamination: Vault-H aggregates are known to the designer and vault-era narratives are in the agents' memory; Vault-H is semi-clean and the pre-charged ledger only partly accounts for it. Only Vault-F is clean, and it accrues ~4 A nights/month.
- Regime non-stationarity: discovery spans the tariff shock through the Iran war start; Vault-H is the Jun-Nov 2026 chip unwind and crash; effects can be regime-specific in either direction; sign consistency reduces but does not remove this.
- Execution realism: hourly first-hit ambiguity, 18:00 gaps through stops, thin Globex depth; realised slippage on Sunday and post-print opens may exceed 4 pts; 52% of A points sit on 12 Sunday nights [FULL].
- Data: the yfinance 730-day cap, missing or revised bars, the stale features CSV; without H0f/H0g every iteration tests a different sample than the report shows.
- Agent failure modes: herding on the obvious filters, re-proposing dead ideas under new names, rationalising near-misses, tuning on discovery before freezing a prediction. Dedup, the graveyard, the deterministic Judge, the Replicator and the pre-registration hash are the defences; informal discovery looks before registration are still invisible to BH, which is why the forward stage is mandatory.
- Orchestrator brittleness: schema failures, non-deterministic sklearn seeds, a harness bug; the 1e-9 reproduction assertion must be re-run after every integration.
- Spec complexity creep and silent redundancy between passed rules (H6 and H1 both removing B nights); the joint-spec persistence check catches breakage, not redundancy.
- Catalogue facts are agent-written and partly unverified; H5/H6 mechanisms inherit that; source verification by the Catalyst theorist is mandatory.
- Operational drift: if `run_daily.py` does not use `lab/decision.py`, the forward ledger tests a different engine than the one integrated.
- The forward phase is slow by design; pressure to shortcut the vault is the failure mode the design exists to prevent.

**Abandon the project when any of these holds**

1. After H0, Grade-A discovery net expectancy has a 90% CI that includes zero on 53 nights and the lower bound stays below zero after the three Vault-H-eligible fixes (H1-H3): there is no honest historical edge to refine.
2. FAILED per 1.3: `S*` vs spec_v0.1 paired all-night lower bound < 0 on >= 80 Vault-F nights, or the kill switch fires and the post-mortem names no mechanism.
3. The Vault-H wallet is spent and the forward phase ends its 6 months in CONVERGED-UNCONFIRMED with Grade-A forward expectancy below +5 pts net: paper-trade only, no capital, no further mining.
4. The data cannot be kept honest: the seal manifest or the forward chain fails verification twice, or the hourly archive develops gaps that change resolved outcomes.
5. ES fails the tradeability floor (expected) *and* NQ passes fail to replicate on either arm for two consecutive iterations: the surviving rules are NQ-and-era-specific artefacts.

What the loop is not allowed to do in response to any of these: extend the budget, move the cutoff backward, re-open a dead hypothesis under a new name, or redefine "maximum" as a number.

---

## 12 Completeness patch (supersedes conflicting text above)

### 12.1 Additional iteration-0 integrity fixes (logged H0i-H0l, not charged)

| id | Defect (verified in the repo) | Fix |
|---|---|---|
| **H0i** | Contract splices in `data/NQ_1h.csv` / `ES_1h.csv`: NQ 2024-06-23 18:00 (+1.27% vs ES 0.00%), 2024-12-22 18:00 (+2.9% vs +0.1%), 2025-03-21 16:00, 2025-09-16 16:00/18:00/19:00 (±0.97% toggles; `post_ret` for 2025-09-16 is fake); ES toggles between two contracts every bar for ~36 h on 2025-12-16/17 (NQ flat). Two NQ splices are Sunday reopens inside the training prefix (labels for RTH dates 2024-06-21 and 2024-12-20 are fake); `nq_minus_es`/`nqes_in_dir` inherit the ES splice. | `harness/splices.py`: flag any between-bar jump where \|log-ret(NQ) − log-ret(ES)\| > 0.45% outside 09:00-16:00 ET, or any within-bar divergence > 0.9% outside RTH, cross-checked against `daily_close.csv` NQ/ES and the 15m file where it exists. Repair = back-adjust the earlier contract by the splice ratio inside the affected Globex date; if the ratio cannot be identified, set that session's outcome labels and every feature derived from the corrupted bar to NaN. Affected sessions are listed in git-tracked `data/splices.csv` (fixed at seal; Validity Auditor signs it). Forward: the 03:10 ET resolver runs the detector on the new bars before resolving; a flagged night is `unresolved_splice` and excluded from every band. `--refresh` never overwrites a stored bar; a per-bar diff log (`data/bar_revisions.csv`) records any value yfinance later changes. |
| **H0j** | `stopped=1` and `hit_vwap_first=1` co-occur on 13 of 588 sessions for the tight pair and 22 of 588 for the wide pair (verified by recomputing `features.path_targets`; `path_outcomes` keeps walking after a target hit), so `stopped` = "stop before the farthest target"; `simulate` books a CONTINUATION win on `stopped==1` even when its own stop (VWAP) was touched first. | `harness.resolve(bars, entry, target, stop, side, fill_rule)` walks the bars for the candidate's own pair and is the only P&L path for every spec (incl. spec_v0.1); classifier labels keep their definitions, documented as "stop before the farthest target"; per-target stop labels are a registrable model-input hypothesis (forward route). |
| **H0k** | Stop-through gaps are filled at the stop level. | If a bar's Open is beyond the stop, fill at Open (15m bar where archived, else hourly); targets fill at level. The difference vs level fills is a line in the cost table. Sunday/print nights additionally use the first 15m bar's midpoint when available. |
| **H0l** | Train/live skew at 17:20 ET: `dchg`/`dlvl` forward-fill daily closes, so a missing day-D VIX/DXY/US10Y/USDJPY row silently becomes D-1; `rth_vol_rel` may be partial; `event_calendar.csv` ends 2027-01-28. | `harness.live_inputs_ok(D)`: every daily-sourced model feature must have a D row (N225/KOSPI/HSI/SSE: the D-dated row from the prior night), RTH volume must be final, the calendar must extend ≥ 60 days. If not, retry at 17:50; if still stale the call is logged `stale_inputs` and counts in `ledger_n` only if the inputs later match the backtest's (checked at 03:10). |

Also at iteration 0: `agent_prompts/weekly_patterns.md` steps 1 and 4 are deleted (no `--refresh`, no `backtest.py`, no recommendations on guard constants); the weekly agent may only file registry proposals. Harness self-test: four planted leaks (a feature built from the 19:00 bar, the pooled calibrator, a catalogue-tag feature, a splice-driven gap feature) must each be caught by `acceptance_tests.py` before iteration 1; failure blocks the iteration.

### 12.2 Vault-H contamination tiers and leak channels

- Registry field `contamination ∈ {none, aggregate_seen, effect_seen}`. H1, H2, H3, H4, H5, H6, H7, H8, H11, H14 are `effect_seen` (sized on [FULL] numbers that include vault nights). A Vault-H PASS on an `effect_seen` id is recorded **PASS\***: it may be integrated into the paper-traded spec but does **not** satisfy provenance 1.2(1) until the same id is BH-confirmed on Vault-F or its forward band holds on ≥ 25 affected nights. Only `none`/`aggregate_seen` ids can earn an unstarred PASS.
- spec_v0's constants (72/63/56, 0.25/1.0/0.03, 0.6, C=0.08, GBM depth 3/150 iters, `FEATURE_COLS_COMPACT`, min_train=150) were chosen on the full sample: `N_trials` starts at 25 (15 informal looks + 10 model-development trials). Absolute Vault-H numbers are inflated; only paired tests vs the vault-tuned incumbent are interpretable, and they favour the incumbent.
- spec_v0's 1e-9 reproduction needs vault nights (pooled isotonic, full-sample regressors): it is run once by the orchestrator at seal time with vault access and never again; agents can only run spec_v0.1.
- Web access during the historical phase is restricted to the Prospective Labeller and to the Catalyst theorist for **discovery-era** source verification; any hypothesis whose mechanism or sizing cites a post-cutoff event is `route: forward` by rule.
- Reusable-holdout control: agents see only `{PASS/FAIL, sign, cleared_MDE}` per Vault-H test; the CI and point estimate stay in `vault_ledger.jsonl` and are released when the historical phase ends.
- Blind labelling: the labeller receives `--blind` briefs with the "quantitative engine's call / active setups" block removed; the supports/contradicts narrative is a second call after the label hash is in the chain. A second label row is written Sunday 17:30 ET for Sunday reopens; the Friday 17:20 call remains the call of record.

### 12.3 Stopping rule, made computable from the files

1. **Nightly multi-spec log.** `forward/<date>_<SYM>.json` gains `calls: {spec_id: {call, grade, confidence, geometry, playbook_call, pnl_net}}` for spec_v0.1 and every version in the chain; the 03:10 resolver fills `pnl_net` for all of them by `harness.resolve`. 3(a) = mean over nights of `pnl_net[S*] − pnl_net[v0.1]` (untraded = 0), ISO-week blocks, 5000 resamples, seed 7.
2. **One S\*.** The paper-traded spec may be bumped at most once in the forward phase and only at the start of forward month 1 or 2; later vault/BH passes are integrated into a *shadow* spec that is logged nightly like any chain version but not paper-traded. The 80-night clock restarts on a bump; a state is declared only for a spec with ≥ 80 logged nights.
3. **Alpha accounting.** Vault-H: a pre-allocated schedule of 12 slots at α = 0.10/12 each (Bonferroni, valid online); unused slots do not roll over; the verdict is `p ≤ slot_alpha`, written to `vault_ledger.jsonl` with the slot number. Vault-F: BH at q = 0.10 is run on the first trading day of each month over the family of **all** forward tests resolved to date; an id is `forward_confirmed` only if BH-rejected in the month it resolves **and** at the terminal evaluation; an element that falls out at the terminal evaluation is removed from S\* and the state is at best CONVERGED-UNCONFIRMED. Condition 4 becomes: every S\* element passed in its Vault-H slot or is `forward_confirmed` at the terminal evaluation.
4. **DSR inputs.** `results.jsonl` stores `sr_disc` (annualised Sharpe of the candidate's Grade-A series on discovery) for every trial, including dead, duplicate and grid entries; DSR uses `N_trials`, `Var(sr_disc)`, and the skew/kurtosis of the Vault-F per-night series; `dsr_A > 0.95` is the CONFIRMED gate.
5. **Kill switch / re-open in reachable units.** Kill: trailing 12 Grade-A forward nights with net sum < −1.5 × 90 × √12 (≈ −470 pts), or pooled ECE > 15 on the trailing 40 resolved graded nights. Re-open: after ≥ 40 forward nights, paired (S\* − v0.1) 80% lower bound < 0 over the trailing 60 calendar nights.
6. **3(b)/(d).** 3(d): a grade is eliminated when its 90% upper bound < 0; a negative point estimate with UB > 0 is "unconfirmed grade" (blocks CONFIRMED, not UNCONFIRMED). 3(b) is a band check and cannot by itself confirm or fail; the only FAILED trigger is 3(a) or the kill switch.
7. **ECE.** Computed on resolved (target/stop) graded nights only, matching P(target | resolves); scratch rate reported separately; the stated n is resolved nights.
8. **Resolution granularity.** Forward primary resolution = hourly (same as discovery); 15m co-reported as `resolution_fidelity`; moving the path resolution to 15m is a registered spec change, never a silent switch.
9. **Exhaustion.** A forward-track id whose discovery touch rate × remaining forward nights < 25 is marked `unreachable_at_horizon`, excluded from 1.2(2), and listed in the final report.
10. **Band file.** `versions/spec_v<N>.json` gains `forward_band: {A_avg: [lo, hi], A_win_min, ece_max, grades_issued, a_per_month_min, regime_mix_expected}`, hashed into `forward_chain.txt`.
11. **Timestamps.** Every append to `forward_chain.txt` and every forward registration is pushed to `origin` within the same minute; the remote push time (or an OpenTimestamps proof of the chain head) is the evidence; local commit times are not.
12. **Frozen spec ≠ frozen models.** Monthly retraining of the 9 classifiers and the causal calibrator continues in the forward phase; retrain cadence, hyper-parameters and `feature_cols` are fields of the frozen spec, and changing any of them is a spec bump under rule 2.

### 12.4 Replication arms, stated honestly

ES has no edge and the pseudo-vault is a different engine, so a sign is ~Bernoulli(0.5) under each arm's null. An arm **supports** only if its own 80% CI excludes zero in the predicted direction, **contradicts** only if its 80% CI excludes zero in the opposite direction, otherwise **uninformative**. Demotion to forward track happens on a *contradicts* from either arm, never on "neither supports". The forward ledger is the only replication; the report says so.

### 12.5 Memory hygiene

Every `KNOWLEDGE.md` line carries an evidence grade: E0 integrity (deterministic), E1 vault/forward pass, E2 discovery-gate pass ("candidate [DISC]"), E3 forensic observation, E4 agent judgment (incl. Pathologist primary causes). The bundle builder prefixes the grade; `completeness_check` rejects "confirmed" on anything but E0/E1 and runs a claim audit: each cited id must exist and its registry status must support the strength word used.

### 12.6 Regime tag on the terminal state

CONVERGED-\* carries `regimes_covered` = weeks per Regime-Labeller label during the confirming forward window and the share of A nights in each; a confirmation in one regime is reported as "confirmed in {regime}" and the re-open rule stays armed after the stop.

### 12.7 Two notes for the Skeptic seats

`p_scratch` in `trade_plan` is the residual `1 − p_t − p_s` of two separately calibrated marginals (normalised only when they sum above 1), not a calibrated probability; H11's `p_scratch > 0.30` gate is dead on arrival unless H1 first produces a calibrated scratch probability. The after-hours flag `|post_ret| > 0.3%` must be evaluated on splice-repaired bars (2025-09-16 is a false positive today).

**Expected end state, stated up front:** calibration fixed, B/C retired or demoted, far targets and wide continuation pruned, costs and fills applied, splices repaired, Grade-A edge CONVERGED-UNCONFIRMED at the 6-month cap with a smaller, cleaner A; CONFIRMED is a calendar outcome that this horizon most likely cannot deliver.

---

## Appendix A: completeness critic's findings (verbatim, numbers corrected where verified)

**Verdict.** The design is unusually honest about power and contamination, and its skeleton (sealed vault, deterministic Judge, pre-registration hash, MDE routing, three terminal states) is sound. It is not yet executable as written: the stopping rule cannot be computed from the files it describes in six places (no nightly baseline call for the paired test, online Holm, vacuous FDR condition, missing DSR inputs, kill-switch windows unreachable in six months, no band file), and the iteration-0 integrity bundle misses two defects that are visible in the repository today: contract-splice artefacts in both hourly files (which 'append-only' would freeze) and a continuation-booking rule that uses an overlapping label. Vault-H is weaker than 'semi-clean' because the first three vault candidates were sized on full-sample effects and the incumbent's constants were tuned on the same nights; the honest reading is that Vault-H can integrate but cannot confirm, and only Vault-F confirms. With the patch below, every terminal condition is a deterministic function of registry/hypotheses.jsonl, results.jsonl, vault_ledger.jsonl, forward/*.json and versions/*.json; the expected end state is still CONVERGED-UNCONFIRMED with a smaller, cleaner Grade-A, and the design should say so in its first line.

**Missing from sections 1–11 before the patch:**

1. Contract-splice artefacts in data/NQ_1h.csv and data/ES_1h.csv are not covered by H0a-H0h: NQ 2024-06-23 18:00 (+1.27% vs ES 0.00%), 2024-12-22 18:00 (+2.9% vs +0.1%), 2025-03-21 16:00 (+0.78% excess), 2025-09-16 16:00/18:00/19:00 (-0.97/+0.99/-0.98% toggles; post_ret for 2025-09-16 is a fake after-hours shock); ES toggles between two contracts for ~36 hours on 2025-12-16/17 (±0.8% every bar, NQ flat). Two of the NQ splices sit on Sunday reopens in the training prefix and corrupt labels; H0f's append-only rule would freeze them forever. No detector, repair rule, or forward nightly check exists.
2. Label semantics / booking defect: stopped=1 and hit_vwap_first=1 co-occur on 13 of 588 sessions (tight VWAP pair; 22 of 588 wide) (sessions.path_outcomes keeps walking after a target hit), so `stopped` means 'stop before the farthest target', and backtest.simulate books a CONTINUATION as a win on stopped==1 even when its own stop (VWAP) was touched first. Zero graded continuation nights are affected today, but H2/H3 re-call nights and could pull them in. The harness must resolve each candidate's own (target, stop) pair by a direct bar walk, not from the 9 classifier labels.
3. Stop-through-gap fills: a bar whose Open is already beyond the stop is booked at the stop level; thin Asia Globex and Sunday opens make this optimistic. Needs fill-at-Open rule (hourly; 15m where the archive exists) and inclusion in the cost line.
4. Train/live skew at the 17:20 ET call: features.dchg/dlvl forward-fill daily closes, so if yfinance has not yet published date D's VIX/DXY/US10Y/USDJPY row, the live call silently uses D-1 values while the backtest used D; rth_vol_rel can be partial intraday. No input-availability assertion; stale calls would enter the forward ledger as if clean. event_calendar.csv ends 2027-01-28 with no horizon check, so calendar flags silently go to 0 after that.
5. Stopping rule 3(a) is not computable from the files as specified: forward/<date>_<SYM>.json logs one spec's call per night, but the paired test needs spec_v0.1's call (and every chain version's) logged live each night (bars are revised, retrains are monthly, so recomputation later is not identical). Also undefined: which S* the 80-night clock applies to when the paper-traded spec changes monthly; at the 6-month cap a spec frozen after forward month 2 cannot reach 80 nights.
6. Condition 4 'Holm family-wise 0.10 over all Vault-H tests ever run' cannot be applied online across iterations (Holm needs the whole family at once); 'FDR <= 10% (BH)' is a property of the procedure, not a checkable condition; the BH family across months is undefined and a hypothesis rejected at month 2 may fall out at month 5.
7. Deflated Sharpe ratio is not computable: results.jsonl stores effect and CI but not each trial's Sharpe, so Var(SR across trials) — a required DSR input — is missing. N_trials also omits the full-sample model-development choices in spec_v0 (72/63/56 cutoffs, guard constants 0.25/1.0/0.03, WIDE_STOP_MULT 0.6, C=0.08, GBM depth/iters, FEATURE_COLS_COMPACT, min_train=150).
8. Kill switch ('rolling 40-night Grade-A') and re-open ('rolling 20-night A win rate') are measured in Grade-A nights; at ~4 A nights/month they need 10 and 5 months, so neither can fire inside the 6-month forward phase.
9. Conditions 3(b) and 3(d) are point-estimate checks on n≈25 with sd≈90 (SE≈18 pts): a true +15 edge fails 3(b) ~40% of the time and a zero-edge grade passes 3(d) ~50% of the time. 3(d) needs a CI rule; 3(b) must be labelled a band check, not a confirmation.
10. ECE is undefined with respect to scratches (confidence is P(target | resolves), so scratch nights must be excluded and the stated n is resolved graded nights). Forward resolution from the 15m archive vs hourly in discovery makes the band comparison apples-to-oranges.
11. Exhaustion condition 1.2(2) is blocked by forward-track hypotheses that cannot reach 25 affected nights before the cap (a 10%-touch veto needs ~15 months); no rule marks them unreachable. The pre-registered forward band has no file location in the schemas.
12. forward_chain.txt is 'git-committed' but local commit timestamps are forgeable; origin exists (https://github.com/Banaqwer/24-yo) and nothing requires a push or an external timestamp.
13. The Prospective Labeller reads the agent brief, which contains the engine's call, grade and active setups (reports/<date>_NQ_agent_brief.md), so prospective labels are anchored on the call; Sunday-night labels are written Friday 17:50 and cannot see weekend news.
14. agent_prompts/weekly_patterns.md tells the weekly agent to run `run_daily.py --refresh` (the 730-day overwrite H0f exists to prevent) and `backtest.py`, and to recommend moving MIN_TARGET_FRAC_OF_RANGE / MAX_STOP_FRAC_OF_P80 / WIDE_STOP_MULT from weekly calibration drift — an unregistered tuning channel outside the registry that the design does not retire.
15. Vault-H contamination is treated uniformly ('pre-charged by 15'), but H1, H2, H3, H4, H5, H6, H7, H8, H11, H14 were sized on [FULL] effects that include vault nights (effect_seen), while the incumbent spec_v0's constants were themselves chosen on the full sample. The design does not distinguish effect_seen from aggregate_seen hypotheses, and a Vault-H PASS on an effect_seen id is counted as provenance.
16. The web-enabled Catalyst theorist can look up post-cutoff (vault-era and Nov-2026) events during the historical phase; that is an unmodelled vault-leak channel.
17. spec_v0's 1e-9 reproduction on discovery dates requires vault nights (pooled isotonic and full-sample regressors), contradicting the seal; it must be a one-time orchestrator check with vault access, never an agent-visible run.
18. Vault-ledger CIs are returned to agents after every Vault-H test; with 12 tests that is a reusable-holdout leak the Bonferroni/Holm accounting does not cover.
19. Replication arms are coin flips: ES has no edge and the pseudo-vault is a different engine (min_train=80), so P(at least one arm agrees by chance) ≈ 75% and a 'neither agrees' demotion fires ~25% of the time on true effects; sign agreement cannot certify or refute.
20. KNOWLEDGE.md has no evidence grading: the completeness script checks scope tags but nothing stops a discovery-gate pass or a Pathologist primary-cause judgment from being written as a 'confirmed fact'. No harness self-test with planted leaks verifies that the acceptance tests actually catch look-ahead.
21. p_scratch in trade_plan is the residual 1 - p_t - p_s of two separately calibrated marginals (normalised only when they sum above 1), not a calibrated scratch probability; H11's 'p_scratch > 0.30' gate is built on it and the design does not flag this.

**Self-deception risks the merged design had not covered:**

- Look-ahead: contract splices (fake Sunday gaps and a fake post-close shock) in the training labels and features; forward-filled daily closes at the live 17:20 call (backtest sees day-D values, live may see D-1); continuation outcome label overlaps its own stop event.
- Survivorship/selection: the Vault-H cutoff (2026-06-01) was chosen after the quarterly A win rates were known, and first-iteration hypotheses H1-H3 were sized on [FULL] numbers that include Vault-H nights, so their Vault-H 'tests' partly recompute known quantities; the incumbent's constants were tuned on the vault era, inflating absolute Vault-H numbers.
- p-hacking across iterations: vault CIs fed back to proposers (reusable-holdout leakage); online Holm is invalid; the weekly pattern agent's guard-constant recommendations and data refresh are an unregistered tuning channel; model-development trials are uncounted in N_trials; 'revise once' after seeing discovery results counts as one trial but the revision choice is informed by the result.
- Agents reading conclusions as facts: no evidence grade on KNOWLEDGE.md lines; the labeller is anchored by the engine's call and active setups inside the brief; Pathologist primary causes are judgments that theorists consume as data; no planted-leak self-test of the harness.
- Regime drift: forward confirmation is a single ~6-month regime by construction and the final state carries no regime tag; the models keep retraining monthly while the 'spec is frozen' — the design does not say the retrain cadence is part of the frozen spec.
- Cost/slippage: gaps through the stop are filled at the stop level; Sunday and post-print first prints are booked at the bar open; the 15m archive is used only as a Referee measurement, not for fills.
- ES being noise: the ES arm's sign is ~Bernoulli(0.5) under its own null, so replication by sign is uninformative; the ES hourly file itself is corrupted on 2025-12-16/17 and nq_minus_es / nqes_in_dir inherit it.
- Terminal-state luck: 3(b) and 3(d) at n≈25 are coin flips in both directions, so CONVERGED-CONFIRMED can be reached by chance under a zero edge and missed under a real one; the design names 3(a) as the powered test but still lists 3(b)-(e) as conditions.
