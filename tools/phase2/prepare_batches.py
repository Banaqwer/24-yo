#!/usr/bin/env python3
"""Build Phase 2 scoring inputs from the Phase 1 workflow output.
Usage: python3 -I tools/phase2/prepare_batches.py <phase1_results.json> <out_dir> [batch_size]
Writes signals_compact.json (every IDEA row with Phase 1 vetting changes applied), batch_N.json files, and context.md.
"""
import json, sys, os, textwrap
src, out = sys.argv[1], sys.argv[2]
bs = int(sys.argv[3]) if len(sys.argv) > 3 else 12
os.makedirs(out, exist_ok=True)
d = json.load(open(src))
r = d.get("result", d)
rows = [x for x in r["seeds"] + r["ideas"] if x.get("verdict") in ("KEEP", "KEEP_WITH_CHANGES")]

def pick(x, key):
    v = (x.get("vet") or {}).get("revised_" + key)
    return v if v not in (None, "", []) else x.get(key)

def cut(s, n):
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"

compact = []
for x in rows:
    v = x.get("vet") or {}
    ds = pick(x, "data_sources") or []
    compact.append({
        "id": x["id"], "name": x["name"], "lens": x["lens"], "sector_focus": cut(x.get("sector_focus"), 300),
        "mechanism": cut(x.get("mechanism"), 1500), "target": x.get("target"), "nowcast_or_forward": x.get("nowcast_or_forward"),
        "lead_time_days": pick(x, "lead_time_days"), "measurement_window": cut(x.get("measurement_window"), 700),
        "universe_coverage": cut(pick(x, "universe_coverage"), 500),
        "data_sources": [{k: cut(s.get(k), 260) for k in ("name", "url", "probe_status", "update_frequency", "history_depth")} for s in ds][:12],
        "cost": cut(x.get("cost"), 400), "who_already_knows": cut(x.get("who_already_knows"), 900),
        "vendors_selling_similar": cut(x.get("vendors_selling_similar"), 500), "why_ours_differs": cut(x.get("why_ours_differs"), 700),
        "falsifiable_hypothesis": cut(pick(x, "hypothesis") or x.get("falsifiable_hypothesis"), 900),
        "strongest_reason_wrong": cut(x.get("strongest_reason_wrong"), 600),
        "phase1_scores": {"crowdedness": pick(x, "crowdedness_1_5"), "signal_noise": pick(x, "signal_noise_1_5"), "legal_risk": pick(x, "legal_risk_1_5"), "confidence_pct": pick(x, "confidence_pct")},
        "vet_changes_made": cut(v.get("changes_made"), 1600), "vet_red_team": cut(v.get("red_team"), 900),
        "vet_vendors_found": [cut(s, 200) for s in (v.get("vendors_found") or [])][:6],
        "vet_literature_found": [cut(s, 200) for s in (v.get("literature_found") or [])][:6],
        "vet_source_checks": [{k: cut(s.get(k), 200) for k in ("url", "status", "note")} for s in (v.get("source_checks") or [])][:8],
    })
compact.sort(key=lambda c: (c["id"][0] != "S", c["id"]))
json.dump(compact, open(os.path.join(out, "signals_compact.json"), "w"), indent=1)

# interleave lenses so every batch is mixed
by_lens = {}
for c in compact: by_lens.setdefault(c["lens"], []).append(c)
order = []
while any(by_lens.values()):
    for l in list(by_lens):
        if by_lens[l]: order.append(by_lens[l].pop(0))
batches = [order[i:i + bs] for i in range(0, len(order), bs)]
for i, b in enumerate(batches, 1):
    json.dump(b, open(os.path.join(out, f"batch_{i}.json"), "w"), indent=1)

context = textwrap.dedent("""
# Phase 2 facts sheet (read before scoring)

## Program constraints
US-listed equities, market cap $500M to $30B, listed options, scheduled earnings; excluding financials, biotech, SPACs. Universe is roughly 1,300 names. Account under $10k; long shares and defined-risk options only; 2 to 10 day event-driven holds around earnings. $0 data budget now, up to $100 per month once a signal is graded PROMISING. US jurisdiction. Legal line: public, lawfully obtained data only, no scraping behind logins or against terms of service.

## Keys verified by a real request on 2026-11-11 (treat the source as accessible, not "needs key")
Tiingo, Alpha Vantage (25 calls per day, shared per IP), FRED, EIA API v2, Census API (ACS and international trade), BLS v2, api.data.gov (Regulations.gov answered; the EPA CAMPD gateway was down that day), FMCSA QCMobile, USDA AMS Market News (MARS), Socrata app token (works across portals), LaborCurrent (evaluation tier: 30-day delayed, 10 calls per day, 10 records per call, 90 days of history), aisstream.io (websocket subscription confirmed; no terms page exists), NASA FIRMS, NASA Earthdata token (LAADS cloud download worked), USDA NASS QuickStats, NOAA NCEI, OpenAQ, openFDA, DOL Open Data, Financial Modeling Prep, Copernicus Data Space OAuth client (Sentinel Hub APIs only).

## Keys NOT available
ICANN CZDS (login rejected; .com/.net access not requested yet), PJM Data Miner 2 (not created), CourtListener and PACER (not created), Google Cloud/BigQuery (not created), API Ninjas transcripts (premium-only; the free key cannot reach them), EPA AirNow (service retired 2026-10-01), SEC User-Agent string (not yet set, trivial), Polygon (not created).

## Container facts from Phase 0 and Phase 1
Probes run from a shared cloud IP. web.archive.org is denied by the environment's network policy (no Wayback history from here). efts.sec.gov (EDGAR full-text search) is intermittent (403 in Phase 0, 200 once in Phase 1). Common Crawl CDX queries reset or timed out in Phase 1. FracFocus returns 403. Nasdaq calendar pages carry a robots flag. TCEQ robots.txt disallows everything (history must come by a Public Information Act request, not crawling). data.iowa.gov no longer serves the liquor dataset at its old SODA path.

## Adjustments the Phase 1 completeness critic required (apply them)
- Crowdedness understated for N55 (PPI), N36 (Komatsu), N18 (broiler placements), N17 (potato stocks), N15 (NRC status), N12 (EIA-860M): these are standard sell-side or trader inputs; do not score crowdedness above 3 without a stated reason.
- N33 (App Store rating velocity) reuses the mechanism S21 was rejected for; score it on its own merits but note the inconsistency.
- N28 and N29 counted bot-blocked sites as coverage; honest N28 coverage today is four chains. Score coverage and accessibility on what is reachable under terms, not on what a residential proxy could reach.
- Forward-collection-only (no backtest history today): N07 and N08 (until Taiwan history is re-derived), N28 beyond Common Crawl, N29, N33, N48, N62, N63, and the Docker Hub and Homebrew legs of N09. History depth for these is 1 or 2.
- Lead-time plausibility: N09, N48 and N62 claim 1 day; N17 depends on one Cold Storage release landing before an early-month print; N27 and N39 lead times describe filing-day news whose earnings-window residual is reasoned, not shown.
- Legal amber inside the kept list: N58 and N02 (TCEQ robots), N63 (CZDS terms), N29 (dealer-site terms), S04 (aisstream terms absent), S23 (Google Trends via pytrends), N35, N07 and N39 (Nasdaq calendar; use EDGAR-derived dates as primary).

## Overlaps (score each row on its own; the ranking step merges the pairs, keeping the higher-scoring member)
N58 with N02; N03 with S07 (NPDES leg); N10 with S16; N27 with S31; N09 with S27; N22 and N26 with S24.

## Single-site physical family (one shared test harness, each row covers eight or fewer names)
S02, S07, N02, N03, N04, N05, N15, N16, N17, N18, N21, N58. Score coverage honestly (most are 1); do not inflate because the family is pooled.
""").strip() + "\n"
open(os.path.join(out, "context.md"), "w").write(context)
print(json.dumps({"signals": len(compact), "batches": [len(b) for b in batches], "lens": {l: sum(1 for c in compact if c["lens"] == l) for l in set(c["lens"] for c in compact)}}))
