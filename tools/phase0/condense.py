import json, sys, collections

path = sys.argv[1]
d = json.load(open(path))
r = d["result"]
rows = r["rows"]

def short(s, n=140):
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"

print("=== COUNTS BY GROUP / FINAL STATUS ===")
c = collections.Counter((x["group"], x["final_status"]) for x in rows)
groups = sorted(set(g for g, _ in c))
for g in groups:
    line = ", ".join(f"{st}={n}" for (gg, st), n in sorted(c.items()) if gg == g)
    print(f"{g}: {line}")

print("\n=== VERIFIER VERDICTS ===")
print(collections.Counter(x.get("verifier") for x in rows))

print("\n=== ROWS (group | source | final | verifier | code | needs | tos | evidence) ===")
for x in rows:
    print(
        f"{x['group']} | {short(x['source'],60)} | {x['final_status']} | {x.get('verifier')} | {x.get('http_code','')} | {short(x.get('needs',''),90)} | {short(x.get('tos_flag',''),70)} | {short(x.get('evidence',''),160)}"
    )

print("\n=== ENV NOTES ===")
for n in r.get("envNotes", []):
    print(short(n, 1500))
    print("--")

print("\n=== COVERAGE ===")
for cv in r.get("coverage", []):
    print(f"- {short(cv['seed_item'],80)} => {cv['best_status']} via {', '.join(cv['probed_sources'])[:200]} :: {short(cv.get('note',''),200)}")

print("\n=== GAPS ===")
for g in r.get("gaps", []):
    print(f"- {short(g['seed_item'],80)} -> {g['suggested_source']} {g['url']}")

print("\n=== INCONSISTENCIES ===")
for i in r.get("inconsistencies", []):
    print("-", short(i, 400))
print("\nDROPPED:", r.get("droppedGroups"))
