#!/usr/bin/env python3
"""Turn the Phase 2 workflow output into register updates and docs.
Usage: python3 -I tools/phase2/build_phase2.py <phase2_workflow_output.json> <repo_root>
Reads result.{rows, finalRanked, verified, critic}; updates register/signal_register.csv (Status, scores, Confidence, Next action),
regenerates register/signal_register.md, writes docs/phase2_scores.md and docs/phase2_scoring_details.md.
"""
import json, sys, csv, re
src, root = sys.argv[1], sys.argv[2]
d = json.load(open(src))
res = d.get("result", d)
rows, critic = res["rows"], res.get("critic") or {}
CRIT = ["A", "L", "S", "C", "U", "H", "G"]
WEIGHT = {"A": .20, "L": .20, "S": .20, "C": .15, "U": .10, "H": .10, "G": .05}
CRIT_NAME = {"A": "Data accessibility", "L": "Lead time", "S": "Signal-to-noise", "C": "Crowdedness (inverse)", "U": "Universe coverage", "H": "History depth", "G": "Legal cleanliness"}
byid = {r["id"]: r for r in rows}
top10 = [t["id"] for t in sorted(critic.get("top10", []), key=lambda t: t["rank"])]
if not top10:
    top10 = [r["id"] for r in sorted([r for r in rows if not r.get("merged_into")], key=lambda r: -r["Wfinal"])[:10]]
parked_reason = {p["id"]: p["reason"] for p in critic.get("parked", [])}
# Documented corrections to the critic's one-liners (see docs/phase2_report.md, section 4).
parked_reason["N55"] = ("First alternate. Tied at W 3.35 with ranks 8-10; the tie was left in Phase 1 id order (S rows before N rows), "
                        "not broken on any criterion. S=3 and U=2 (25-40 names) beat S16 on the two tradability criteria; never verifier-tested. "
                        "Re-open first if any top-10 row fails its Phase 3 gate.")

def clean(s, n=None):
    s = str(s if s is not None else "").replace("\n", " ").replace("|", "/").strip()
    return s if n is None or len(s) <= n else s[: n - 1] + "…"

# ---- register update
COLS = ["Signal", "Category", "Hypothesis", "Data sources", "Cost", "Lead time", "Universe coverage",
        "Crowdedness (1-5)", "Expected signal/noise (1-5)", "Legal risk (1-5)", "Status", "Confidence %", "Next action"]
reg = list(csv.DictReader(open(f"{root}/register/signal_register.csv")))
updated = 0
for rr in reg:
    sid = rr["Signal"].split(" ", 1)[0]
    r = byid.get(sid)
    if not r or rr["Status"] != "IDEA":
        continue
    f = r["final"]; W = r["Wfinal"]
    rr["Crowdedness (1-5)"] = str(f["C"]); rr["Expected signal/noise (1-5)"] = str(f["S"]); rr["Legal risk (1-5)"] = str(6 - f["G"])
    v = r.get("verifier") or {}
    if v.get("confidence_pct") is not None:
        rr["Confidence %"] = str(int(round(v["confidence_pct"])))
    if sid in top10:
        rr["Status"] = "SOURCING"
        rr["Next action"] = f"Phase 3 sourcing plan (Phase 2 score {W:.2f}, rank {top10.index(sid) + 1})"
    else:
        rr["Status"] = "PARKED"
        why = parked_reason.get(sid) or (f"merged into {r['merged_into']}" if r.get("merged_into") else f"rank {r.get('finalRank')}")
        rr["Next action"] = f"PARKED (Phase 2 score {W:.2f}" + (f", rank {r.get('finalRank')}" if r.get("finalRank") else "") + f"): {clean(why)}"
    updated += 1
with open(f"{root}/register/signal_register.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=COLS); w.writeheader(); w.writerows(reg)

# ---- register markdown (keep the existing phase log, append Phase 2)
old_md = open(f"{root}/register/signal_register.md").read()
log_lines = [l for l in old_md.split("## Phase log", 1)[1].strip().splitlines() if l.startswith("- ")] if "## Phase log" in old_md else []
n_top = len(top10); n_parked = sum(1 for rr in reg if rr["Status"] == "PARKED")
log_lines.append(f"- Phase 2 (2026-11-11): all 59 IDEA rows scored on the seven weighted criteria by a three-scorer panel (lower median), seven rows folded into six overlap groups, top 15 re-verified adversarially with live probes. {n_top} rows moved to SOURCING, {n_parked} to PARKED. See docs/phase2_report.md and docs/phase2_scores.md.")
md = ["# Signal Register", "",
      "Living register for the Alt-Data Edge Research Pipeline. One row per signal, updated at the end of every phase. The CSV next to this file is the source of truth; this view truncates long cells.", "",
      "Status vocabulary: IDEA, PARKED, SOURCING, SPECIFIED, AWAITING DATA, TESTING, VALIDATED, PROMISING, INCONCLUSIVE, REJECTED (phase). Category: Physical, Regulatory, Digital, Second-order. Scores: Crowdedness 1 = heavily sold or published, 5 = nobody covers it. Signal/noise 1 = weak proxy, 5 = direct physical measure. Legal risk 1 = clearly public and licensed, 5 = stop. IDs: S = Seed Catalogue item, N = new idea from Phase 1, G = new idea from the Phase 1 gap round.", "",
      "| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
for rr in reg:
    md.append("| " + " | ".join(clean(rr[c], 110 if c in ("Hypothesis", "Data sources") else 70) for c in COLS) + " |")
md += ["", "## Phase log", ""] + log_lines
open(f"{root}/register/signal_register.md", "w").write("\n".join(md) + "\n")

# ---- scores table
ranked = sorted([r for r in rows if not r.get("merged_into")], key=lambda r: -r["Wfinal"])
merged = [r for r in rows if r.get("merged_into")]
out = ["# Phase 2 scores", "",
       "Every IDEA row scored 1 to 5 on the seven criteria. Panel = lower median of three independent scorers (data engineer, quant PM, skeptic). Final = the adversarial verifier's adjusted scores for the top 15, otherwise the panel median. Weighted score = 0.20 A + 0.20 L + 0.20 S + 0.15 C + 0.10 U + 0.10 H + 0.05 G. Spread = largest disagreement among the three scorers on any criterion.", "",
       "A = data accessibility, L = lead time, S = signal-to-noise, C = crowdedness (inverse), U = universe coverage, H = history depth, G = legal cleanliness.", "",
       "Ties in the weighted score are listed in Phase 1 id order (S, then N, then G), which is not a ranking rule. The four-way tie at 3.35 (S33, S04, S16, N55) is discussed in docs/phase2_report.md.", "",
       "## Ranking", "",
       "| Rank | ID | Signal | A | L | S | C | U | H | G | Final | Panel | Spread | Flags |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in ranked:
    f = r["final"]; flags = []
    if r["id"] in top10: flags.append("TOP 10")
    if r.get("forward_collection_only"): flags.append("forward-only")
    if r.get("verifier"): flags.append("verified" + ("" if r["verifier"].get("stay") else ", verifier says drop"))
    out.append(f"| {r['finalRank']} | {r['id']} | {clean(r['name'], 70)} | {f['A']} | {f['L']} | {f['S']} | {f['C']} | {f['U']} | {f['H']} | {f['G']} | {r['Wfinal']:.2f} | {r['W']:.2f} | {max(r['spread'].values())} | {', '.join(flags)} |")
out += ["", "## Merged into a better-scoring overlap", "", "| ID | Signal | Merged into | Panel score |", "|---|---|---|---|"]
for r in sorted(merged, key=lambda r: r["id"]):
    out.append(f"| {r['id']} | {clean(r['name'], 70)} | {r['merged_into']} | {r['W']:.2f} |")
if critic:
    out += ["", "## Top 10 (critic's rationale)", ""]
    for t in sorted(critic.get("top10", []), key=lambda t: t["rank"]):
        r = byid.get(t["id"], {})
        out += [f"### {t['rank']}. {t['id']} {clean(r.get('name',''))} (score {r.get('Wfinal', 0):.2f})", "",
                f"- Rationale: {clean(t.get('rationale'))}", f"- Phase 3 dependencies: {clean(t.get('dependencies'))}", f"- First build step: {clean(t.get('first_build_step'))}"]
        v = r.get("verifier") or {}
        if v: out += [f"- Verifier: {'stay' if v.get('stay') else 'drop'} ({v.get('confidence_pct')}% confidence). Changes: {clean(v.get('changes'))}", f"- Strongest case against: {clean(v.get('refutation'))}"]
        out.append("")
    out += ["## Parked list", "", "| ID | Signal | Score | Reason |", "|---|---|---|---|"]
    for p in sorted(critic.get("parked", []), key=lambda p: -(byid.get(p["id"], {}).get("Wfinal", 0))):
        r = byid.get(p["id"], {})
        out.append(f"| {p['id']} | {clean(r.get('name',''), 60)} | {r.get('Wfinal', 0):.2f} | {clean(p['reason'])} |")
    out += ["", "## Ranking disputes raised by the critic", ""] + [f"- {clean(x)}" for x in critic.get("ranking_disputes", [])]
    out += ["", "## Concerns", ""] + [f"- {clean(x)}" for x in critic.get("concerns", [])]
    out += ["", f"Balance: {clean(critic.get('balance_note'))}", "", f"Critic confidence: {critic.get('confidence_pct')}%. Main uncertainty: {clean(critic.get('main_uncertainty'))}"]
open(f"{root}/docs/phase2_scores.md", "w").write("\n".join(out) + "\n")

# ---- details: every scorer's justification and the verifier's evidence
det = ["# Phase 2 scoring details", "", "Per signal: each scorer's per-criterion justification and lead-time arithmetic, then the verifier's probes, schedule check, vendor search, changes and refutation (top 15 only).", ""]
for r in sorted(rows, key=lambda r: (r.get("finalRank") or 999, r["id"])):
    det += [f"## {r['id']} {clean(r['name'])}", "", f"- Final rank {r.get('finalRank') or 'merged into ' + str(r.get('merged_into'))}; final score {r['Wfinal']:.2f}; panel {r['W']:.2f}; forward-collection-only: {r.get('forward_collection_only')}."]
    for v in r.get("votes", []):
        det.append(f"- {v['scorer']}: " + " ".join(f"{c}={v[c]}" for c in CRIT))
    for j in r.get("justifications", []):
        det += [f"- {j['scorer']} justification: {clean(j.get('text'))}", f"- {j['scorer']} lead-time arithmetic: {clean(j.get('lead'))}"]
    for c in r.get("concerns", []): det.append(f"- Concern: {clean(c)}")
    v = r.get("verifier")
    if v:
        det += [f"- Verifier changes: {clean(v.get('changes'))}", f"- Verifier release-schedule check: {clean(v.get('release_schedule_check'))}",
                f"- Verifier vendor and literature check: {clean(v.get('vendor_and_literature_check'))}", f"- Verifier refutation: {clean(v.get('refutation'))}",
                f"- Verifier verdict: {'stay in top ten' if v.get('stay') else 'should not stay'}; confidence {v.get('confidence_pct')}%."]
        for p in v.get("probes", []): det.append(f"  - Probe: {clean(p.get('url'))} -> {clean(p.get('status'))} {clean(p.get('note'))}")
    det.append("")
open(f"{root}/docs/phase2_scoring_details.md", "w").write("\n".join(det) + "\n")
print(json.dumps({"rows": len(rows), "ranked": len(ranked), "merged": len(merged), "top10": top10, "register_rows_updated": updated, "parked": n_parked}))
