# Phase 1 — Idea generation

Date: 2026-11-11. Goal: at least 25 additional non-mainstream signals beyond the Seed Catalogue, each with a mechanism, a target, a lead time and a universe coverage estimate; vendor-sold ideas rejected unless our version is cheaper, faster or more granular; the Signal Register updated; stop at the gate.

Claim labels: TESTED HERE (a request actually made from the research container on 2026-11-11), LITERATURE (a cited paper or practitioner source), REASONED, UNKNOWN. Every per-signal claim keeps the label it was given in `docs/phase1_signal_details.md`.

## 1. Method

The phase ran as a multi-agent pipeline (29 agents, 504 tool calls, about 4 hours wall clock), scripted in `tools/workflows/phase1_idea_generation.js` and grounded in the Phase 0 working-sources list so that every data source cited is one that returned data or asked only for a key when probed.

1. Generate. Four lens agents (physical bottlenecks, regulatory exhaust, digital exhaust, second-order linkages), five sector agents (retail, industrials, energy and materials, shipping and transport, consumer tech) and two seed-expansion agents each proposed ideas with mechanism, target, lead time, coverage, sources, cost, who already knows, vendors selling similar, why ours differs, a falsifiable hypothesis, the strongest reason it is wrong, and a confidence number.
2. Dedupe. One agent grouped near-duplicates, kept the best statement of each, and folded restatements of Seed Catalogue items back into the seed row.
3. Vet. Every canonical idea and every seed item went to an adversarial vetting agent in batches of eight. The vetter searched for vendors selling the same thing and for literature, re-fetched the cited sources, red-teamed the mechanism, and returned KEEP, KEEP_WITH_CHANGES or REJECT with revised scores and a changes list.
4. Coverage. A completeness critic mapped the kept set against the universe's sectors and the four lenses, flagged inconsistencies, and named gaps. A gap round generated nine more ideas against the named gaps, which went through the same vetting.

Raw output: `data/phase1/phase1_workflow_results.json`. Register built by `tools/phase1/build_register.py`. Full per-signal write-ups: `docs/phase1_signal_details.md`. All tables: `docs/phase1_tables.md`.

## 2. Results

| Item | Count |
|---|---|
| Candidate ideas generated (before dedupe) | 80 |
| Folded into seed rows as restatements | 1 |
| Canonical new ideas vetted | 74 |
| New ideas kept (status IDEA) | 42 |
| New ideas rejected (status REJECTED (Phase 1)) | 32 |
| Seed Catalogue items kept | 17 of 36 |
| Register rows after Phase 1 | 110 (59 IDEA, 51 REJECTED) |

Kept new ideas by lens: regulatory 19, digital 10, physical 8, second-order 5. Kept seeds by lens: digital 7, physical 4, regulatory 4, second-order 2. Combined IDEA rows: regulatory 23, digital 17, physical 12, second-order 7.

The 25-idea floor is met on the raw count. It is met with little margin on the honest count: the critic identified six kept ideas that largely duplicate kept seeds or each other (N58 and N02; N03 and the NPDES leg of S07; N10 and S16; N27 and S31; N09 and S27; N22 and N26 with S24), leaving roughly 31 distinct new signal families, and about eight of those have no backtest path today and are forward-collection only (N07 and N08 until Taiwan history is re-derived, N28 beyond Common Crawl, N29, N33, N48, N62, N63, and the Docker Hub and Homebrew legs of N09). The distinct, backtestable new families therefore number in the mid-twenties. Phase 2 scores families, not duplicates, and labels forward-collection-only rows so they are not counted toward the floor twice.

### 2.1 Kept new ideas with the highest vetted confidence

Confidence here is the vetting agent's number after red-teaming; the full register carries all 59 IDEA rows.

| ID | Signal | Lens | Target | Lead time (days) | Coverage | Conf % |
|---|---|---|---|---|---|---|
| N01 | Texas mixed-beverage gross receipts by location as a same-store sales nowcast for bar-heavy restaurant chains | Regulatory | Same-store sales, EPS surprise | 7 | 12 to 20 names | 30 |
| N08 | Taiwan monthly-revenue chain map: TWSE and TPEx open-data prints of Taiwan suppliers and customers of US mid-caps | Second-order | Revenue, EPS surprise | 12 | 25 to 40 names | 30 |
| N21 | MSHA closure orders and quarterly Form 7000-2 hours and tonnage by controller | Regulatory | Volumes, EPS surprise | 10 | 20 to 25 names | 30 |
| N35 | Earnings-date scheduling behaviour: confirmed date versus the firm's historical filing-date pattern | Digital | EPS surprise | 7 | All names (EDGAR delay feature) | 30 |
| N39 | Earnings-triggered early lock-up release clauses in 424B4 prospectuses | Second-order | Post-earnings abnormal return | 30 | 25 to 50 recent IPOs | 30 |
| N43 | Securitization-trust 10-D monthly servicer reports as a nowcast of captive-finance credit (CarMax, CNH) | Regulatory | Finance-segment EPS | 7 | 2 to 3 names | 30 |
| N62 | FedRAMP Marketplace status transitions and reusing-agency counts from GSA's public data repository | Regulatory | Revenue, guidance | 1 | 30 to 40 names | 30 |
| N18 | USDA broiler-hatchery placements, slaughter and AMS egg and chicken price indexes (CALM, PPC) | Physical | Revenue, margin | 25 | 2 primary, 5 secondary | 25 |
| N27 | Mid-quarter non-earnings 8-K items (2.04, 2.05, 2.06, 3.01, 4.01, 4.02) as a negative-surprise flag | Regulatory | EPS surprise, guidance | 20 | All names | 25 |
| N28 | Quarter-end unit counts and closure or coming-soon flags from store locators | Digital | Unit growth, guidance | 25 | 4 chains verified today, 40 to 50 claimed | 25 |
| N32 | Customer-side adoption panel: third-party job postings that name a vendor's product as a required skill | Digital | Revenue, guidance | 25 | About 20 names | 25 |
| N36 | Komatsu monthly KOMTRAX operating hours and demand by region as a read-through to US machinery suppliers | Second-order | Revenue, rental utilisation | 10 | About 7 names | 25 |
| N49 | State DOT bid-letting results: apparent-low-bid totals by contractor | Regulatory | Awards and backlog guidance | 20 | 2 primary, 3 secondary | 25 |
| N50 | Rooftop-weighted hail-swath index from NOAA SPC storm reports (roofing and building products) | Physical | Revenue, margin | 25 | 2 primary, 2 secondary | 25 |
| N51 | Sunbelt pool-permit counts from city and county open-data portals | Regulatory | Revenue, guidance | 20 | 2 primary, 1 secondary | 25 |
| N55 | BLS PPI detailed-commodity indexes as full-quarter realised price for single-product producers | Regulatory | Revenue, margin, EPS | 10 | 25 to 40 names | 25 |
| N07 | Taiwan dedicated-OEM monthly revenue as a sell-in nowcast for US consumer brands | Second-order | Revenue, guidance | 15 | 3 to 4 names | 25 |
| N29 | Nationwide in-stock unit counts and model-year mix from dealer-group inventory feeds (marine, RV) | Digital | Revenue, margin, guidance | 20 | 7 to 8 names | 25 |

Kept seeds with the highest vetted confidence: S07 regulatory exhaust of industrial water and power use (25%), S16 summed federal contract obligations (25%), S24 complaint-spike precursor to recalls (20%), S33 supplier-first disclosures (20%).

### 2.2 What the kept set looks like as families

- Single-site physical throughput from regulatory exhaust: S02, S07, N02, N03, N04, N05, N15, N16, N17, N18, N21, N58. Sixteen kept ideas cover eight or fewer names each (N04, N05, N16, N17 cover one). None can be validated on its own for a 2 to 10 day trade; Phase 2 pools them into one family with one test harness and a minimum event count before any is traded.
- Government and court filings as a nowcast: S12, S14, S16, S18, S31, N10, N22, N26, N27, N35, N39, N43, N62, G02.
- State and municipal open data: N01, N44, N49, N51, G01, G08.
- Own-collection digital exhaust with no history yet: S19, S25, N28, N29, N32, N33, N48, N65, N09 (partly). These start accruing value only once a daily collector runs.
- Cross-listing and supply-chain second order: S33, S35, N07, N08, N36, N39.
- Price and demand series from statistical agencies: S22, S23, N55, N50.

## 3. Rejected ideas, by reason

The full reason for each of the 32 rejected new ideas and 19 rejected seeds is in `docs/phase1_tables.md`. Grouped:

- Sold at scale or published and decayed (fails the vendor test): S01 satellite parking lots, S21 app-rating velocity, S32 call evasiveness, S34 customer-concentration cascade, N37 off-cycle peers (intra-industry transfer, decayed per LITERATURE), N40 used-equipment auction values, N31 menu prices, N46 theme-park wait times, G03 state oil-and-gas regulator files (Enverus), G05 AD/CVD determinations.
- Terms or licence block: N06 ADS-B census (OpenSky non-commercial), N13 used-truck storefronts (Ryder and Penske terms forbid robots), N47 eBay listings (restricted API licence), S20 employee voice (Glassdoor), S26 distributor catalogues (every target behind a WAF and terms), N64 FCC grants (mirror throttles pagination).
- Mechanism broken or sign-ambiguous: N14 EIA weekly state coal is an allocation of a national estimate, N24 bonus targets are set from consensus, N41 Item 1.02 materiality runs the wrong way, N45 RV yard fill, N59 airline aircraft sit in owner trusts, N61 ads.txt authorisation is not spend, N30 lead-time wording, G07 no loaded-versus-empty split in the BTS data, G09 NHSN admissions only for respiratory diagnoses.
- Already in consensus by T-1: S08 river stages, S09 wastewater (same content as FluView), N19 hydro conditions (in guidance), N25 MDL counts (accruals follow settlement frameworks).
- Timing fails the 2 to 10 day event window: N11 railcar lessors (54-month leases), N20 FERC EQR (0 to 8 day lead), S17 foreign subsidiary accounts (9 to 21 months old), S13 UCC liens (pre-empted by 8-K Item 2.03), S15 FDA inspection outcomes (posting dates create look-ahead), S28 trademark filings (not a quarter nowcast).
- No history, no power, or too thin: S30 website diffs, S36 trade-show footprints, S05 blast catalogue, S03 Sentinel-5P at plant scale, S10 planning approvals (not attributable), S11 interconnection queues, S29 Statuspage incidents (immaterial), N23 import alerts (too few events), N38 REIT tenant tables (mega-cap tenants), N42 buyback blackouts (no effect found), N52 municipal fleet approvals, N54 two-name stockpile imagery, N57 Hawaii arrivals, N60 HS 8486 flows (large-cap dominated), G04 pipeline postings (no rows retrievable), G06 Japan customs (no sign-unambiguous name).

Folded: one candidate (daily Shopify products.json stock-out ratio) was a restatement of seed item 25 and its tested field list was attached to S25 as implementation notes.

## 4. Critic findings and how they carry into Phase 2

The completeness critic's full text is in `docs/phase1_tables.md`. The points that change what happens next:

1. Overlaps and the honest count (section 2 above). Phase 2 scores families.
2. Statistical power. The single-site family gets one harness and a minimum-event rule.
3. Inconsistency with seed verdicts. N33 (App Store rating velocity) uses the mechanism S21 was rejected for. Phase 2 either drops N33 or restricts it to the review-text outage and price-change angle the S21 verdict left open.
4. Blocked sources counted as coverage. N28 and N29 list chains and OEMs that returned 403 and propose browser or residential fetches, which is the workaround that made N31 a legal-4 reject. Honest N28 coverage today is four chains. No fetch through a residential proxy against a site's terms, in any phase.
5. Common Crawl is load-bearing for N28 backfill, N32 panel discovery and all of N65, but the CDX index reset or timed out in the N61 probe. Phase 3 verifies CDX and WARC range access before any of these is sourced; otherwise N65 has no source.
6. Crowding understated. N55 (PPI), N36 (Komatsu), N18 (broiler placements), N17 (potato stocks), N15 (NRC status), N12 (EIA-860M) are standard sell-side or trader inputs. Phase 2 lowers their crowdedness by one and requires a measured gap versus consensus, as the brief demands.
7. Lead-time plausibility. N09, N48 and N62 claim one day; N17 depends on one Cold Storage release landing before an early-month print; N27 and N39 lead times describe filing-day news whose earnings-window residual is REASONED, not shown.
8. Legal amber flags inside the kept list: N58 and N02 (TCEQ robots.txt disallows everything, so history comes by a Public Information Act request, not crawling), N63 (ICANN CZDS terms unread), N29 (dealer-site terms unread), S04 (aisstream.io terms not found), S23 (Google Trends via pytrends), N35, N07 and N39 (Nasdaq calendar robots flag; use EDGAR-derived expected dates as primary). Six kept rows carry legal risk 3; none carries 4 or 5.
9. Source concentration: Nasdaq calendar in N07, N35, N39; TCEQ in N02, N58; Taiwan open data in N07, N08; Socrata hosts in N01, N44, N51, N56, G01, G08; USAspending in N10, N49, N62; EDGAR in several. A declared User-Agent is mandatory on every SEC request.
10. Sentiment exposure is low, as the brief requires: no kept idea is a text-sentiment signal.

## 5. Sector gaps still open after the gap round

The gap round closed homebuilders (G01, county permits under builder LLC names), generic and injectable pharma (G02, FDA drug-shortage transitions) and spirits and beer (G08, control-state item-level sales). Still uncovered, and to be carried as known gaps rather than filled with weak ideas: airlines, air cargo, rail, ocean tankers and bulkers, intermodal; upstream E&P (the regulator-file idea failed the vendor test and FracFocus is blocked from the container); auto and heavy-vehicle suppliers beyond recalls; consumer tech hardware beyond S22 and S25; physical or regulatory ideas for specialty and apparel retail; hospitals (NHSN measures the wrong thing); real estate and regulated utilities ex-nuclear; aerospace and defence suppliers.

## 6. Red team of this phase

- The generators and vetters are language-model agents working from web search and single HTTP requests. "TESTED HERE" in the details means one request on 2026-11-11, not a history pull, and several vet notes say the vendor search could not run in the time available, so a share of the crowdedness scores is REASONED rather than checked.
- Universe coverage figures are REASONED estimates against a roughly 1,300-name universe that has not yet been built. Phase 2 builds the universe list from the screens approved in Phase 0 and recomputes coverage per signal.
- KEEP_WITH_CHANGES was the vetters' way of keeping an idea alive while narrowing it. The keep rate for new ideas (57%) is higher than for seeds (47%), which may reflect generators writing to pass the vetting rubric. Phase 2's weighted scoring is the corrective.
- Confidence numbers are the vetting agents' self-reports. They cluster between 15% and 30%, which is the right order of magnitude for untested hypotheses, but they are uncalibrated.
- Every source probe ran from this container's shared cloud IP. A home IP may open some sources that returned 403 here, and may be blocked by others, so the probe statuses behind the coverage counts are container-specific.

Confidence in this phase: 70% that the kept set contains at least ten signals that survive Phase 2 scoring and Phase 3 sourcing. Main driver of uncertainty: crowdedness rests on web searches rather than vendor catalogues, and coverage counts are unverified.

## 7. Keys and accounts added to the tracker by Phase 1

`API_KEYS.md` is updated. Nothing in the kept list needs a paid key. New free items: USDA AMS market-news credentials (N18), a Socrata app token (six signals), a Google Cloud project for BigQuery public datasets (N09 and N65 history), an aisstream.io key (S04, terms to be read first), a LaborCurrent evaluation key (S12), a PACER account for the Case Locator (S14 backtest), a dedicated mailbox for retailer promotional email (N48), and a declared SEC User-Agent string. Items whose only signal was rejected moved to LATER or SKIP: USPTO, FDA Data Dashboard, DOL, Companies House, PeMS, Best Buy, Reddit, Global Fishing Watch.

## 8. Gate

Stopped at the end of Phase 1. Awaiting approval to continue to Phase 2 (triage and scoring with the weighted criteria: data accessibility 20%, lead time 20%, signal-to-noise 20%, crowdedness inverse 15%, universe coverage 10%, history depth 10%, legal and terms cleanliness 5%; top 10 plus a parked list), and any answers on the open items in section 4.
