# Event calendar notes — CME Globex Asia-session study (NQ/ES)

Built 2026-11-10. Companion to `event_calendar.csv` (826 rows, 2024-06-01 .. 2027-01-31).
Columns: `date, event, category, time_et, notes`. No commentary rows in the CSV; all caveats live in the `notes` column and here.

## Date / time conventions

- **US & Europe events**: `date` = US calendar date of release; `time_et` = ET clock time (EST/EDT per date, computed with tz rules).
- **Asia-Pacific events** (`boj`, `jp_data`, `cn_data`, `rba`, `cn_policy`): `date` = **local** (Japan/China/Australia) date, as requested for BoJ. These hit Globex during the US evening of the **prior** US date; `time_et` is the ET clock time of that evening and `notes` states the US date explicitly (e.g. "08:30 JST = 18:30 ET on 2026-11-19").
  - Japan 08:30 JST = 18:30 EST / 19:30 EDT; Tankan 08:50 JST = 18:50/19:50 ET.
  - China NBS 09:30 CST = 20:30 EST / 21:30 EDT; NBS activity 10:00 CST = 21:00/22:00 ET; Caixin/S&P 09:45 CST = 20:45/21:45 ET; GAC trade ~10-11:00 CST (irregular).
  - RBA 14:30 Sydney = 22:30 EST (Nov-Mar), 23:30 EDT (Oct, early Apr), 00:30 EDT same date (AEST months Apr-Oct) — all inside the 18:00-03:00 window.
  - BoJ: no fixed time; decision ~22:00-23:30 ET prior night (noted on every `boj` row); presser ~15:30 JST = 01:30/02:30 ET.
- ECB 14:15 CET = 08:15 ET except EU/US DST mismatch weeks (09:15 ET: 2025-10-30, 2026-03-19, 2026-10-29). BoE 12:00 London = 07:00 ET except mismatch weeks (08:00 ET: 2025-03-20, 2026-03-19).
- Earnings `time_et` 16:05 is nominal "after the close"; NVDA typically ~16:20 with 17:00 call.
- `roll` = CME equity-index roll date = Thursday 8 days before the 3rd-Friday quarterly expiry (the industry/CME convention). The task text said "Thursday before 3rd Friday"; if you want the Thursday immediately before expiry (D-1) instead, shift `roll` rows +7 days.
- Holidays: Globex ES/NQ hours are the standard CME equity-index pattern (Monday/Friday holidays: halt 13:00 ET, reopen 18:00 ET; Christmas/New Year/Good Friday: no overnight session). Rows backed by an explicit CME notice say so (2025-01-09 day of mourning; 2026-04-03 Good Friday abbreviated session).

## Sources used

Official (primary):
- Fed FOMC calendar 2024-2027 + minutes dates: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- BLS annual schedules: https://www.bls.gov/schedule/2024/home.htm, /2025/home.htm, /2026/home.htm, /2027/home.htm; monthly pages https://www.bls.gov/schedule/2025/10_sched.htm, 11_sched.htm, 12_sched.htm; indicator pages https://www.bls.gov/schedule/news_release/cpi.htm, empsit.htm, ppi.htm, jolts.htm
- BEA: https://www.bea.gov/news/schedule (2026), https://www.bea.gov/news/schedule/full-2025, https://www.bea.gov/news/schedule/next-year (2027), 2024 list https://apps.bea.gov/scb/issues/2023/12-december/1223-news-releases-2024.htm
- Census retail: https://www.census.gov/retail/release_schedule.html, https://www.census.gov/economic-indicators/calendar-listview-2024.html, -2025.html, -2026.html, calendar-listview.html (2027)
- Treasury refunding statements: https://home.treasury.gov/news/press-releases/jy2062 (2024-01-31), jy2697 (2024-10-30), sb0305 (2025-11-05), sb0590 (2026-08-05), sb0678 (2026-11-04); May-2024/Jul-2024/Feb-2025/Apr-2025/Jul-2025/Feb-2026/May-2026 dates from the "next announcement" line of the preceding statement + Treasury buyback-schedule PDFs
- BoJ MPM schedule: https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm (2026-27), https://www.boj.or.jp/en/mopo/mpmsche_minu/past.htm (2024-25); release calendar https://www.boj.or.jp/en/announcements/calendar/
- Japan CPI schedule (2026-27): https://www.stat.go.jp/english/data/cpi/1582.htm
- China NBS calendars: https://www.stats.gov.cn/english/PressRelease/ReleaseCalendar/202401/t20240104_1946223.html (2024), .../202412/t20241231_1958129.html (2025), .../202512/t20251226_1962154.html (2026)
- ECB: https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html (only Dec-2026 onward shown)
- BoE: https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates (2026-27); 2024/2025 via BoE news releases https://www.bankofengland.co.uk/news/2023/september/mpc-confirmed-dates-for-2024, https://www.bankofengland.co.uk/news/2024/september/monetary-policy-committee-dates-for-2025
- RBA: https://www.rba.gov.au/schedules-events/board-meeting-schedules.html (2026-27), https://www.rba.gov.au/media-releases/2024/mr-24-09.html (2025), https://www.rba.gov.au/media-releases/2023/mr-23-18.html (2024)
- NYSE holidays: https://www.nyse.com/markets/hours-calendars (2026-28); 2024-25 https://ir.theice.com/press/news-details/2023/NYSE-Group-Announces-2024-2025-and-2026-Holiday-and-Early-Closings-Calendar/default.aspx
- CME: Good Friday 2026 clearing advisory https://www.cmegroup.com/tools-information/holiday-calendar/files/2026/2026-good-friday-clearing-advisory.pdf; Jan-9-2025 day-of-mourning hours https://www.cmegroup.com/media-room/press-releases/2025/12/30/cme_group_announcestradinghoursforusnationaldayofmourningtohonor.html (cmegroup.com holiday pages returned 503 during this session; 2025/2026 hours cross-checked at https://blog.crosstrade.io/cme-trading-hours-for-2025/ and /cme-trading-hours-2026/)
- Earnings: SEC EDGAR 8-K (Item 2.02) filing lists, e.g. https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001045810&type=8-K (NVDA); CIKs 0000320193 AAPL, 0000789019 MSFT, 0001652044 GOOGL, 0001018724 AMZN, 0001326801 META, 0001318605 TSLA, 0001730168 AVGO. Upcoming: NVDA 2026-11-17 (company-confirmed per https://www.wallstreethorizon.com/nvidia-earnings-calendar and press), AVGO 2026-12-10 (TipRanks/EarningsWhispers "confirmed")
- Jackson Hole: https://www.kansascityfed.org/research/jackson-hole-economic-symposium/ (2026 Aug 27-29); 2024/2025 Friday speech dates from contemporaneous press (PBS, Reuters via Washington Times, Fortune)
- Politics: https://en.wikipedia.org/wiki/2026_United_States_federal_government_shutdowns; https://en.wikipedia.org/wiki/Tariffs_in_the_second_Trump_administration; https://www.supplychaindive.com/news/us-china-to-extend-trade-war-truce-by-2-months/831251/; https://rollcall.com/2025/11/12/house-clears-spending-package-to-end-longest-government-shutdown/; Fed Register notice via policyrisk.com (Nov 10 2026 12:01 ET truce expiry)
- China policy: https://en.wikipedia.org/wiki/20th_Central_Committee_of_the_Chinese_Communist_Party (plenum dates); https://sinocism.com/p/july-2026-politburo-meeting-fifth; Xinhua/China Daily (NPC 2026 Mar 5-12)

Secondary (used where official pages only show upcoming dates):
- ISM: ismworld.org calendar redirects to a login; dates taken from release-history calendars https://www.metatrader.com/en/economic-calendar/united-states/ism-manufacturing-pmi (+?page=2), .../ism-non-manufacturing-pmi, https://www.financecalendar.com/us-ism-manufacturing-pmi/, /us-ism-services-pmi/
- Caixin/S&P China PMIs, China trade, Japan CPI 2024-25, Tankan: S&P Global release calendar returned 403; stat.go.jp only lists forward dates; used https://www.metatrader.com/en/economic-calendar/china/caixin-manufacturing-pmi, .../caixin-services-pmi, .../china/trade-balance, .../japan/national-consumer-price-index-yy, .../japan/tankan-large-manufacturing-index (GMT dates converted to local)
- ECB 2024/2025/2026 Jan-Nov: https://youngplatform.com/en/blog/news/next-meeting-ecb-calendar-complete-date, https://equalsmoney.com/economic-calendar/events/ecb-interest-rate-decision, plus ECB schedule snippets

## Items I could NOT verify (flagged in CSV notes or omitted)

1. **FOMC minutes for the Oct 27-28 and Dec 8-9 2026 meetings** — not yet on the Fed calendar. Included 2026-11-18 and 2026-12-30 as UNVERIFIED (3-week convention).
2. **2027 FOMC schedule** — IS published (Jan 26-27, Mar 16-17, Apr 27-28, Jun 8-9, Jul 27-28, Sep 14-15, Oct 26-27, Dec 7-8; tentative until confirmed). Only Jan 27 2027 falls in range.
3. **ISM dates**: ISM's official calendar is paywalled. 2024-2026 dates are from release-history calendars (consistent with ISM's first/third-business-day rule). Dec-2026 Services (Dec 3) and Jan-2027 (Jan 4 / Jan 6) are rule-based ESTIMATES. One calendar showed Oct 5 2025 (a Sunday) for Services; Oct 3 used.
4. **Japan CPI 2024-2025 and Tankan dates** — from a third-party release history (dates are consistent with the official 2026 pattern). Dec-2026 Tankan (Dec 14) is an ESTIMATE; BoJ's schedule page did not yet show it.
5. **Caixin/S&P China PMI and GAC trade dates** — no official calendar reachable; from release history. Nov-10-2026 trade release marked tentative; Dec-2026 trade date unknown and omitted. NBS Feb-2026 PMI date parsed as Mar 4 (uncertain).
6. **CME per-holiday hours for 2024** — not fetched from CME (site returned 503); standard equity-index pattern applied and labelled as such. Good Friday 2026 abbreviated-session close time unverified (CME advisory confirms equities were open).
7. **Earnings**: all historical dates are SEC 8-K Item 2.02 filing dates (same-day for these companies). Historical same-day coincidences (META and TSLA both 2026-10-21) are as filed. Upcoming MSFT/TSLA 2027-01-27 and AAPL 2027-01-28 are third-party estimates. GOOGL/AMZN/META next reports fall in Feb 2027 (out of range).
8. **Politics from general knowledge, not re-verified by fetch this session**: 2024-09-30 and 2024-12-20 CR deadlines, 2025-01-01 debt-limit reinstatement, 2025-03-14 CR, 2025-07-04 OBBBA debt-limit increase, 2025-08-12 China-truce extension. Verified via sources: 2025 Oct 1-Nov 12 shutdown, 2026 lapses (Jan 31-Feb 3; DHS Feb 14-Apr 30), CR to Dec 11 2026, SCOTUS IEEPA ruling Feb 20 2026, Section 122 Feb 24-Jul 24 2026, Section 301 tariffs from Jul 24 2026.
9. **US-China truce extension to 2027-01-10** — single source (Supply Chain Dive, 2026-09-24) which itself said the White House had not formally documented it. Both 2026-11-10 and 2027-01-10 rows carry this caveat.
10. **Politburo meetings** (Apr/Dec economic meetings 2024-2026, Central Economic Work Conference) — dates not verified; omitted except the verified Jul 30 2026 meeting. NPC 2025 (Mar 5-11) is from general knowledge; NPC 2027 not yet announced. 21st Party Congress moved to H2 2027 (out of range).
11. Oct-2025 CPI was never published (shutdown); Sep-2025 JOLTS skipped; Q3-2025 GDP advance cancelled (initial estimate Dec 23 2025). These gaps are real, not omissions.
12. Web-search budget was exhausted late in the session; the items above were the ones still open at that point.

## Upcoming six+ weeks, day by day (2026-11-10 .. 2026-12-31)

Times are ET on that US date; Asia-local items say which prior US evening they hit.

- **2026-11-10 (Tue)**
  - TARIFF_DEADLINE [politics] 00:01 ET — Original US-China truce expiry; reported extended to Jan 10 2027 (Supply Chain Dive, Sep 24 2026; single source, said not yet formally documented)
  - CPI [us_data_tier1] 08:30 ET — BLS CPI
  - CN_TRADE [cn_data] 22:00 ET — China date; GAC trade data ~10:00-11:00 CST (often late) = ~22:00 ET on 2026-11-09; dates from release history (no official GAC calendar found); tentative
- 2026-11-11 (Wed): nothing scheduled in this calendar
- 2026-11-12 (Thu): nothing scheduled in this calendar
- **2026-11-13 (Fri)**
  - PPI [us_data_tier2] 08:30 ET — BLS PPI
- 2026-11-14 (Sat): weekend
- 2026-11-15 (Sun): weekend
- **2026-11-16 (Mon)**
  - CN_ACTIVITY [cn_data] 21:00 ET — China date; NBS activity data (IP/retail/FAI) 10:00 CST = 21:00 ET on 2026-11-15
- **2026-11-17 (Tue)**
  - RETAIL_SALES [us_data_tier2] 08:30 ET — Census advance retail sales
  - EARN_NVDA [earnings] 16:20 ET — NVDA FQ3-2027 results; CONFIRMED by company (call 17:00 ET)
- **2026-11-18 (Wed)**
  - FOMC_MINUTES [fed_minutes] 14:00 ET — UNVERIFIED: minutes of Oct 27-28 meeting not yet posted on Fed calendar; date per 3-week convention
- 2026-11-19 (Thu): nothing scheduled in this calendar
- **2026-11-20 (Fri)**
  - OPEX [opex] 16:00 ET — Monthly options expiration (3rd Friday)
  - JP_CPI [jp_data] 18:30 ET — Japan date; 08:30 JST = 18:30 ET on 2026-11-19 (prior US evening); official stat.go.jp schedule
- 2026-11-21 (Sat): weekend
- 2026-11-22 (Sun): weekend
- 2026-11-23 (Mon): nothing scheduled in this calendar
- 2026-11-24 (Tue): nothing scheduled in this calendar
- **2026-11-25 (Wed)**
  - PCE [us_data_tier1] 08:30 ET — BEA Personal Income & Outlays (PCE price index)
- **2026-11-26 (Thu)**
  - THANKSGIVING [holiday] time n/a — NYSE closed. Globex ES/NQ: overnight session Wed->Thu open; halt 13:00 ET Thu; reopen 18:00 ET; Globex hours per standard CME equity-index holiday pattern unless a CME notice is cited
- **2026-11-27 (Fri)**
  - EARLY_CLOSE [holiday] time n/a — NYSE 13:00 close. Globex ES/NQ early halt 13:15 ET; weekend; Globex hours per standard CME equity-index holiday pattern unless a CME notice is cited
- 2026-11-28 (Sat): weekend
- 2026-11-29 (Sun): weekend
- **2026-11-30 (Mon)**
  - CN_PMI_NBS [cn_data] 20:30 ET — China date; NBS official PMI 09:30 CST = 20:30 ET on 2026-11-29 (prior US evening)
- **2026-12-01 (Tue)**
  - ISM_MFG [us_data_tier2] 10:00 ET — ISM Manufacturing PMI (dates from release history; ISM calendar paywalled)
  - JOLTS [us_data_tier2] 10:00 ET — BLS JOLTS
  - CN_PMI_CAIXIN [cn_data] 20:45 ET — China date; S&P Global/Caixin-series mfg PMI 09:45 CST = 20:45 ET on 2026-11-30; dates from release history (S&P calendar blocked); next scheduled
- 2026-12-02 (Wed): nothing scheduled in this calendar
- **2026-12-03 (Thu)**
  - ISM_SVC [us_data_tier2] 10:00 ET — ESTIMATED per ISM third-business-day rule; not confirmed
  - CN_PMI_CAIXIN_SVC [cn_data] 20:45 ET — China date; S&P Global/Caixin-series services PMI 09:45 CST = 20:45 ET on 2026-12-02; dates from release history; next scheduled
- **2026-12-04 (Fri)**
  - NFP [us_data_tier1] 08:30 ET — BLS Employment Situation
- 2026-12-05 (Sat): weekend
- 2026-12-06 (Sun): weekend
- 2026-12-07 (Mon): nothing scheduled in this calendar
- **2026-12-08 (Tue)**
  - RBA [rba] 22:30 ET — Australia date; decision 14:30 Sydney = 22:30 ET on 2026-12-07
- **2026-12-09 (Wed)**
  - FOMC [fed] 14:00 ET — FOMC statement 14:00 ET; presser 14:30; with SEP/dot plot
  - CN_CPI [cn_data] 20:30 ET — China date; NBS CPI+PPI 09:30 CST = 20:30 ET on 2026-12-08 (prior US evening)
- **2026-12-10 (Thu)**
  - CPI [us_data_tier1] 08:30 ET — BLS CPI
  - EARN_AVGO [earnings] 16:05 ET — AVGO FQ4-2026 results after close; 3rd-party calendars mark confirmed; verify on IR site
  - ES_NQ_ROLL [roll] time n/a — CME equity-index roll date (Thursday 8 days before 3rd-Friday expiry); volume migrates to next contract
- **2026-12-11 (Fri)**
  - FUNDING_DEADLINE [politics] time n/a — CR expiry; FY2027 full-year appropriations unfinished as of late Sep 2026
- 2026-12-12 (Sat): weekend
- 2026-12-13 (Sun): weekend
- **2026-12-14 (Mon)**
  - TANKAN [jp_data] 18:50 ET — Japan date; 08:50 JST = 18:50 ET on 2026-12-13 (prior US evening); ESTIMATED from 3rd-party calendar (BoJ schedule page not yet showing it)
- **2026-12-15 (Tue)**
  - PPI [us_data_tier2] 08:30 ET — BLS PPI
  - CN_ACTIVITY [cn_data] 21:00 ET — China date; NBS activity data (IP/retail/FAI) 10:00 CST = 21:00 ET on 2026-12-14
- **2026-12-16 (Wed)**
  - RETAIL_SALES [us_data_tier2] 08:30 ET — Census advance retail sales
- **2026-12-17 (Thu)**
  - BOE [boe] 07:00 ET — BoE MPC decision 12:00 London = 07:00 ET (bankofengland.co.uk MPC dates)
  - ECB [ecb] 08:15 ET — ECB decision 14:15 CET = 08:15 ET; presser 14:45 CET; ECB official calendar
- **2026-12-18 (Fri)**
  - TRIPLE_WITCHING [witching] 09:30 ET — Quarterly expiry: ES/NQ futures + index options + stock options; AM settlement
  - JP_CPI [jp_data] 18:30 ET — Japan date; 08:30 JST = 18:30 ET on 2026-12-17 (prior US evening); official stat.go.jp schedule
  - BOJ [boj] time n/a — Japan date; decision ~22:00-23:30 ET prior night (no fixed time); Governor presser ~15:30 JST = 01:30/02:30 ET
- 2026-12-19 (Sat): weekend
- 2026-12-20 (Sun): weekend
- 2026-12-21 (Mon): nothing scheduled in this calendar
- 2026-12-22 (Tue): nothing scheduled in this calendar
- **2026-12-23 (Wed)**
  - PCE [us_data_tier1] 08:30 ET — BEA Personal Income & Outlays (PCE price index)
- **2026-12-24 (Thu)**
  - EARLY_CLOSE [holiday] time n/a — NYSE 13:00 close. Globex ES/NQ early halt 13:15 ET; NO overnight session into Dec 25; Globex hours per standard CME equity-index holiday pattern unless a CME notice is cited
- **2026-12-25 (Fri)**
  - CHRISTMAS [holiday] time n/a — NYSE closed (Fri). Globex ES/NQ: CLOSED; reopens Sun 18:00 ET; Globex hours per standard CME equity-index holiday pattern unless a CME notice is cited
- 2026-12-26 (Sat): weekend
- 2026-12-27 (Sun): weekend
- 2026-12-28 (Mon): nothing scheduled in this calendar
- 2026-12-29 (Tue): nothing scheduled in this calendar
- **2026-12-30 (Wed)**
  - FOMC_MINUTES [fed_minutes] 14:00 ET — UNVERIFIED: minutes of Dec 8-9 meeting not yet posted on Fed calendar; date per 3-week convention
- **2026-12-31 (Thu)**
  - CN_PMI_NBS [cn_data] 20:30 ET — China date; NBS official PMI 09:30 CST = 20:30 ET on 2026-12-30 (prior US evening)
  - NYE [holiday] time n/a — NYSE normal full day. Globex ES/NQ: NO overnight session into Jan 1; Globex hours per standard CME equity-index holiday pattern unless a CME notice is cited
