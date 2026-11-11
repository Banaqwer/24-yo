# Phase 2 report: triage and scoring

Date: 2026-11-11. Input: the 59 IDEA rows left by Phase 1. Output: a top 10 moved to SOURCING, 49 rows PARKED with a one-line reason each, and the per-signal scores in `docs/phase2_scores.md` (ranking, merged rows, critic rationale, parked list, disputes, concerns) and `docs/phase2_scoring_details.md` (every scorer's justification and every verifier probe). Raw workflow output: `data/phase2/phase2_workflow_results.json`.

Headline: the rubric produced a top 10, but the adversarial verifiers argued that four of those ten should not be there, and only four of the ten carry an explicit "stay" verdict. The verifiers' objections landed on properties the rubric does not score (event frequency, whether the comparison variable exists, whether the mechanism showed up in the first live check), so the weighted score barely moved and the arithmetic kept them. Section 4 says what I did about that and section 8 asks for a decision.

## 1. Method

- **Scoring rubric.** Master prompt Phase 2: each signal scored 1 to 5 on A data accessibility (20%), L lead time (20%), S signal-to-noise (20%), C crowdedness inverse (15%), U universe coverage (10%), H history depth (10%), G legal cleanliness (5%). Written anchors for every band (the rubric text is in `tools/workflows/phase2_triage_scoring.js`), including the rule that lead time must be computed from the release schedule, not copied from the record.
- **Inputs.** Compact Phase 1 records (vetted hypothesis, sources with probe status, lead time, universe, red team, critic adjustments) plus a facts sheet of hard constraints: which keys are verified, which sources are unreachable from the container, the single-site-family coverage cap, and the Phase 1 critic's crowdedness caps.
- **Judge panel.** Three independent scorers per batch with different briefs (data engineer, quant PM, skeptic), five batches of 11 or 12 signals with lenses interleaved, 15 scoring runs. Panel score per criterion = lower median of the three (ties to the lower value). 59 of 59 signals scored, none missing.
- **Overlap merge.** Six Phase 1 overlap groups resolved by keeping the higher panel score; seven rows folded (N02 into N58, N10 into S16, N26 and S24 into N22, S07 into N03, S27 into N09, S31 into N27). This was done on panel scores, before verification. See section 4 for the consequence.
- **Adversarial verification.** The panel's top 15 each went to a separate verifier agent with live access, told to re-derive every criterion from evidence, probe the sources that day, check release schedules on EDGAR, search for vendors and literature, and write the strongest case against. Final scores for those 15 are the verifier's; the other 37 ranked rows keep the panel median. 470 live tool calls across the run; every probe is listed in the details document with its URL and status.
- **Critic.** One agent read every row, verdict and probe, wrote the top-10 rationale, dependencies and first build step, a one-line reason for every parked row, the ranking disputes, and the concerns. Its confidence: 45%.
- **Register mapping.** Crowdedness = C, Expected signal/noise = S, Legal risk = 6 minus G, Confidence % = the verifier's confidence where one ran, Next action = rank and Phase 3 gate or the parked reason. Status SOURCING for the ten, PARKED for the rest.
- **Tie-break.** The workflow sorted on the weighted score only. Ties kept Phase 1 id order (S, then N, then G), which is arbitrary, not a rule. It matters once, at the four-way tie at 3.35 (section 4).
- Cost: 31 agents, about 4.1 million tokens, 2 h 22 min wall clock.

## 2. Results

Score distribution over the 52 ranked rows (the merged seven excluded):

| Weighted score | Rows |
|---|---|
| 3.25 and above | 15 |
| 3.00 to 3.24 | 14 |
| 2.50 to 2.99 | 19 |
| below 2.50 | 4 |

The field is flat. The gap between rank 1 (3.65) and rank 15 (3.25) is 0.40, within what a one-point change on a single 20% criterion produces. Ranks are therefore suggestive, not decisive, and the verifier text matters more than the order.

### 2.1 The top 10

| Rank | ID | Signal | A L S C U H G | Score | Verifier | What carries it | What the verifier found against it |
|---|---|---|---|---|---|---|---|
| 1 | N18 | USDA broiler placements and AMS egg and chicken prices (CALM, PPC) | 5 5 3 2 1 4 5 | 3.65 | drop (55%) | AMS prices final at quarter end; 8-K dates give 31 to 53 day leads; MARS and NASS keys verified | The named consensus source returns null revenue for CALM and one or two EPS estimates for PPC, so the hypothesis as written cannot be run; Cal-Maine's conventional eggs price off Urner Barry, not the AMS index; two names, one HPAI/feed driver, about eight correlated events a year |
| 2 | N15 | NRC daily reactor status: unplanned outage days (TLN) | 4 5 3 2 1 5 5 | 3.55 | stay (60%) | Gapless free files to 1999; 30 to 37 day leads; crawling permitted | The 10-EFPD unplanned trigger never fired in a Q3 in seven years; the largest event (Susquehanna Q2 2025) produced no negative surprise; needs PJM prices (account not created) and point-in-time consensus EPS; at best a veto rule for one merchant name |
| 3 | N50 | Rooftop-weighted hail-swath index from NEXRAD hail signatures (OC, QXO) | 4 5 3 2 1 5 5 | 3.55 | stay (55%) | Frozen yearly signature files to 1995; 30 to 51 day leads; Census key verified | Primary SWDI web service returned 500 on all 14 calls (bulk CSV fallback works); the only quantitative treatment found puts the roofing boost in the same quarter with payback two quarters later, the opposite lag to the hypothesis; QXO's acquisitions break year-over-year comps |
| 4 | N03 | EPA NPDES effluent flow and organic load at single-site plants | 5 3 2 5 1 4 5 | 3.50 | drop (60%) | Keyless ECHO JSON, bulk DMR zips 2009 to 2026, no vendor or paper uses it; DMR receipt dates give 9 to 18 day leads | At the flagship permit (AdvanSix Hopewell) the process outfall is flat at 19 to 21 MGD for 15 months while cooling-water outfalls swing; three of the five gate names have no usable process-flow permit; three or four usable permits, not 13 names |
| 5 | N09 | npm package-download share for vendor-owned billable SDKs | 5 4 2 3 1 5 4 | 3.45 | stay (55%) | Daily history since 2015, keyless, one-day lag, kill rule written into the hypothesis; the cheapest full backtest in the set | Downloads count CI re-pulls driven by release cadence; nine tickers under the vet-restricted spec; permanent zero-day holes in registry totals; TickerTrends already sells the series |
| 6 | N22 | NHTSA Part 573 recall filings and remedy-completion reports | 5 4 2 3 1 4 5 | 3.40 | drop (65%) | Free daily flat files; quarter tally public by QE+10, median lead 19 to 20 days | Only 15 to 25 firm-quarters since 2015 clear the 1%-of-revenue remedy trigger against the record's own 60-event abandon gate; nine active names; THO and WGO fiscal quarters do not align with the completion reports; survived the merge with N26, which now scores higher |
| 7 | G02 | FDA drug-shortage transitions and competitor ANDA approvals | 5 5 2 3 1 2 5 | 3.40 | drop (72%) | Structured openFDA with a verified key; 29 to 35 day leads | Forward-collection-only: the shortages endpoint is current-state and purges Resolved rows after about three months, so the entries it trades cannot be backtested; 5 to 7 names, two with no shortage rows as suppliers; four quarters of snapshots needed before any trade |
| 8 | S33 | Supplier-first disclosures flagging customer cuts | 4 3 3 3 3 4 4 | 3.35 | not verified | The only top-10 row with coverage above a dozen names (reasoned 120 to 150) and a direct driver when it fires | Entered the top 10 only because four panel rows were demoted; U and S are panel reasoning, not counts; the transcript leg is dead (API Ninjas transcripts are premium-only), so events must come from 8-K exhibits alone |
| 9 | S04 | AIS vessel calls at exclusive-use bulk, LNG and fertilizer terminals | 5 4 3 2 1 4 3 | 3.35 | not verified | NOAA daily AIS zips give a 2010 to 2024 backtest; draft-weighted loaded departures are a direct volume measure | No free live history: the NOAA archive stops at 2024 and aisstream must be self-archived from day one; aisstream has no terms page (legal amber); 5 to 8 verified berths |
| 10 | S16 | Summed federal civilian contract obligations (USAspending) | 5 4 2 2 2 4 5 | 3.35 | stay (55%) | Keyless, near-final by QE+7, 14 to 29 day leads, 15 to 20 civilian-heavy names | The first live check was wrong-signed for two of three names (BAH civilian obligations +8% against Civil revenue -15%; ICF -5% against revenue +1%); September carries 61 to 75% of a Q3's obligations as year-end funding of next year's work |

Lens mix: four physical (N18, N15, N50, S04), four regulatory (N03, N22, G02, S16), one digital (N09), one second-order (S33). Seven of the ten have U = 1 (under a dozen names) and five of the ten have S = 2. Eight of the ten are physical-economy industrial, materials, energy or staples names; no restaurant, retail or consumer-digital row survived.

### 2.2 What verification changed

The panel's top 10 was N15, N03, S18, N09, S16, N50, N01, N21, N22, N04. Six of those fell out after live checks:

| ID | Panel | Final | Why |
|---|---|---|---|
| S18 Clustered insider buying | 3.60 | 2.70 | L 5 to 1: the reading is itself a Form 4 filing, priced on posting (trade-to-filing lag median 2 days); U 3 to 2: the record's own rule yields about 8 or 9 in-universe clusters a quarter. Scorer spread of 4 on L |
| N01 Texas mixed-beverage receipts | 3.50 | 3.20 | L 3 to 2: the September quarter became final in the November 7 refresh, after every covered print, so only two of three months are readable; U 2 to 1: 8 to 10 names with 20 or more matched units |
| N21 MSHA closure orders and Form 7000-2 | 3.50 | 3.15 | S 3 to 2: 141 of the 156 qualifying orders are 103(k) accident-control orders that are routinely modified to let the mine keep running, so the sign is ambiguous; C 3 to 2: S&P Platts republishes the series and the counts are mandatory 10-Q Exhibit 95 disclosures |
| N04 Great Lakes iron-ore loadings | 3.45 | 3.15 | S 3 to 2: CLF-mapped port loadings agreed in sign with CLF steel shipments in 4 of 11 quarters; G 4 to 2: the Lake Carriers' Association terms allow personal, non-commercial viewing only and forbid copying |
| N44 State liquor and food-service licences | 3.45 | 3.10 | S 2 to 1: the quarterly count per covered chain is 0 to 3 licences, so a 10% shortfall cannot be resolved; C 3 to 2: several Apify actors and a newsletter already sell Texas licence monitors |
| N05 FAA registry diffs (Textron) | 3.35 | 2.75 | L 4 to 2: certificate issue lags the airworthiness date by a median 36 days, so only 18 to 64% of a quarter's jets are registered by QE+7; S 3 to 2: registry counts ran 51 to 111% of reported deliveries with one wrong-signed quarter |

Two rows rose: N18 went from panel 3.45 (rank 12) to 3.65 (rank 1) because the verifier's EDGAR date check raised L from 4 to 5, even while the same verifier said the row should not stay. N50's L went from 4 to 5 on the same kind of check, offset by A falling to 4 after the primary API failed. Across all 15 verified rows, 11 verdicts were "drop" and 4 were "stay".

### 2.3 Parked

49 rows: 7 merged into a better-scoring overlap and 42 ranked 11 to 52. The alternates, in order:

| Rank | ID | Signal | Score | Note |
|---|---|---|---|---|
| 11 | N55 | BLS PPI detailed-commodity indexes as realised price | 3.35 | First alternate: tied with ranks 8 to 10, S = 3 and U = 2 (25 to 40 names); not verified |
| 12 | N32 | Customer-side adoption panel from job postings | 3.30 | Forward-collection-only; S = 2 |
| 13 | N43 | Securitization-trust 10-D servicer reports | 3.30 | U = 1 (KMX plus two or three names) |
| 14 | S02 | VIIRS thermal activity at single plants | 3.25 | Verifier: drop; five vendors sell plant thermal activity; S-NPP FIRMS retired 2026-11-02 |
| 15 | N51 | Sunbelt pool-permit counts | 3.25 | U = 1 (SWIM, HAYW) |

Among the merged rows, N26 (MAUDE device-event velocity, panel 3.50, U = 2) and S07 (NPDES and CAMPD, panel 3.55) now score higher than the survivors they were folded into, because the survivors were verified downward and they were not. Both are parked with that fact in the reason and are the designated replacements if N22 or N03 fail their Phase 3 gate.

The full parked list with one-line reasons is in `docs/phase2_scores.md`.

## 3. Dependencies the top 10 put on Phase 3

Shared by all ten:

- `SEC_USER_AGENT` set in the environment, and an EDGAR 8-K Item 2.02 release-date harness. Trivial, but it blocks every row at once.
- A point-in-time consensus source. Five hypotheses (N18, N15, N22, S16, S33) compare against or condition on consensus, and N09's controls need it. No $0 source with history exists: Nasdaq returns null for CALM, Alpha Vantage is 25 calls a day shared per IP, FMP's consensus history is unverified. Phase 3 must either start daily consensus snapshots now (forward history only) or Phase 4 must respecify these rows against reported year-over-year, sequential price or guidance-midpoint stand-ins.

Per row (all free unless noted):

| Row | Needs | Status |
|---|---|---|
| N18 | USDA MARS key, NASS QuickStats key, pdfplumber for AMS PDFs | Both keys verified |
| N15 | PJM Data Miner 2 account for PJM West day-ahead prices; EIA v2 key | PJM not created; EIA verified |
| N50 | NCEI bulk nx3hail CSVs (2 to 175 MB each) while the SWDI service is down; Census key; FRED key | Keys verified; SWDI outage to monitor |
| N03 | Keyless ECHO; annual DMR zips (264 to 645 MB each); BLS v2 key | Verified |
| N09 | Keyless npm API at 1 request per second; Google Cloud only for an optional PyPI backfill | Google Cloud not created, optional |
| N22 | Keyless NHTSA flat files; a corrective-action text classifier | Nothing to create |
| G02 | openFDA key; a daily snapshot collector started now | Key verified; collector needs an always-on host |
| S33 | EDGAR full-text search (intermittent); XBRL frames; drop the API Ninjas transcript leg | Nothing to create |
| S04 | aisstream key plus an always-on geofenced collector started now; NOAA AIS archive; Census trade key | Keys verified; collector needs an always-on host; aisstream has no terms page |
| S16 | Keyless USAspending; the verified api.data.gov key for SAM award notices as a cross-check | Verified |

Two of the ten (G02, S04) and the consensus snapshots lose history every day a collector is not running. This research container is ephemeral and cannot host them; Phase 3 needs a decision on where collectors run (your machine, a small VPS, or this platform's scheduled tasks).

## 4. The critic's disputes and what I did with them

1. **Rubric artefact.** The weights give plumbing (A, L, H, G) 55% and tradability (S, U) 30%, and nothing scores event frequency. Rows with S = 2 and U = 1 fill five of the top ten, and rows whose own verifier counted one qualifying event every two to three years (N15) or 15 to 25 events in eleven years against a 60-event gate (N22) rank 2 and 6. Three verifiers named this independently. I did not change the weights: they are the master prompt's, and changing a rubric after seeing the result is the kind of post hoc move Phase 2 exists to prevent. Instead the Phase 3 entry gate for each row is its "first build step" from the critic, which in every case is the cheap kill test the verifier identified (section 8).
2. **Four "drop" verdicts inside the top ten** (N18, N03, N22, G02). The verifiers' findings moved the weighted score by 0 to 0.10 because they landed on U or on unscored properties. Kept in the top ten per the rubric, with the verdict written into the scores document, the register confidence, and the gate below.
3. **The tie at 3.35.** S33, S04, S16 and N55 tied; the workflow left them in id order, so N55 fell to rank 11 by accident of its label. A tie-break on the tradability criteria (S, then U) would put N55 at rank 10 and S16 at 11. I have not applied one, because choosing the rule after seeing which row it promotes is also post hoc. N55 is recorded as the first alternate and the choice is yours (section 8).
4. **Merges before verification.** S07 and N26 were folded into N03 and N22 on panel scores and never verified; after verification they would outscore the survivors. Recorded in both parked reasons; N26 is the designated replacement for N22 and S07's fate follows N03 since they share the flat-outfall defect.
5. **Unverified rows in the top ten.** S33 and S04 entered only because four panel rows were demoted, and never had a verifier pass. Their S = 3 and S33's U = 3 are the only unverified scores in the top ten. Phase 3 starts with a verifier pass on S33, S04 and N55 before any sourcing effort.
6. **Verifiers saw panel ranks, not the final order.** Their texts cite stale ranks. No one has checked the final ten as a set except the critic, whose confidence is 45%.
7. **Record corrections.** Verifiers found wrong file paths (N44, Florida) and stale release dates (N50, OC) in the Phase 1 records; the records still carry them. Phase 3 applies the corrections before sourcing.

## 5. Red team of this phase

- **The scorers were language-model agents working from the same facts sheet**, so their errors are correlated and the three-way agreement understates uncertainty. The lower median protects against one optimistic scorer, not against a shared blind spot. The verifiers' live probes are the real check, and they overturned 11 of 15 panel placements.
- **Every live probe ran once, from one shared cloud IP, on one day.** The NCEI SWDI 500s, the EPA CAMPD outage, and the Alpha Vantage cap may all be transient, and a source that answered today may not tomorrow.
- **Lead-time arithmetic used the most recent fiscal year's 8-K dates**, which can shift by a week or two across years. Rows on a band boundary (N09 at 27 to 28 days for TWLO, G02's AMRX at 25) can move a band.
- **Event-count claims by verifiers (N15, N22) are TESTED HERE on raw files parsed in one session**, not reproduced. They are the single most important findings in this phase and should be the first thing Phase 3 reproduces.
- **The critic's rationale text condenses the verifier text.** Where they disagree, the verifier's own words in `docs/phase2_scoring_details.md` are the source.
- **Nothing in Phase 2 measured whether any signal predicts a surprise.** That is Phase 4 and later. The two live sign checks that were run (S16: wrong-signed two of three; N15: the largest event produced no surprise) are the only evidence of that kind so far, and both point the wrong way.
- **web.archive.org is blocked from this container**, so no point-in-time check of any changing web source was possible.

## 6. Keys and accounts

Changed in `API_KEYS.md`: PJM Data Miner 2 is now a Phase 3 blocker (N15, rank 2), not a Tier 2 maybe; `SEC_USER_AGENT` blocks all ten; Google Cloud stays optional (N09 PyPI backfill only); the always-on collector host for G02, S04 and consensus snapshots is listed as a decision, not a key. Nothing new to sign up for beyond PJM.

## 7. Confidence

Confidence that this top 10 is the best ten of the 59 under the master prompt's rubric: 70%. The arithmetic is reproducible from the stored output and the scorers agreed within one point on most criteria. Main uncertainty: the merges and tie-break were mechanical and the two unverified entrants were never refuted.

Confidence that at least five of the ten survive Phase 4 specification: 40%. The critic's per-row survival estimates sum to about 4.4. Main uncertainty: the shared point-in-time consensus dependency, which five rows need and no free source provides, and the single-digit event counts the verifiers measured for N15 and N22.

## 8. Gate

Phase 2 is complete. Before Phase 3 (data sourcing plan), I need three decisions:

1. **Approve the top 10 as the rubric produced it**, or swap N55 in for S16 on a stated tradability tie-break. My recommendation: approve as produced, carry N55 as first alternate, and treat the tie as the first thing a verifier pass settles.
2. **Phase 3 entry gates.** My recommendation: no row gets a sourcing plan built until its first build step (the cheap kill test from the critic) is run and passes. The four rows the verifiers would drop are tested first, so the order is N22 (60-event count, one day), N03 (correlation gate on four permits, two days), N18 (does any CALM revenue consensus exist; pass-through regression, two days), G02 (stand up the snapshot collector, then the ANDA leg only), then N15 (qualifying-event count since 2010), then verifier passes on S33, S04, N55. Replacements come from N26, S07, N55 and N32 in that order.
3. **Where collectors run.** G02, S04 and the consensus snapshots lose history every day they are not collecting. This container cannot host them. Options: your own machine, a small VPS, or a scheduled task on this platform.

Still open from Phase 1 and the key check: set `SEC_USER_AGENT`; rotate the ICANN CZDS password and set `CZDS_USERNAME` to the registered email; add all keys to the environment's Network secrets; create the PJM Data Miner 2 account.
