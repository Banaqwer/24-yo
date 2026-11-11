# Phase 0 — Setup

Date: 2026-11-11. Program: Alt-Data Edge Research Pipeline. Role: head of alternative-data research. This phase restates the inputs, resolves ambiguities with five questions, confirms which tools actually run in this environment, and creates the empty Signal Register. Nothing in the attached repository was read or changed, per instruction.

Claim labels used throughout: TESTED HERE, LITERATURE, REASONED, UNKNOWN.

## 1. Inputs restated

- Universe: US-listed equities, market cap $500M to $30B, with listed options and scheduled earnings dates; excluding financials, biotech and SPACs; liquid enough that bid-ask spreads stay small relative to the expected earnings move.
- Capital and constraints: personal account under $10k; long shares and defined-risk options only (long calls or puts, debit spreads); no margin, no short selling; every position held at least overnight so the $25k pattern-day-trader rule never applies; commissions, option spreads and slippage assumed to eat a large share of any edge.
- Holding horizon: 2 to 10 days, event-driven; enter in the days before earnings, guidance or another scheduled disclosure, exit within a few days after; no multi-month positions; signals that predict the earnings surprise or guidance change take priority over long capex cycles.
- Domain knowledge: no single industry; follow the data to whichever sector has the cleanest signal; favour sectors with rich public physical and regulatory data (retail, industrials, energy, shipping, consumer tech); industry context to be explained as we go.
- Tools: web search, Python code execution, file uploads; no paid data APIs yet.
- Data budget: $0 to start; up to $100 per month once a signal is graded PROMISING or better.
- Jurisdiction: US. Time available: 5 hours per week.

## 2. Ambiguities: five questions, each with the assumption I proceed on if unanswered

1. Universe edges. "Biotech" is taken as the GICS Biotechnology sub-industry plus pre-revenue pharma; medtech, commercial pharma and healthcare services stay in. "Financials" is the GICS Financials sector; real estate stays in unless you say otherwise. Liquidity is made numeric as average daily dollar volume of at least $10M and a front-expiry at-the-money option bid-ask of at most 10% of mid at entry. Are these edges right?
2. Target variable. Free point-in-time consensus is thin (TESTED HERE): only the final EPS estimate at report date exists historically, with no revenue consensus and no revision history. I propose the primary target be the earnings-announcement abnormal return (close T-1 to close T+1, and to T+2 for drift, versus the sector ETF), with EPS surprise versus final consensus as the secondary target, and daily snapshots started now so a real point-in-time consensus history accrues forward. Acceptable?
3. Free registrations and the licence line. About a dozen of the most useful sources cost $0 but need you to register and hand me a key: Tiingo, Alpha Vantage, FRED, EIA, Census, CourtListener, NASA Earthdata, Copernicus Data Space, PJM, USPTO, BLS, a Reddit script app. Will you create them (I will rank the list by value in Phase 3) and add the keys as environment secrets? Separately, three sources are free only for non-commercial use (OpenSky history, Cloudflare Radar, Google Earth Engine). My default is to treat trading research as commercial and leave them out. Agree?
4. Persistence and scheduling. This container is wiped between sessions; nothing survives except what is pushed to GitHub or downloaded by you. Several of the best signals only have point-in-time history if snapshotted daily from now (earnings calendar, consensus, job-post counts, Shopify stock and discounts, ETF holdings). Options: (a) let me commit code and data to the attached GitHub repository and run daily scheduled cloud sessions; (b) you run a small fetch script on your own machine; (c) another store you name. Which?
5. Costs and budget. I assume $0 stock commissions, $0.65 per option contract, option spreads of 5% to 10% of mid on small caps, 10 basis points of slippage on shares, the $100 per month as a total across all signals, and the full account available to the program. Correct any of these, and tell me your broker's option approval level if it is below long options plus debit spreads.

## 3. Tool check (TESTED HERE unless labelled)

What runs here:

- Web search and web fetch both work; the SEC developer API page was fetched and read.
- Python 3.13.18 with pandas 3.0.5, numpy 2.5.3, requests, BeautifulSoup, lxml and openpyxl preinstalled. scipy, statsmodels, scikit-learn, matplotlib, pyarrow, duckdb, yfinance, pytrends, polars, httpx and the geospatial stack are absent but install from PyPI in under a minute into a session directory. They must be reinstalled every session.
- Compute: 4 vCPUs, 15 GB RAM, about 29 GB of free disk. A foreground command may run 10 minutes, a background one 2 hours (REASONED from the harness documentation).
- A headless Chromium via Playwright (Node and Python) loads pages through the proxy, for JavaScript-rendered public pages only, never login walls.
- File I/O: your uploads are readable (this prompt document was), and the scratchpad and working directory are writable.
- Network: HTTPS through the environment proxy. 319 source rows were probed, 217 of them re-fetched by an independent verifier. Totals: 169 return real data with no key, 56 need a key or login (most free), 38 are bot-blocked by the site, 8 are blocked by this container, 46 errors (27 of which are simply missing Python libraries), 1 timeout, 1 not tested.
- Scheduled recurring cloud sessions exist in this harness (REASONED: the tool is present; not exercised).

What does not run here:

- Nothing persists across sessions without a git push or a download by you.
- web.archive.org is denied by the environment's network policy, so Wayback diffs cannot be fetched from here. You can add web.archive.org under Allowed domains in the environment's Network access settings (steps at https://code.claude.com/docs/en/cloud-environments#network-access). status.cloudflare.com and search.patentsview.org fail at the proxy gateway. eogdata.mines.edu fails only because the container's trust store lacks the emSign root (fixable with a fuller CA bundle). fred.stlouisfed.org drops this IP for its CSV endpoint, though the FRED API with a free key answers.
- SEC full-text search (efts.sec.gov) returns 403 to this datacenter IP; every SEC structured API works, and the Financial Statement and Notes datasets give the footnote text offline. All fcc.gov hosts are Akamai-blocked; the fccid.io mirror works.
- Site-side bot blocks from this cloud IP: Texas WARN, MISO, LBNL, ImportYeti, CBP, Trustpilot, Glassdoor, Indeed, Grainger, Fastenal, McMaster-Carr, Target, Walmart, Amazon, Downdetector, Port of Long Beach, Union Pacific investor site, Stooq, New York eCourts, Cal-Access. Some would open from a home IP, but the review sites and distributors also prohibit automated access in their terms, so they are out regardless.
- Paid-only: shipment-level bills of lading (Panjiva, ImportGenius), live global AIS (MarineTraffic, VesselFinder), options history (except a community DoltHub database, licence to be checked), PACER per page, Similarweb, WARNTracker.
- No paid keys, no broker connection, no live trading, no material non-public information, no scraping behind logins or against terms of service.
- Inside this container GitHub's repository endpoint is gated to the session's repository; search endpoints work and GH Archive bulk files download. On your machine the API is open.

Highlights that return real data keyless right now (TESTED HERE; full table in phase0_capability_matrix.md):

- Prices and events: Yahoo chart API and yfinance (prices, earnings dates 2021 to 2027, option chains), Nasdaq earnings calendar (405 names for 2026-11-12) and analyst consensus endpoint, CBOE delayed option chains, FINRA short interest, Kenneth French factors, State Street daily ETF holdings, FTSE Russell reconstitution lists, Nasdaq Trader symbol directories.
- SEC: submissions, companyfacts, frames (including ConcentrationRiskPercentage1 cross-sections), daily index with acceptance timestamps, Form 4 bulk and live feed, 8-K live feed (Item 5.02 departures), Financial Statement and Notes datasets.
- Federal and state exhaust: USAspending, FPDS, lda.gov lobbying (2.0M filings), openFDA, FDA 483 spreadsheets, NHTSA, CPSC, CFPB, EPA ECHO and GHGRP, OSHA severe injury, Federal Register, Regulations.gov, FERC eCollection, WARN notices for California (xlsx), New York, Illinois, Washington and Florida, Legistar and CivicPlus agendas, ERCOT and CAISO queues, Florida UCC backend API, Texas franchise search, Harris County records.
- Physical: USGS and NOAA river gauges, Pegelonline Rhine, USGS quarry-blast catalog and EarthScope waveforms, EIA weekly CSVs and grid monitor, NYISO and CAISO, CDC wastewater, NOAA AIS archive (2023), Port of Los Angeles, Copernicus catalogue, Planetary Computer and Earth Search STAC, AWS Sentinel-2, Carbon Mapper methane plumes, NWS, NCEI, OpenSky live positions, adsb.lol, FAA registry, STB rail CSV, BNSF carload PDFs, FHWA TMAS, TxDOT and MnDOT ArcGIS.
- Digital: Greenhouse, Lever, Ashby and SmartRecruiters job APIs, Apple lookup, charts and review feeds, Statuspage APIs, crt.sh, RDAP, CT logs, Tranco, Wikipedia pageviews, Common Crawl, Shopify products.json, pypistats, npm, Docker Hub, Homebrew, Hacker News, GH Archive, GLEIF, UK Companies House bulk accounts, Norwegian and French registries, BLS PPI.

Red team of this phase: the probes ran from a shared cloud egress IP, so bot blocks and rate limits will differ on your home connection, probably for the better, and the GitHub behaviour is container-specific. Reachable today is not stable: Yahoo, Nasdaq, Shopify products.json and the Apple feeds are unofficial endpoints that can change without notice, which is itself a decay risk to log against any signal built on them. Verification was a re-fetch minutes after the first, so it confirms reachability, not history depth or licence terms; those are checked in Phase 3 and Phase 9. Confidence in this tool check: 90%. Main driver of uncertainty: IP-dependent blocking.

Connected business systems in this workspace (a Shopify store, a helpdesk, a data warehouse) are unrelated to this program and will not be used.

## 4. Signal Register (empty)

Columns: Signal, Category, Hypothesis, Data sources, Cost, Lead time, Universe coverage, Crowdedness (1–5), Expected signal/noise (1–5), Legal risk (1–5), Status, Confidence %, Next action.

Files: signal_register.csv (header only) and signal_register.md (empty table plus vocabularies) in this folder.

## 5. Gate

Stopped at the end of Phase 0. Awaiting approval and answers to the five questions. On "Approved. Continue to Phase 1." I proceed on the stated assumptions for any question left unanswered.
