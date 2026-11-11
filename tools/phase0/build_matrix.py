import json, sys, csv, collections

src, out_csv, out_md = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(src))
rows = d["result"]["rows"]

# Corrections from the coverage critic's inconsistency list, applied only where the
# recorded evidence makes the right status unambiguous.
FIX = {
    "crt.sh certificate search": ("REACHABLE_DATA", "evidence shows 3,320 rows returned; prober mislabelled"),
    "Wikimedia Pageviews API": ("REACHABLE_DATA", "first call 429 (shared egress IP), retry 200 with 31 days; set a contact User-Agent"),
    "Workday CXS jobs endpoint": ("ERROR", "only 401s observed; no working tenant demonstrated"),
    "Company IR webcast pages (Q4-hosted)": ("ERROR", "hosts did not resolve (NXDOMAIN) for the test ticker; not a bot block"),
    "Alpha Vantage EARNINGS (demo key)": ("REACHABLE_NEEDS_KEY", "demo key only serves demo symbols; free key (25 req/day) needed"),
    "MarineTraffic": ("REACHABLE_NEEDS_KEY", "website bot-blocked, but API answers 401 (paid service key)"),
    "NOAA CMSP AIS daily zip": ("REACHABLE_DATA", "2023 daily file present (319 MB); 2024 index link 404 (stale index)"),
    "USPTO bulk data portal": ("REACHABLE_NEEDS_KEY", "page loads; API needs free MyUSPTO key"),
    "USPTO Open Data Portal (site)": ("REACHABLE_NEEDS_KEY", "page loads; API needs free MyUSPTO key"),
    "GitHub REST (anonymous) - repo metadata": ("BLOCKED_BY_PROXY", "container session gate on /repos; public outside this container"),
}

def short(s, n):
    s = (s or "").replace("\n", " ").replace("|", "/").strip()
    return s if len(s) <= n else s[: n - 1] + "…"

out = []
for r in rows:
    st = r["final_status"]
    note = ""
    if r["source"] in FIX:
        st, note = FIX[r["source"]]
    out.append({
        "group": r["group"],
        "source": r["source"],
        "final_status": st,
        "verifier": r.get("verifier", ""),
        "http_code": r.get("http_code", ""),
        "needs": r.get("needs", ""),
        "tos_flag": r.get("tos_flag", ""),
        "history": r.get("history", ""),
        "format": r.get("format", ""),
        "url": r.get("url", ""),
        "evidence": r.get("evidence", ""),
        "correction": note,
    })

with open(out_csv, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
    w.writeheader()
    w.writerows(out)

GROUP_NAMES = {
    "A": "Runtime, libraries, compute, persistence",
    "B": "Market data: prices, earnings dates, options, fundamentals",
    "C1": "SEC and federal regulatory exhaust",
    "C2": "State, local, legal, logistics, aviation",
    "D": "Physical world: satellites, rivers, seismic, grid, ships",
    "E": "Digital exhaust: code, archives, apps, jobs, reviews, retail",
    "G": "Coverage gaps probed in round two",
}
ORDER = ["REACHABLE_DATA", "REACHABLE_NEEDS_KEY", "REACHABLE_BOT_BLOCKED", "BLOCKED_BY_PROXY", "TIMEOUT", "ERROR", "UNCONFIRMED", "NOT_TESTED"]

cnt = collections.Counter(x["final_status"] for x in out)
lines = ["# Phase 0 capability matrix", "",
         "Every row is an HTTP request or command actually run from this cloud container on 2026-11-11 (TESTED HERE). "
         "Rows marked CONFIRMED were re-fetched independently by a second agent. Corrections column records where the "
         "coverage critic found the original label inconsistent with the evidence.", "",
         "## Totals", "", "| Status | Rows |", "|---|---|"]
for s in ORDER:
    if cnt.get(s):
        lines.append(f"| {s} | {cnt[s]} |")
lines.append(f"| **Total** | {len(out)} |")
lines.append("")
lines.append("Status meanings: REACHABLE_DATA = 2xx with real data, no key. REACHABLE_NEEDS_KEY = host up, needs an API key or login (free or paid, see Needs). "
             "REACHABLE_BOT_BLOCKED = site-side WAF, captcha or terms block. BLOCKED_BY_PROXY = this container's egress policy or gateway. "
             "ERROR / TIMEOUT = see evidence.")
lines.append("")

for g in ["A", "B", "C1", "C2", "D", "E", "G"]:
    sub = [x for x in out if x["group"] == g]
    if not sub:
        continue
    lines.append(f"## Group {g}: {GROUP_NAMES[g]}")
    lines.append("")
    lines.append("| Source | Status | Verified | Needs / unlock | ToS flag | Evidence |")
    lines.append("|---|---|---|---|---|---|")
    for x in sorted(sub, key=lambda x: ORDER.index(x["final_status"]) if x["final_status"] in ORDER else 99):
        lines.append(f"| {short(x['source'],70)} | {x['final_status']} | {x['verifier']} | {short(x['needs'],110)} | {short(x['tos_flag'],60)} | {short(x['evidence'],170)} |")
    lines.append("")

lines.append("## Coverage of the Seed Catalogue")
lines.append("")
for cv in d["result"]["coverage"]:
    lines.append(f"- **{cv['seed_item']}**: best status {cv['best_status']}. {short(cv.get('note',''),400)}")
lines.append("")
lines.append("## Gap sources probed in round two")
lines.append("")
for gp in d["result"]["gaps"]:
    lines.append(f"- **{gp['seed_item']}**: {short(gp['suggested_source'],300)} ({gp['url']})")
lines.append("")
lines.append("## Inconsistencies flagged by the critic")
lines.append("")
for i in d["result"]["inconsistencies"]:
    lines.append(f"- {i}")

open(out_md, "w").write("\n".join(lines) + "\n")
print(json.dumps(cnt))
print("rows", len(out))
