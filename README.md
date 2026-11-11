# Alt-Data Edge Research Pipeline

A staged research program that turns non-mainstream public data into measurable stock-prediction edge around scheduled earnings events, for a sub-$10k, long-only-and-defined-risk-options account. Driven by the master prompt in `docs/master_prompt.md`, one phase per session, with a gate for approval at the end of every phase.

This is a research framework, not investment advice. Backtested edge is not live edge, and small accounts are hurt most by costs and slippage.

## Layout

| Path | Contents |
|---|---|
| `register/signal_register.csv` | The living Signal Register, one row per signal, updated every phase. The CSV is the source of truth. |
| `register/signal_register.md` | Readable view of the same register plus the phase log. |
| `docs/phase0_report.md` | Phase 0: inputs, the five resolved ambiguities, the tool check, the gate. |
| `docs/phase1_report.md` | Phase 1: idea generation across four lenses, vetting results, rejected ideas. |
| `docs/phase0_capability_matrix.md` | 319 data sources probed from the research container with real requests, with status, unlock steps and terms flags. |
| `docs/phase0_working_sources.md` | The subset of sources that return data or need only a key. |
| `API_KEYS.md` | What accounts and keys you need to create, by tier, with the environment variable name each one will be read from. |
| `data/probe/` | Raw probe output (JSON) and the matrix as CSV. |
| `tools/` | Scripts used to condense and build the matrices and registers. |

## Standing rules (from the master prompt)

- Never fabricate data, results, statistics or sources. Label every claim TESTED HERE, LITERATURE, REASONED or UNKNOWN.
- Every signal is a falsifiable hypothesis with a direction, a measurement window, a target and a lead time over the disclosure it anticipates.
- The edge is the gap between the signal and consensus, never the signal alone.
- Point-in-time discipline. Prefer physical bottlenecks and regulatory exhaust over sentiment.
- Public, lawfully obtained data only. No material non-public information, no scraping behind logins or against terms of service.
- Red-team every finding; report confidence as a number with the main driver of uncertainty named.

## Phase status

| Phase | Status |
|---|---|
| 0 Setup | Done, approved |
| 1 Idea generation | Done, awaiting approval |
| 2 Triage and scoring | Next |
| 3 to 10 | Pending |
