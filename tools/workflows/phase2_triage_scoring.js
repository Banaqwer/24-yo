export const meta = {
  name: 'phase2-triage-scoring',
  description: 'Score all 59 IDEA signals on the seven weighted Phase 2 criteria with a judge panel, verify the top 15 adversarially, write the top 10 and parked list',
  phases: [
    { title: 'Score', detail: 'three independent scorers per batch of ~12 signals' },
    { title: 'Verify', detail: 'one adversarial verifier per top-15 signal with live probes' },
    { title: 'Critic', detail: 'final ranking review, top-10 rationale, parked reasons' },
  ],
}

const DIR = args.dir
const NB = args.batches
const CONTEXT = `${DIR}/context.md`
const COMPACT = `${DIR}/signals_compact.json`

const RUBRIC = `Score every criterion as an integer 1 to 5 using these anchors (from the master prompt, made explicit):
A. Data accessibility (weight 20%). 5 = free, structured (API, CSV, JSON), fetchable by code, and verified reachable (probe status DATA, or KEY with the key verified in the facts sheet). 4 = free and fetchable by code but needs parsing of PDF or HTML tables, or a free key not yet obtained. 3 = free but needs a headless browser, a manual download, a records request, or is partly blocked from the container. 2 = needs a paid tier within $100 per month, or access is unverified. 1 = paid beyond budget, blocked, or no source exists.
L. Lead time over public disclosure (20%). 5 = the full-quarter reading is final 28 or more days before the earnings release. 4 = 14 to 27 days. 3 = 7 to 13 days. 2 = 2 to 6 days. 1 = 0 to 1 day, or the "lead" is over a filing that is itself priced on the filing day.
S. Expected signal-to-noise (20%). 5 = a direct physical measure of the target quantity for the specific company, near identity. 4 = a direct measure of a major driver, one step removed. 3 = a proxy with a clear mechanism and moderate confounders. 2 = an indirect proxy with sign ambiguity or heavy confounders. 1 = weak or sentiment-like.
C. Crowdedness, inverse (15%). 5 = no vendor sells it and no paper covers it. 4 = a niche vendor or one paper, not in sell-side models. 3 = the series is known or sold but our version is cheaper, faster or more granular in a way that matters. 2 = commonly used by sell-side or traders, or sold by several vendors. 1 = heavily sold or published; assume priced in.
U. Universe coverage (10%). 5 = half or more of the ~1,300-name universe. 4 = 20 to 49% (260 to 650 names). 3 = 5 to 19% (65 to 250 names). 2 = 1 to 4% (13 to 60 names). 1 = under 1% (12 names or fewer).
H. History depth (10%). 5 = five or more years of point-in-time history obtainable free. 4 = three to five years, or five-plus with a minor look-ahead caveat. 3 = one to three years, or history that must be reconstructed from archived vintages. 2 = under one year, or forward collection with a partial backfill. 1 = none; forward collection only.
G. Legal and terms cleanliness (5%). 5 = clearly public (government or official API) with no scraping conflict. 4 = public with a mild flag (undocumented endpoint, attribution clause). 3 = terms unread or ambiguous. 2 = terms restrict some uses, robots.txt conflicts, or a non-commercial clause that may apply. 1 = prohibited.
Weighted score = 0.20A + 0.20L + 0.20S + 0.15C + 0.10U + 0.10H + 0.05G. Do not compute it; return the seven integers.`

const ENV = `Environment: cloud container, HTTPS through a preset proxy (never disable TLS verification or unset HTTPS_PROXY). Some sites block this datacenter IP; report that as a fact, never work around it. Read only: create no accounts, submit no forms. Label any live check TESTED HERE; everything else comes from the record (LITERATURE if a cited source, REASONED, or UNKNOWN).`

const SCORE_SCHEMA = {
  type: 'object',
  properties: {
    scorer: { type: 'string' },
    scores: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          A: { type: 'integer', minimum: 1, maximum: 5 }, L: { type: 'integer', minimum: 1, maximum: 5 }, S: { type: 'integer', minimum: 1, maximum: 5 },
          C: { type: 'integer', minimum: 1, maximum: 5 }, U: { type: 'integer', minimum: 1, maximum: 5 }, H: { type: 'integer', minimum: 1, maximum: 5 }, G: { type: 'integer', minimum: 1, maximum: 5 },
          justification: { type: 'string', description: 'One clause per criterion: "A: ...; L: ...; S: ...; C: ...; U: ...; H: ...; G: ..." each naming the fact in the record (or TESTED HERE) that sets the score' },
          lead_time_arithmetic: { type: 'string', description: 'When the full-quarter reading is final versus a typical release date for the covered names, in days' },
          forward_collection_only: { type: 'boolean' },
          concerns: { type: 'string' },
        },
        required: ['id', 'A', 'L', 'S', 'C', 'U', 'H', 'G', 'justification', 'lead_time_arithmetic', 'forward_collection_only'],
      },
    },
  },
  required: ['scorer', 'scores'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    id: { type: 'string' },
    adjusted: { type: 'object', properties: { A: { type: 'integer', minimum: 1, maximum: 5 }, L: { type: 'integer', minimum: 1, maximum: 5 }, S: { type: 'integer', minimum: 1, maximum: 5 }, C: { type: 'integer', minimum: 1, maximum: 5 }, U: { type: 'integer', minimum: 1, maximum: 5 }, H: { type: 'integer', minimum: 1, maximum: 5 }, G: { type: 'integer', minimum: 1, maximum: 5 } }, required: ['A', 'L', 'S', 'C', 'U', 'H', 'G'] },
    changes: { type: 'string', description: 'Which criteria you changed from the panel median, and the evidence for each change' },
    probes: { type: 'array', items: { type: 'object', properties: { url: { type: 'string' }, status: { type: 'string' }, note: { type: 'string' } }, required: ['url', 'status'] } },
    release_schedule_check: { type: 'string', description: 'The source publication schedule you found (URL) and the resulting lead time in days against typical release dates for the covered names' },
    vendor_and_literature_check: { type: 'string' },
    refutation: { type: 'string', description: 'The strongest case that this signal should NOT be in the top ten' },
    should_stay_in_top_ten: { type: 'boolean' },
    confidence_pct: { type: 'number' },
  },
  required: ['id', 'adjusted', 'changes', 'probes', 'release_schedule_check', 'vendor_and_literature_check', 'refutation', 'should_stay_in_top_ten', 'confidence_pct'],
}

const CRITIC_SCHEMA = {
  type: 'object',
  properties: {
    top10: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, rank: { type: 'integer' }, rationale: { type: 'string' }, dependencies: { type: 'string', description: 'keys, accounts, collectors or requests that Phase 3 needs for this signal' }, first_build_step: { type: 'string' } }, required: ['id', 'rank', 'rationale', 'dependencies', 'first_build_step'] } },
    parked: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, reason: { type: 'string', description: 'one line, naming the criterion that sank it or the signal it merged into' } }, required: ['id', 'reason'] } },
    ranking_disputes: { type: 'array', items: { type: 'string' }, description: 'Cases where you think the arithmetic ranking is wrong and why; you may not change scores, only flag' },
    concerns: { type: 'array', items: { type: 'string' } },
    balance_note: { type: 'string' },
    confidence_pct: { type: 'number' },
    main_uncertainty: { type: 'string' },
  },
  required: ['top10', 'parked', 'ranking_disputes', 'concerns', 'balance_note', 'confidence_pct', 'main_uncertainty'],
}

const PERSONAS = [
  { key: 'data-engineer', text: 'You are the data engineer on the desk. You care most about whether the data can actually be fetched by code, how many years of point-in-time history exist, and whether the terms allow it. Be literal about probe statuses and history_depth fields in the record. If a source listed as UNPROBED decides the accessibility or history score, make one live check (curl or Python requests) and label it TESTED HERE.' },
  { key: 'quant-pm', text: 'You are the portfolio manager who will trade this. You care most about signal-to-noise (does the measured thing move the number the stock moves on?), lead time (is the reading final before the print, with the release schedule arithmetic written out?), and crowdedness (use the vendors and literature in the record; a series quoted in every sell-side preview is crowded regardless of how clever the mapping is).' },
  { key: 'skeptic', text: 'You are the skeptic. Default to the lower score whenever the record does not contain evidence for the higher one. Check every lead-time claim against the source\'s actual publication cadence and the covered names\' typical release timing. Treat forward-collection-only ideas as history 1 or 2. Treat coverage claims that include bot-blocked or terms-prohibited sites as if those sites were absent.' },
]

const scorerPrompt = (p, bi) => `${p.text}

Task: score every signal in the batch file ${DIR}/batch_${bi}.json on the seven Phase 2 criteria. First read ${CONTEXT} (facts sheet: verified keys, container facts, the adjustments the Phase 1 critic required, overlaps). Then read the batch file. Score each signal on its own record; do not skip any id in the batch.

${RUBRIC}

${ENV}

Return one entry per signal with the seven integers, the justification clause per criterion, the lead-time arithmetic, the forward_collection_only flag, and concerns. Set scorer to "${p.key}".`

const verifyPrompt = (row) => `You are an adversarial verifier. The scoring panel put signal ${row.id} ("${row.name}") at rank ${row.rank} of 59 with weighted score ${row.W.toFixed(2)} (panel medians A=${row.m.A} L=${row.m.L} S=${row.m.S} C=${row.m.C} U=${row.m.U} H=${row.m.H} G=${row.m.G}). Your job is to find what the panel got wrong, with evidence.

Read the facts sheet ${CONTEXT} and this signal's full record in ${COMPACT} (find the object whose id is "${row.id}"). Panel justifications (three scorers): ${JSON.stringify(row.justifications)}.

Do all of this:
1. Live-probe the primary data sources named in the record (keyless ones; for keyed ones listed as verified in the facts sheet, assume the key works). Confirm the endpoint answers, the format is structured, and how far back the history goes. Record each probe (url, status, note). Label TESTED HERE.
2. Find the source's official publication schedule (the agency release calendar or the page that states the lag) and write the lead-time arithmetic: when the full-quarter reading is final versus the typical earnings-release timing of the covered names.
3. Run one vendor and literature search for the mechanism; name what you find.
4. Write the strongest case that this signal should not be in the top ten.
5. Return adjusted scores: keep the panel median unless you have evidence to change a criterion, and say exactly what changed and why.

${RUBRIC}

${ENV}`

phase('Score')
const batchIdx = Array.from({ length: NB }, (_, i) => i + 1)
const scorerRuns = await parallel(batchIdx.flatMap(bi => PERSONAS.map(p => () =>
  agent(scorerPrompt(p, bi), { label: `score:b${bi}:${p.key}`, phase: 'Score', schema: SCORE_SCHEMA }))))
const runs = scorerRuns.filter(Boolean)
log(`Scoring runs returned: ${runs.length}/${NB * PERSONAS.length}`)

// ---- aggregate: lower median per criterion across scorers
const CRIT = ['A', 'L', 'S', 'C', 'U', 'H', 'G']
const WEIGHT = { A: 0.20, L: 0.20, S: 0.20, C: 0.15, U: 0.10, H: 0.10, G: 0.05 }
const byId = {}
for (const run of runs) for (const s of run.scores) {
  byId[s.id] = byId[s.id] || { id: s.id, votes: [], justifications: [], forward: [], concerns: [] }
  byId[s.id].votes.push({ scorer: run.scorer, ...Object.fromEntries(CRIT.map(c => [c, s[c]])) })
  byId[s.id].justifications.push({ scorer: run.scorer, text: s.justification, lead: s.lead_time_arithmetic })
  byId[s.id].forward.push(!!s.forward_collection_only)
  if (s.concerns) byId[s.id].concerns.push(`${run.scorer}: ${s.concerns}`)
}
const lowerMedian = (arr) => { const a = [...arr].sort((x, y) => x - y); return a[Math.floor((a.length - 1) / 2)] }
const NAMES = args.names || {}
const rows = Object.values(byId).map(r => {
  const m = Object.fromEntries(CRIT.map(c => [c, lowerMedian(r.votes.map(v => v[c]))]))
  const spread = Object.fromEntries(CRIT.map(c => [c, Math.max(...r.votes.map(v => v[c])) - Math.min(...r.votes.map(v => v[c]))]))
  const W = CRIT.reduce((acc, c) => acc + WEIGHT[c] * m[c], 0)
  return { id: r.id, name: NAMES[r.id] || r.id, votes: r.votes, m, spread, W, justifications: r.justifications, forward_collection_only: r.forward.filter(Boolean).length >= 2, concerns: r.concerns }
})
log(`Signals scored: ${rows.length}; missing from all runs: ${(args.ids || []).filter(id => !byId[id]).join(', ') || 'none'}`)

// ---- overlap merging: keep the higher-scoring member of each group
const GROUPS = [['N58', 'N02'], ['N03', 'S07'], ['N10', 'S16'], ['N27', 'S31'], ['N09', 'S27'], ['N22', 'N26', 'S24']]
const rowById = Object.fromEntries(rows.map(r => [r.id, r]))
for (const g of GROUPS) {
  const present = g.map(id => rowById[id]).filter(Boolean).sort((a, b) => b.W - a.W)
  for (const r of present.slice(1)) r.merged_into = present[0].id
}
const ranked = rows.filter(r => !r.merged_into).sort((a, b) => b.W - a.W)
ranked.forEach((r, i) => { r.rank = i + 1 })
log(`Ranked ${ranked.length} after merging ${rows.length - ranked.length} overlaps. Top 5: ${ranked.slice(0, 5).map(r => `${r.id} ${r.W.toFixed(2)}`).join(', ')}`)

phase('Verify')
const TOPN = 15
const verified = await parallel(ranked.slice(0, TOPN).map(r => () =>
  agent(verifyPrompt(r), { label: `verify:${r.id}`, phase: 'Verify', schema: VERIFY_SCHEMA, effort: 'high' })))
const vById = Object.fromEntries(verified.filter(Boolean).map(v => [v.id, v]))
for (const r of rows) {
  const v = vById[r.id]
  if (v) { r.final = v.adjusted; r.verifier = { changes: v.changes, refutation: v.refutation, stay: v.should_stay_in_top_ten, confidence_pct: v.confidence_pct, release_schedule_check: v.release_schedule_check, vendor_and_literature_check: v.vendor_and_literature_check, probes: v.probes } }
  else r.final = r.m
  r.Wfinal = CRIT.reduce((acc, c) => acc + WEIGHT[c] * r.final[c], 0)
}
const finalRanked = rows.filter(r => !r.merged_into).sort((a, b) => b.Wfinal - a.Wfinal)
finalRanked.forEach((r, i) => { r.finalRank = i + 1 })
log(`Verified ${Object.keys(vById).length}/${TOPN}. Final top 10: ${finalRanked.slice(0, 10).map(r => r.id).join(', ')}`)

phase('Critic')
const table = rows.map(r => ({ id: r.id, name: r.name, panel: r.m, final: r.final, W_panel: +r.W.toFixed(2), W_final: +r.Wfinal.toFixed(2), rank: r.finalRank || null, merged_into: r.merged_into || null, forward_collection_only: r.forward_collection_only, spread: r.spread, verifier_refutation: r.verifier ? r.verifier.refutation : null, verifier_changes: r.verifier ? r.verifier.changes : null, verifier_stay: r.verifier ? r.verifier.stay : null }))
const critic = await agent(`You are the completeness critic and the writer of the Phase 2 output. Read the facts sheet ${CONTEXT}. The full records are in ${COMPACT} (read any you need). Here is the final scoring table for all 59 signals (panel medians, verifier-adjusted finals, weighted scores, ranks; merged_into marks overlap rows folded into a better-scoring sibling):
${JSON.stringify(table)}

Produce:
1. top10: the ten highest final ranks, in order, each with a two-sentence rationale grounded in its scores and record, the dependencies Phase 3 will need (keys, accounts, daily collectors, records requests), and the first build step.
2. parked: one line for every other signal (ranks 11 and below, and merged rows), naming the criterion that sank it (with its score) or the signal it merged into. Every id not in the top ten must appear here.
3. ranking_disputes: where you think the arithmetic ranking misleads (for example a verifier said it should not stay but the score kept it in; a single-site family member with coverage 1 outranking a broad signal only on lead time), with the reason. You may not change scores.
4. concerns and a balance_note (lens and sector concentration of the top ten; shared-harness dependencies; forward-collection-only rows in the top ten).
5. confidence_pct that the top ten contains at least five signals that survive Phase 3 sourcing and Phase 4 specification, with the main uncertainty named.`,
  { label: 'critic', phase: 'Critic', schema: CRITIC_SCHEMA })

return { rows, finalRanked: finalRanked.map(r => ({ id: r.id, name: r.name, W_final: r.Wfinal, rank: r.finalRank })), verified: verified.filter(Boolean), critic, scorerRunCount: runs.length }