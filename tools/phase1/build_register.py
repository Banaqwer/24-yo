"""Build the Signal Register and Phase 1 tables from the Phase 1 workflow output.

Usage: python3 -I build_register.py <workflow_output.json> <repo_root>

Writes:
  register/signal_register.csv   one row per signal (seed rows and new ideas, kept and rejected)
  register/signal_register.md    readable register plus phase log
  docs/phase1_signal_details.md  mechanism, context, sources, vendors, red-team notes per signal
  docs/phase1_tables.md          summary tables used by the Phase 1 report
"""
import csv
import json
import sys
from collections import Counter

src, root = sys.argv[1], sys.argv[2]
d = json.load(open(src))
res = d["result"] if "result" in d else d
seeds, ideas = res["seeds"], res["ideas"]
folded, critic = res.get("folded", []), res.get("critic") or {}

LENS = {"physical": "Physical", "regulatory": "Regulatory", "digital": "Digital", "second_order": "Second-order"}
COLS = ["Signal", "Category", "Hypothesis", "Data sources", "Cost", "Lead time", "Universe coverage",
        "Crowdedness (1-5)", "Expected signal/noise (1-5)", "Legal risk (1-5)", "Status", "Confidence %", "Next action"]


def clean(s, n=None):
    s = str(s if s is not None else "").replace("\n", " ").replace("|", "/").strip()
    return s if n is None or len(s) <= n else s[: n - 1] + "…"


def pick(x, key, revised_key):
    v = x.get("vet") or {}
    r = v.get(revised_key)
    if r not in (None, "", []):
        return r
    return x.get(key)


def sources(x):
    v = x.get("vet") or {}
    srcs = v.get("revised_data_sources") or x.get("data_sources") or []
    return "; ".join(f"{s.get('name','?')} [{s.get('probe_status','?')}]" for s in srcs)


def row(x, kind):
    v = x.get("vet") or {}
    verdict = x.get("verdict", "UNVETTED")
    if verdict in ("KEEP", "KEEP_WITH_CHANGES"):
        status, nxt = "IDEA", "Phase 2 scoring"
    elif verdict == "REJECT":
        status, nxt = "REJECTED (Phase 1)", "Rejected: " + clean(v.get("reject_reason", ""), 200)
    else:
        status, nxt = "IDEA (unvetted)", "Vet in Phase 2"
    lead = pick(x, "lead_time_days", "revised_lead_time_days")
    lead_s = f"{int(lead)} days before announcement" if isinstance(lead, (int, float)) else clean(lead)
    if x.get("measurement_window"):
        lead_s += "; covers " + clean(x["measurement_window"], 90)
    return {
        "Signal": f"{x['id']} {clean(x.get('name'))}",
        "Category": LENS.get(x.get("lens"), x.get("lens", "")),
        "Hypothesis": clean(pick(x, "falsifiable_hypothesis", "revised_hypothesis")),
        "Data sources": clean(sources(x)),
        "Cost": clean(x.get("cost"), 120),
        "Lead time": lead_s,
        "Universe coverage": clean(pick(x, "universe_coverage", "revised_universe_coverage"), 160),
        "Crowdedness (1-5)": v.get("revised_crowdedness_1_5", x.get("prelim_crowdedness_1_5", "")),
        "Expected signal/noise (1-5)": v.get("revised_signal_noise_1_5", x.get("prelim_signal_noise_1_5", "")),
        "Legal risk (1-5)": v.get("revised_legal_risk_1_5", x.get("prelim_legal_risk_1_5", "")),
        "Status": status,
        "Confidence %": v.get("revised_confidence_pct", x.get("confidence_pct", "")),
        "Next action": nxt,
    }


rows = [row(x, "seed") for x in seeds] + [row(x, "new") for x in ideas]

with open(f"{root}/register/signal_register.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    w.writerows(rows)

# Readable register
md = ["# Signal Register", "",
      "Living register for the Alt-Data Edge Research Pipeline. One row per signal, updated at the end of every phase. The CSV next to this file is the source of truth; this view truncates long cells.", "",
      "Status vocabulary: IDEA, PARKED, SOURCING, SPECIFIED, AWAITING DATA, TESTING, VALIDATED, PROMISING, INCONCLUSIVE, REJECTED (phase). Category: Physical, Regulatory, Digital, Second-order. Scores: Crowdedness 1 = heavily sold or published, 5 = nobody covers it. Signal/noise 1 = weak proxy, 5 = direct physical measure. Legal risk 1 = clearly public and licensed, 5 = stop. IDs: S = Seed Catalogue item, N = new idea from Phase 1, G = new idea from the Phase 1 gap round.", "",
      "| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
for r in rows:
    md.append("| " + " | ".join(clean(r[c], 110 if c in ("Hypothesis", "Data sources") else 70) for c in COLS) + " |")
md += ["", "## Phase log", "",
       "- Phase 0 (2026-11-11): register created, empty. Tool capability check run; see docs/phase0_report.md.",
       f"- Phase 1 (2026-11-11): {len(seeds)} seed rows structured and vetted; {len(ideas)} new ideas after dedupe, of which "
       f"{sum(1 for x in ideas if x.get('verdict') in ('KEEP','KEEP_WITH_CHANGES'))} kept and {sum(1 for x in ideas if x.get('verdict')=='REJECT')} rejected. See docs/phase1_report.md."]
open(f"{root}/register/signal_register.md", "w").write("\n".join(md) + "\n")

# Details per signal
det = ["# Phase 1 signal details", "",
       "One section per signal in the register. Fields come from the generating agent, revised by the vetting agent where it changed them. Claim labels (TESTED HERE, LITERATURE, REASONED, UNKNOWN) appear inside the text where the agents applied them.", ""]
for x in seeds + ideas:
    v = x.get("vet") or {}
    det.append(f"## {x['id']} {x.get('name','')}")
    det.append("")
    det.append(f"- Category: {LENS.get(x.get('lens'), x.get('lens',''))}. Sector focus: {clean(x.get('sector_focus'))}. Target: {clean(x.get('target'))} ({x.get('nowcast_or_forward','')}).")
    if x.get("seed_item_extended") and x.get("seed_item_extended") != "new":
        det.append(f"- Seed item: {clean(x['seed_item_extended'])}")
    if x.get("merged_from"):
        det.append(f"- Merged duplicates: {', '.join(x['merged_from'])}")
    det.append(f"- Verdict: {x.get('verdict','UNVETTED')}." + (f" Changes: {clean(v.get('changes_made'))}" if v.get("changes_made") else "") + (f" Reject reason: {clean(v.get('reject_reason'))}" if v.get("reject_reason") else ""))
    det.append(f"- Mechanism: {clean(x.get('mechanism'))}")
    det.append(f"- Industry context: {clean(x.get('industry_context'))}")
    det.append(f"- Measurement window: {clean(x.get('measurement_window'))}. Lead time: {pick(x,'lead_time_days','revised_lead_time_days')} days.")
    det.append(f"- Universe coverage: {clean(pick(x,'universe_coverage','revised_universe_coverage'))}")
    det.append(f"- Hypothesis: {clean(pick(x,'falsifiable_hypothesis','revised_hypothesis'))}")
    det.append(f"- Who already knows: {clean(x.get('who_already_knows'))}")
    det.append(f"- Vendors selling similar (generator): {clean(x.get('vendors_selling_similar'))}. Why ours differs: {clean(x.get('why_ours_differs'))}")
    if v.get("vendors_found"):
        det.append(f"- Vendors found by reviewer: {'; '.join(clean(s) for s in v['vendors_found'])}")
    if v.get("literature_found"):
        det.append(f"- Literature found by reviewer: {'; '.join(clean(s) for s in v['literature_found'])}")
    srcs = v.get("revised_data_sources") or x.get("data_sources") or []
    det.append("- Data sources:")
    for s in srcs:
        det.append(f"  - {clean(s.get('name'))} [{s.get('probe_status','?')}] {clean(s.get('url'))} (update: {clean(s.get('update_frequency'))}; history: {clean(s.get('history_depth'))})")
    if v.get("source_checks"):
        det.append("- Reviewer source checks: " + "; ".join(f"{clean(c.get('url'),80)} -> {clean(c.get('status'))} {clean(c.get('note'),80)}" for c in v["source_checks"]))
    det.append(f"- Cost: {clean(x.get('cost'))}")
    det.append(f"- Scores (crowdedness / signal-noise / legal): {v.get('revised_crowdedness_1_5', x.get('prelim_crowdedness_1_5'))} / {v.get('revised_signal_noise_1_5', x.get('prelim_signal_noise_1_5'))} / {v.get('revised_legal_risk_1_5', x.get('prelim_legal_risk_1_5'))}. Confidence: {v.get('revised_confidence_pct', x.get('confidence_pct'))}%.")
    det.append(f"- Strongest reason it is wrong (generator): {clean(x.get('strongest_reason_wrong'))}")
    det.append(f"- Red team (reviewer): {clean(v.get('red_team'))}")
    det.append("")
open(f"{root}/docs/phase1_signal_details.md", "w").write("\n".join(det) + "\n")

# Summary tables
kept = [x for x in ideas if x.get("verdict") in ("KEEP", "KEEP_WITH_CHANGES")]
rej = [x for x in ideas if x.get("verdict") == "REJECT"]
t = ["# Phase 1 tables", ""]
t += ["## Counts", "", "| Item | Count |", "|---|---|",
      f"| Candidate ideas generated (before dedupe) | {res.get('generatedCount','?')} |",
      f"| Folded into seed rows as restatements | {len(folded)} |",
      f"| Canonical new ideas vetted | {len(ideas)} |",
      f"| New ideas kept | {len(kept)} |",
      f"| New ideas rejected | {len(rej)} |",
      f"| Seed rows kept | {sum(1 for x in seeds if x.get('verdict') in ('KEEP','KEEP_WITH_CHANGES'))} of {len(seeds)} |", ""]
lc = Counter(LENS.get(x.get("lens"), x.get("lens")) for x in kept)
t += ["## Kept new ideas by lens", "", "| Lens | Kept |", "|---|---|"] + [f"| {k} | {n} |" for k, n in sorted(lc.items())] + [""]
t += ["## Kept new ideas", "", "| ID | Signal | Lens | Target | Lead time (days) | Coverage | Crowd | S/N | Legal | Conf % |", "|---|---|---|---|---|---|---|---|---|---|"]
for x in kept:
    v = x.get("vet") or {}
    t.append(f"| {x['id']} | {clean(x.get('name'),60)} | {LENS.get(x.get('lens'),'')} | {clean(x.get('target'),30)} | {pick(x,'lead_time_days','revised_lead_time_days')} | {clean(pick(x,'universe_coverage','revised_universe_coverage'),60)} | {v.get('revised_crowdedness_1_5','')} | {v.get('revised_signal_noise_1_5','')} | {v.get('revised_legal_risk_1_5','')} | {v.get('revised_confidence_pct','')} |")
t += ["", "## Rejected new ideas", "", "| ID | Signal | Reason |", "|---|---|---|"]
for x in rej:
    t.append(f"| {x['id']} | {clean(x.get('name'),60)} | {clean((x.get('vet') or {}).get('reject_reason'),200)} |")
t += ["", "## Seed rows", "", "| ID | Signal | Verdict | Crowd | S/N | Legal | Conf % | Note |", "|---|---|---|---|---|---|---|---|"]
for x in seeds:
    v = x.get("vet") or {}
    t.append(f"| {x['id']} | {clean(x.get('name'),60)} | {x.get('verdict')} | {v.get('revised_crowdedness_1_5','')} | {v.get('revised_signal_noise_1_5','')} | {v.get('revised_legal_risk_1_5','')} | {v.get('revised_confidence_pct','')} | {clean(v.get('reject_reason') or v.get('changes_made'),140)} |")
if folded:
    t += ["", "## Candidates folded into seed rows", "", "| Candidate | Seed item | Reason |", "|---|---|---|"]
    for f_ in folded:
        t.append(f"| {clean(f_.get('name'),60)} | {clean(f_.get('seed_item'),60)} | {clean(f_.get('reason'),140)} |")
if critic:
    t += ["", "## Completeness critic", "", f"Kept non-seed count reported: {critic.get('kept_non_seed_count')}. Lens counts: {json.dumps(critic.get('lens_counts'))}.", ""]
    t += ["Sector gaps: " + ("; ".join(critic.get("sector_gaps", [])) or "none"), ""]
    t += ["Gaps raised:"] + [f"- {clean(g.get('description'))} ({g.get('lens')}, {g.get('sector','')}): {clean(g.get('hint'))}" for g in critic.get("gaps", [])] + [""]
    t += ["Concerns:"] + [f"- {clean(c)}" for c in critic.get("concerns", [])]
# Keys needed by kept signals
keyneeds = Counter()
for x in kept + [s for s in seeds if s.get("verdict") in ("KEEP", "KEEP_WITH_CHANGES")]:
    v = x.get("vet") or {}
    for s in (v.get("revised_data_sources") or x.get("data_sources") or []):
        if s.get("probe_status") == "KEY":
            keyneeds[clean(s.get("name"), 60)] += 1
t += ["", "## Keyed sources cited by kept signals", "", "| Source | Signals citing it |", "|---|---|"] + [f"| {k} | {n} |" for k, n in keyneeds.most_common()]
open(f"{root}/docs/phase1_tables.md", "w").write("\n".join(t) + "\n")
print(json.dumps({"seeds": len(seeds), "ideas": len(ideas), "kept": len(kept), "rejected": len(rej), "folded": len(folded)}))
