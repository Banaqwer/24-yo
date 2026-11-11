export const meta = {
  name: 'phase0-capability-probe',
  description: 'Empirically test runtime, libraries, and reachability of free public data sources for the alt-data research pipeline (Phase 0 tool check)',
  phases: [
    { title: 'Probe', detail: 'six agents each fetch a group of sources for real' },
    { title: 'Verify', detail: 'a skeptic per group re-fetches every reachable claim' },
    { title: 'Coverage', detail: 'critic maps results to the Seed Catalogue and probes gaps' },
  ],
}

const SCRATCH = args.scratch

const PREAMBLE = `CONTEXT: Phase 0 of an alternative-data equity research program (US small/mid caps, event-driven around earnings, $0 data budget to start, Python plus web). Your job is to EMPIRICALLY test, from inside this cloud container, whether specific free public data sources are reachable and return real data. Never guess: every status you report must come from an HTTP request or command you actually ran in this session. Report honestly; a source that fails is a useful result.

NETWORK FACTS: outbound HTTPS goes through a pre-configured agent proxy (HTTPS_PROXY is already set; CA bundle /root/.ccr/ca-bundle.crt). Never disable TLS verification and never unset HTTPS_PROXY. If a request fails with TLS error, connection reset, or HTTP 403/405/407 that comes from the PROXY (check headers / body text mentioning agentproxy; you can also run: curl -sS "$HTTPS_PROXY/__agentproxy/status"), classify it BLOCKED_BY_PROXY. A 401/403 that comes from the site itself (key required, login wall, bot block) is REACHABLE_NEEDS_KEY or REACHABLE_BOT_BLOCKED, not BLOCKED_BY_PROXY. Read /root/.ccr/README.md once if anything proxy-related is unclear.

METHOD: use curl with '-sS -m 20' and write status codes with '-w %{http_code}', or Python requests with timeout=20. Keep fetches tiny (HEAD, limit=1, a 5-day range, Range: bytes=0-2000). For SEC hosts send header 'User-Agent: altdata-research-probe/0.1 (research; no-reply@example.org)'. For api.nasdaq.com and similar send a browser-like User-Agent and Accept headers. Create the directory ${SCRATCH}/probe_<GROUP>/ and save any sample you download there (never run scripts from inside it). Do not install anything system-wide. Do not log in anywhere, do not bypass any login or paywall, do not retry aggressively (one retry max per source). If a source is paid-only or login-only just confirm the host responds and record REACHABLE_NEEDS_KEY with what signup is required and whether it is free.

STATUS VALUES: REACHABLE_DATA (2xx and the body is the expected real data; evidence must quote a tiny snippet or counts), REACHABLE_NEEDS_KEY (host up, requires API key/login; say if free signup exists), REACHABLE_BOT_BLOCKED (host up but anti-bot/captcha/TOS block), BLOCKED_BY_PROXY, TIMEOUT, ERROR (anything else, with the error text), NOT_TESTED (with reason). In 'tos_flag' note any obvious terms-of-service or robots.txt conflict you noticed ('none seen' if not). In 'history' note what history depth the source appears to offer if visible from the response or docs page, else 'unknown'. In 'needs' say exactly what a human must do to unlock it (e.g. 'free FRED API key at ...'). Your final structured output must contain one row per source listed below plus any extra sources you tested. Set 'group' to the group letter. Put general observations in environment_notes.

`

const GROUPS = [
  { key: 'A', prompt: `GROUP A — Runtime, libraries, compute, persistence. Report each item as a row (put the command in 'url', the output in 'evidence', status REACHABLE_DATA if it works, ERROR if not):
1. python3 --version ; pip --version ; which python3
2. For each library run: python3 -c "import X; print(getattr(X,'__version__','?'))" — libraries: pandas, numpy, scipy, statsmodels, sklearn, requests, bs4, lxml, matplotlib, pyarrow, duckdb, yfinance, pandas_datareader, pytrends, openpyxl, polars, httpx, aiohttp, numba, xgboost, lightgbm, geopandas, rasterio, xarray, netCDF4, h5py, shapely, sqlalchemy, playwright. One row per library.
3. PyPI reachability: pip install --target ${SCRATCH}/piptest --no-cache-dir yfinance ; then PYTHONPATH=${SCRATCH}/piptest python3 -c "import yfinance; print(yfinance.__version__)". Report whether installs work.
4. Compute: nproc ; free -g ; df -h ${SCRATCH} ; python3 -c "import os; print(os.cpu_count())" ; ulimit -a (summarize).
5. Other runtimes/tools: node --version ; R --version ; java -version ; sqlite3 --version ; jq --version ; curl --version | head -1 ; wget --version | head -1 ; git --version ; duckdb CLI if present.
6. Persistence: touch ${SCRATCH}/persist_test.txt and touch /home/user/24-yo/.persist_test && rm /home/user/24-yo/.persist_test ; report both writable or not. Note (REASONED from harness docs, do not test) that the container is ephemeral so only git pushes or user downloads survive.
7. Plain HTTP (not HTTPS): curl -sS -m 20 -o /dev/null -w '%{http_code}' http://example.com and http://web.archive.org/cdx/search/cdx?url=example.com&limit=1
8. Direct egress bypassing the proxy: curl -sS -m 10 --noproxy '*' -o /dev/null -w '%{http_code}' https://example.com — report whether direct egress is blocked (expected) versus via the proxy.
9. Proxy status: curl -sS "$HTTPS_PROXY/__agentproxy/status" and summarize what it says about allowed hosts or policy (quote the key lines).
10. Headless browser: python3 -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); pg=b.new_page(); pg.goto('https://example.com', timeout=30000); print(pg.title()); b.close(); p.stop()" — report whether a headless browser can load a page through the proxy (do NOT run 'playwright install').` },

  { key: 'B', prompt: `GROUP B — Market data: prices, earnings dates, options, fundamentals, factors. Test every source below with a real request:
1. Yahoo Finance chart API: https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=5d&interval=1d (send a browser User-Agent). Evidence: number of timestamps returned.
2. Yahoo quoteSummary calendarEvents (earnings dates): https://query2.finance.yahoo.com/v10/finance/quoteSummary/AAPL?modules=calendarEvents — note if it demands a crumb/cookie.
3. yfinance library end-to-end (install to ${SCRATCH}/piptest with pip install --target if not importable): download 5 days of AAPL and call Ticker('AAPL').earnings_dates and .options; report whether each returns data.
4. Stooq daily CSV: https://stooq.com/q/d/l/?s=aapl.us&i=d
5. Nasdaq earnings calendar: https://api.nasdaq.com/api/calendar/earnings?date=2026-11-12 with headers User-Agent (browser), Accept: application/json, Accept-Language: en-US.
6. FRED CSV without key: https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10 ; and FRED API with key (expect 400 without key): https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json
7. Kenneth French factors: HEAD https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip
8. CBOE delayed option quotes: https://cdn.cboe.com/api/global/delayed_quotes/options/AAPL.json — evidence: number of option rows.
9. SEC XBRL companyfacts: https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json (SEC User-Agent) — evidence: count of EPS entries under us-gaap EarningsPerShareDiluted.
10. SEC XBRL frames (cross-section): https://data.sec.gov/api/xbrl/frames/us-gaap/Revenues/USD/CY2024Q4.json
11. SEC financial statement data sets: HEAD https://www.sec.gov/files/dera/data/financial-statement-data-sets/2025q3.zip
12. Alpha Vantage demo: https://www.alphavantage.co/query?function=EARNINGS&symbol=IBM&apikey=demo — and note the free-key limits from the response or docs.
13. Nasdaq Data Link: https://data.nasdaq.com/api/v3/datasets/WIKI/AAPL.json?rows=1 (expect key error; classify)
14. Tiingo: https://api.tiingo.com/tiingo/daily/aapl/prices?startDate=2025-01-01 (expect 401 without token; classify) and Polygon: https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2025-01-01/2025-01-10 (expect 401/403)
15. FINRA short interest API: https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest?limit=1 (classify)
16. Financial Modeling Prep: https://financialmodelingprep.com/api/v3/earning_calendar?apikey=demo (classify)
17. Earnings dates from EDGAR 8-K Item 2.02 via full-text search: https://efts.sec.gov/LatestSearch/search-index?q=%22results%20of%20operations%22&forms=8-K&dateRange=custom&startdt=2025-10-01&enddt=2025-10-31 — evidence: total hits.
18. EDGAR daily index for point-in-time filing timestamps: https://www.sec.gov/Archives/edgar/daily-index/2025/QTR4/ (SEC UA) — evidence: list of files.
19. Options history free sources: HEAD https://www.cboe.com/us/options/market_statistics/historical_data/ and https://optiondata.org (classify what is free).
20. Wikipedia S&P/Russell constituents as a universe seed: https://en.wikipedia.org/wiki/List_of_S%26P_400_companies — evidence: table row count via pandas.read_html if lxml is available.
21. Russell 2000 / 3000 constituent files from iShares: https://www.ishares.com/us/products/239710/ishares-russell-2000-etf/1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund — evidence: row count.` },

  { key: 'C1', prompt: `GROUP C1 — SEC and federal regulatory exhaust. Test every source with a real request (SEC User-Agent where needed):
1. EDGAR submissions API: https://data.sec.gov/submissions/CIK0000320193.json — evidence: count of recent filings.
2. EDGAR full-text search: https://efts.sec.gov/LatestSearch/search-index?q=%22largest%20customer%22&forms=10-K&dateRange=custom&startdt=2025-01-01&enddt=2025-03-31 — evidence: total hits.
3. Form 4 insider transactions bulk data set: HEAD https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/2025q2_form345.zip and list page https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets
4. EDGAR latest Form 4 feed: https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&count=10&output=atom
5. USAspending API: POST https://api.usaspending.gov/api/v2/search/spending_by_award/ with body {"filters":{"time_period":[{"start_date":"2025-10-01","end_date":"2025-10-31"}],"award_type_codes":["A","B","C","D"]},"fields":["Award ID","Recipient Name","Award Amount"],"limit":3,"page":1} — evidence: 3 recipient names.
6. openFDA device recalls: https://api.fda.gov/device/recall.json?limit=1 and openFDA drug enforcement: https://api.fda.gov/drug/enforcement.json?limit=1
7. FDA inspection classification database / Form 483 data: https://datadashboard.fda.gov/ora/api/inspectionscitations.json?limit=1 (if that path fails, find the current FDA Data Dashboard API endpoint and test it) ; also HEAD https://www.fda.gov/media/107718/download (inspection citations spreadsheet) or the current equivalent.
8. FCC equipment authorization public search: https://apps.fcc.gov/oetcf/eas/reports/GenericSearch.cfm (GET the form page; report whether it loads) and https://fccid.io/ (third party; classify TOS).
9. USPTO PatentsView: https://search.patentsview.org/api/v1/patent/?q={"patent_date":"2025-01-07"}&f=["patent_id"] (expect key requirement; classify) ; USPTO Open Data Portal: https://data.uspto.gov/ (loads?) ; trademark TSDR: https://tsdrapi.uspto.gov/ts/cd/casestatus/sn78787878/info.json (classify)
10. Federal Register API: https://www.federalregister.gov/api/v1/documents.json?per_page=1&conditions[term]=recall
11. Regulations.gov API: https://api.regulations.gov/v4/documents?api_key=DEMO_KEY&page[size]=1
12. Senate lobbying (LDA) API: https://lda.senate.gov/api/v1/filings/?filing_year=2025&page_size=1 — evidence: count field.
13. CourtListener search API (RECAP/PACER mirror): https://www.courtlistener.com/api/rest/v4/search/?q=%22unpaid%20invoices%22&type=r&order_by=dateFiled%20desc (anonymous allowed?) — evidence: count.
14. PACER itself: HEAD https://pcl.uscourts.gov/pcl/index.jsf (classify: paid).
15. NHTSA complaints API: https://api.nhtsa.gov/complaints/complaintsByVehicle?make=tesla&model=model%203&modelYear=2023 — evidence: count ; NHTSA recalls: https://api.nhtsa.gov/recalls/recallsByVehicle?make=tesla&model=model%203&modelYear=2023
16. CPSC recalls API: https://www.saferproducts.gov/RestWebServices/Recall?format=json&RecallDateStart=2025-10-01&RecallDateEnd=2025-10-31 — evidence: count.
17. CFPB consumer complaints API: https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/?size=1&company=Affirm — evidence: hits total.
18. EPA ECHO facility API: https://echodata.epa.gov/echo/echo_rest_services.get_facilities?output=JSON&p_st=TX&p_act=Y&responseset=1 ; EPA GHGRP Envirofacts: https://data.epa.gov/efservice/pub_dim_facility/year/2023/state_name/TEXAS/rows/0:2/JSON
19. OSHA enforcement data: https://enforcedata.dol.gov/views/data_summary.php (loads?) and OSHA severe injury report CSV HEAD https://www.osha.gov/severe-injury-reports (page) ; also the DOL enforcement API if documented.
20. FERC eLibrary: https://elibrary.ferc.gov/eLibrary/search (loads?) and FERC Form 1 data: https://www.ferc.gov/general-information-0/electric-industry-forms/form-1-electric-utility-annual-report (page).
21. EIA API v2 (needs free key): https://api.eia.gov/v2/petroleum/sum/sndw/data/?frequency=weekly&data[0]=value&length=1 (expect key error; classify) ; EIA open CSV without key: https://ir.eia.gov/wpsr/table1.csv
22. UK Companies House API: https://api.company-information.service.gov.uk/company/00000006 (expect 401; classify as free key signup) ; UK CH bulk accounts: https://download.companieshouse.gov.uk/en_accountsdata.html (page loads?)
23. OpenCorporates API: https://api.opencorporates.com/v0.4/companies/search?q=apple&per_page=1 (classify).` },

  { key: 'C2', prompt: `GROUP C2 — State, local, legal, logistics, and corporate-aviation exhaust. Test every source with a real request:
1. WARN notices by state — test these exact pages/files and report format: California EDD https://edd.ca.gov/en/jobs_and_training/Layoff_Services_WARN/ (find and HEAD the current WARN xlsx link on the page) ; New York https://dol.ny.gov/warn-notices ; Texas TWC https://www.twc.texas.gov/data-reports/warn-notices (or the current URL) ; Illinois https://labor.illinois.gov/employers/warn.html ; Washington https://esd.wa.gov/about-employees/WARN ; Florida http://floridajobs.org/office-directory/division-of-workforce-services/workforce-programs/reemployment-and-emergency-assistance-coordination-team-react/warn-notices ; and the aggregator https://www.warntracker.com/ (classify: commercial?) and https://layoffdata.com/ (classify).
2. US DOL list of state WARN contacts/pages: https://www.dol.gov/agencies/eta/layoffs/warn
3. UCC filings — test whether any state offers free structured UCC search without login: California https://bizfileonline.sos.ca.gov/search/ucc ; Texas https://direct.sos.state.tx.us/acct/acct-login.asp (classify: paid) ; Delaware https://icis.corp.delaware.gov/ecorp/entitysearch/namesearch.aspx (classify) ; Florida https://www.floridaucc.com/ ; New York https://appext20.dos.ny.gov/pls/ucc_public/web_search.main_frame . Report status and whether any is machine-readable.
4. Local planning / council minutes via Legistar API: https://webapi.legistar.com/v1/seattle/matters?$top=2 and https://webapi.legistar.com/v1/phoenix/events?$top=2 — evidence: items returned. Also test Granicus/CivicPlus agenda page for a data-center county, e.g. https://www.loudoun.gov/AgendaCenter (loads?).
5. Utility interconnection queues: PJM queue page https://www.pjm.com/planning/service-requests/services-request-status (loads?) and PJM data miner API https://api.pjm.com/api/v1/ (classify; free key?) ; ERCOT GIS report https://www.ercot.com/gridinfo/resource (page) ; MISO queue https://www.misoenergy.org/planning/generator-interconnection/GI_Queue/ (page) ; CAISO queue https://www.caiso.com/planning/generator-interconnection (page) ; LBNL Queued Up dataset https://emp.lbl.gov/queues (page).
6. Corporate jet tracking: OpenSky Network anonymous API https://opensky-network.org/api/states/all?lamin=40&lomin=-75&lamax=41&lomax=-73 (evidence: number of states) ; OpenSky flights-by-aircraft requires auth: https://opensky-network.org/api/flights/aircraft?icao24=a835af&begin=1735689600&end=1735776000 (classify) ; FAA aircraft registry database download https://registry.faa.gov/database/ReleasableAircraft.zip (HEAD) ; ADS-B Exchange https://www.adsbexchange.com/data/ (classify: paid) ; adsb.lol or airplanes.live public APIs e.g. https://api.airplanes.live/v2/point/40.7/-74/50 (classify).
7. Customs import records (bills of lading): ImportYeti public page https://www.importyeti.com/company/apple (loads? note TOS) ; Panjiva/S&P https://panjiva.com (classify paid) ; CBP AMS data https://www.cbp.gov/trade/automated/ams (classify) ; USITC DataWeb https://dataweb.usitc.gov/ (classify) ; Census trade API https://api.census.gov/data/timeseries/intltrade/imports/hs?get=CTY_CODE,GEN_VAL_MO&time=2025-06&I_COMMODITY=8471 (evidence: rows).
8. Court dockets beyond CourtListener: state court portals, e.g. Delaware Chancery via https://courts.delaware.gov/ (page) and New York https://iapps.courts.state.ny.us/webcivil/ecourtsMain (page) ; UniCourt https://unicourt.com/ (classify) ; Trellis (classify).
9. Mechanic's liens / county recorders: test one, e.g. Harris County Clerk https://www.cclerk.hctx.net/applications/websearch/RP.aspx (classify).
10. State business registries for shell-name permit matching: OpenCorporates covered elsewhere; test Delaware entity search page (above) and Texas comptroller franchise tax search https://mycpa.cpa.state.tx.us/coa/ (page loads?).
11. Government contracts beyond USAspending: SAM.gov opportunities API https://api.sam.gov/opportunities/v2/search?limit=1&postedFrom=10/01/2025&postedTo=10/31/2025 (expect key; classify) ; FPDS ATOM feed https://www.fpds.gov/ezsearch/FEEDS/ATOM?FEEDNAME=PUBLIC&q=apple (evidence: entries).
12. Lobbying at the state level: California Cal-Access https://cal-access.sos.ca.gov/Lobbying/ (page) ; and House lobbying disclosures https://disclosurespreview.house.gov/ (page).
13. Trade shows and events: CES exhibitor directory https://exhibitors.ces.tech/ (loads? classify TOS) ; NRF Big Show exhibitor list https://nrfbigshow.nrf.com/exhibitor-list (loads?).
14. Rail carloads: AAR rail traffic page https://www.aar.org/data-center/rail-traffic-data/ (what is free? PDF?) ; STB weekly https://www.stb.gov/reports-data/rail-service-data/ (page, formats) ; Union Pacific weekly carloads https://www.up.com/investor/aar-stb_reports/ (page/CSV?) ; BNSF https://www.bnsf.com/about-bnsf/financial-information/index.html#Weekly+Carload+Reports (page).
15. State DOT traffic counters: Georgia DOT TCDS https://gdottrafficdata.drakewell.com/publicmultinodemap.asp (loads? API?) ; MnDOT https://www.dot.state.mn.us/traffic/data/ (page) ; FHWA TMAS/TVT https://www.fhwa.dot.gov/policyinformation/tables/tmasdata/ (page, formats) ; Caltrans PeMS https://pems.dot.ca.gov/ (classify: login) ; Texas TxDOT traffic count ArcGIS https://gis-txdot.opendata.arcgis.com/ (loads?).` },

  { key: 'D', prompt: `GROUP D — Physical-world exhaust: satellites, emissions, rivers, seismic, utilities, wastewater, ships. Test every source with a real request:
1. NASA Earthdata login requirement: https://urs.earthdata.nasa.gov/ (page) ; NASA Black Marble VIIRS nighttime lights listing https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5000/VNP46A2/2025/001/ (classify: free login?) ; NASA FIRMS API https://firms.modaps.eosdis.nasa.gov/api/area/csv/DEMO_KEY/VIIRS_SNPP_NRT/world/1 (classify) ; NASA GIBS WMTS tile (no login) https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/VIIRS_SNPP_DayNightBand_At_Sensor_Radiance/default/2025-01-01/250m/3/2/3.png (evidence: content-type).
2. EOG (Colorado School of Mines) VIIRS nightly lights and Nightfire flaring: https://eogdata.mines.edu/products/vnl/ (page) and https://eogdata.mines.edu/nighttime_light/nightly/rade9d/ (classify: registration?) ; Nightfire https://eogdata.mines.edu/products/vnf/ (page).
3. Sentinel-5P (methane, NO2) via Copernicus Data Space: https://catalogue.dataspace.copernicus.eu/odata/v1/Products?$filter=Collection/Name%20eq%20%27SENTINEL-5P%27&$top=1 (catalogue search without login?) ; download requires token: https://dataspace.copernicus.eu/ (classify free account) ; Sentinel Hub statistical API (classify) ; Google Earth Engine https://earthengine.google.com/ (classify: needs Google account/project).
4. USGS water (Mississippi at St. Louis): https://waterservices.usgs.gov/nwis/iv/?sites=07010000&parameterCd=00065&format=json&period=P1D — evidence: number of values ; USGS daily values history: https://waterservices.usgs.gov/nwis/dv/?sites=07010000&parameterCd=00065&startDT=2015-01-01&endDT=2015-01-10&format=json
5. NOAA NWPS river stages: https://api.water.noaa.gov/nwps/v1/gauges/EADM7/stageflow (or current NWPS API path) ; Rhine at Kaub via Pegelonline: https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations/KAUB/W/measurements.json?start=P1D — evidence: number of values.
6. Seismic: USGS earthquake catalog with quarry-blast event type https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&eventtype=quarry%20blast,explosion,mining%20explosion&starttime=2025-01-01&endtime=2025-01-31&limit=5 — evidence: count ; IRIS FDSN station service https://service.iris.edu/fdsnws/station/1/query?net=US&format=text&level=network ; IRIS dataselect sample https://service.iris.edu/fdsnws/dataselect/1/query?net=IU&sta=ANMO&loc=00&cha=BHZ&start=2025-01-01T00:00:00&end=2025-01-01T00:01:00 (evidence: bytes).
7. EIA without key: https://ir.eia.gov/wpsr/table1.csv and https://ir.eia.gov/ngs/ngs.html ; EIA Hourly Electric Grid Monitor bulk: HEAD https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/EIA930_BALANCE_2025_Jan_Jun.csv
8. ISO load/price data without login: PJM https://dataminer2.pjm.com/ (classify key) ; ERCOT public reports https://www.ercot.com/mp/data-products/data-product-details?id=NP6-346-CD (page) ; NYISO CSV http://mis.nyiso.com/public/csv/pal/20250101pal_csv.zip (HEAD) ; CAISO OASIS http://oasis.caiso.com/oasisapi/SingleZip?queryname=SLD_FCST&market_run_id=DAM&startdatetime=20250101T08:00-0000&enddatetime=20250102T08:00-0000&version=1 (classify).
9. CDC NWSS wastewater (Socrata): https://data.cdc.gov/resource/2ew6-ywp6.json?$limit=1 — evidence: a field name ; WastewaterSCAN https://data.wastewaterscan.org/ (page/classify).
10. AIS ship tracking: NOAA MarineCadastre historical AIS https://marinecadastre.gov/ais/ (page; HEAD one monthly zip e.g. https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2024/AIS_2024_01_01.zip and report size) ; AISHub https://www.aishub.net/api (classify: requires feeding data) ; MarineTraffic https://www.marinetraffic.com/ (classify paid/TOS) ; VesselFinder (classify) ; Global Fishing Watch API https://gateway.api.globalfishingwatch.org/v3/vessels/search?query=maersk (classify: free token?) ; Danish Maritime Authority free AIS http://web.ais.dk/aisdata/ (listing loads?) ; Port of Long Beach TEU stats https://polb.com/business/port-statistics/ (page) ; Port of LA https://www.portoflosangeles.org/business/statistics/container-statistics (page).
11. Municipal water/power for industrial users: test a city open-data portal for large-user water billing, e.g. https://data.cityofnewyork.us/resource/66be-66yr.json?$limit=1 (NYC water consumption) and Austin Energy https://data.austintexas.gov/resource/ (classify) ; Texas Water Development Board https://www.twdb.texas.gov/waterplanning/waterusesurvey/ (page).
12. Soil moisture / crops: USDA NASS QuickStats API https://quickstats.nass.usda.gov/api/api_GET/?key=DEMO&commodity_desc=CORN&year=2025&format=JSON (classify free key) ; NASA SMAP (Earthdata login; classify) ; USDA Crop Progress reports page https://usda.library.cornell.edu/concern/publications/8336h188j (loads?).
13. Weather: https://api.weather.gov/points/38.63,-90.2 (evidence: forecast URL) ; NOAA NCEI https://www.ncei.noaa.gov/cdo-web/api/v2/datasets (classify token).
14. Thermal/industrial activity: Landsat via USGS M2M API https://m2m.cr.usgs.gov/api/api/json/stable/login (classify) ; Sentinel-2 via Copernicus (same as 3) ; Microsoft Planetary Computer STAC (no login for search) https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a (evidence: title) and item search POST https://planetarycomputer.microsoft.com/api/stac/v1/search with {"collections":["sentinel-2-l2a"],"bbox":[-95.4,29.7,-95.3,29.8],"datetime":"2025-01-01/2025-01-15","limit":1} ; AWS open data Sentinel-2 COGs https://sentinel-cogs.s3.us-west-2.amazonaws.com/?list-type=2&prefix=sentinel-s2-l2a-cogs/10/T/ES/2025/1/&max-keys=2 (evidence: keys) ; Element84 Earth Search STAC https://earth-search.aws.element84.com/v1/collections (evidence: count).
15. Methane plumes public: Carbon Mapper data portal API https://api.carbonmapper.org/api/v1/catalog/plumes/annotated?limit=1 (classify) ; EPA GHGRP already covered elsewhere.
16. Air quality (NO2/PM) ground sensors: EPA AirNow API https://www.airnowapi.org/aq/observation/zipCode/current/?format=application/json&zipCode=77002&API_KEY=DEMO (classify) ; OpenAQ v3 https://api.openaq.org/v3/locations?limit=1 (classify key) ; PurpleAir (classify key).
17. Trucking/logistics: FMCSA SAFER company snapshot https://safer.fmcsa.dot.gov/CompanySnapshot.aspx (page) and FMCSA QCMobile API https://mobile.fmcsa.dot.gov/qc/services/carriers/docket-number/139506?webKey=DEMO (classify free key) ; Cass Freight Index page https://www.cassinfo.com/freight-audit-payment/cass-transportation-indexes (page) ; DAT trendlines (classify).` },

  { key: 'E', prompt: `GROUP E — Digital exhaust: code, web archives, search trends, apps, jobs, reviews, status pages, domains, retail sites. Test every source with a real request and be explicit about terms-of-service flags:
1. GitHub REST (anonymous): https://api.github.com/repos/hashicorp/terraform (evidence: stargazers_count and the X-RateLimit-Limit header) ; GitHub search issues https://api.github.com/search/issues?q=repo:hashicorp/terraform+is:issue+created:>2025-10-01&per_page=1 (evidence: total_count) ; GH Archive bulk HEAD https://data.gharchive.org/2025-01-01-0.json.gz (evidence: size).
2. Wayback Machine CDX: https://web.archive.org/cdx/search/cdx?url=allbirds.com/collections/mens&from=2024&to=2025&limit=5&output=json (evidence: rows) ; Wayback availability https://archive.org/wayback/available?url=allbirds.com&timestamp=20240601 ; fetch one archived snapshot body size.
3. Google Trends: pip install --target ${SCRATCH}/piptest pytrends (if needed) then build_payload(['allbirds'], timeframe='today 3-m') and interest_over_time() — report whether it returns rows or a 429/blocked ; also test direct https://trends.google.com/trends/api/explore (classify).
4. Apple App Store: iTunes lookup https://itunes.apple.com/lookup?id=284882215 (evidence: userRatingCount) ; top charts RSS https://rss.marketingtools.apple.com/api/v2/us/apps/top-free/10/apps.json (evidence: count) ; App Store reviews RSS https://itunes.apple.com/us/rss/customerreviews/id=284882215/sortBy=mostRecent/json (evidence: entries). Google Play: https://play.google.com/store/apps/details?id=com.duolingo&hl=en&gl=us (loads? classify TOS for scraping) ; google-play-scraper library (classify TOS).
5. Job postings via sanctioned ATS JSON endpoints: Greenhouse https://boards-api.greenhouse.io/v1/boards/duolingo/jobs?content=false (evidence: job count) ; Lever https://api.lever.co/v0/postings/plaid?mode=json (evidence: count) ; Ashby https://api.ashbyhq.com/posting-api/job-board/ramp (evidence: count) ; Workday example https://wd1.myworkdaysite.com/wday/cxs/wayfair/External/jobs (POST {"limit":1,"offset":0}) (evidence: total) ; SmartRecruiters https://api.smartrecruiters.com/v1/companies/Visa/postings?limit=1 ; iCIMS (classify). Also classify LinkedIn Jobs and Indeed as TOS-restricted without testing a scrape (a HEAD of https://www.indeed.com/jobs?q=warehouse is fine to show reachability).
6. Employee reviews: HEAD https://www.glassdoor.com/Reviews/index.htm and note the TOS/robots status (do not scrape) ; Indeed company reviews (same) ; Blind (classify).
7. Product reviews and complaints: Trustpilot public page https://www.trustpilot.com/review/allbirds.com (loads? note robots/TOS) ; BBB https://www.bbb.org/ (classify) ; Amazon product page HEAD https://www.amazon.com/dp/B08N5WRWNW (classify: TOS prohibits scraping) ; Reddit JSON https://www.reddit.com/r/wallstreetbets/new.json?limit=1 with a descriptive User-Agent (classify) ; Yelp Fusion API (classify key).
8. Status pages (Statuspage.io public API): https://www.githubstatus.com/api/v2/incidents.json (evidence: incident count) ; https://status.cloudflare.com/api/v2/summary.json ; https://status.twilio.com/api/v2/incidents.json ; and an index of statuspage sites e.g. https://www.statuspage.io/ (page).
9. Domains and certificates: crt.sh https://crt.sh/?q=%25.allbirds.com&output=json (evidence: count) ; RDAP https://rdap.org/domain/allbirds.com (evidence: registration date) ; ICANN CZDS https://czds.icann.org/ (classify: free account) ; Certificate Transparency via Google https://ct.googleapis.com/logs/us1/argon2025h1/ct/v1/get-sth (classify).
10. Trademarks: USPTO TSDR is in another group; test EUIPO https://euipo.europa.eu/eSearch/ (page) and the USPTO trademark bulk data https://data.uspto.gov/ (page).
11. Web traffic proxies: Tranco list HEAD https://tranco-list.eu/top-1m.csv.zip (size) ; Cloudflare Radar API https://api.cloudflare.com/client/v4/radar/ranking/top?limit=5 (classify free token) ; Wikipedia pageviews https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/Allbirds/daily/20250101/20250131 (evidence: number of days) ; Similarweb public page https://www.similarweb.com/website/allbirds.com/ (classify) ; Common Crawl index https://index.commoncrawl.org/collinfo.json (evidence: latest crawl id).
12. Retailer own-site exhaust: Shopify public products.json (many small caps run Shopify) https://www.allbirds.com/products.json?limit=2 (evidence: product titles and whether 'available' per variant is present; note Shopify TOS/robots) ; https://www.figs.com/products.json?limit=1 ; Target redsky https://redsky.target.com/ (classify) ; Walmart product page HEAD (classify TOS) ; Best Buy API https://api.bestbuy.com/v1/products?apiKey=DEMO (classify free key).
13. B2B / industrial distributor catalogs: HEAD https://www.grainger.com/product/3LPG4 and https://www.fastenal.com/ (classify bot-block/TOS) ; McMaster-Carr (classify).
14. Earnings-call transcripts (free sources): Motley Fool transcript page e.g. https://www.fool.com/earnings-call-transcripts/ (loads? TOS) ; SEC 8-K exhibit transcripts via full-text search https://efts.sec.gov/LatestSearch/search-index?q=%22conference%20call%22%20%22transcript%22&forms=8-K&dateRange=custom&startdt=2025-10-01&enddt=2025-10-31 (evidence: hits) ; API Ninjas earnings transcript https://api.api-ninjas.com/v1/earningstranscript?ticker=MSFT&year=2024&quarter=2 (classify free key) ; Seeking Alpha (classify paid/TOS) ; company IR webcast pages (classify).
15. Status/outage aggregator: Downdetector (classify TOS) ; and HEAD https://isdown.app/ (classify).
16. Open-source package downloads as developer-tool demand: PyPI stats https://pypistats.org/api/packages/snowflake-connector-python/recent (evidence: counts) ; npm downloads https://api.npmjs.org/downloads/point/last-week/@datadog/browser-rum (evidence: downloads) ; Docker Hub https://hub.docker.com/v2/repositories/elastic/elasticsearch/ (evidence: pull_count) ; Homebrew analytics https://formulae.brew.sh/api/analytics/install/30d.json (evidence: size).
17. Hacker News / Algolia API as tech-sentiment proxy: https://hn.algolia.com/api/v1/search?query=datadog&tags=story&numericFilters=created_at_i>1735689600 (evidence: nbHits).` },
]

const PROBE_SCHEMA = {
  type: 'object',
  properties: {
    group: { type: 'string' },
    results: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          source: { type: 'string' },
          url: { type: 'string' },
          method: { type: 'string' },
          status: { type: 'string', enum: ['REACHABLE_DATA', 'REACHABLE_NEEDS_KEY', 'REACHABLE_BOT_BLOCKED', 'BLOCKED_BY_PROXY', 'TIMEOUT', 'ERROR', 'NOT_TESTED'] },
          http_code: { type: 'string' },
          evidence: { type: 'string' },
          needs: { type: 'string' },
          tos_flag: { type: 'string' },
          history: { type: 'string' },
          format: { type: 'string' },
        },
        required: ['source', 'url', 'status', 'evidence'],
      },
    },
    environment_notes: { type: 'string' },
  },
  required: ['group', 'results'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          source: { type: 'string' },
          verdict: { type: 'string', enum: ['CONFIRMED', 'NOT_CONFIRMED', 'DOWNGRADED'] },
          new_status: { type: 'string' },
          evidence: { type: 'string' },
        },
        required: ['source', 'verdict', 'evidence'],
      },
    },
  },
  required: ['verdicts'],
}

const VERIFY_PREAMBLE = `You are a skeptical verifier. Another agent probed free public data sources from this cloud container and claims the sources below are reachable. Your job is to independently RE-RUN each fetch yourself right now and confirm or refute each claim. Default to NOT_CONFIRMED when uncertain or when you cannot reproduce it. Rules: use the same URL and method the prober recorded (you may fix an obviously malformed URL, but record what you actually ran); apply the same network rules (HTTPS through the preset proxy, never disable TLS verification, never unset HTTPS_PROXY, curl -sS -m 20, tiny fetches, SEC User-Agent 'altdata-research-probe/0.1 (research; no-reply@example.org)', browser-like User-Agent for consumer sites, one retry max). CONFIRMED means you got a 2xx with the same kind of real data (for REACHABLE_DATA) or the same key/login requirement (for REACHABLE_NEEDS_KEY). DOWNGRADED means the host responded but the status should be different (say which: REACHABLE_NEEDS_KEY, REACHABLE_BOT_BLOCKED, BLOCKED_BY_PROXY, TIMEOUT, ERROR) and give the evidence. Also check that the prober's evidence is plausible for the data (for example an HTML login page is not data). Save any sample under ${SCRATCH}/verify_<GROUP>/ . Return one verdict per claimed source, matching the 'source' string exactly.

CLAIMS TO VERIFY (JSON):
`

phase('Probe')
log('Probing six source groups in parallel; each reachable claim is then re-fetched by a skeptic')

const verified = await pipeline(
  GROUPS,
  g => agent(PREAMBLE + g.prompt, { label: `probe:${g.key}`, phase: 'Probe', schema: PROBE_SCHEMA }),
  (probe, g) => {
    if (!probe) return null
    const claims = (probe.results || []).filter(r => r.status === 'REACHABLE_DATA' || r.status === 'REACHABLE_NEEDS_KEY')
    if (!claims.length) return { probe, verify: { verdicts: [] } }
    return agent(VERIFY_PREAMBLE.replace('<GROUP>', g.key) + JSON.stringify(claims), { label: `verify:${g.key}`, phase: 'Verify', schema: VERIFY_SCHEMA })
      .then(v => ({ probe, verify: v || { verdicts: [] } }))
  },
)

const dropped = GROUPS.filter((g, i) => !verified[i]).map(g => g.key)
if (dropped.length) log(`Groups with no probe result (agent died or skipped): ${dropped.join(', ')}`)

function merge(entry) {
  const byName = {}
  for (const v of (entry.verify.verdicts || [])) byName[v.source] = v
  return entry.probe.results.map(r => {
    const v = byName[r.source]
    let final = r.status
    if (v) {
      if (v.verdict === 'NOT_CONFIRMED') final = 'UNCONFIRMED'
      else if (v.verdict === 'DOWNGRADED' && v.new_status) final = v.new_status
    }
    return { group: entry.probe.group, ...r, final_status: final, verifier: v ? v.verdict : 'n/a', verifier_evidence: v ? v.evidence : '' }
  })
}

const merged = verified.filter(Boolean).flatMap(merge)
const envNotes = verified.filter(Boolean).map(e => `[${e.probe.group}] ${e.probe.environment_notes || ''}`)
log(`Merged ${merged.length} source rows across ${verified.filter(Boolean).length} groups`)

phase('Coverage')

const SEED = [
  'Satellite parking-lot car counts', 'Night-time light intensity (NASA VIIRS) and thermal imagery of plants, smelters, refineries', 'Flaring and emissions from Sentinel-5P (methane, NO2)', 'AIS ship tracking: vessel queues at single-company ports, LNG terminals, mining export docks', 'Public seismometer networks picking up quarry and mine blasting frequency', 'Truck counts from state DOT traffic counters near large distribution centers; weekly rail carloads by commodity', 'Municipal water and power usage for large industrial users, and permit renewals', 'River levels (Rhine, Mississippi) and soil moisture', 'Wastewater epidemiology as a demand lead for pharma and consumer-health',
  'Local planning-committee minutes and permit applications for data centers, plants, warehouses', 'Utility interconnection and power-capacity requests', 'WARN Act mass-layoff notices', 'UCC filings showing inventory or receivables pledged as collateral', 'Court dockets: supplier suits over unpaid invoices, mechanics liens, PACER', 'FDA inspection reports and Form 483s, FCC equipment filings, patent and trademark applications', 'Lobbying disclosure spikes and small government contract awards on USAspending.gov', 'Foreign subsidiary accounts (UK Companies House, EU registries)', 'Clustered insider buying (Form 4) and corporate jet flight tracking',
  'Job postings: counts by region, hiring freezes, wording shifts', 'Employee review sentiment trends', 'App downloads, store rankings, web-traffic trends', 'Customs import records (bills of lading)', 'Google Trends for single-product small caps', 'Product review velocity and defect-complaint spikes preceding recalls', 'Out-of-stock frequency and discount depth from the retailer own site', 'Price-change frequency in B2B and industrial-distributor catalogs', 'GitHub activity for developer-tool companies', 'Domain registrations and trademark filings before launches', 'Status-page outage frequency and support-forum complaint volume for SaaS', 'Wayback Machine diffs', 'LinkedIn departure clusters', 'Earnings-call language: hedging, evasiveness, tone shifts',
  'Small supplier earnings calls mentioning a cut from their largest customer', 'Customer-concentration maps from 10-K major-customer disclosures', 'Index addition/deletion mechanics; forced sellers', 'Trade-show footprint changes',
  'BASELINE: daily prices and volume for US small/mid caps with history', 'BASELINE: scheduled earnings dates (future and historical, point-in-time)', 'BASELINE: options quotes/implied move around earnings', 'BASELINE: consensus EPS/revenue estimates as of a past date (point-in-time)', 'BASELINE: universe construction (market cap, sector, listed options)',
]

const GAPS_SCHEMA = {
  type: 'object',
  properties: {
    coverage: { type: 'array', items: { type: 'object', properties: { seed_item: { type: 'string' }, probed_sources: { type: 'array', items: { type: 'string' } }, best_status: { type: 'string' }, note: { type: 'string' } }, required: ['seed_item', 'probed_sources', 'best_status'] } },
    gaps: { type: 'array', items: { type: 'object', properties: { seed_item: { type: 'string' }, suggested_source: { type: 'string' }, url: { type: 'string' }, how_to_test: { type: 'string' } }, required: ['seed_item', 'suggested_source', 'url', 'how_to_test'] } },
    inconsistencies: { type: 'array', items: { type: 'string' } },
  },
  required: ['coverage', 'gaps', 'inconsistencies'],
}

const critic = await agent(`You are a completeness critic for a data-source capability check. Below is (1) the Seed Catalogue of signal ideas this research program must be able to source, including five BASELINE needs, and (2) the merged, verified results of probing free public data sources from this container. For EVERY seed item, map which probed sources cover it and the best final_status among them. Then list GAPS: seed items that have no probed source with final_status REACHABLE_DATA or REACHABLE_NEEDS_KEY, or whose only coverage is weak, together with a concrete free public source (exact URL) that was NOT probed and a one-line test. Prefer sources that are structured, free, and legal; do not suggest scraping behind logins or against terms of service. Keep gaps to the ones that matter (max 12). Also list any inconsistencies you see in the results (e.g. the same host marked both BLOCKED_BY_PROXY and REACHABLE, or evidence that does not match the claimed status). Do not run anything yourself; this is a reading task.

SEED ITEMS (JSON): ${JSON.stringify(SEED)}

MERGED RESULTS (JSON): ${JSON.stringify(merged.map(r => ({ group: r.group, source: r.source, url: r.url, final_status: r.final_status, evidence: (r.evidence || '').slice(0, 200), needs: r.needs, tos_flag: r.tos_flag })))}`, { label: 'critic:coverage', phase: 'Coverage', schema: GAPS_SCHEMA })

let gapRows = []
if (critic && critic.gaps && critic.gaps.length) {
  log(`Critic found ${critic.gaps.length} coverage gaps; probing them`)
  const gapProbe = await agent(PREAMBLE + `GROUP G — Coverage gaps. Test each of these specific sources exactly as described (one row per item; set group to 'G'):\n` + JSON.stringify(critic.gaps, null, 2), { label: 'probe:gaps', phase: 'Coverage', schema: PROBE_SCHEMA })
  if (gapProbe) {
    const claims = (gapProbe.results || []).filter(r => r.status === 'REACHABLE_DATA' || r.status === 'REACHABLE_NEEDS_KEY')
    let gv = { verdicts: [] }
    if (claims.length) gv = (await agent(VERIFY_PREAMBLE.replace('<GROUP>', 'G') + JSON.stringify(claims), { label: 'verify:gaps', phase: 'Coverage', schema: VERIFY_SCHEMA })) || { verdicts: [] }
    gapRows = merge({ probe: gapProbe, verify: gv })
  }
} else {
  log('Critic found no coverage gaps')
}

return { rows: merged.concat(gapRows), envNotes, coverage: critic ? critic.coverage : [], gaps: critic ? critic.gaps : [], inconsistencies: critic ? critic.inconsistencies : [], droppedGroups: dropped }
