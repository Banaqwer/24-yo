#!/usr/bin/env python3
"""Test every API key the program uses with one real, minimal request.

Reads keys ONLY from environment variables (the names in API_KEYS.md). Never prints a key.
Usage:  python3 -I tools/keys/check_keys.py [--only VAR1,VAR2] [--json out.json]
Exit code 0 always; the table is the result. Each row: OK (key accepted), FAIL (endpoint
reachable, key rejected or quota hit), UNTESTABLE (blocked from this network / no library),
SKIP (variable not set, or test needs something we do not have).
"""
import os, sys, json, time, base64, argparse
import requests

TIMEOUT = 40
UA = os.environ.get("SEC_USER_AGENT") or "alt-data-research key-check (contact unset)"
results = []

def mask(text, secrets):
    s = str(text)
    for sec in secrets:
        if sec and len(sec) > 3:
            s = s.replace(sec, "<KEY>")
    return s

def record(name, var, status, detail, secrets=()):
    results.append({"service": name, "variable": var, "status": status, "detail": mask(detail, secrets)[:220]})

def env(*names):
    vals = [os.environ.get(n, "") for n in names]
    return vals if len(vals) > 1 else vals[0]

def http(name, var, method, url, ok, secrets, **kw):
    """Run one request; ok(resp) -> (bool, detail)."""
    try:
        r = requests.request(method, url, timeout=TIMEOUT, headers={"User-Agent": UA, **kw.pop("headers", {})}, **kw)
    except Exception as e:  # network, TLS, proxy
        record(name, var, "UNTESTABLE", f"request error: {type(e).__name__}: {e}", secrets)
        return None
    try:
        good, detail = ok(r)
    except Exception as e:
        good, detail = False, f"HTTP {r.status_code}; parse error {type(e).__name__}; body: {r.text[:150]!r}"
    record(name, var, "OK" if good else "FAIL", f"HTTP {r.status_code}; {detail}", secrets)
    return r

def jkey(r, key, label=None):
    j = r.json()
    if isinstance(j, dict) and key in j:
        return True, f"{label or key} present ({len(j[key]) if hasattr(j[key], '__len__') else j[key]})"
    return False, f"body: {r.text[:160]!r}"

def jlist(r, minlen=1):
    j = r.json()
    if isinstance(j, list) and len(j) >= minlen:
        return True, f"list of {len(j)}"
    return False, f"body: {r.text[:160]!r}"

# ---------------------------------------------------------------- Tier 1
def t_tiingo():
    k = env("TIINGO_API_KEY")
    if not k: return record("Tiingo", "TIINGO_API_KEY", "SKIP", "not set")
    http("Tiingo", "TIINGO_API_KEY", "GET",
         f"https://api.tiingo.com/tiingo/daily/aapl/prices?startDate=2025-01-02&endDate=2025-01-03&token={k}",
         lambda r: jlist(r), [k])

def t_alphavantage():
    k = env("ALPHAVANTAGE_API_KEY")
    if not k: return record("Alpha Vantage", "ALPHAVANTAGE_API_KEY", "SKIP", "not set")
    def ok(r):
        j = r.json()
        if "quarterlyEarnings" in j: return True, f"quarterlyEarnings {len(j['quarterlyEarnings'])} rows"
        return False, f"body: {r.text[:160]!r}"
    http("Alpha Vantage", "ALPHAVANTAGE_API_KEY", "GET",
         f"https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey={k}", ok, [k])

def t_fred():
    k = env("FRED_API_KEY")
    if not k: return record("FRED", "FRED_API_KEY", "SKIP", "not set")
    http("FRED", "FRED_API_KEY", "GET",
         f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&observation_start=2025-01-01&observation_end=2025-01-10&api_key={k}&file_type=json",
         lambda r: jkey(r, "observations"), [k])

def t_eia():
    k = env("EIA_API_KEY")
    if not k: return record("EIA", "EIA_API_KEY", "SKIP", "not set")
    http("EIA API v2", "EIA_API_KEY", "GET",
         f"https://api.eia.gov/v2/petroleum/sum/sndw/data/?frequency=weekly&data[0]=value&length=1&api_key={k}",
         lambda r: jkey(r, "response"), [k])

def t_census():
    k = env("CENSUS_API_KEY")
    if not k: return record("Census", "CENSUS_API_KEY", "SKIP", "not set")
    http("Census (ACS)", "CENSUS_API_KEY", "GET",
         f"https://api.census.gov/data/2023/acs/acs5?get=NAME,B25001_001E&for=state:48&key={k}", lambda r: jlist(r, 2), [k])
    http("Census (intl trade)", "CENSUS_API_KEY", "GET",
         f"https://api.census.gov/data/timeseries/intltrade/imports/hs?get=CTY_CODE,CTY_NAME,GEN_VAL_MO&I_COMMODITY=8703&COMM_LVL=HS4&time=2025-01&key={k}",
         lambda r: jlist(r, 2), [k])

def t_bls():
    k = env("BLS_API_KEY")
    if not k: return record("BLS v2", "BLS_API_KEY", "SKIP", "not set")
    def ok(r):
        j = r.json()
        st = j.get("status"); msgs = j.get("message", [])
        if st == "REQUEST_SUCCEEDED" and j.get("Results", {}).get("series"):
            n = len(j["Results"]["series"][0].get("data", []))
            return True, f"{st}; {n} observations; msgs={msgs[:1]}"
        return False, f"{st}; {msgs[:2]}"
    http("BLS v2", "BLS_API_KEY", "POST", "https://api.bls.gov/publicAPI/v2/timeseries/data/", ok, [k],
         json={"seriesid": ["WPU10"], "startyear": "2024", "endyear": "2025", "registrationkey": k})

def t_sec():
    ua = env("SEC_USER_AGENT")
    if not ua: return record("SEC EDGAR User-Agent", "SEC_USER_AGENT", "SKIP", "not set (set to 'Name email')")
    http("SEC EDGAR User-Agent", "SEC_USER_AGENT", "GET", "https://data.sec.gov/submissions/CIK0000320193.json",
         lambda r: jkey(r, "filings"), [], headers={"User-Agent": ua})

# ---------------------------------------------------------------- Tier 2
def t_datagov():
    k = env("DATA_GOV_API_KEY")
    if not k: return record("api.data.gov", "DATA_GOV_API_KEY", "SKIP", "not set")
    r = http("api.data.gov (EPA CAMPD)", "DATA_GOV_API_KEY", "GET",
             f"https://api.epa.gov/easey/facilities-mgmt/facilities/attributes?year=2024&stateCode=LA&page=1&perPage=1&api_key={k}",
             lambda r: jlist(r), [k])
    if r is not None and r.status_code == 404 and "Requested route" in r.text:
        results[-1]["status"] = "UNTESTABLE"; results[-1]["detail"] = "CAMPD gateway route missing today (HTTP 404 'Requested route does not exist'); key judged by the Regulations.gov call"
    http("api.data.gov (Regulations.gov)", "DATA_GOV_API_KEY", "GET",
         f"https://api.regulations.gov/v4/documents?page[size]=5&api_key={k}", lambda r: jkey(r, "data"), [k])

def t_fmcsa():
    k = env("FMCSA_WEBKEY")
    if not k: return record("FMCSA QCMobile", "FMCSA_WEBKEY", "SKIP", "not set")
    http("FMCSA QCMobile", "FMCSA_WEBKEY", "GET", f"https://mobile.fmcsa.dot.gov/qc/services/carriers/139506?webKey={k}",
         lambda r: jkey(r, "content"), [k])

def t_mars():
    k = env("USDA_MARS_API_KEY")
    if not k: return record("USDA AMS MARS", "USDA_MARS_API_KEY", "SKIP", "not set")
    http("USDA AMS MARS", "USDA_MARS_API_KEY", "GET", "https://marsapi.ams.usda.gov/services/v1.2/reports",
         lambda r: jlist(r), [k], auth=(k, ""))

def t_socrata():
    k = env("SOCRATA_APP_TOKEN")
    if not k: return record("Socrata app token", "SOCRATA_APP_TOKEN", "SKIP", "not set")
    http("Socrata (data.texas.gov)", "SOCRATA_APP_TOKEN", "GET", "https://data.texas.gov/resource/naix-2893.json?$limit=1",
         lambda r: jlist(r), [k], headers={"X-App-Token": k})
    http("Socrata (data.austintexas.gov)", "SOCRATA_APP_TOKEN", "GET", "https://data.austintexas.gov/resource/3syk-w9eu.json?$limit=1",
         lambda r: jlist(r), [k], headers={"X-App-Token": k})

def t_laborcurrent():
    k = env("LABORCURRENT_API_KEY")
    if not k: return record("LaborCurrent", "LABORCURRENT_API_KEY", "SKIP", "not set")
    def ok(r):
        j = r.json()
        if isinstance(j, dict):
            for key in ("records", "data", "results"):
                if key in j: return True, f"{key}: {len(j[key])} rows; keys={list(j)[:6]}"
            return False, f"keys={list(j)[:8]}; body: {r.text[:120]!r}"
        return jlist(r)
    # evaluation tier is 10 calls per day: exactly one call here
    http("LaborCurrent", "LABORCURRENT_API_KEY", "GET", "https://laborcurrent.com/api/records?limit=1", ok, [k], headers={"X-API-Key": k})

def t_apininjas():
    k = env("API_NINJAS_KEY")
    if not k: return record("API Ninjas", "API_NINJAS_KEY", "SKIP", "not set")
    def ok(r):
        j = r.json()
        if isinstance(j, dict) and j.get("transcript"): return True, f"transcript {len(j['transcript'])} chars"
        if isinstance(j, list) and j: return True, f"list of {len(j)}"
        return False, f"body: {r.text[:160]!r}"
    http("API Ninjas (earningscalendar, free)", "API_NINJAS_KEY", "GET",
         "https://api.api-ninjas.com/v1/earningscalendar?ticker=MSFT", lambda r: jlist(r), [k], headers={"X-Api-Key": k})
    r = http("API Ninjas (earningstranscript)", "API_NINJAS_KEY", "GET",
             "https://api.api-ninjas.com/v1/earningstranscript?ticker=MSFT&year=2024&quarter=2", ok, [k], headers={"X-Api-Key": k})
    if r is not None and "premium" in r.text.lower():
        results[-1]["status"] = "PREMIUM"; results[-1]["detail"] = "key valid, but this endpoint is premium-only on API Ninjas"

def t_czds():
    u, p = env("CZDS_USERNAME", "CZDS_PASSWORD")
    if not (u and p): return record("ICANN CZDS", "CZDS_USERNAME/PASSWORD", "SKIP", "not set")
    def ok(r):
        j = r.json(); return ("accessToken" in j), ("accessToken present" if "accessToken" in j else f"body: {r.text[:120]!r}")
    r = http("ICANN CZDS (authenticate)", "CZDS_USERNAME/PASSWORD", "POST", "https://account-api.icann.org/api/authenticate", ok, [u, p],
             json={"username": u, "password": p}, headers={"Content-Type": "application/json", "Accept": "application/json"})
    if r is not None and r.status_code == 200 and "accessToken" in r.text:
        tok = r.json()["accessToken"]
        def ok2(r2):
            j = r2.json(); return True, f"approved zone links: {len(j)} -> {[x.split('/')[-1] for x in j][:6]}"
        http("ICANN CZDS (approved zones)", "CZDS_USERNAME/PASSWORD", "GET", "https://czds-api.icann.org/czds/downloads/links", ok2, [u, p, tok],
             headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"})

def t_aisstream():
    k = env("AISSTREAM_API_KEY")
    if not k: return record("aisstream.io", "AISSTREAM_API_KEY", "SKIP", "not set")
    try:
        import asyncio, ssl, websockets
    except ImportError:
        return record("aisstream.io", "AISSTREAM_API_KEY", "UNTESTABLE", "python 'websockets' not installed (pip install --target <scratch>/piptest websockets)")
    async def run():
        ctx = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)
        sub = {"APIKey": k, "BoundingBoxes": [[[28.5, -95.5], [30.5, -93.0]]], "FilterMessageTypes": ["PositionReport"]}
        try:
            async with websockets.connect("wss://stream.aisstream.io/v0/stream", ssl=ctx, open_timeout=20, proxy=True) as ws:
                await ws.send(json.dumps(sub))
                msg = await asyncio.wait_for(ws.recv(), timeout=30)
                if isinstance(msg, (bytes, bytearray)): msg = msg.decode("utf-8", "replace")
                j = json.loads(msg)
                if "error" in j: return "FAIL", f"server error: {j['error']}"
                return "OK", f"first message type {j.get('MessageType') or list(j)[:3]}"
        except TypeError:
            # older websockets without proxy= support
            async with websockets.connect("wss://stream.aisstream.io/v0/stream", ssl=ctx, open_timeout=20) as ws:
                await ws.send(json.dumps(sub))
                msg = await asyncio.wait_for(ws.recv(), timeout=30)
                if isinstance(msg, (bytes, bytearray)): msg = msg.decode("utf-8", "replace")
                j = json.loads(msg)
                if "error" in j: return "FAIL", f"server error: {j['error']}"
                return "OK", f"first message type {j.get('MessageType') or list(j)[:3]}"
    try:
        st, d = asyncio.run(run())
        record("aisstream.io", "AISSTREAM_API_KEY", st, d, [k])
    except Exception as e:
        record("aisstream.io", "AISSTREAM_API_KEY", "UNTESTABLE", f"websocket error: {type(e).__name__}: {e}", [k])

# ---------------------------------------------------------------- Tier 3
def t_firms():
    k = env("FIRMS_MAP_KEY")
    if not k: return record("NASA FIRMS", "FIRMS_MAP_KEY", "SKIP", "not set")
    def ok(r):
        j = r.json()
        if isinstance(j, dict) and "current_transactions" in j: return True, f"transactions used {j['current_transactions']}/{j.get('transaction_limit')}"
        return False, f"body: {r.text[:160]!r}"
    http("NASA FIRMS (key status)", "FIRMS_MAP_KEY", "GET", f"https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY={k}", ok, [k])
    http("NASA FIRMS (area CSV)", "FIRMS_MAP_KEY", "GET", f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{k}/VIIRS_SNPP_NRT/-95,29,-94,30/1",
         lambda r: (r.text.startswith("latitude"), f"csv header {r.text[:40]!r}, {r.text.count(chr(10))} lines"), [k])

def t_earthdata():
    k = env("EARTHDATA_TOKEN")
    if not k: return record("NASA Earthdata token", "EARTHDATA_TOKEN", "SKIP", "not set")
    try:
        payload = json.loads(base64.urlsafe_b64decode(k.split(".")[1] + "==="))
        exp = time.strftime("%Y-%m-%d", time.gmtime(payload.get("exp", 0)))
    except Exception:
        exp = "unreadable"
    try:
        g = requests.get("https://cmr.earthdata.nasa.gov/search/granules.json?short_name=VNP46A2&page_size=1&sort_key=-start_date",
                         headers={"User-Agent": UA}, timeout=TIMEOUT).json()
        links = [l["href"] for l in g["feed"]["entry"][0]["links"] if l.get("href", "").startswith("https://") and l["href"].endswith(".h5")]
        url = links[0]
    except Exception as e:
        return record("NASA Earthdata token", "EARTHDATA_TOKEN", "UNTESTABLE", f"CMR granule lookup failed: {type(e).__name__}: {e}")
    http("NASA Earthdata token (LAADS download, first 1 KB)", "EARTHDATA_TOKEN", "GET", url,
         lambda r: (r.status_code in (200, 206), f"content-type {r.headers.get('content-type')}; {len(r.content)} bytes; token expires {exp}; host {url.split('/')[2]}"), [k],
         headers={"Authorization": f"Bearer {k}", "Range": "bytes=0-1023"}, allow_redirects=True)
    http("NASA Earthdata (same download, no token: expect 401)", "EARTHDATA_TOKEN", "GET", url,
         lambda r: (r.status_code in (401, 403) or "urs.earthdata.nasa.gov" in r.url, f"final host {r.url.split('/')[2]}"), [],
         headers={"Range": "bytes=0-1023"}, allow_redirects=True)

def t_cdse():
    cid, sec = env("CDSE_CLIENT_ID", "CDSE_CLIENT_SECRET")
    if not (cid and sec): return record("Copernicus Data Space (OAuth client)", "CDSE_CLIENT_ID/SECRET", "SKIP", "not set (needs both the client ID, which starts with 'sh-', and the secret)")
    def ok(r):
        j = r.json(); return ("access_token" in j), ("access_token issued" if "access_token" in j else f"body: {r.text[:140]!r}")
    r = http("Copernicus Data Space (token)", "CDSE_CLIENT_ID/SECRET", "POST", "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token", ok, [cid, sec],
             data={"grant_type": "client_credentials", "client_id": cid, "client_secret": sec})
    if r is not None and r.status_code == 200 and "access_token" in r.text:
        tok = r.json()["access_token"]
        # an 8x8 Process API request: a bogus token gets 401, a valid one gets a PNG (TESTED 2026-11-11)
        ev = "//VERSION=3\nfunction setup(){return{input:['B04'],output:{bands:1}}}\nfunction evaluatePixel(s){return[s.B04]}"
        body = {"input": {"bounds": {"bbox": [-95.4, 29.7, -95.3, 29.8]},
                          "data": [{"type": "sentinel-2-l2a", "dataFilter": {"timeRange": {"from": "2025-06-01T00:00:00Z", "to": "2025-06-30T00:00:00Z"}}}]},
                "output": {"width": 8, "height": 8, "responses": [{"identifier": "default", "format": {"type": "image/png"}}]}, "evalscript": ev}
        http("Copernicus Data Space (Sentinel Hub Process API)", "CDSE_CLIENT_ID/SECRET", "POST", "https://sh.dataspace.copernicus.eu/api/v1/process",
             lambda r2: (r2.status_code == 200 and "image" in r2.headers.get("content-type", ""), f"content-type {r2.headers.get('content-type')}; {len(r2.content)} bytes; note: OData/S3 downloads need a user token (password grant), not this client token"),
             [cid, sec, tok], json=body, headers={"Authorization": f"Bearer {tok}"})

def t_nass():
    k = env("NASS_API_KEY")
    if not k: return record("USDA NASS QuickStats", "NASS_API_KEY", "SKIP", "not set")
    http("USDA NASS QuickStats", "NASS_API_KEY", "GET",
         f"https://quickstats.nass.usda.gov/api/get_counts/?key={k}&commodity_desc=CHICKENS&statisticcat_desc=PLACEMENTS&year=2025",
         lambda r: jkey(r, "count"), [k])

# ---------------------------------------------------------------- Later / backup
def t_ncei():
    k = env("NCEI_TOKEN")
    if not k: return record("NOAA NCEI CDO", "NCEI_TOKEN", "SKIP", "not set")
    http("NOAA NCEI CDO", "NCEI_TOKEN", "GET", "https://www.ncei.noaa.gov/cdo-web/api/v2/datasets?limit=1", lambda r: jkey(r, "results"), [k], headers={"token": k})

def t_airnow():
    k = env("AIRNOW_API_KEY")
    if not k: return record("EPA AirNow", "AIRNOW_API_KEY", "SKIP", "not set")
    r = http("EPA AirNow", "AIRNOW_API_KEY", "GET",
             f"https://www.airnowapi.org/aq/observation/zipCode/current/?format=application/json&zipCode=77002&distance=50&API_KEY={k}", lambda r: jlist(r, 0), [k])
    if r is not None and r.status_code == 410:
        results[-1]["status"] = "RETIRED"; results[-1]["detail"] = "AirNow web service retired 2026-10-01 (HTTP 410); see https://docs.airnowapi.org/webservices/retired"

def t_openaq():
    k = env("OPENAQ_API_KEY")
    if not k: return record("OpenAQ", "OPENAQ_API_KEY", "SKIP", "not set")
    http("OpenAQ v3", "OPENAQ_API_KEY", "GET", "https://api.openaq.org/v3/locations?limit=1", lambda r: jkey(r, "results"), [k], headers={"X-API-Key": k})

def t_openfda():
    k = env("OPENFDA_API_KEY")
    if not k: return record("openFDA", "OPENFDA_API_KEY", "SKIP", "not set")
    http("openFDA", "OPENFDA_API_KEY", "GET", f"https://api.fda.gov/device/event.json?api_key={k}&limit=1", lambda r: jkey(r, "results"), [k])

def t_fda_dashboard():
    k = env("FDA_DASHBOARD_KEY")
    if not k: return record("FDA Data Dashboard", "FDA_DASHBOARD_KEY", "SKIP", "not set")
    user = env("FDA_DASHBOARD_USER")
    if not user:
        return record("FDA Data Dashboard", "FDA_DASHBOARD_KEY", "SKIP", "needs FDA_DASHBOARD_USER (the email you registered with) sent as the Authorization-User header; not set")
    http("FDA Data Dashboard", "FDA_DASHBOARD_KEY", "POST", "https://api-datadashboard.fda.gov/v1/inspections_citations",
         lambda r: jkey(r, "result"), [k, user], json={"start": 1, "rows": 1, "sort": "InspectionEndDate", "sortorder": "DESC", "filters": {}},
         headers={"Authorization-Type": "API KEY", "Authorization-User": user, "Authorization-Key": k, "Content-Type": "application/json"})

def t_dol():
    k = env("DOL_API_KEY")
    if not k: return record("DOL Open Data", "DOL_API_KEY", "SKIP", "not set")
    # accepted only as a query parameter; the X-API-KEY header returns 401 (TESTED 2026-11-11)
    http("DOL Open Data (OSHA inspection)", "DOL_API_KEY", "GET", f"https://apiprod.dol.gov/v4/get/OSHA/inspection/json?limit=1&X-API-KEY={k}",
         lambda r: jkey(r, "data"), [k])

def t_polygon():
    k = env("POLYGON_API_KEY")
    if not k: return record("Polygon.io", "POLYGON_API_KEY", "SKIP", "not set")
    http("Polygon.io", "POLYGON_API_KEY", "GET", f"https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2025-01-02/2025-01-03?apiKey={k}",
         lambda r: jkey(r, "results"), [k])

def t_fmp():
    k = env("FMP_API_KEY")
    if not k: return record("Financial Modeling Prep", "FMP_API_KEY", "SKIP", "not set")
    http("Financial Modeling Prep", "FMP_API_KEY", "GET", f"https://financialmodelingprep.com/stable/profile?symbol=AAPL&apikey={k}", lambda r: jlist(r), [k])

TESTS = [t_tiingo, t_alphavantage, t_fred, t_eia, t_census, t_bls, t_sec,
         t_datagov, t_fmcsa, t_mars, t_socrata, t_laborcurrent, t_apininjas, t_czds, t_aisstream,
         t_firms, t_earthdata, t_nass, t_cdse,
         t_ncei, t_airnow, t_openaq, t_openfda, t_fda_dashboard, t_dol, t_polygon, t_fmp]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated variable names to test")
    ap.add_argument("--json", help="write results to this path")
    ap.add_argument("--libs", help="extra site-packages dir (for 'websockets' when running under python -I)")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    if a.libs: sys.path.insert(0, a.libs)
    for t in TESTS:
        if only and not any(v in t.__code__.co_consts for v in only):
            continue
        try:
            t()
        except Exception as e:
            record(t.__name__, "?", "UNTESTABLE", f"test crashed: {type(e).__name__}: {e}")
    w = max(len(r["service"]) for r in results)
    print(f"{'Service'.ljust(w)}  {'Variable'.ljust(26)}  Status      Detail")
    for r in results:
        print(f"{r['service'].ljust(w)}  {r['variable'].ljust(26)}  {r['status'].ljust(10)}  {r['detail']}")
    if a.json:
        json.dump(results, open(a.json, "w"), indent=1)
