# API keys and accounts

Running tracker, updated at the end of every phase and whenever keys are added or tested. Everything in the free tiers costs $0.

**Where keys live.** Never paste a key into chat: add it in the cloud environment's settings (the environment menu in the session title bar, then Edit) under Network secrets, or as an environment variable, using the variable name in the tables. A new session picks it up automatically. Keys are never written to this repository.

**Security note, 2026-11-11.** The keys below were pasted into a chat session once. Treat anything pasted in chat as exposed: regenerate the ICANN CZDS password (it is a login password, not an API key, and it did not authenticate anyway), and regenerate any key you care about from its provider's dashboard. Free-data API keys are low value to an attacker, but regeneration is one click.

**Checking keys.** `python3 -I tools/keys/check_keys.py` reads every variable from the environment, makes one minimal real request per key, and prints OK / FAIL / PREMIUM / RETIRED / UNTESTABLE / SKIP without printing any key. Pass `--libs <dir>` with a `websockets` install for the AIS test.

Status values: VERIFIED (a real request succeeded on the date shown; add the key to the environment if not yet there), TODO (you need to create it), NEEDS YOU (I need one thing from you to finish), FAIL (rejected), RETIRED (the service is gone), SKIP (decided against), LATER (only once a signal that needs it is graded PROMISING).

## Open items that need you

| Item | What is needed |
|---|---|
| `SEC_USER_AGENT` | Set the variable to a string of the form `Your Name your@email`. SEC requires it on every automated request. No signup. Blocks all ten Phase 2 top-10 rows (every one needs the EDGAR 8-K release-date harness). |
| PJM Data Miner 2 | N15 is rank 2 in the Phase 2 top 10 and its hypothesis needs PJM West day-ahead prices. Create the free account at https://apiportal.pjm.com/ and set `PJM_API_KEY` to the key it gives you; the exact steps inside the portal are UNKNOWN from here. |
| Collector host (decision, not a key) | G02 (FDA shortage snapshots), S04 (aisstream geofenced AIS) and the consensus snapshots lose history every day nothing is collecting. This research container is ephemeral and cannot host them. Options: your own machine, a small VPS, or a scheduled task on this platform. |
| Consensus snapshots (decision, not a key) | Five top-10 rows compare against point-in-time consensus and no free source with history exists. Either start daily snapshots now (Alpha Vantage 25 calls a day, FMP) for forward history only, or accept that Phase 4 respecifies those rows against reported year-over-year or guidance-midpoint stand-ins. |
| ICANN CZDS | Authentication was rejected (HTTP 401, same as a bogus login). CZDS signs in with the email address you registered, not a handle. After you change the password, set `CZDS_USERNAME` to that email and `CZDS_PASSWORD` to the new password in the environment, and I will retest. Also open https://czds.icann.org/ and request .com and .net access from Verisign; approval takes days to weeks. |
| FDA Data Dashboard | The key is in hand, but the API also requires the email you registered with, sent as a header on every call. Set `FDA_DASHBOARD_USER` to that email in the environment if you want this tested; it is a LATER item, so skipping it costs nothing now. |
| USPTO | Your MyUSPTO account exists but the key pages render only in a browser (both returned empty from here). Sign in at https://data.uspto.gov and look for an API key or API management entry in the account menu; for the trademark TSDR key use https://account.uspto.gov/api-manager/ while signed in. Steps beyond that are UNKNOWN from here. LATER item. |

## Needed by the Phase 2 top 10

What each SOURCING row needs before Phase 3 can source it. Everything here is free.

| Row | Needs | Status |
|---|---|---|
| All ten | `SEC_USER_AGENT`; EDGAR 8-K Item 2.02 release-date harness | NEEDS YOU (the variable) |
| N18 USDA broiler and egg prices | `USDA_MARS_API_KEY`, `NASS_API_KEY`; a consensus source (see open items) | Keys VERIFIED; consensus open |
| N15 NRC reactor status | `PJM_API_KEY`; `EIA_API_KEY` | PJM TODO; EIA VERIFIED |
| N50 Hail-swath index | `CENSUS_API_KEY`, `FRED_API_KEY`; NCEI bulk files while the SWDI service is down (keyless) | VERIFIED |
| N03 NPDES effluent flow | Keyless ECHO and DMR zips; `BLS_API_KEY` for controls | VERIFIED |
| N09 npm download share | Keyless npm API; Google Cloud only for an optional PyPI backfill | Nothing to create; Google Cloud optional |
| N22 NHTSA recalls | Keyless flat files | Nothing to create |
| G02 FDA shortages | `OPENFDA_API_KEY`; a daily snapshot collector on an always-on host | Key VERIFIED; host is a decision |
| S33 Supplier-first disclosures | `SEC_USER_AGENT`; EDGAR full-text search (keyless, intermittent); the API Ninjas transcript leg is dropped (premium-only) | Nothing new to create |
| S04 AIS terminal calls | `AISSTREAM_API_KEY` plus an always-on geofenced collector; `CENSUS_API_KEY` for trade data | Keys VERIFIED; host is a decision; aisstream has no terms page |
| S16 Federal obligations | Keyless USAspending; `DATA_GOV_API_KEY` for SAM award notices as a cross-check | VERIFIED |

## Tier 1 — baseline data every backtest needs

| Service | What it unlocks | Signup | Free tier limits | Status | Variable |
|---|---|---|---|---|---|
| Tiingo | Clean daily prices with long history for small and mid caps | https://www.tiingo.com | Hourly and daily request caps and a symbol cap | VERIFIED 2026-11-11 | `TIINGO_API_KEY` |
| Alpha Vantage | EARNINGS, EARNINGS_CALENDAR, EARNINGS_ESTIMATES; the N35 fallback calendar and the S33 consensus snapshot | https://www.alphavantage.co/support/#api-key | 25 requests per day, counted per key and per IP. From this shared cloud IP the daily cap can already be spent by others (seen on the second test), so Alpha Vantage pulls are best run once a day early, or from your own machine | VERIFIED 2026-11-11 | `ALPHAVANTAGE_API_KEY` |
| FRED | Macro controls; HS import price indexes used to deflate S22 | https://fred.stlouisfed.org/docs/api/api_key.html | Generous; attribution required | VERIFIED 2026-11-11 | `FRED_API_KEY` |
| EIA | EIA-860M, EIA-923, EIA-914 and weekly series by API (N12, N15, N21, S07) | https://www.eia.gov/opendata/register.php | Generous | VERIFIED 2026-11-11 | `EIA_API_KEY` |
| Census Bureau | Monthly imports and exports by HS code (S22, S04 anchor); housing units per tract (N50) | https://api.census.gov/data/key_signup.html | 500 requests per day | VERIFIED 2026-11-11 (ACS and international trade both answered) | `CENSUS_API_KEY` |
| BLS v2 | PPI detailed-commodity indexes with 20 years of history (N55, S22) | https://data.bls.gov/registrationEngine/ | 500 queries per day | VERIFIED 2026-11-11 | `BLS_API_KEY` |
| SEC EDGAR User-Agent | Not a key. Required on every SEC request; used by the target variable, N27, N35, N39, N43, S14, S18, S31, S33 | None; choose the string | 10 requests per second | NEEDS YOU | `SEC_USER_AGENT` |

## Tier 2 — needed when the corresponding signal enters Phase 3 sourcing

| Service | Signals | What it unlocks | Signup | Free tier limits | Status | Variable |
|---|---|---|---|---|---|---|
| CourtListener | S14 | RECAP federal dockets with nature-of-suit codes | https://www.courtlistener.com/sign-in/ then profile API token | 5,000 requests per hour | TODO | `COURTLISTENER_API_TOKEN` |
| PACER (Case Locator) | S14 | Party-name search for the backtest | https://pacer.uscourts.gov/register-account | $0.10 per page, waived below $30 per quarter | TODO | `PACER_USERNAME`, `PACER_PASSWORD` |
| api.data.gov | S07, N62 | One key for Regulations.gov, SAM.gov and EPA CAMPD | https://api.data.gov/signup/ | 1,000 requests per hour | VERIFIED 2026-11-11 on Regulations.gov. The EPA CAMPD gateway returned "route does not exist" for every path that day, an outage on EPA's side to recheck in Phase 3 | `DATA_GOV_API_KEY` |
| PJM Data Miner 2 | N15 | PJM West day-ahead prices | https://apiportal.pjm.com/ | Generous | TODO, needed for Phase 3 (N15 is rank 2) | `PJM_API_KEY` |
| FMCSA QCMobile | N56 | Per-carrier inspection counts and fleet sizes | https://mobile.fmcsa.dot.gov/QCDevsite/ | Generous | VERIFIED 2026-11-11 | `FMCSA_WEBKEY` |
| USDA AMS Market News (MARS) | N18 | Machine-readable egg and chicken price reports (1,051 report slugs listed) | https://mymarketnews.ams.usda.gov/ | Free | VERIFIED 2026-11-11 (basic auth, key as username) | `USDA_MARS_API_KEY` |
| Socrata app token | N01, N44, N51, N56, G01, G08 | Higher rate limits across Socrata portals; one token worked on data.texas.gov and data.austintexas.gov. Note for G08: data.iowa.gov no longer serves the liquor dataset at its old resource path; find the new id in Phase 3 | https://data.texas.gov/profile/edit/developer_settings | Free | VERIFIED 2026-11-11 | `SOCRATA_APP_TOKEN` |
| Google Cloud project | N09, N65 | BigQuery public datasets (PyPI downloads, HTTP Archive). Create a project, enable BigQuery, make a service account with BigQuery Job User, download its JSON key; billing can stay disabled | https://console.cloud.google.com/ | 1 TB of queries per month | TODO | `GCP_PROJECT_ID`, `GCP_SERVICE_ACCOUNT_JSON` |
| aisstream.io | S04 | Free terrestrial AIS websocket stream (`wss://stream.aisstream.io/v0/stream`; subscribe within 3 s; 3 connections per account; no SLA; per-user bandwidth limits from September 2026 unless compressed) | https://aisstream.io/account (GitHub login) | Free | VERIFIED 2026-11-11 (subscription confirmed). Terms: no terms page exists (404); the site and docs say free; nothing found on storage or commercial use. Legal risk stays 3 and S04 should ask the operator before a persistent archive | `AISSTREAM_API_KEY` |
| LaborCurrent | S12 | National WARN notices, `GET https://laborcurrent.com/api/records` with header `X-API-Key`. Evaluation tier per its pricing page: 30-day delayed, 10 calls per day, 10 records per call, 90 days of history, 30-day trial (its docs page states slightly different numbers). Terms permit research use, forbid redistribution of raw data, require attribution, say nothing on storage | https://laborcurrent.com/ | As stated | VERIFIED 2026-11-11 | `LABORCURRENT_API_KEY` |
| Retailer promo mailbox | N48 | A fresh mailbox subscribed to retailer broadcast lists, read over IMAP. No lawful history exists, so start it as soon as N48 passes Phase 2 | Any provider with IMAP | Free | TODO | `PROMO_MAILBOX_IMAP_HOST`, `PROMO_MAILBOX_USER`, `PROMO_MAILBOX_PASSWORD` |
| API Ninjas | S33 | Key is valid (earnings calendar answered), but the earnings-transcript endpoint is premium-only, so the free tier does not give S33 what it needed | https://api-ninjas.com/ | Transcripts not on the free tier | VERIFIED 2026-11-11, transcripts PREMIUM | `API_NINJAS_KEY` |
| ICANN CZDS | N63 | Daily .com and .net zone files; per-TLD approval by Verisign | https://czds.icann.org/ | Free | FAIL 2026-11-11: login rejected; see open items | `CZDS_USERNAME`, `CZDS_PASSWORD` |

## Tier 3 — physical-world sources

| Service | Signals | What it unlocks | Signup | Free tier limits | Status | Variable |
|---|---|---|---|---|---|---|
| NASA FIRMS | S02 | VIIRS 375 m thermal anomalies (key status endpoint and area CSV both answered) | https://firms.modaps.eosdis.nasa.gov/api/map_key/ | 5,000 transactions per 10 minutes | VERIFIED 2026-11-11 | `FIRMS_MAP_KEY` |
| NASA Earthdata Login | S02 | Black Marble downloads; a ranged download from the LAADS cloud host succeeded with the token and was refused without it. The token expires 2027-01-10; generate a new one on the profile page before then | https://urs.earthdata.nasa.gov/ | Free | VERIFIED 2026-11-11 | `EARTHDATA_TOKEN` |
| USDA NASS QuickStats | N17, N18 | Cold Storage, Potato Stocks, weekly Broiler Hatchery | https://quickstats.nass.usda.gov/api | 50,000 records per call | VERIFIED 2026-11-11 | `NASS_API_KEY` |
| Copernicus Data Space | none kept | OAuth client for the Sentinel Hub APIs (Process, Statistical, Catalog): a token was issued and an 8x8 Process API request returned an image. OData and S3 downloads of whole products use a different token (your username and password with `client_id=cdse-public` at the same token endpoint), which this client cannot get. OAuth clients are created at https://shapps.dataspace.copernicus.eu/dashboard/#/account/settings under User Settings, OAuth clients (the secret is shown once). No kept signal needs it (S03 and N45 were rejected) | https://dataspace.copernicus.eu/ | 10,000 requests and 10,000 processing units per month on Sentinel Hub | VERIFIED 2026-11-11; LATER for use | `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET` |
| NOAA NCEI CDO | none kept | Station weather history | https://www.ncei.noaa.gov/cdo-web/token | 10,000 requests per day | VERIFIED 2026-11-11 | `NCEI_TOKEN` |
| EPA AirNow | none kept | Ground air-quality observations | https://docs.airnowapi.org/ | The observation web service was retired on 2026-10-01 (HTTP 410 with that message) | RETIRED; OpenAQ covers the same need | `AIRNOW_API_KEY` |
| OpenAQ | none kept | Global air-quality sensors (v3) | https://explore.openaq.org/register | Free | VERIFIED 2026-11-11 | `OPENAQ_API_KEY` |

## Tier 4 — digital and other sources

| Service | Signals | What it unlocks | Signup | Free tier limits | Status | Variable |
|---|---|---|---|---|---|---|
| openFDA key | N26, S24, G02 | Higher rate limits on device-event, recall and drug-shortage endpoints | https://open.fda.gov/apis/authentication/ | 120,000 requests per day | VERIFIED 2026-11-11 | `OPENFDA_API_KEY` |
| GitHub personal token | S27 | Higher search rate limits | https://github.com/settings/tokens | 5,000 requests per hour | LATER | `GITHUB_TOKEN` |
| USPTO Open Data Portal and TSDR | none kept | Patent and trademark bulk data (S28 and S15 rejected) | https://data.uspto.gov, https://account.uspto.gov/api-manager/ | Generous | LATER; account created, key location unconfirmed (see open items) | `USPTO_API_KEY`, `USPTO_TSDR_API_KEY` |
| FDA Data Dashboard | none kept | Inspection classifications (S15 rejected for look-ahead) | https://datadashboard.fda.gov/oii/api | Unknown | Key received; NEEDS YOU to test (registered email as header) | `FDA_DASHBOARD_KEY`, `FDA_DASHBOARD_USER` |
| DOL Open Data Portal | none kept | OSHA inspections by establishment. The key is accepted only as the `X-API-KEY` query parameter; the same name as a header returns 401 | https://dataportal.dol.gov/registration | Generous | VERIFIED 2026-11-11 | `DOL_API_KEY` |
| Bid Express (Infotech) | N49 | State DOT letting results; UNKNOWN whether results need a paid tier | https://www.bidx.com/ | Unknown | LATER, pending check in Phase 3 | `BIDX_USERNAME`, `BIDX_PASSWORD` |
| Financial Modeling Prep | backup | Backup price, profile and calendar source via the `/stable/` endpoints (the old `/api/v3/` paths are closed to new accounts) | https://site.financialmodelingprep.com | 250 requests per day | VERIFIED 2026-11-11 (the key supplied under the Polygon row was an FMP key) | `FMP_API_KEY` |
| Polygon.io | backup | Backup prices | https://polygon.io | 5 requests per minute | LATER, not created | `POLYGON_API_KEY` |

## Decided against (licence, terms, or the signal was rejected)

| Service | Reason |
|---|---|
| UK Companies House | S17 (foreign subsidiary accounts) rejected: accounts are 9 to 21 months stale. |
| Caltrans PeMS | The truck-count leg of S06 was dropped: months of lag, no single-tenant stations. |
| Best Buy Developer API | Dropped from S25: commercial use needs Best Buy approval and caching is limited to a temporary basis. |
| Reddit script app | S20 rejected; terms are non-commercial. |
| Global Fishing Watch | API licence is CC BY-NC 4.0 (non-commercial); dropped from S04. |
| OpenSky Network account (historical flights) | Free tier is non-commercial only; the corporate-jet leg of S18 and N06 were dropped. |
| Cloudflare Radar | Data licensed CC BY-NC 4.0. |
| Google Earth Engine | Free tier is non-commercial only. Planetary Computer and AWS open buckets cover the same imagery. |
| Glassdoor, Indeed, LinkedIn, Amazon, Trustpilot, Grainger, Fastenal, McMaster-Carr, Ryder and Penske used-truck sites, Milled, eBay Browse API | Terms prohibit automated access or restrict market-data use, and most block it. |

## Paid, only after a signal is graded PROMISING (budget $100 per month total)

| Service | Price | Unlocks | Signal |
|---|---|---|---|
| LaborCurrent Starter | $49 per month | Same-day national WARN coverage including Texas, 200 calls per day, 1 year of history | S12 |
| API Ninjas premium | Price not checked | Earnings-call transcripts (the free key cannot reach them) | S33 |
| Polygon Starter | about $29 per month | Minute bars, full options reference data | execution |
| optiondata.org / HistoricalData.net | $68 per month for updates; $160 to $580 one-time for the archive | End-of-day option chains back to 2002 | execution |
| LayoffData.com | $8 to $10 per month | Downloadable multi-state WARN database (alternative to LaborCurrent) | S12 |
| Tiingo Power | $30 per month | Higher request caps | prices |
| Browser-fetch or proxy service | $10 to $20 per month | Only for sites whose terms permit automated access; never to bypass a block | N28, N29 |

Over budget and therefore out: WARNTracker ($250 per month), Panjiva and ImportGenius bills of lading, MarineTraffic and VesselFinder live AIS, Similarweb, PACER at volume, UniCourt and Trellis, commercial satellite imagery.
