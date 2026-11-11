export const meta = {
  name: 'phase1-idea-generation',
  description: 'Generate, dedupe and adversarially vet 25+ non-mainstream alt-data signals for earnings-event trading (Phase 1)',
  phases: [
    { title: 'Generate', detail: 'four lens agents, five sector agents, two seed-structuring agents' },
    { title: 'Dedupe', detail: 'merge near-duplicates and fold restatements into seed rows' },
    { title: 'Vet', detail: 'skeptics check vendor crowding, data reality, timing, legality' },
    { title: 'Coverage', detail: 'critic finds gaps; one targeted generation and vet round' },
  ],
}

const SOURCES = args.sources

const PROGRAM = `PROGRAM CONTEXT (everything you produce must fit it)
- Role: alternative-data research for a small quantitative fund. Rigorous, skeptical, allergic to fabricated results.
- Universe: US-listed equities, market cap $500M to $30B, with listed options and scheduled earnings dates; excluding GICS Financials, the Biotechnology sub-industry, pre-revenue pharma and SPACs; average daily dollar volume at least $10M. Roughly 1,300 names across industrials, consumer discretionary and staples, energy, materials, healthcare (ex-biotech), technology, communication services, utilities and real estate.
- Trade: hold 2 to 10 days, event-driven. Enter 1 to 5 trading days before a scheduled earnings release (or guidance / 8-K disclosure), exit within 1 to 5 days after. Long shares, long calls or puts, debit spreads only. Account under $10k. No short selling, no margin. Costs and slippage eat a large share of any edge.
- Target variables: PRIMARY = earnings-announcement abnormal return (close T-1 to close T+1 and T+2, versus the sector ETF). SECONDARY = EPS or revenue surprise versus final consensus, and guidance change.
- So a useful signal must (a) measure something about the quarter being reported (a nowcast) or about next-quarter guidance, (b) have its final reading available at least 1 trading day BEFORE the announcement, and (c) not already be in consensus. The edge is the gap between the signal and consensus, never the signal alone: for every idea say who already knows this and how much is priced in.
- Data: $0 budget now; up to $100 per month later. Only public, lawfully obtained data: no material non-public information, no paying or pressing employees, no scraping behind logins or against terms of service, no leaked data. Prefer physical bottlenecks and regulatory exhaust over sentiment.
- Capability constraint: a Phase 0 probe tested about 320 sources from the research container. The file ${SOURCES} lists the roughly 200 that work (DATA = keyless, KEY = needs a free or paid key as stated). READ IT FIRST and cite sources from it wherever possible. If you propose a source not in it, mark it probe_status UNPROBED and give the exact URL. Known blocks from the container: web.archive.org (Wayback), efts.sec.gov full-text search, fcc.gov, Glassdoor, Indeed, LinkedIn, Amazon, Trustpilot, Grainger, Fastenal, McMaster-Carr, Target, Walmart, ImportYeti, MarineTraffic, Stooq, Texas WARN, MISO.
- Claim labels: TESTED HERE / LITERATURE (cite) / REASONED / UNKNOWN. Never invent a paper, a vendor product or a dataset; if unsure, write REASONED or UNKNOWN.
- Reject ideas that institutional data vendors already sell at scale (satellite parking lots, card-panel spend, web-traffic panels, app-download panels, aggregated job postings, bills of lading) unless you can name a cheaper, faster or more granular version.
`

const SEED = [
  ['physical', 'Satellite parking-lot car counts (use only as a crowded benchmark; assume mostly priced in)'],
  ['physical', 'Night-time light intensity (NASA VIIRS) and thermal imagery of plants, smelters, refineries'],
  ['physical', 'Flaring and emissions from Sentinel-5P (methane, NO2) as output proxies for oil, steel, chemicals'],
  ['physical', 'AIS ship tracking: vessel queues at single-company ports, LNG terminals, and mining export docks'],
  ['physical', 'Public seismometer networks picking up quarry and mine blasting frequency'],
  ['physical', 'Truck counts from state DOT traffic counters near large distribution centers; weekly rail carloads by commodity'],
  ['physical', 'Municipal water and power usage for large industrial users, and permit renewals that reveal it'],
  ['physical', 'River levels (Rhine, Mississippi) and soil moisture for chemicals, grain, and bulk shipping'],
  ['physical', 'Wastewater epidemiology as a demand lead for pharma and consumer-health names'],
  ['regulatory', 'Local planning-committee minutes and permit applications for data centers, plants, warehouses, often filed under shell names'],
  ['regulatory', 'Utility interconnection and power-capacity requests for data centers and factories'],
  ['regulatory', 'WARN Act mass-layoff notices, published by states 60 days ahead'],
  ['regulatory', 'UCC filings showing inventory or receivables pledged as collateral'],
  ['regulatory', 'Court dockets: supplier suits over unpaid invoices, mechanics liens, PACER filings'],
  ['regulatory', 'FDA inspection reports and Form 483s, FCC equipment filings, patent and trademark applications'],
  ['regulatory', 'Lobbying disclosure spikes and small government contract awards on USAspending.gov'],
  ['regulatory', 'Foreign subsidiary accounts (UK Companies House, EU registries) revealing segment data the parent hides'],
  ['regulatory', 'Clustered insider buying (Form 4) and corporate jet flight tracking before M&A'],
  ['digital', 'Job postings: counts by region, hiring freezes, and wording shifts (build versus maintain, restructuring roles)'],
  ['digital', 'Employee review sentiment trends, especially leadership complaints'],
  ['digital', 'App downloads, store rankings, and web-traffic trends for consumer tech'],
  ['digital', 'Customs import records (bills of lading) showing supplier shifts and inventory build'],
  ['digital', 'Google Trends for single-product small caps'],
  ['digital', 'Product review velocity (rate of new reviews) and defect-complaint spikes preceding recalls'],
  ['digital', 'Out-of-stock frequency and discount depth scraped from the retailer own site'],
  ['digital', 'Price-change frequency in B2B and industrial-distributor catalogs'],
  ['digital', 'GitHub activity (stars, forks, issues, fix speed) for developer-tool companies'],
  ['digital', 'Domain registrations and trademark filings months before launches'],
  ['digital', 'Status-page outage frequency and support-forum complaint volume for SaaS'],
  ['digital', 'Wayback Machine diffs: removed products, softened claims, deleted customer logos'],
  ['digital', 'LinkedIn departure clusters concentrated in one department'],
  ['digital', 'Earnings-call language: hedging words, evasiveness in Q&A, tone shifts quarter over quarter'],
  ['second_order', 'Small supplier earnings calls that mention a cut from their largest customer'],
  ['second_order', 'Customer-concentration maps built from 10-K major-customer disclosures'],
  ['second_order', 'Index addition and deletion mechanics; forced sellers such as distressed funds and ETF rebalances'],
  ['second_order', 'Trade-show footprint changes: shrinking booths, executives skipping keynotes, fewer event-staff postings'],
]
const SEED_TEXT = SEED.map((s, i) => `${i + 1}. [${s[0]}] ${s[1]}`).join('\n')

const IDEA_PROPS = {
  name: { type: 'string' },
  lens: { type: 'string', enum: ['physical', 'regulatory', 'digital', 'second_order'] },
  sector_focus: { type: 'string' },
  mechanism: { type: 'string' },
  target: { type: 'string' },
  nowcast_or_forward: { type: 'string', enum: ['nowcast', 'forward', 'both'] },
  lead_time_days: { type: 'number' },
  measurement_window: { type: 'string' },
  universe_coverage: { type: 'string' },
  data_sources: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, url: { type: 'string' }, probe_status: { type: 'string', enum: ['DATA', 'KEY', 'UNPROBED'] }, update_frequency: { type: 'string' }, history_depth: { type: 'string' } }, required: ['name', 'url', 'probe_status'] } },
  cost: { type: 'string' },
  who_already_knows: { type: 'string' },
  vendors_selling_similar: { type: 'string' },
  why_ours_differs: { type: 'string' },
  prelim_crowdedness_1_5: { type: 'number' },
  prelim_signal_noise_1_5: { type: 'number' },
  prelim_legal_risk_1_5: { type: 'number' },
  falsifiable_hypothesis: { type: 'string' },
  industry_context: { type: 'string' },
  strongest_reason_wrong: { type: 'string' },
  confidence_pct: { type: 'number' },
  seed_item_extended: { type: 'string' },
}
const IDEA_REQUIRED = ['name', 'lens', 'sector_focus', 'mechanism', 'target', 'nowcast_or_forward', 'lead_time_days', 'measurement_window', 'universe_coverage', 'data_sources', 'cost', 'who_already_knows', 'vendors_selling_similar', 'why_ours_differs', 'prelim_crowdedness_1_5', 'prelim_signal_noise_1_5', 'prelim_legal_risk_1_5', 'falsifiable_hypothesis', 'industry_context', 'strongest_reason_wrong', 'confidence_pct', 'seed_item_extended']
const GEN_SCHEMA = { type: 'object', properties: { ideas: { type: 'array', items: { type: 'object', properties: IDEA_PROPS, required: IDEA_REQUIRED } }, notes: { type: 'string' } }, required: ['ideas'] }

const QUALITY = `QUALITY BAR for every idea:
- mechanism: the causal chain from the measured quantity to the reported quarter's revenue, margin or guidance, in 2 to 4 sentences; name the specific kind of company it applies to.
- target: one of revenue, margin, EPS surprise, guidance, capex, recall, M&A, distress (or a short combination).
- lead_time_days: integer calendar days before the earnings announcement at which the FINAL signal reading is available. Be honest: monthly government data published with a six-week lag may only cover months 1 to 2 of the quarter; say what the reading covers in measurement_window.
- universe_coverage: estimated share of the ~1,300-name universe, e.g. '~8%: about 100 names in building products, HVAC, electrical equipment', plus 3 to 5 example companies of the right size if you are confident they fit; otherwise describe the type.
- data_sources: exact URLs; probe_status DATA or KEY only if the source is in the working-sources file, else UNPROBED. Give update frequency and history depth where known (REASONED if inferred).
- who_already_knows: sell-side coverage, vendor products, how much is likely priced in. The edge is the gap versus consensus.
- vendors_selling_similar: name real vendors only if you are sure they sell this (for example Placer.ai, Orbital Insight, RS Metrics, Yipit, M Science, Consumer Edge, Earnest, Second Measure, Thinknum, LinkUp, Revelio, Lightcast, Panjiva, ImportGenius, Kpler, Vortexa, Spire, Kayrros, SafeGraph, Advan, Apptopia, Sensor Tower, data.ai, Similarweb, Quiver Quant). If a vendor sells it at scale, why_ours_differs must name a cheaper, faster or more granular angle, or drop the idea.
- preliminary scores 1 to 5: crowdedness (1 = widely sold or published, 5 = nobody covers it), signal_noise (1 = weak proxy, 5 = direct physical measure of the target), legal_risk (1 = clearly public and licensed, 5 = stop).
- falsifiable_hypothesis in the form: 'A [direction] change of [size] in [signal] over [window], measured [N] days before [event], predicts [target], controlling for [consensus revisions, sector, size, momentum].'
- industry_context: two sentences a generalist needs to understand why the mechanism works.
- strongest_reason_wrong: the best argument that the signal is spurious, a proxy for a known factor, or already priced.
- confidence_pct: 0 to 100 that the signal has real, exploitable edge after costs.
Prefer physical bottlenecks and regulatory exhaust; at most two sentiment-type ideas. Favour measurements specific to a sub-industry or a single company's facilities, since those map to tickers. Every data claim labelled TESTED HERE / LITERATURE / REASONED / UNKNOWN inside the relevant field. Never invent a paper, vendor or dataset.
`

const GEN_PREAMBLE = PROGRAM + `
YOUR TASK: generate NEW non-mainstream signal ideas for this program following the brief below. First Read ${SOURCES}. The Seed Catalogue below is already in the register: do not restate its items. You MAY deepen a seed item into a specific, differently measured, testable signal (then set seed_item_extended to the seed text), but at least two-thirds of your ideas must be new (seed_item_extended = 'new').
` + QUALITY + `
SEED CATALOGUE (already registered):
` + SEED_TEXT + `
`

const LENSES = [
  { key: 'physical', n: 10, brief: `LENS: PHYSICAL BOTTLENECKS. For companies in the universe ask: which scarce input, permit, vehicle, utility or logistics step gates output or sales, and where is that step measured publicly at least monthly (government statistics, ISO and exchange data, port and rail reports, gauges, satellites, public sensors, regulatory meters)? Think about: electricity and gas consumption of named industrial facilities; ISO nodal load near plants; pipeline nominations and informational postings; refinery turnaround notices and EIA operator-level capacity; FERC gas pipeline postings; port-specific TEU and vessel calls; Class I railroad weekly carloads by commodity mapped to a shipper's mix; BTS T-100 and DOT on-time data for airlines; USDA slaughter and cold storage; Army Corps lock transits; NOAA fishery landings; USGS mineral commodity data; MSHA mine-level production reports; state oil and gas commission well-level production, permits and rigs; EIA 923/860 plant-level generation and fuel; EPA CEMS hourly emissions from named power plants and industrial boilers; drought and water allocation notices; Hurricane and freeze disruptions by facility. Produce 10 ideas spread across industrials, energy, materials, shipping and consumer.` },
  { key: 'regulatory', n: 10, brief: `LENS: REGULATORY AND LEGAL EXHAUST. What must a company, or its customers and suppliers, file somewhere obscure before it tells investors? The advantage is the filing timestamp: public days or weeks before the quarter's results. Think about: 8-K items beyond 2.02 (1.01 material agreements, 1.02 terminations, 2.04 triggering events, 2.05 exit costs, 2.06 impairments, 3.01 delisting notices, 4.01 auditor changes, 4.02 non-reliance, 5.02 departures, 7.01 Reg FD); NT 10-Q and NT 10-K late-filing notices; S-8, S-3 and ATM programs; 13D/G amendments; Form 144 sale notices; DEF 14A pay metrics; XBRL footnote text (concentration of risk, going concern, customer names); MSHA quarterly mine filings; state oil and gas regulators; FDA 510(k), PMA, warning letters, import alerts, MAUDE; USDA FSIS recalls; CPSC; NHTSA early-warning reporting; FAA airworthiness directives; FCC grants via fccid.io; FERC tariff and rate cases; state PUC dockets; EPA enforcement and consent decrees; OSHA citations; DOL WARN; state attorney-general settlements; CourtListener dockets (supplier payment suits, product liability); county property records (plant purchases, liens); building permits on open-data portals; interconnection queue updates; FPDS and USAspending awards and terminations; SAM exclusions; CMS data for healthcare providers; ITC Section 337 complaints; Commerce AD/CVD determinations; BIS entity list; USTR exclusions. Produce 10 ideas.` },
  { key: 'digital', n: 10, brief: `LENS: DIGITAL EXHAUST. What do the company, its customers or its employees leak through websites, apps, job boards, repos, status pages, domains, package registries and public forums? Only terms-clean, login-free sources count: Greenhouse, Lever, Ashby, SmartRecruiters and Workday job boards; Shopify storefront products.json; Apple lookup, charts and review feeds; Statuspage APIs; package registries (npm, PyPI, Docker Hub, Homebrew); GitHub search and GH Archive; CT logs, crt.sh and RDAP; Wikipedia pageviews; Common Crawl; Hacker News; public Discourse forums; company press and IR RSS; EDGAR. Do not use Glassdoor, Indeed, LinkedIn, Amazon, Trustpilot or big-box retailer scraping (blocked and prohibited). Note that the Wayback Machine is NOT reachable from the research container, so history must be built forward by daily snapshots or from Common Crawl. Favour measurements specific to one company that update daily so a reading 1 to 3 days before earnings is informative about the quarter: store-locator counts and closures, catalogue breadth, price and discount depth, variant stock-outs, shipping cut-off and lead-time wording, pricing-page changes, SKU retirements, incident counts, API changelog and release cadence, careers-page role counts by function, franchise disclosure documents, dealer-locator counts, app version cadence and rating-count velocity, SDK adoption via registry downloads, CT evidence of new product hostnames. Produce 10 ideas.` },
  { key: 'second_order', n: 10, brief: `LENS: SECOND-ORDER CHAINS. Who upstream or downstream reports earlier, reacts slower, or is forced to trade? Think about: suppliers and customers that report 1 to 6 weeks earlier (map via 10-K major-customer disclosures and XBRL ConcentrationRiskPercentage1); foreign-listed suppliers and customers reporting MONTHLY revenue (Taiwan and Japan monthly sales); large-customer capex guidance flowing to component makers; freight carriers' weekly volumes implying retailer inventories; landlord and REIT tenant disclosures implying retailer store counts; lessor disclosures (aircraft, railcar, container lessors) implying airline and shipper demand; auction and used-equipment price indices implying new-equipment demand; index reconstitution and ETF mechanics (Russell preliminary lists, S&P 400/600 adds, SPDR daily holdings diffs); forced sellers (13F exits, distressed funds, share pledges and margin calls in 13D amendments); lockup expiries from S-1 and 424B; buyback blackout windows; peer-earnings read-through (the first reporter in a sub-industry predicts the rest); guidance-withdrawal clustering; supplier 8-K 1.02 contract terminations naming the customer; government budget and appropriations flow to contractors. Produce 10 ideas.` },
]

const SECTORS = [
  { key: 'retail_consumer', brief: `SECTOR SWEEP: RETAIL, RESTAURANTS, APPAREL, CONSUMER BRANDS, LEISURE. Universe examples: specialty retailers, direct-to-consumer brands on Shopify, restaurant chains and franchisors, footwear and apparel, RV, boat and powersports makers, home furnishings, beverage and snack brands, cosmetics, fitness. Use all four lenses (physical bottlenecks, regulatory and legal exhaust, digital exhaust, second-order chains), at least one idea per lens. Produce 8 ideas.` },
  { key: 'industrials', brief: `SECTOR SWEEP: INDUSTRIALS. Universe examples: machinery, building products, HVAC, electrical equipment, aerospace and defense suppliers, engineering and construction, waste and environmental services, staffing, truck, railcar and trailer makers, industrial distributors, pool and irrigation, agricultural equipment. Use all four lenses, at least one idea per lens. Produce 8 ideas.` },
  { key: 'energy_materials', brief: `SECTOR SWEEP: ENERGY AND MATERIALS. Universe examples: exploration and production, oilfield services, refiners, midstream, coal, uranium, solar and renewable developers, chemicals, steel, aluminum, packaging, fertilizers, lithium, aggregates and cement, forest products. Use all four lenses, at least one idea per lens. Produce 8 ideas.` },
  { key: 'shipping_transport', brief: `SECTOR SWEEP: SHIPPING, TRANSPORT AND LOGISTICS. Universe examples: truckload and LTL carriers, regional railroads, marine shipping (tankers, dry bulk, containers, LNG, product tankers), airlines, air freight, freight forwarders and brokers, ports and terminals, equipment lessors, parcel and last-mile, marine services. Use all four lenses, at least one idea per lens. Produce 8 ideas.` },
  { key: 'consumer_tech', brief: `SECTOR SWEEP: CONSUMER TECH, SOFTWARE AND HARDWARE. Universe examples: SaaS and developer tools, cybersecurity, semiconductors and equipment, consumer electronics and peripherals, gaming, streaming and media, marketplaces, ad-tech, telecom equipment, IT services. Use all four lenses, at least one idea per lens. Produce 8 ideas.` },
]

const SEED_PREAMBLE = PROGRAM + `
YOUR TASK: turn each Seed Catalogue item below into a fully specified register row using the schema (one idea object per seed item; set seed_item_extended to the seed text verbatim; name = a concise signal name; lens = the item's lens). First Read ${SOURCES} and cite the working sources from the Phase 0 probe that would feed it; if the only sources are paid, blocked or terms-prohibited, say so in data_sources (probe_status KEY or UNPROBED) and in cost, and set legal_risk accordingly. Be honest about crowdedness (satellite parking-lot counts are a vendor-sold benchmark, crowdedness 1). Give lead_time_days relative to the earnings announcement for the version of the item most useful to a 2 to 10 day event trade, and describe in measurement_window what the reading covers.
` + QUALITY + `
SEED ITEMS TO STRUCTURE:
`
const SEED_GROUPS = [
  { key: 'phys_reg', items: SEED.filter(s => s[0] === 'physical' || s[0] === 'regulatory') },
  { key: 'dig_second', items: SEED.filter(s => s[0] === 'digital' || s[0] === 'second_order') },
]

phase('Generate')
log('Generating ideas: 4 lens agents, 5 sector agents, 2 seed-structuring agents')

const genTasks = [
  ...LENSES.map(l => ({ label: `lens:${l.key}`, kind: 'gen', prompt: GEN_PREAMBLE + '\nBRIEF: ' + l.brief })),
  ...SECTORS.map(s => ({ label: `sector:${s.key}`, kind: 'gen', prompt: GEN_PREAMBLE + '\nBRIEF: ' + s.brief })),
  ...SEED_GROUPS.map(g => ({ label: `seed:${g.key}`, kind: 'seed', prompt: SEED_PREAMBLE + g.items.map((s, i) => `${i + 1}. [${s[0]}] ${s[1]}`).join('\n') })),
]

const genResults = await parallel(genTasks.map(t => () => agent(t.prompt, { label: t.label, phase: 'Generate', schema: GEN_SCHEMA }).then(r => ({ task: t, result: r }))))

const generated = []
const seeds = []
for (const r of genResults.filter(Boolean)) {
  if (!r.result || !r.result.ideas) { log(`No ideas from ${r.task.label}`); continue }
  for (const idea of r.result.ideas) {
    const rec = { ...idea, origin: r.task.label }
    if (r.task.kind === 'seed') seeds.push(rec); else generated.push(rec)
  }
}
log(`Generated ${generated.length} candidate ideas and ${seeds.length} structured seed rows`)

phase('Dedupe')
const DEDUPE_SCHEMA = {
  type: 'object',
  properties: {
    groups: { type: 'array', items: { type: 'object', properties: { canonical_name: { type: 'string' }, keep: { type: 'string' }, members: { type: 'array', items: { type: 'string' } }, reason: { type: 'string' } }, required: ['canonical_name', 'keep', 'members'] } },
    folded_into_seed: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, seed_item: { type: 'string' }, reason: { type: 'string' } }, required: ['name', 'seed_item'] } },
  },
  required: ['groups', 'folded_into_seed'],
}
const dedupeInput = generated.map(g => ({ name: g.name, lens: g.lens, sector_focus: g.sector_focus, mechanism: g.mechanism, sources: (g.data_sources || []).map(d => d.name).join('; '), seed_item_extended: g.seed_item_extended }))
const dedupe = await agent(`You are given ${generated.length} candidate alt-data signals produced by several independent agents for an earnings-event research program. Group near-duplicates: same measured quantity and same mechanism, even if worded differently or framed for a different sector. Singletons are groups of one. For each group choose 'keep' = the member whose spec is most specific and testable (copy its name exactly). Separately, list under folded_into_seed any candidate that is merely a restatement of a Seed Catalogue item (same measurement as the seed item with no new source, granularity or angle); a candidate that extends a seed item with a genuinely new measurement stays in groups. Every input name must appear exactly once across all groups and folded_into_seed, copied exactly. Do not run tools; this is a reading task.

SEED CATALOGUE:
${SEED_TEXT}

CANDIDATES (JSON):
${JSON.stringify(dedupeInput)}`, { label: 'dedupe', phase: 'Dedupe', schema: DEDUPE_SCHEMA })

const byName = {}
for (const g of generated) byName[g.name] = g
const placed = new Set()
const ideas = []
const folded = []
if (dedupe) {
  for (const f of dedupe.folded_into_seed || []) { if (byName[f.name]) { placed.add(f.name); folded.push({ ...f, record: byName[f.name] }) } }
  for (const grp of dedupe.groups || []) {
    const members = (grp.members || []).filter(m => byName[m] && !placed.has(m))
    if (!members.length) continue
    const keepName = members.includes(grp.keep) ? grp.keep : members[0]
    members.forEach(m => placed.add(m))
    ideas.push({ ...byName[keepName], canonical_name: grp.canonical_name || keepName, merged_from: members.filter(m => m !== keepName), alt_records: members.filter(m => m !== keepName).map(m => ({ name: m, origin: byName[m].origin, mechanism: byName[m].mechanism, data_sources: byName[m].data_sources })) })
  }
}
for (const g of generated) if (!placed.has(g.name)) ideas.push({ ...g, canonical_name: g.name, merged_from: [], alt_records: [] })
ideas.forEach((x, i) => { x.id = 'N' + String(i + 1).padStart(2, '0') })
seeds.forEach((x, i) => { x.id = 'S' + String(i + 1).padStart(2, '0') })
log(`After dedupe: ${ideas.length} canonical new ideas, ${folded.length} folded into seed rows`)

phase('Vet')
const SRC_PROPS = { name: { type: 'string' }, url: { type: 'string' }, probe_status: { type: 'string' }, update_frequency: { type: 'string' }, history_depth: { type: 'string' } }
const VET_SCHEMA = {
  type: 'object',
  properties: {
    verdicts: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' },
      verdict: { type: 'string', enum: ['KEEP', 'KEEP_WITH_CHANGES', 'REJECT'] },
      reject_reason: { type: 'string' },
      vendors_found: { type: 'array', items: { type: 'string' } },
      literature_found: { type: 'array', items: { type: 'string' } },
      source_checks: { type: 'array', items: { type: 'object', properties: { url: { type: 'string' }, status: { type: 'string' }, note: { type: 'string' } }, required: ['url', 'status'] } },
      revised_lead_time_days: { type: 'number' },
      revised_universe_coverage: { type: 'string' },
      revised_crowdedness_1_5: { type: 'number' },
      revised_signal_noise_1_5: { type: 'number' },
      revised_legal_risk_1_5: { type: 'number' },
      revised_confidence_pct: { type: 'number' },
      revised_data_sources: { type: 'array', items: { type: 'object', properties: SRC_PROPS, required: ['name', 'url', 'probe_status'] } },
      revised_hypothesis: { type: 'string' },
      red_team: { type: 'string' },
      changes_made: { type: 'string' },
    }, required: ['id', 'verdict', 'vendors_found', 'literature_found', 'source_checks', 'revised_crowdedness_1_5', 'revised_signal_noise_1_5', 'revised_legal_risk_1_5', 'revised_confidence_pct', 'red_team'] } },
  },
  required: ['verdicts'],
}
const VET_PREAMBLE = PROGRAM + `
YOUR TASK: you are a skeptical reviewer. For each candidate signal below, try to kill it. Per signal:
1. Vendor and literature check: load WebSearch (ToolSearch query 'select:WebSearch') and run 1 to 2 searches in mode 'standard': does an institutional data vendor sell this at scale, and is there a published paper or well-known practitioner report? Record ONLY vendors and papers you actually saw in results, as 'name or title - URL'. Never invent.
2. Data reality: Read ${SOURCES}. Each cited source should be DATA or KEY there. For a source marked UNPROBED, run ONE quick reachability test with curl -sS -m 15 -o /dev/null -w '%{http_code}' URL through the preset proxy (never disable TLS verification, never unset HTTPS_PROXY) and record the code in source_checks. A signal whose only sources are paid, blocked or terms-prohibited gets REJECT unless a clean alternative exists; then KEEP_WITH_CHANGES and put the alternative in revised_data_sources.
3. Timing: is the final reading really available at least 1 trading day before the announcement, and does it inform the quarter being reported or the guidance? If the data covers a period ending weeks before quarter end with a long publication lag, lower signal_noise and say so in changes_made; correct revised_lead_time_days.
4. Crowding: if the information is already in consensus by the time it is public (company press releases, widely followed government releases, vendor products), lower crowdedness (1 = widely sold or published).
5. Legal line: public, lawful, no material non-public information, no terms conflict. Non-commercial-only licences are AMBER: say so in red_team and set legal_risk to at least 3.
6. Revise the four numbers (crowdedness 1 to 5, signal_noise 1 to 5, legal_risk 1 to 5, confidence 0 to 100) and, where you changed the spec, revised_hypothesis.
7. red_team: the single strongest reason the signal is spurious, a proxy for a known factor (analyst revisions, momentum, size, sector), survivorship, look-ahead, or already priced.
Default to REJECT when the mechanism is vague, the lead time is implausible, or the data cannot legally be obtained; KEEP only what you would stake effort on. Verdicts: KEEP, KEEP_WITH_CHANGES (state exactly what in changes_made), REJECT (reject_reason). One verdict per signal, id copied exactly.

CANDIDATES (JSON):
`
function chunk(arr, n) { const out = []; for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n)); return out }
function slim(x) { return { id: x.id, name: x.name, lens: x.lens, sector_focus: x.sector_focus, mechanism: x.mechanism, target: x.target, nowcast_or_forward: x.nowcast_or_forward, lead_time_days: x.lead_time_days, measurement_window: x.measurement_window, universe_coverage: x.universe_coverage, data_sources: x.data_sources, cost: x.cost, who_already_knows: x.who_already_knows, vendors_selling_similar: x.vendors_selling_similar, why_ours_differs: x.why_ours_differs, prelim_crowdedness_1_5: x.prelim_crowdedness_1_5, prelim_signal_noise_1_5: x.prelim_signal_noise_1_5, prelim_legal_risk_1_5: x.prelim_legal_risk_1_5, falsifiable_hypothesis: x.falsifiable_hypothesis, strongest_reason_wrong: x.strongest_reason_wrong, confidence_pct: x.confidence_pct, seed_item_extended: x.seed_item_extended } }

const all = seeds.concat(ideas)
const batches = chunk(all, 8)
log(`Vetting ${all.length} signals in ${batches.length} batches of up to 8`)
const vetResults = await pipeline(batches, (b, _, i) => agent(VET_PREAMBLE + JSON.stringify(b.map(slim)), { label: `vet:${i + 1}/${batches.length}`, phase: 'Vet', schema: VET_SCHEMA }))
const verdictById = {}
for (const v of vetResults.filter(Boolean)) for (const d of (v.verdicts || [])) verdictById[d.id] = d
function applyVerdict(x) {
  const v = verdictById[x.id]
  if (!v) return { ...x, verdict: 'UNVETTED', vet: null }
  return { ...x, verdict: v.verdict, vet: v }
}
let seedsV = seeds.map(applyVerdict)
let ideasV = ideas.map(applyVerdict)
const kept = ideasV.filter(x => x.verdict === 'KEEP' || x.verdict === 'KEEP_WITH_CHANGES')
log(`Vet: ${kept.length} new ideas kept, ${ideasV.filter(x => x.verdict === 'REJECT').length} rejected, ${ideasV.filter(x => x.verdict === 'UNVETTED').length} unvetted`)

phase('Coverage')
const CRITIC_SCHEMA = {
  type: 'object',
  properties: {
    kept_non_seed_count: { type: 'number' },
    lens_counts: { type: 'object', properties: { physical: { type: 'number' }, regulatory: { type: 'number' }, digital: { type: 'number' }, second_order: { type: 'number' } } },
    sector_gaps: { type: 'array', items: { type: 'string' } },
    gaps: { type: 'array', items: { type: 'object', properties: { description: { type: 'string' }, lens: { type: 'string' }, sector: { type: 'string' }, hint: { type: 'string' } }, required: ['description', 'lens', 'hint'] } },
    concerns: { type: 'array', items: { type: 'string' } },
  },
  required: ['kept_non_seed_count', 'gaps', 'concerns'],
}
const critic = await agent(PROGRAM + `
YOUR TASK: completeness critic for Phase 1 idea generation. The program needs at least 25 kept NEW ideas (beyond the Seed Catalogue), spread across the four lenses, covering the favoured sectors (retail and consumer, industrials, energy and materials, shipping and transport, consumer tech), and skewed toward physical bottlenecks and regulatory exhaust rather than sentiment. Below are the kept new ideas, the rejected ones with reasons, and the seed rows' verdicts. Report lens counts and sector gaps, list up to 8 concrete GAPS (a mechanism or data source family that is missing and would plausibly add edge, with a hint of where it is measured), and any CONCERNS about the kept list (too many sentiment ideas, implausible lead times, over-reliance on one source such as Shopify or Yahoo, legal amber flags). Do not run tools.

KEPT NEW IDEAS: ${JSON.stringify(kept.map(x => ({ id: x.id, name: x.name, lens: x.lens, sector_focus: x.sector_focus, target: x.target, lead_time_days: (x.vet && x.vet.revised_lead_time_days) || x.lead_time_days, universe_coverage: (x.vet && x.vet.revised_universe_coverage) || x.universe_coverage, sources: (x.data_sources || []).map(d => d.name).join('; ') })))}

REJECTED: ${JSON.stringify(ideasV.filter(x => x.verdict === 'REJECT').map(x => ({ id: x.id, name: x.name, lens: x.lens, reason: x.vet && x.vet.reject_reason })))}

SEED ROW VERDICTS: ${JSON.stringify(seedsV.map(x => ({ id: x.id, name: x.name, verdict: x.verdict, reason: x.vet && x.vet.reject_reason })))}`, { label: 'critic', phase: 'Coverage', schema: CRITIC_SCHEMA })

let gapIdeasV = []
if (critic && critic.gaps && critic.gaps.length) {
  log(`Critic found ${critic.gaps.length} gaps; running one targeted generation and vet round`)
  const existing = all.map(x => x.name)
  const gapGen = await agent(GEN_PREAMBLE + `
BRIEF: TARGETED ROUND. A completeness critic found these gaps in the idea set. Produce up to ${Math.min(10, critic.gaps.length + 2)} ideas, at least one per gap, each meeting the full quality bar. Do not duplicate any of these existing signal names: ${JSON.stringify(existing)}.
GAPS: ${JSON.stringify(critic.gaps)}
CRITIC CONCERNS TO AVOID REPEATING: ${JSON.stringify(critic.concerns)}`, { label: 'gen:gaps', phase: 'Coverage', schema: GEN_SCHEMA })
  if (gapGen && gapGen.ideas && gapGen.ideas.length) {
    const lower = new Set(existing.map(n => n.toLowerCase()))
    const fresh = gapGen.ideas.filter(g => !lower.has((g.name || '').toLowerCase())).map((g, i) => ({ ...g, origin: 'gen:gaps', id: 'G' + String(i + 1).padStart(2, '0'), canonical_name: g.name, merged_from: [], alt_records: [] }))
    const gapBatches = chunk(fresh, 8)
    const gapVets = await pipeline(gapBatches, (b, _, i) => agent(VET_PREAMBLE + JSON.stringify(b.map(slim)), { label: `vet:gaps:${i + 1}`, phase: 'Coverage', schema: VET_SCHEMA }))
    for (const v of gapVets.filter(Boolean)) for (const d of (v.verdicts || [])) verdictById[d.id] = d
    gapIdeasV = fresh.map(applyVerdict)
    log(`Gap round: ${gapIdeasV.filter(x => x.verdict !== 'REJECT' && x.verdict !== 'UNVETTED').length} of ${gapIdeasV.length} kept`)
  }
} else {
  log('Critic found no gaps')
}

const finalIdeas = ideasV.concat(gapIdeasV)
const keptCount = finalIdeas.filter(x => x.verdict === 'KEEP' || x.verdict === 'KEEP_WITH_CHANGES').length
log(`Final: ${keptCount} kept new ideas, ${finalIdeas.filter(x => x.verdict === 'REJECT').length} rejected, ${seedsV.length} seed rows`)

return { seeds: seedsV, ideas: finalIdeas, folded: folded.map(f => ({ name: f.name, seed_item: f.seed_item, reason: f.reason, origin: f.record.origin })), critic, generatedCount: generated.length }
