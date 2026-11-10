# ES PRE-ASIA REPORT — RTH Mon 2026-11-09 → Asia session Tue 2026-11-10 (18:00–03:00 ET)
_Generated 2026-11-10 01:23 UTC · decision point 18:00 ET · training window 2024-06-18 → 2026-11-08 (walk-forward, no look-ahead)_

## 1. THE CALL

**CONTINUATION: LONG (with the up move, tight stop, target stop_level)**  
Confidence meter: `[###############---------------] 51/100`  → grade **NO EDGE**  
_Confidence = calibrated probability the called trade wins when it resolves (target vs stop), out-of-sample calibrated. Grade A ≥72, B ≥63, C ≥56, else no edge._

- RTH move: **UP** +1.41% (7,466.75 → 7,572.25), +1.0σ of 20d daily vol · closed at the extreme (CLV +0.61) · 0.11 range-widths beyond VWAP
- Entry reference (17:00 close): **7,580.25** · Stop for the fade: **7,614.98** (35 pts = $1,736/contract)
- Expected Asia range: median **41 pts** (54 bp), 80th pct **51 pts** (68 bp) · model expected signed reversion +9 bp
- P(Asia closes against the RTH move) = **62%** (close-to-close direction is near coin-flip historically; the path targets below carry the edge)

| Fade target | Stop variant | Target level | Dist (pts) | Stop level | Stop dist | P(target first) | P(stop first) | P(scratch) | Win rate on resolution | EV (pts) | EV ($/contract) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RTH VWAP | tight | 7,556.06 | 24 | 7,614.98 | 35 | 29% | 30% | 40% | 49% | -3.4 | -169 |
| 38.2% retrace | tight | 7,531.95 | 48 | 7,614.98 | 35 | 6% | 30% | 64% | 17% | -7.5 | -374 |
| 50% retrace | tight | 7,519.50 | 61 | 7,614.98 | 35 | 9% | 30% | 61% | 23% | -5.8 | -291 |
| RTH VWAP | wide | 7,556.06 | 24 | 7,623.68 | 43 | 33% | 12% | 55% | 74% | +3.0 | +148 |
| 38.2% retrace | wide | 7,531.95 | 48 | 7,623.68 | 43 | 16% | 12% | 72% | 57% | +2.5 | +126 |
| 50% retrace | wide | 7,519.50 | 61 | 7,623.68 | 43 | 14% | 12% | 74% | 55% | +2.2 | +112 |

_Tight stop = RTH extreme + 10% of RTH range. Wide stop = max(0.6× recent median Asia range, 0.3× today's RTH range) from the 17:00 close. Scratch = neither target nor stop by 03:00, valued at the model's expected signed reversion return. Each (target, stop) pair has its own out-of-sample calibrated first-hit model._

**Trade plan implied by the call**

- LONG ES from the 18:00 reopen (reference 7,580.25); target **7,614.98** (35 pts / $1,736); stop **7,556.06** (24 pts / $1,209) · reward:risk 1.44
- P(target first) 30% · P(stop first) 29% · P(neither by 03:00) 40% · EV **+3 pts** ($+170/contract) before costs
- Continuation means: price is more likely to trade through the stop level of the fade than to retrace to VWAP first. It is a momentum trade with the stop at VWAP, not a forecast of a large trend; use the expected range for runners.

**Does the setup evidence agree with the call?**

- ✔ supports: NQ underperformed ES by > 0.5% (n=43, rev-rate 42%, avg -10 bp, t=-2.2)

## 2. WHERE PRICE IS AND WHAT PUT IT THERE

**Levels**

| Level | Price | vs 17:00 close |
|---|---|---|
| 17:00 close (entry ref) | 7,580.25 | +0 pts (+0.00%) |
| RTH close 16:00 | 7,572.25 | -8 pts (-0.11%) |
| RTH VWAP | 7,556.06 | -24 pts (-0.32%) |
| RTH high | 7,600.50 | +20 pts (+0.27%) |
| RTH low | 7,455.75 | -124 pts (-1.64%) |
| RTH open | 7,466.75 | -114 pts (-1.50%) |
| Prior settle | 7,402.00 | -178 pts (-2.35%) |
| Prior RTH high | 7,469.00 | -111 pts (-1.47%) |
| Prior RTH low | 7,382.00 | -198 pts (-2.62%) |
| Last Asia high | 7,452.50 | -128 pts (-1.69%) |
| Last Asia low | 7,385.50 | -195 pts (-2.57%) |
| 20d SMA | 7,682.73 | +102 pts (+1.35%) |
| 50d SMA | 7,718.52 | +138 pts (+1.82%) |
| Fade stop | 7,614.98 | +35 pts (+0.46%) |
| 20d ATR (RTH range) | 94 | today's range = 1.55× ATR |

**Price structure (P)**

- Session: gap at open +0.87% (not filled) → RTH +1.41% → settle-to-settle +2.30% → post-close 16-17h +0.11%
- Range 1.55× ATR, high printed at 15:xx, low at 09:xx ET; close location +0.61 (−1 low … +1 high); late-day behaviour: held the extreme into the close
- Broke prior RTH high: yes · below prior RTH low: no · vs last Asia high +1.3 ATR, vs last Asia low +2.0 ATR

**Trend / stretch (T)**

- vs 5d SMA +0.4 ATR · vs 20d SMA **-1.2 ATR** · vs 50d SMA **-1.6 ATR** · 20d SMA slope -1.02%/5d
- 5d return -0.05% · 20d return -3.62% · 2-day up streak · -3.70% from 20d high · +2.64% from 20d low
- Today's move **corrects** the stretch from the 20d mean (stretch-in-direction -1.2 ATR)

**Volatility (V)**

- VIX **19.92** (-22.3% today, z20 +0.3) · VVIX 98.4 · VIX CONFIRMED the equity move
- Realised vol 20d 22% · 5d 43% (ratio 1.97) · implied−realised -2 vol pts · recent Asia range median 47 bp, last night 90 bp

**Cross-asset (X)** — all closes known by 18:00 ET

- Dollar: DXY -0.61% · USDJPY **158.29** (+0.50% today, +0.39% 5d) 
- Rates: US10Y **4.864%** (+0 bp today, -3 bp 5d) · 3m-10y curve +83 bp
- Asia equities (prior session): Nikkei -5.96% (5d -11.17%) · KOSPI -6.02% · HSI -1.27% · Shanghai -1.10% · US-after-Tokyo divergence +8.26%
- US internals: SOX vs NQ +4.55% · RUT vs NQ +0.85% · NQ vs ES -1.10% · Europe (SX5E) -0.98%
- Commodities/crypto: gold +1.58% · crude -4.78% (5d -10.34%) · copper +2.56% · BTC during US hours +0.21%

**Session memory (S)**

- Last night's Asia -0.29% (already reverted the prior RTH) · Europe +1.01% · full overnight into today's open +0.87% · RTH extended the overnight · RTH volume 0.98× 20d avg

**Calendar (C)**

- Today: CN_CPI · tonight/tomorrow: CN_TRADE;CPI;TARIFF_DEADLINE · days to FOMC 30 · days since FOMC 12 · Monday

## 3. WHY — FACTOR ATTRIBUTION

Logistic contributions (log-odds) toward **Asia touches RTH VWAP before the tight stop** — positive pushes toward the target, negative toward the stop:

| Factor | Tonight's value | Contribution |
|---|---|---|
| post-close move in move direction | 0.001 | -0.57 ▼ |
| 5d/20d realised vol | 1.974 | -0.47 ▼ |
| distance beyond VWAP in move direction | 0.112 | +0.41 ▲ |
| VIX confirmed the move | 0.223 | -0.35 ▼ |
| semis relative strength in move direction | 0.046 | -0.30 ▼ |
| RTH range vs ATR | 1.545 | -0.18 ▼ |
| closed at extreme in move direction | 0.610 | -0.14 ▼ |
| opening gap in move direction | 0.009 | +0.14 ▲ |
| prior overnight in move direction | 0.009 | +0.14 ▲ |
| RTH was a down day | 0 | -0.08 ▼ |

Top factors raising **stop-first** risk: post-close move in move direction (+0.56), 5d/20d realised vol (+0.28), closed at extreme in move direction (+0.11), move extends stretch from 20d SMA (+0.11).

**Active setups tonight and their historical record** (data strictly before tonight; outcomes in the reversion direction)

| Setup | n (all) | Rev-rate | Avg rev (bp) | VWAP first | 38% first | Stopped | Med Asia range (bp) | t | n (1y) | Rev-rate 1y |
|---|---|---|---|---|---|---|---|---|---|---|
| _all nights (base rate)_ | 464 | 54% | +2.6 | 47% | 43% | 30% | 41 | | | |
| RTH up more than 1% | 31 | 42% | -6.6 | 16% | 19% | 35% | 56 | -0.7 | 11 | 55% |
| Closed in outer 20% of range in the move's direction | 224 | 54% | +2.4 | 25% | 33% | 42% | 40 | +0.9 | 84 | 55% |
| Gapped and extended in gap direction | 79 | 54% | +3.7 | 37% | 39% | 38% | 46 | +0.6 | 28 | 54% |
| RTH range > 1.5x 20d ATR | 78 | 53% | -2.7 | 32% | 26% | 31% | 53 | -0.4 | 31 | 48% |
| Closed above prior RTH high | 173 | 50% | +2.4 | 42% | 40% | 27% | 33 | +1.0 | 71 | 51% |
| VIX down more than 10% today | 41 | 56% | +2.7 | 34% | 24% | 27% | 46 | +0.5 | 15 | 60% |
| 5d realised vol > 1.6x 20d (vol expanding) | 30 | 63% | +6.1 | 40% | 33% | 33% | 50 | +0.6 | 9 | 67% |
| SOX outperformed NQ by > 1.5% | 103 | 53% | +3.3 | 46% | 47% | 29% | 37 | +1.0 | 52 | 56% |
| Semis led in the direction of the move (>1%) | 180 | 54% | +2.2 | 39% | 39% | 31% | 43 | +0.6 | 79 | 57% |
| Nikkei fell > 1.5% in the prior Tokyo session | 58 | 45% | -6.2 | 40% | 38% | 36% | 51 | -0.8 | 33 | 58% |
| US moved > 1.5% opposite to Tokyo's session | 115 | 52% | +2.5 | 44% | 40% | 30% | 46 | +0.7 | 52 | 56% |
| NQ underperformed ES by > 0.5% | 43 | 42% | -10.1 | 26% | 23% | 37% | 41 | -2.2 | 22 | 45% |
| Last night's Asia already reverted the prior RTH | 242 | 50% | +2.0 | 50% | 44% | 29% | 43 | +0.8 | 103 | 56% |
| CPI/NFP/PCE tomorrow (pre-event night) | 60 | 53% | +1.6 | 43% | 40% | 30% | 43 | +0.4 | 23 | 65% |
| China data during tonight's Asia session | 111 | 50% | +0.5 | 46% | 39% | 32% | 43 | +0.1 | 41 | 59% |
| Monday | 91 | 52% | +2.3 | 48% | 38% | 31% | 46 | +0.6 | 39 | 54% |

_Read: 'Rev-rate' = share of nights Asia closed against the RTH move; 'VWAP first' = reached RTH VWAP before the stop; t = t-stat of the average reversion return (|t| > 2 is meaningful; most setups are not)._

## 4. WHERE THIS HAPPENED BEFORE — NEAREST ANALOG NIGHTS

Nearest 12 nights in setup space (same RTH direction, weighted on move size, close location, VWAP distance, stretch, VIX behaviour):

| Date | RTH | Asia rev-ret (bp) | Retrace | VWAP first | 38% first | Stopped | Asia range (bp) | What happened (research catalogue) |
|---|---|---|---|---|---|---|---|---|
| 2025-11-24 Mon | +0.99% | +12 | 0.24 | 0 | 0 | 0 | 26 | — |
| 2026-03-31 Tue | +1.79% | -89 | 0.01 | 0 | 0 | 1 | 93 | RTH: Quarter-end relief rally, best day since May 2025: S&P +2.91%, Nasdaq +3.83% (NQ gapped +1.3% at open, +2.31% open-to-close); unconfirmed report Iranian President Pezeshkian open to ending war with guarantees; Trum… |
| 2024-08-08 Thu | +1.57% | -3 | 0.24 | 0 | 0 | 0 | 64 | — |
| 2024-06-18 Tue | +0.28% | +0 | 0.10 | 0 | 0 | 1 | 12 | events: RBA;RETAIL_SALES |
| 2024-07-22 Mon | +0.42% | +12 | 0.62 | 1 | 1 | 0 | 34 | — |
| 2026-09-02 Wed | +0.50% | -1 | 0.31 | 1 | 1 | 0 | 30 | events: EARN_AVGO |
| 2025-11-21 Fri | +0.49% | -3 | 0.67 | 0 | 0 | 0 | 39 | events: JP_CPI;OPEX |
| 2025-01-03 Fri | +0.97% | -5 | 0.24 | 0 | 0 | 0 | 32 | events: ISM_MFG |
| 2026-07-30 Thu | +1.00% | -25 | 0.13 | 0 | 0 | 1 | 58 | RTH: Extra row: Jul 30 RTH Nasdaq +2.8% ended 6-day losing streak (MSFT +16%, SOXX +8%, Micron +18%, SK Hynix +17%); Q2 GDP 1.5% vs 1.8%; Apple/Amazon after the close (AMZN +12% premarket on cloud, AAPL -7% on services … |
| 2026-03-16 Mon | +0.88% | +45 | 0.61 | 1 | 1 | 0 | 54 | events: CN_ACTIVITY |
| 2026-03-04 Wed | +0.38% | +29 | 1.50 | 1 | 1 | 0 | 82 | events: CN_PMI_CAIXIN;CN_PMI_CAIXIN_SVC;CN_PMI_NBS;EARN_AVGO;ISM_SVC |
| 2026-03-19 Thu | +0.44% | +33 | 0.82 | 0 | 0 | 0 | 51 | events: BOE;BOJ;ECB |

Analog summary: reverted 50% · avg rev-ret +1 bp · VWAP first 33% · stopped 25% · median range 45 bp

## 5. EXPECTED RANGE AND TIMING

- Model Asia range tonight: median **41 pts** / P80 **51 pts** (vs 20d median 36 pts). Size stops so that the stop sits outside ~0.6× the P80 range from entry unless the setup justifies the RTH-extreme stop.
- Hour the VWAP target was first reached (history): 18h 67%, 19h 7%, 20h 9%, 21h 3%, 22h 3%, 23h 3%, 00h 1%, 01h 3%, 02h 2%
- Hour the stop was hit (history): 18h 49%, 19h 9%, 20h 11%, 21h 5%, 22h 6%, 23h 4%, 00h 4%, 01h 8%, 02h 6%
- Typical rhythm: 18:00–20:00 reopen impulse & US after-hours news → 19:00/20:00 Tokyo cash open (Nikkei/SoftBank/Advantest), 21:00–22:00 China/HK open and China data, 20:30–23:30 BoJ decisions, 01:00–03:00 pre-London positioning.

## 6. WHAT TO WATCH TONIGHT

- Tue 11-10 **CPI** (us_data_tier1, 08:30 ET) BLS CPI
- Tue 11-10 **TARIFF_DEADLINE** (politics, 00:01 ET) Original US-China truce expiry; reported extended to Jan 10 2027 (Supply Chain Dive, Sep 24 2026; single source, said not yet formally documented)
- Tue 11-10 **CN_TRADE** (cn_data, 22:00 ET) China date; GAC trade data ~10:00-11:00 CST (often late) = ~22:00 ET on 2026-11-09; dates from release history (no official GAC calendar found); tentative

**Conditional notes**

- CPI/NFP/PCE tomorrow morning: Asia tends to position rather than trend; expect range compression into 03:00 and fade extremes.
- Nikkei moved -5.96% last session: a second-day Tokyo follow-through at 19:00/20:00 ET is the main path risk tonight.

**Invalidation**

- Fade is wrong if price trades through **7,614.98** (RTH extreme + 10% range) — especially before 21:00 ET (reopen momentum) or on a Tokyo-open impulse.
- Continuation is wrong if price reclaims VWAP **7,556.06** and holds it through the China open (21:30 ET).

**Live macro context (from the research layer)**

CURRENT CONTEXT (as of 2026-11-10, pre-CPI)

**Levels (Nov 9 close; Weekend Spread digest, secondary):** NQ 27,907.63 (+3.4% d/d), S&P 7,549.94, Nasdaq 25,253, Dow 52,390; VIX 19.92 (VXN 29.11 — Nasdaq vol still 9 pts over VIX), MOVE 88.5; 2y 4.56%, 10y 4.88%, 30y 5.26%; DXY 101.71; USDJPY 157.69 (high 158.53); Brent $92.91, WTI $87.07; gold $4,140; BTC $74,876. S&P sits just above its 200-dma and just below its Election-Day level; Nasdaq Composite is ~8% below the Oct 6 record. [Weekend Spread](https://theweekendspread.substack.com/p/the-close-monday-november-9-2026), [CNBC Nov 9 live](https://www.cnbc.com/2026/11/09/stock-market-today-live-updates.html).

**Live narratives**
1. **Fed path into Dec 8-9.** Hike priced ~80% (FedWatch) after NFP +165k/UE 4.1%; BofA: a hike unless CPI is "indisputably soft" (0.1% m/m) or markets sell off sharply; Goolsbee says AI data-center construction "looks like old-fashioned demand overheating". Oct CPI (today 08:30 ET) consensus +0.3% headline / +0.2% core, **no official y/y** (2025 shutdown gap; unofficial estimates 3.8–4.0% headline, 2.7–2.8% core). [CNBC CPI preview](https://www.cnbc.com/2026/11/09/october-cpi-report-2026-inflation.html), [Kiplinger](https://www.kiplinger.com/investing/economy/october-2026-cpi-report-what-to-expect).
2. **AI capex / chips / neoclouds.** Hyperscaler Q3 capex ~$209B; Alphabet and Amazon negative FCF; Meta raising $95B; Microsoft cutting neocloud partners and winding down Oracle contract; Gartner: up to 80% of neoclouds gone by 2030; Citi downgraded global tech to Neutral Nov 9. Chips rebounding ex-Nvidia (SOX +6.85% Nov 9). CoreWeave reports tonight after the close. [CNBC Oct 29](https://www.cnbc.com/2026/10/29/microsoft-google-ai-capex-estimates.html), [CNBC Nov 5/6 live](https://www.cnbc.com/2026/11/05/stock-market-today-live-updates.html).
3. **Nvidia governance.** Board probe into whether CEO Huang was targeted by Chinese MSS via an affair partner (NYT/FT); Huang stays CEO; House China Committee requested a briefing; Ives flags removal risk. NVDA $178.67 (-4.3%), earnings **Tue Nov 17 AMC** (IR-confirmed per two sources; one tracker shows "expected"). [CNBC](https://www.cnbc.com/2026/11/09/nvidia-jensen-huang-chinese-spy-investigation.html), [Bloomberg](https://www.bloomberg.com/news/articles/2026-11-08/nvidia-board-to-probe-spying-case-after-ceo-jensen-huang-admits-infidelity), [cmelitegroup](https://www.cmelitegroup.com/knowledge-hub/nvidia-earnings-date/).
4. **Midterm aftermath.** Democratic control of both chambers from January; data-center politics (TX/OH governors, Sanders moratorium call) vs. Redbud: voters rejected DC restrictions in 39/40 ballot measures; Trump "fully supports" the build-out. Watch for House/Senate hearings on "who pays for the build-out" (Century Financial). [The National](https://www.thenationalnews.com/business/markets/2026/11/06/nasdaq-plunges-5-as-investors-dump-ai-stocks-after-midterms/).
5. **Oil / Iran.** Brent -16% last week (worst since Covid), -5.9% Monday on Trump's "strikes highly unlikely while talks progress"; Rubio called Iran demands "outrageous"; Qatar PM reportedly carrying an interim Hormuz proposal (unconfirmed); shipping attacks continue; Rapidan puts odds of resumed fighting at 80%. Energy was the only sector down Nov 9. [GV Wire](https://gvwire.com/2026/11/09/oil-slides-as-trump-signals-restraint-on-iran-despite-fresh-shipping-attacks/), [CNBC Nov 8 live](https://www.cnbc.com/2026/11/08/stock-market-today-live-updates.html).
6. **Yen / BoJ.** USDJPY 157.7 with 158.5 the recent high; MoF has confirmed record July intervention (¥7.98T on Jul 30); Katayama repeated "ready to act" Nov 2 and Nov 5; BoJ next decision Dec 18 with a hike in Dec/Jan the consensus (CNBC survey) after Oct 30's "inflation consistent with 2%" language. Intervention risk rises above 158.5–160; a yen *bid* on equity weakness (Nov 5, Nov 9) is the carry-unwind tell. [investing.com](https://www.investing.com/analysis/usdjpy-near-158-as-yield-gap-support-collides-with-japans-intervention-risk-200689760), [Nation Thailand](https://www.nationthailand.com/business/banking-finance/40073293), [CNBC Oct 30](https://www.cnbc.com/2026/10/30/yen-steady-before-boj-ai-jitters-drive-treasury-rally-weigh-on-dollar.html).
7. **Positioning.** Goldman: record HF net tech selling (week to Oct 16); AAII bears 53% (Sep 18); EM outflows $33.8B in Oct (IIF); XLK five straight weekly losses; Hartnett risk-off (Oct 16); RBC 5–10% pullback call (Oct 26). VXN-VIX spread wide → Nasdaq protection still bid.

**Tonight / this week (ET)**
- Tue Nov 10: Asia already open — Kospi +5% (upside halt), Nikkei +2.7%, NQ futures +0.2% (CNBC). 08:30 Oct CPI (+0.3/+0.2 cons.); 13:00 $42B 10y auction; AMC CoreWeave, Sea, On; Anthropic IPO roadshow reportedly begins (Nasdaq "ANT"). [CNBC Nov 9 live](https://www.cnbc.com/2026/11/09/stock-market-today-live-updates.html)
- Wed Nov 11: Veterans Day (bond market closed; equities open — calendar fact, not sourced to an article). Cisco earnings (CNBC lists this week).
- Thu Nov 12: US budget balance (digest). Fri Nov 13: PPI (CNBC says "Friday"; StockMarketWatch digest says Nov 13); Applied Materials earnings this week.
- Mon Nov 16: GM moves to Nasdaq Nov 17 (Citi: NDX inclusion possible in Dec).
- **Tue Nov 17: NVDA FQ3 AMC**; Walmart earnings (digest). Wed Nov 18: FOMC minutes of Oct 27-28 (standard 3-week lag — inferred, not sourced).
- **Fri Nov 20: monthly OPEX** (3rd Friday — calendar).
- Thu Nov 26: Thanksgiving (US closed); Fri Nov 27 half-day (calendar).
- Dec 8-9 FOMC (sourced); Dec 18 BoJ (tradingeconomics/newtrading listings) and Dec 18 quad witching (calendar).

**What the overnight desk is watching tonight:** (1) whether Kospi's +5% halt holds into the Tokyo close or fades like Oct 21/Oct 27 (both upside halts were followed by down US sessions within 1–3 days); (2) CPI core print vs 0.2% — a 0.3% likely re-prices Dec to >90% and re-tests 10y 5%; (3) NVDA headline risk (probe findings, Congressional briefing) — Sunday's -0.8% NQ gap shows the stock still sets the overnight tone; (4) Brent $92–93: a Hormuz interim-deal confirmation would extend the ES bid, resumed strikes would reverse it; (5) USDJPY 158.5 — MoF line.

---

## 7. HONESTY BOX — HOW GOOD IS THIS MODEL OUT OF SAMPLE?

| Outcome | OOS n | Base rate | Brier (base) | Brier (model) | Accuracy | Tonight's p | Realised rate in tonight's bucket |
|---|---|---|---|---|---|---|---|
| reverted | 301 | 57% | 0.245 | 0.240 | 57% | 62% | 57% (n=278) |
| hit_vwap_first | 301 | 51% | 0.250 | 0.166 | 74% | 29% | 30% (n=74) |
| hit_r382_first | 301 | 44% | 0.246 | 0.194 | 67% | 6% | 7% (n=55) |
| hit_r500_first | 301 | 37% | 0.233 | 0.193 | 68% | 9% | 12% (n=68) |
| stopped | 301 | 34% | 0.223 | 0.189 | 72% | 30% | 28% (n=120) |
| hit_vwap_first_w | 301 | 50% | 0.250 | 0.187 | 70% | 33% | 31% (n=87) |
| hit_r382_first_w | 301 | 44% | 0.246 | 0.210 | 65% | 16% | 13% (n=53) |
| hit_r500_first_w | 301 | 37% | 0.233 | 0.202 | 67% | 14% | 8% (n=36) |
| stopped_w | 301 | 25% | 0.189 | 0.176 | 75% | 12% | 15% (n=107) |

- Asia-range median model: OOS MAE 21 bp vs naive 24 bp; coverage of the median 47% (should be ≈50%; below it means the recent regime is more volatile than the training window).
- Signed-magnitude model (expected reversion return): OOS R² -0.14; the scratch outcome in the EV table is therefore weighted by 0.00 (0 = no skill, ignored).
- Brier below the base-rate Brier = the model adds information. Close-to-close direction ('reverted') is barely better than a coin flip; the path outcomes (VWAP/38% first, stopped) are where the edge is. Treat grades below B as information, not a trade.
- Much of the path-outcome skill is geometry: how far the targets and the stop sit from the entry relative to the expected Asia range. That is exactly what a fade trade needs, but it means a high-confidence CONTINUATION call often says 'the fade stop is too close', not 'a trend is coming'.
- Sample: ~17 months of hourly Globex data; the 'past year' is ~250 nights. Rare setups (n < 15) are anecdotes, not statistics.

## 8. REPEATING PATTERNS FROM THE YEAR-LONG RESEARCH LAYER

1. **AI-capex-driven RTH selloffs were followed by Asia continuation, with Tokyo/Seoul over-reacting.** Nov 3->4, Nov 4->5, Nov 17->18, Nov 20->21, Dec 15->16: every RTH day where the cited driver was AI valuation/capex saw NQ lower in the 18:00-03:00 window and Nikkei/Kospi down 2-4x the NQ move (SoftBank, Advantest, Tokyo Electron, SK Hynix, Samsung as the proxies). Test: sign(asia_ret) == sign(rth_ret) and |Nikkei| > 2x|NQ asia| when tags contain ai_capex and rth_ret < -0.5.  _(source: narrative_2025Q4_2026Jan.md)_
2. **After-close megacap/AI prints override the RTH direction.** Dec 10 (FOMC rally -> Oracle -> NQ futures -1.3% in Asia), Nov 19 (NVDA -> +1.7% overnight peak then faded), Jan 28/29 (MSFT/META split, then Apple + Warsh). When a $100B+ AI-exposed company reports after 16:00 ET, the overnight sign follows the print's capex/margin read, not the RTH tape. Test: rows tagged earnings_megacap/earnings_semis with a post-close report show |asia_ret| > 0.7 and sign independent of rth_ret.  _(source: narrative_2025Q4_2026Jan.md)_
3. **The post-NVDA overnight peak was not held.** Nov 19-20: NQ futures +1.7% at ~21:00 ET, RTH closed -2.2%. Nov 21 Asia then sold the Japan AI proxies (Advantest -12%). Test: overnight high after NVDA earnings vs next RTH close.  _(source: narrative_2025Q4_2026Jan.md)_
4. **Sunday 18:00 ET opens in January gapped on weekend policy headlines regardless of the Friday RTH sign.** Jan 11 (DOJ/Powell, NQ -202 pts), Jan 18 (Greenland, NQ -1.1% in MLK-thin trade), Jan 25 (yen intervention signals + Canada tariff; press: NQ -0.4% early). All three Friday RTH sessions had been up days. Test: Friday rth_ret is uninformative for Sunday-open asia_ret in Jan 2026; headline tags (fed/tariffs/geopolitics) dominate.  _(source: narrative_2025Q4_2026Jan.md)_
5. **Semis prints inside the 18:00-03:00 window are clean NQ catalysts.** Samsung/SK Hynix-Nvidia headlines (Nov 16-17, NQ +0.7%), Micron into BoJ day (Dec 17-19), ASML at ~01:00 ET (Jan 28, NQ +0.9% by 04:44 ET). Test: NQ asia_ret > +0.6 on nights with a positive semis print in Asia/Europe hours.  _(source: narrative_2025Q4_2026Jan.md)_
6. **BoJ: fully-priced hikes produced "sell the fact" in yen and "buy the fact" in Nikkei; hawkish surprises came from speeches, not meetings.** Dec 19 hike (unanimous, priced ~80% since Ueda's Dec 1 speech): yen weakened, Nikkei +1-1.4%, 10y JGB 2%. Jan 23 hold with hawkish projections: yen flat at 158.6, Nikkei +0.3%. The yen shocks that hurt Nikkei were Ueda's Dec 1 Nagoya speech (155.5) and the Jan 24-26 intervention signalling (158 -> 154, Nikkei -1.8%). Test: |USDJPY move| on BoJ decision days < |USDJPY move| on Ueda-speech / MoF-signal days in this window.  _(source: narrative_2025Q4_2026Jan.md)_
7. **Weak yen = Nikkei records = cushioned NQ overnight.** Jan 12-13 (USD/JPY 158.65, Nikkei +3.1% record; FXEmpire: yen slide "cushions US futures") and Nov 20-21 (yen at 10-month low did not prevent Nikkei -2.4%) show the cushion only works absent an AI-valuation shock. Test: on nights with USD/JPY up > 0.5%, asia_ret for NQ is less negative than on yen-up nights, conditional on no ai_capex tag.  _(source: narrative_2025Q4_2026Jan.md)_
8. **Pre-CPI nights were NOT compressed in this window.** Jan 12->13: Nikkei +3.1% record; Dec 17->18: Micron print and BoJ positioning. The dataset's Asia ranges on these nights should be checked, but the press record shows active, catalyst-driven sessions rather than quiet ones.  _(source: narrative_2025Q4_2026Jan.md)_
9. **FOMC nights: the Fed itself was not the overnight driver.** Dec 10 (Oracle) and Jan 28 (MSFT/META, gold +4%) both had larger non-Fed catalysts. Test: asia_rng on FOMC nights (1.60 on Dec 10) exceeds the window median, but attribution is to earnings/dollar, not to the statement.  _(source: narrative_2025Q4_2026Jan.md)_
10. **Thin-holiday Globex sessions amplify headline moves.** MLK (Jan 19): NQ futures -1.1% on Greenland with US cash/Treasuries closed. Test: holiday_thin + tariffs/geopolitics rows show |asia_ret| above the window median.  _(source: narrative_2025Q4_2026Jan.md)_
11. **Technical-level breaks were followed through overnight.** Nov 17 close below the 50-DMA (first since April) -> Nikkei -3%/NQ -0.83 overnight; Dec 15 Nikkei first close below 50,000 followed the Dec 12-15 Broadcom/Oracle break. Test: rows tagged technical_level with negative rth_ret have negative asia_ret.  _(source: narrative_2025Q4_2026Jan.md)_
12. **Dollar-slide nights were NQ-positive, gold-positive.** Jan 27->28 (DXY 96.0, gold +4.1%, NQ +0.9%), Dec 10->11 (dollar down on Fed message but Oracle dominated). Test: on nights with DXY -0.2% or worse and no earnings shock, NQ asia_ret > 0.  _(source: narrative_2025Q4_2026Jan.md)_
1. **Sunday 18:00 ET gaps during the war were set by weekend oil/Iran headlines and were directionally right for the Asia window in 5 of 7 Sundays** (1 Mar −, 8 Mar −, 22 Mar −, 5 Apr −, 12 Apr −; exceptions 15 Mar and 29 Mar where NQ finished +0.98% after −0.3%/−0.7% opens). Test: sign(NQ 18:00–18:30 move) vs sign(18:00–03:00) on Sundays, conditional on |ΔWTI at reopen| > 3%.  _(source: narrative_2026Q1_Apr.md)_
2. **A WTI move of >±5% at or after the 18:00 ET reopen predicted the sign of the NQ Asia return in every identified case** (8 Mar, 9 Mar, 11 Mar, 18 Mar, 30 Mar, 1 Apr, 7 Apr, 12 Apr). Oil, not US futures, was the leading indicator in the first 60 minutes. Test: regress NQ(18:00–03:00) on WTI(18:00–19:00) over Mar–Apr; expect β<0 with R² far above the Feb baseline.  _(source: narrative_2026Q1_Apr.md)_
3. **Kospi was the highest-beta expression of the NQ overnight move** (|Kospi| ≈ 2–3× |NQ Asia| on war nights; Samsung/SK Hynix led both ways). Test: Kospi open (20:00 ET) vs NQ 18:00–20:00 move; expect slope >2.  _(source: narrative_2026Q1_Apr.md)_
4. **Trump posts/remarks between 18:00 and 21:30 ET were the single most frequent overnight catalyst** (8 Mar 18:13, 22 Mar weekend ultimatum, 29 Mar, 1 Apr 21:00 address, 5 Apr 18:09, 7 Apr 18:51, 12 Apr 18:20, 21 Apr ~16:05). Their market impact scaled with whether they changed oil supply expectations (Hormuz open/closed), not with tone. Test: tag overnight headlines as "Hormuz-relevant" vs "rhetoric"; compare absolute NQ response.  _(source: narrative_2026Q1_Apr.md)_
5. **RTH reversal days (open-to-close sign opposite the gap) that were not accompanied by an oil decline were faded overnight**: 2 Mar (RTH +1.63%, Asia −1.31%), 1 Apr (RTH +0.58% ahead of the speech, Asia −1.51%). Conversely RTH rallies with oil down ≥3% carried into Asia (31 Mar, 7 Apr, 13 Apr).  _(source: narrative_2026Q1_Apr.md)_
6. **Relief rallies began off-hours:** the three largest two-day NQ rallies of the window all started with an overnight or pre-market headline (23 Mar 07:39, 30 Mar WSJ evening report, 7 Apr 18:51), not in RTH. Test: share of cumulative Mar–Apr NQ gain accruing 16:00–09:30 vs 09:30–16:00.  _(source: narrative_2026Q1_Apr.md)_
7. **Scheduled US macro (CPI 11 Mar, 10 Apr; NFP 6 Mar, 3 Apr; FOMC 18 Mar, 29 Apr) did not generate large Asia moves by itself** — the overnight sessions around them were flat at 18:00 (±0.2%) unless an Iran/oil headline coincided. Only the 18 Mar FOMC had a lasting rates effect (cuts priced out the next morning). BoJ decisions (19 Mar, 28 Apr) moved USD/JPY <1% and did not register in NQ Asia ranges.  _(source: narrative_2026Q1_Apr.md)_
8. **Quad witching / roll:** CME roll day 12 Mar coincided with 2026 lows and a −0.9% evening slide on the SPR headline; 20 Mar quad witching produced the window's largest RTH loss (−1.56%) with selling accelerating on a 14:43 Reuters headline and then a −0.8% Sunday gap. Testable: realised RTH range on expiry/roll days vs non-event days during the same VIX regime.  _(source: narrative_2026Q1_Apr.md)_
9. **Chip-sector idiosyncratic shocks hit RTH, not Asia:** NVDA (26 Feb), MU (19 Mar), SMCI (20 Mar), TurboQuant (26 Mar), OpenAI-miss report (28 Apr) all landed pre-market/RTH; the corresponding 18:00 ET futures prints were within ±0.2%. Exception: Korean chip reactions (Samsung/SK Hynix) amplified NQ overnight on the H200-approval/exports night (17–18 Mar).  _(source: narrative_2026Q1_Apr.md)_
10. **Safe-haven playbook inverted:** on war-escalation nights Treasuries sold (yields up), the yen weakened, and gold often fell on the biggest risk-off days (−5% on 3 Mar and 23 Mar; −10% w/w by 19 Mar). Test: correlation of overnight NQ with USD/JPY should be positive (yen down = risk-off) rather than the usual negative carry relationship.  _(source: narrative_2026Q1_Apr.md)_
11. **Asia range ≫ |Asia return|:** in the ten listed rows the median range/|return| ratio ≈1.4; even the +2.68% ceasefire night had a 3.46% range (early +0.8%, then +~3% peak, fade on Iranian violation claims). Fading the first 18:00–19:00 impulse was wrong on headline nights but right on no-headline nights (24 Mar +0.9% at 18:02 → Nikkei +2.9%; 8 Apr flat → Asia −1%).  _(source: narrative_2026Q1_Apr.md)_
1. **Mean reversion dominates after US-origin shocks; continuation dominates after Asia-origin shocks.** Of the 24 sample sessions, sign(asia) = −sign(rth) in 15. The 9 continuations are almost all nights where the catalyst was *Asian* (Jun 4 Kospi −5.5%; Jun 25 Kospi −5.8%; Jul 16 Japan AI names −9%; Jul 27 Kospi −10.8%) or the RTH move was a record-high grind (May 29, Jun 8, Jul 8, Jul 14). Test: condition on whether Kospi's close-to-close move exceeds ±3%; expect continuation when it does and reversal when it does not.  _(source: narrative_2026Q2_Jul.md)_
2. **RTH ≤ −1.5% → Asia positive.** Jun 5 (−3.45 → +0.70), Jun 16 (−1.67 → +0.79), Jun 17 (−1.63 → +0.92), Jul 2 (−2.14 → +0.68), Jul 29 (−2.04 → +0.82) — 5 of 6; the exception Jun 25 (−1.50 → −0.80) had a fresh after-hours catalyst (OpenAI IPO delay). Test: after a ≥1.5% NQ RTH drop with no new AH headline, long at 18:00 / flat at 03:00.  _(source: narrative_2026Q2_Jul.md)_
3. **Gap-and-stall RTH days (|rth| < 0.1% open-to-close after a big overnight gap up) are followed by negative Asia sessions**: Jun 8 (+0.64 is the counter-example), Jul 6 (−0.91), Jul 14 (+0.75 counter-example), Jul 10 (−0.88). Mixed — only 2 of 4; drop unless more data.  _(source: narrative_2026Q2_Jul.md)_
4. **Fed/BoJ decision nights are not the big Asia nights.** FOMC Jun 17 → +0.92; FOMC Jul 29 → +0.82; BoJ Jun 16 (Asia hours) and Jul 31 (Asia hours) coincided with Nikkei records / +4%. The hawkish-Fed reaction was absorbed in RTH; Asia bought it. Test: Asia range on FOMC night < sample median (Jun 17 rng 1.14 and Jul 29 rng 1.82 vs median ~1.3 — only partly true; range is average, direction is positive).  _(source: narrative_2026Q2_Jul.md)_
5. **CPI nights (Jun 10, Jul 14) were both positive in Asia (+1.18, +0.75)** regardless of the print's sign — because the overnight driver was a *geopolitical de-escalation* (Trump cancelling strikes; Trump dropping the Hormuz fee). Test: CPI-day Asia direction is explained by the 18:00–22:00 ET Iran headline, not by CPI.  _(source: narrative_2026Q2_Jul.md)_
6. **NFP nights: Jun 5 (hot) → Sunday +0.70; Jul 2 (weak) → +0.68.** Both positive, both after a ≥2% RTH drop. Same as pattern 2.  _(source: narrative_2026Q2_Jul.md)_
7. **Kospi open (20:00 ET) is the inflection.** On Jun 22/23, Jul 12/13, Jul 6/7 and Jul 27/28 the NQ move was flat at 18:00–20:00 and almost entirely accrued 20:00–03:00. Test: split the window at 20:00 ET; the 20:00–03:00 sub-session should carry > 80% of |asia_ret| on days where Kospi moved ≥ 5%.  _(source: narrative_2026Q2_Jul.md)_
8. **Oil was NOT the equity driver overnight except via the Fed-hike channel.** Brent spikes (May 11 +4%, Jul 13 +4%, Jul 21 +3.4%) coincided with negative NQ Asia sessions only when they came with rate-hike repricing; oil *drops* (Jun 22, Jul 27 −8.7%) did not help NQ when a chip catalyst was present. Test: regress asia_ret on Δoil and ΔKospi; expect the Kospi coefficient to dominate.  _(source: narrative_2026Q2_Jul.md)_
9. **Yen-carry did not fire.** USD/JPY stayed 158–163 all window; the one yen shock (Jul 30, −2.6% in Asian morning) coincided with a *positive* NQ session (+0.82). Tag `yen_carry` is informational, not a direction predictor in this window.  _(source: narrative_2026Q2_Jul.md)_
10. **Largest ranges (≥ 1.8%) cluster around Asia circuit-breaker days**: Jun 10 (1.89), Jun 22 (2.45), Jun 25 (2.46), Jul 29 (1.82). Test: Korean circuit breaker / sidecar flag ⇒ asia_rng above 75th percentile.  _(source: narrative_2026Q2_Jul.md)_
11. **Thin-holiday sessions were small and negative:** Jun 18→19 (Juneteenth, −0.76, rng 0.86), Jul 2→3 (+0.68 but rng 0.86). Sample too small; keep as a prior only.  _(source: narrative_2026Q2_Jul.md)_
12. **The "RTH driver" was frequently a rotation, not an index shock**: Dow records on Jun 4, Jun 16, Jun 22 (Russell), Jul 2, Jul 6, Jul 28 all came with Nasdaq down. NQ-specific overnight behaviour therefore tracked SOX/SMH and Kospi far better than ES. Test: asia_ret(NQ) − asia_ret(ES) spread should be explained by Kospi/SMH, not by S&P.  _(source: narrative_2026Q2_Jul.md)_
1. **Capitulation reversal.** After an NQ RTH loss ≥ 2%, the Asia session closed *up* with range ≥ 1%: 2/2 (Oct 16 → +0.85/1.06; Nov 5 → +1.28/2.98). Mechanism both times: forced selling at the Seoul/Tokyo open (halts, record HF tech sales) then US futures bid. Test: condition on Kospi circuit-breaker/sidecar triggered within first 30 min and NQ ≤ -2%; expect positive 18:00→03:00 return.  _(source: narrative_2026Q3_Nov.md)_
2. **Moderate-down-day continuation.** After NQ RTH between -0.3% and -1.3% with an AI/rates driver, Asia continued lower: 5/6 (Aug 17, Sep 23, Oct 12, Oct 14, Nov 6). The exception (Sep 16) was an FOMC day. Test: exclude FOMC/quarter-end days; expect negative overnight.  _(source: narrative_2026Q3_Nov.md)_
3. **Regime flip on up days (late Sep onward).** Through Sep 18, Asia after an NQ up day continued higher (3/3: Aug 4, Sep 17, Sep 18). From Sep 25, Asia faded every NQ up day (4/4: Sep 25, Oct 21, Oct 23, Nov 4), average -0.99%. Common driver: Korea/Japan semis selling (Kospi -2.7/-3.5/-1.5/-5.3%) plus an oil/Iran headline. Test: "fade the US close in Asia" worked only once Kospi was in its drawdown from the June 9,385 peak (Oct 15: -41%).  _(source: narrative_2026Q3_Nov.md)_
4. **Event-day reversals.** FOMC (Sep 16: -0.49 → +0.68) and quarter-end (Sep 30: -0.07 → +1.03) both reversed the US session; Oct 28 FOMC hold was flat RTH but Alphabet AH drove the overnight. Test: on FOMC days, overnight sign ≠ RTH sign.  _(source: narrative_2026Q3_Nov.md)_
5. **Weekend gaps are geopolitics-first, then idiosyncratic.** Sunday 18:00 opens: Sep 27 -0.2% (Trump rejected Iran deal), Oct 18 +0.4% (Iran threats but oversold), Oct 25 +0.6% (strike leaks, oil off), Nov 8 -0.8% (Nvidia probe). Friday-row Asia returns: +0.65, -0.64, +0.85, -0.71, -1.06 — sign matched the weekend's *oil* direction in 4/5 (Sep 20 oil down/NQ up; Sep 27 oil up/NQ down; Oct 18 oil down/NQ up; Oct 25 oil down but NQ down — exception; Nov 8 n/a). Test: overnight NQ sign vs Sunday-night Brent sign.  _(source: narrative_2026Q3_Nov.md)_
