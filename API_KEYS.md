# API keys and accounts to create

Running tracker, updated at the end of every phase. Everything in the "Free" tiers costs $0. Never paste a key into chat: add it in the cloud environment's settings (the environment menu in the session title bar, then Edit) under Network secrets, or as an environment variable, using the variable name in the last column. A new session picks it up automatically.

Status values: TODO (you need to create it), ADDED (I can see the variable), SKIP (decided against), LATER (only once a signal that needs it is graded PROMISING).

## What changed in Phase 1

- Tier 1 is unchanged except for one new required variable: a declared SEC EDGAR User-Agent string. EDGAR is used by the target variable and by at least six kept signals.
- New free items added to Tier 2 because a kept signal depends on them: USDA AMS market-news credentials, a Socrata app token, a Google Cloud project (BigQuery public datasets, free query quota), an aisstream.io key, a LaborCurrent evaluation key, a PACER account, a dedicated mailbox for retailer promotional email.
- Moved to LATER because the only signal that needed them was rejected or dropped that leg: USPTO, FDA Data Dashboard, DOL Open Data, GitHub token, openFDA key, Copernicus Data Space.
- Moved to SKIP: Companies House (S17 rejected), Caltrans PeMS (truck-count leg of S06 dropped), Best Buy (leg of S25 dropped on terms), Reddit (S20 rejected), Global Fishing Watch (non-commercial licence).
- Nothing in the kept list needs a paid key. The only likely spend under $100 per month is LaborCurrent's live tier ($49) if S12 is graded PROMISING, and a browser-fetch service for N28 and N29 only if each site's terms permit automated access.

## Tier 1 — create now (baseline data every backtest needs)

| Service | What it unlocks | Signup | Free tier limits | Status | Variable |
|---|---|---|---|---|---|
| Tiingo | Clean daily prices with long history for small and mid caps; terms-of-service-cleaner than Yahoo | https://www.tiingo.com (account, then API token) | Hourly and daily request caps and a symbol cap; enough for a 1,300-name universe refreshed in batches | TODO | `TIINGO_API_KEY` |
| Alpha Vantage | EARNINGS (historical reported vs estimated EPS), EARNINGS_CALENDAR (upcoming dates), EARNINGS_ESTIMATES (consensus with revision counts). Also the N35 fallback calendar and the S33 consensus snapshot | https://www.alphavantage.co/support/#api-key | 25 requests per day; no card | TODO | `ALPHAVANTAGE_API_KEY` |
| FRED | Macro controls; HS import price indexes used to deflate S22 | https://fred.stlouisfed.org/docs/api/api_key.html | Generous; attribution required | TODO | `FRED_API_KEY` |
| EIA | EIA-860M, EIA-923, EIA-914 and weekly series by API (N12, N15, N21, S07) | https://www.eia.gov/opendata/register.php | Generous | TODO | `EIA_API_KEY` |
| Census Bureau | Monthly imports and exports by HS code (S22, S04 anchor); housing units per tract (N50); keyless access is refused from this container | https://api.census.gov/data/key_signup.html | 500 requests per day | TODO | `CENSUS_API_KEY` |
| BLS v2 | PPI detailed-commodity indexes with 20 years of history (N55, S22) | https://data.bls.gov/registrationEngine/ | 500 queries per day (v1 keyless is 25 and 3 years) | TODO | `BLS_API_KEY` |
| SEC EDGAR User-Agent | Not a key. SEC requires every automated request to declare a User-Agent of the form "Company or person name, contact email". Used by the target variable, N27, N35, N39, N43, S14, S18, S31, S33 | No signup; choose the string yourself | 10 requests per second | TODO | `SEC_USER_AGENT` |

## Tier 2 — create when the corresponding signal enters Phase 3 sourcing

| Service | Signals | What it unlocks | Signup | Free tier limits | Status | Variable |
|---|---|---|---|---|---|---|
| CourtListener | S14 | RECAP federal dockets with nature-of-suit codes | https://www.courtlistener.com/sign-in/ then profile API token | 5,000 requests per hour | TODO | `COURTLISTENER_API_TOKEN` |
| PACER (Case Locator) | S14 | Party-name search with filing dates back decades, for the backtest | https://pacer.uscourts.gov/register-account | $0.10 per page, waived below $30 per quarter | TODO | `PACER_USERNAME`, `PACER_PASSWORD` |
| api.data.gov | S07, N62 | Lifts the DEMO_KEY throttle on EPA CAMPD; SAM.gov opportunities if N62 adds that leg | https://api.data.gov/signup/ | 1,000 requests per hour | TODO | `DATA_GOV_API_KEY` |
| PJM Data Miner 2 | N15 | PJM West day-ahead prices to value lost nuclear output | https://apiportal.pjm.com/ | Generous | TODO | `PJM_API_KEY` |
| FMCSA QCMobile | N56 | Per-carrier inspection counts and fleet sizes by USDOT number | https://mobile.fmcsa.dot.gov/QCDevsite/ | Generous | TODO | `FMCSA_WEBKEY` |
| USDA AMS Market News (MARS) | N18 | Machine-readable egg and chicken price reports; the endpoint returns 403 without credentials (TESTED HERE) | https://mymarketnews.ams.usda.gov/ (register, then API key under your profile) | Free | TODO | `USDA_MARS_API_KEY` |
| Socrata app token | N01, N44, N51, N56, G01, G08 | Higher rate limits on Texas Comptroller, Austin, Los Angeles, Iowa and other open-data portals; one token works across portals | https://data.texas.gov/profile/edit/developer_settings (any Socrata portal account) | Free | TODO | `SOCRATA_APP_TOKEN` |
| Google Cloud project | N09, N65 | BigQuery public datasets: PyPI download history, HTTP Archive technology detections. Create a project, enable BigQuery, create a service account with BigQuery Job User, download its JSON key. Billing can stay disabled | https://console.cloud.google.com/ | 1 TB of queries per month free | TODO | `GCP_PROJECT_ID`, `GCP_SERVICE_ACCOUNT_JSON` (file contents) |
| aisstream.io | S04 | Free terrestrial AIS websocket stream to archive vessel calls from day one. AMBER: its terms page was not found, so read the terms before relying on it | https://aisstream.io/ (sign in with GitHub, create key) | Free | TODO after terms check | `AISSTREAM_API_KEY` |
| LaborCurrent (formerly WARN Firehose) | S12 | National WARN notices; the $0 evaluation tier serves 30-day-delayed history, enough for the backtest | https://laborcurrent.com/ | Evaluation tier free | TODO | `LABORCURRENT_API_KEY` |
| Retailer promo mailbox | N48 | A fresh mailbox at any free provider, subscribed to retailer broadcast lists and read over IMAP. No history exists anywhere lawful, so this should start as soon as N48 passes Phase 2 | Any provider that allows IMAP (an app password if two-factor is on) | Free | TODO | `PROMO_MAILBOX_IMAP_HOST`, `PROMO_MAILBOX_USER`, `PROMO_MAILBOX_PASSWORD` |
| API Ninjas | S33 | Earnings-call transcripts for the few supplier calls flagged by S33 | https://api-ninjas.com/ | Monthly call cap on the free tier | TODO | `API_NINJAS_KEY` |
| ICANN CZDS | N63 | Daily .com and .net zone files. Per-TLD approval by Verisign takes days to weeks and the access agreement restricts use, so legal risk stays 3 until read | https://czds.icann.org/ | Free | TODO after terms check | `CZDS_USERNAME`, `CZDS_PASSWORD` |

## Tier 3 — physical-world sources

| Service | Signals | What it unlocks | Signup | Free tier limits | Status | Variable |
|---|---|---|---|---|---|---|
| NASA FIRMS | S02 | VIIRS 375 m thermal anomalies at plants, smelters, kilns and flares (the primary S02 series) | https://firms.modaps.eosdis.nasa.gov/api/map_key/ | 5,000 transactions per 10 minutes | TODO | `FIRMS_MAP_KEY` |
| NASA Earthdata Login | S02 | Black Marble nightly radiance as the secondary S02 series (accept the LAADS licence once in the browser) | https://urs.earthdata.nasa.gov/users/new | Free | TODO | `EARTHDATA_TOKEN` (bearer token from the profile page) |
| USDA NASS QuickStats | N17, N18 | Cold Storage, Potato Stocks, weekly Broiler Hatchery by state | https://quickstats.nass.usda.gov/api (key emailed) | Free | TODO | `NASS_API_KEY` |
| Copernicus Data Space | none kept | Sentinel-5P and Sentinel-2 downloads (S03 and N45 were rejected) | https://dataspace.copernicus.eu/ | Free quota | LATER | `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET` |
| NOAA NCEI CDO | none kept | Station weather history (the keyless Access Data Service already works) | https://www.ncei.noaa.gov/cdo-web/token | 10,000 requests per day | LATER | `NCEI_TOKEN` |
| EPA AirNow, OpenAQ | none kept | Ground air-quality observations | https://docs.airnowapi.org/account/request/ and https://explore.openaq.org/register | Free | LATER | `AIRNOW_API_KEY`, `OPENAQ_API_KEY` |

## Tier 4 — digital and other sources

| Service | Signals | What it unlocks | Signup | Free tier limits | Status | Variable |
|---|---|---|---|---|---|---|
| openFDA key | N26, S24, G02 | Higher rate limits on device-event, recall and drug-shortage endpoints; keyless works for now | https://open.fda.gov/apis/authentication/ | 120,000 requests per day with key | LATER | `OPENFDA_API_KEY` |
| GitHub personal token | S27 | Higher search rate limits for repository activity (GH Archive bulk is keyless) | https://github.com/settings/tokens (read-only public scope) | 5,000 requests per hour | LATER | `GITHUB_TOKEN` |
| USPTO Open Data Portal and TSDR | none kept | Patent and trademark bulk data (S28 and S15 rejected) | https://account.uspto.gov/api-manager/ | Generous | LATER | `USPTO_API_KEY`, `USPTO_TSDR_API_KEY` |
| FDA Data Dashboard | none kept | Inspection classifications (S15 rejected for look-ahead) | https://datadashboard.fda.gov/oii/api | Unknown | LATER | `FDA_DASHBOARD_KEY` |
| DOL Open Data Portal | none kept | OSHA inspections by establishment | https://dataportal.dol.gov/registration | Generous | LATER | `DOL_API_KEY` |
| Bid Express (Infotech) | N49 | State DOT letting results where the DOT's own site does not publish apparent-low-bid tables. UNKNOWN whether results need a paid tier | https://www.bidx.com/ | Unknown | LATER, pending check in Phase 3 | `BIDX_USERNAME`, `BIDX_PASSWORD` |
| Polygon.io, Financial Modeling Prep | backup | Backup price and calendar sources | https://polygon.io, https://site.financialmodelingprep.com | 5 requests per minute; 250 per day | LATER | `POLYGON_API_KEY`, `FMP_API_KEY` |

## Decided against (licence, terms, or the signal was rejected)

| Service | Reason |
|---|---|
| UK Companies House | S17 (foreign subsidiary accounts) rejected: accounts are 9 to 21 months stale. |
| Caltrans PeMS | The truck-count leg of S06 was dropped: months of lag, no single-tenant stations. |
| Best Buy Developer API | Dropped from S25: commercial use needs Best Buy approval and caching is limited to a temporary basis, which conflicts with a daily archive. |
| Reddit script app | S20 rejected; terms are non-commercial. |
| Global Fishing Watch | API licence is CC BY-NC 4.0 (non-commercial); dropped from S04. |
| OpenSky Network account (historical flights) | Free tier is non-commercial only; the corporate-jet leg of S18 and N06 were dropped. |
| Cloudflare Radar | Data licensed CC BY-NC 4.0. |
| Google Earth Engine | Free tier is non-commercial only. Planetary Computer and AWS open buckets cover the same imagery. |
| Glassdoor, Indeed, LinkedIn, Amazon, Trustpilot, Grainger, Fastenal, McMaster-Carr, Ryder and Penske used-truck sites, Milled, eBay Browse API | Terms prohibit automated access or restrict market-data use, and most block it. |

## Paid, only after a signal is graded PROMISING (budget $100 per month total)

| Service | Price | Unlocks | Signal |
|---|---|---|---|
| LaborCurrent live tier | $49 per month | Same-day national WARN coverage including Texas | S12 |
| Polygon Starter | about $29 per month | Minute bars, full options reference data | execution |
| optiondata.org / HistoricalData.net | $68 per month for updates; $160 to $580 one-time for the archive | End-of-day option chains back to 2002 (implied-move history) | execution |
| LayoffData.com | $8 to $10 per month | Downloadable multi-state WARN database (alternative to LaborCurrent) | S12 |
| Tiingo Power | $30 per month | Higher request caps | prices |
| Browser-fetch or proxy service | $10 to $20 per month | Only for sites whose terms permit automated access; never to bypass a block | N28, N29 |

Over budget and therefore out: WARNTracker ($250 per month), Panjiva and ImportGenius bills of lading, MarineTraffic and VesselFinder live AIS, Similarweb, PACER at volume, UniCourt and Trellis, commercial satellite imagery.
