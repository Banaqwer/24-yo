# Alt-Data Edge Research Pipeline

A staged research program that turns non-mainstream public data into measurable stock-prediction edge around scheduled earnings events, for a sub-$10k, long-only-and-defined-risk-options account. Driven by the master prompt in `docs/master_prompt.md`, one phase per session, with a gate for approval at the end of every phase.

This is a research framework, not investment advice. Backtested edge is not live edge, and small accounts are hurt most by costs and slippage.

## Layout

| Path | Contents |
|---|---|
| `register/signal_register.csv` | The living Signal Register, one row per signal, updated every phase. The CSV is the source of truth. |
| `register/signal_register.md` | Readable view of the same register plus the phase log. |
| `API_KEYS.md` | What accounts and keys you need to create, by tier, with the environment variable name each one will be read from. Updated every phase. |
| `docs/phase0_report.md` | Phase 0: inputs, the five resolved ambiguities, the tool check, the gate. |
| `docs/phase0_capability_matrix.md` | 319 data sources probed from the research container with real requests, with status, unlock steps and terms flags. |
| `docs/phase0_working_sources.md` | The subset of sources that return data or need only a key. |
| `docs/phase1_report.md` | Phase 1: method, counts, strongest kept ideas, rejected ideas by reason, critic findings, red team, gate. |
| `docs/phase1_tables.md` | Phase 1: every kept and rejected idea with scores and reasons, seed verdicts, the completeness critic's full text. |
| `docs/phase1_signal_details.md` | Phase 1: the full write-up of every signal (mechanism, hypothesis, sources, vendors, literature, red team, changes made). |
| `docs/phase2_report.md` | Phase 2: method, the top 10 with what carries each and what the verifier found against it, what verification changed, parked summary, dependencies, the critic's disputes, red team, gate. |
| `docs/phase2_scores.md` | Phase 2: the full ranking with scores, merged rows, the critic's top-10 rationale and first build steps, the parked list with reasons, disputes and concerns. |
| `docs/phase2_scoring_details.md` | Phase 2: every scorer's per-criterion justification and lead-time arithmetic, and every verifier probe, change and refutation. |
| `data/probe/` | Phase 0 raw probe output (JSON) and the matrix as CSV. |
| `data/phase1/` | Phase 1 raw workflow output (JSON): every idea, verdict and critic finding. |
| `data/phase2/` | Phase 2 raw workflow output (JSON): every score, verifier verdict and the critic's text. |
| `tools/` | Scripts used to condense and build the matrices and registers, and the multi-agent workflow scripts. |

## Standing rules (from the master prompt)

- Never fabricate data, results, statistics or sources. Label every claim TESTED HERE, LITERATURE, REASONED or UNKNOWN.
- Every signal is a falsifiable hypothesis with a direction, a measurement window, a target and a lead time over the disclosure it anticipates.
- The edge is the gap between the signal and consensus, never the signal alone.
- Point-in-time discipline. Prefer physical bottlenecks and regulatory exhaust over sentiment.
- Public, lawfully obtained data only. No material non-public information, no scraping behind logins or against terms of service.
- Red-team every finding; report confidence as a number with the main driver of uncertainty named.

## Phase status

| Phase | Status | Register |
|---|---|---|
| 0 Setup | Done, approved | Empty register, 319 sources probed |
| 1 Idea generation | Done, approved | 110 rows: 59 IDEA, 51 REJECTED |
| 2 Triage and scoring | Done, awaiting approval | 110 rows: 10 SOURCING, 49 PARKED, 51 REJECTED |
| 3 Data sourcing plan | Next | Sourcing plan and kill test per SOURCING row |
| 4 to 10 | Pending | |
