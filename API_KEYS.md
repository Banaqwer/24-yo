# API keys and accounts to create

Running tracker, updated at the end of every phase. Everything in the "Free" tiers costs $0. Never paste a key into chat: add it in the cloud environment's settings (the environment menu in the session title bar, then Edit) under Network secrets, or as an environment variable, using the variable name in the last column. A new session picks it up automatically.

Status values: TODO (you need to create it), ADDED (I can see the variable), SKIP (decided against), LATER (only once a signal that needs it is graded PROMISING).

## Tier 1 — create now (baseline data every backtest needs)

| Service | What it unlocks | Signup | Free tier limits | Status | Variable |
|---|---|---|---|---|---|
| Tiingo | Clean daily prices with long history for small/mid caps; terms-of-service-cleaner than Yahoo | https://www.tiingo.com (account, then API token) | Free: hourly/daily request caps and a symbol cap; enough for a 1,300-name universe refreshed in batches | TODO | `TIINGO_API_KEY` |
| Alpha Vantage | EARNINGS (historical reported vs estimated EPS and surprise), EARNINGS_CALENDAR (upcoming dates, 3/6/12 months), EARNINGS_ESTIMATES (EPS and revenue consensus with revision counts) | https://www.alphavantage.co/support/#api-key | 25 requests per day; no card | TODO | `ALPHAVANTAGE_API_KEY` |
| FRED | Macro controls (rates, spreads, activity indices) | https://fred.stlouisfed.org/docs/api/api_key.html | Generous; attribution required | TODO | `FRED_API_KEY` |
| EIA | Energy physical data by API (weekly petroleum, gas storage, electricity, refinery and operator-level series) | https://www.eia.gov/opendata/register.php | Generous | TODO | `EIA_API_KEY` |
| Census Bureau | Monthly imports/exports by HS code and country; economic indicators; keyless access is now refused from this container | https://api.census.gov/data/key_signup.html | 500 requests per day | TODO | `CENSUS_API_KEY` |
| BLS v2 | PPI and CPI series (distributor and industrial price proxies) | https://data.bls.gov/registrationEngine/ | 500 queries per day (v1 keyless is 25) | TODO | `BLS_API_KEY` |

## Tier 2 — create when the corresponding signal enters Phase 3 sourcing

| Service | What it unlocks | Signup | Free tier limits | Status | Variable |
|---|---|---|---|---|---|
| CourtListener | RECAP federal dockets and PACER mirror search (supplier suits, liens, product liability) | https://www.courtlistener.com/sign-in/ then profile API token | 5,000 requests per hour | TODO | `COURTLISTENER_API_TOKEN` |
| USPTO Open Data Portal and TSDR | Patent and trademark filings by assignee, bulk data | MyUSPTO account, then https://account.uspto.gov/api-manager/ | Generous | TODO | `USPTO_API_KEY`, `USPTO_TSDR_API_KEY` |
| api.data.gov (Regulations.gov, SAM.gov) | Regulations.gov full rate limit; SAM.gov contract opportunities | https://api.data.gov/signup/ | 1,000 requests per hour | TODO | `DATA_GOV_API_KEY` |
| FDA Data Dashboard | Inspection classifications and Form 483 citations by firm | https://datadashboard.fda.gov/oii/api (request credentials) | Unknown until granted | TODO | `FDA_DASHBOARD_KEY` |
| DOL Open Data Portal | OSHA inspections and citations by establishment | https://dataportal.dol.gov/registration | Generous | TODO | `DOL_API_KEY` |
| UK Companies House | Subsidiary accounts and filings by company number | https://developer.company-information.service.gov.uk/ | 600 requests per 5 minutes | TODO | `COMPANIES_HOUSE_API_KEY` |
| PJM Data Miner 2 | Interconnection queue, load and generation data | https://apiportal.pjm.com/ | Generous | TODO | `PJM_API_KEY` |
| Caltrans PeMS | California highway truck counts | https://pems.dot.ca.gov/ (account) | Web downloads only | TODO | `PEMS_USERNAME`, `PEMS_PASSWORD` |
| FMCSA QCMobile | Carrier fleet sizes and safety records by DOT number | https://mobile.fmcsa.dot.gov/QCDevsite/ | Generous | TODO | `FMCSA_WEBKEY` |

## Tier 3 — physical-world sources (satellite, thermal, soil, weather)

| Service | What it unlocks | Signup | Free tier limits | Status | Variable |
|---|---|---|---|---|---|
| NASA Earthdata Login | Black Marble VIIRS nightlights, SMAP soil moisture, LAADS archive | https://urs.earthdata.nasa.gov/users/new (accept the LAADS licence once in the browser) | Free | TODO | `EARTHDATA_TOKEN` (bearer token from the profile page) |
| NASA FIRMS | Thermal anomalies (plants, flares, smelters) via MAP_KEY | https://firms.modaps.eosdis.nasa.gov/api/map_key/ | 5,000 transactions per 10 minutes | TODO | `FIRMS_MAP_KEY` |
| Copernicus Data Space | Sentinel-5P methane/NO2 and Sentinel-2 downloads; Sentinel Hub Statistical API | https://dataspace.copernicus.eu/ (register, then create OAuth client) | Free quota | TODO | `CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET` |
| USDA NASS QuickStats | Crop progress, livestock, cold storage by state | https://quickstats.nass.usda.gov/api (key emailed) | Free | TODO | `NASS_API_KEY` |
| NOAA NCEI CDO | Station weather history (optional; the keyless Access Data Service already works) | https://www.ncei.noaa.gov/cdo-web/token | 10,000 requests per day | LATER | `NCEI_TOKEN` |
| EPA AirNow | Ground air-quality observations (industrial activity proxy) | https://docs.airnowapi.org/account/request/ | 500 requests per hour | LATER | `AIRNOW_API_KEY` |
| OpenAQ | Global air-quality sensors | https://explore.openaq.org/register | Free | LATER | `OPENAQ_API_KEY` |
| Global Fishing Watch | Vessel events and encounters (check commercial-use terms before relying on it) | https://globalfishingwatch.org/our-apis/ | Free | LATER | `GFW_API_TOKEN` |

## Tier 4 — digital sources

| Service | What it unlocks | Signup | Free tier limits | Status | Variable |
|---|---|---|---|---|---|
| Best Buy Developer | Product prices, availability and sale status at Best Buy (consumer electronics brands) | https://developer.bestbuy.com/ | 5 requests per second, 50,000 per day | TODO | `BESTBUY_API_KEY` |
| API Ninjas | Earnings-call transcripts (the only terms-clean programmatic source found) | https://api-ninjas.com/ | Monthly call cap on the free tier | TODO | `API_NINJAS_KEY` |
| GitHub personal token | Repository metadata outside this container (inside it the proxy gates /repos; search endpoints work keyless) | https://github.com/settings/tokens (read-only public scope) | 5,000 requests per hour | LATER | `GITHUB_TOKEN` |
| Socrata app token | Higher rate limits on CDC, NYC, Austin and other open-data portals | https://data.cdc.gov/profile/edit/developer_settings | Free | LATER | `SOCRATA_APP_TOKEN` |
| ICANN CZDS | Daily zone files for .com and others (new domain registrations); each registry approves access separately | https://czds.icann.org/ | Free, approval takes days | LATER | `CZDS_USERNAME`, `CZDS_PASSWORD` |
| Reddit script app | Post volume and sentiment on company and product subreddits | https://www.reddit.com/prefs/apps | 100 queries per minute; terms are non-commercial, so AMBER until decided | SKIP for now | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` |
| Polygon.io, Financial Modeling Prep | Backup price and calendar sources | https://polygon.io, https://site.financialmodelingprep.com | Free tiers (5 requests per minute; 250 per day) | LATER | `POLYGON_API_KEY`, `FMP_API_KEY` |

## Decided against (licence or terms)

| Service | Reason |
|---|---|
| OpenSky Network account (historical flights) | Free tier is non-commercial only; trading research treated as commercial. Live anonymous positions stay usable. |
| Cloudflare Radar | Data licensed CC BY-NC 4.0 (non-commercial). |
| Google Earth Engine | Free tier is non-commercial only. Planetary Computer and AWS open buckets cover the same imagery. |
| Glassdoor, Indeed, LinkedIn, Amazon, Trustpilot, Grainger, Fastenal, McMaster-Carr scraping | Terms prohibit automated access and the sites block it. |

## Paid, only after a signal is graded PROMISING (budget $100 per month total)

| Service | Price | Unlocks |
|---|---|---|
| Polygon Starter | about $29 per month | Minute bars, full options reference data |
| optiondata.org / HistoricalData.net | $68 per month for updates; $160 to $580 one-time for the archive | End-of-day option chains back to 2002 (implied-move history) |
| LayoffData.com | $8 to $10 per month | Downloadable multi-state WARN database |
| Tiingo Power | $30 per month | Higher request caps |

Over budget and therefore out: WARNTracker ($250 per month), Panjiva and ImportGenius bills of lading, MarineTraffic and VesselFinder live AIS, Similarweb, PACER at volume.
