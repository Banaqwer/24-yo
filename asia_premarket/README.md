# Asia-session pre-market mean-reversion engine (NQ / ES)

A daily, pre-Asia-open (18:00 ET Globex reopen) quantitative report for Nasdaq-100 (NQ) and
S&P 500 (ES) futures. At 17:xx ET it answers:

1. **Where is price and what put it there** — every factor knowable at 18:00 ET: RTH move, gap,
   close location, VWAP distance, stretch from 20/50-day means, streaks, realised and implied
   volatility, dollar, yen, yields, Nikkei/KOSPI/HSI, semis vs NQ, gold/oil/copper/BTC, what the
   prior Asia/Europe sessions did, and the calendar (FOMC, CPI/NFP/PCE, BoJ, China data, opex,
   roll, earnings, Sunday reopen, holidays, month-end).
2. **Why** — which factors push toward a reversion target vs toward the stop (logistic
   attribution) and the historical record of every setup that is active tonight.
3. **Where in the past this happened** — the nearest analog nights with their realised Asia
   outcome and the narrative from the agent-built research catalogue (what moved it then).
4. **The call** — a calibrated confidence meter (0–100) and grade (A/B/C/no edge) for the trade
   that resolves best: fade to VWAP / 38.2% / 50% retrace with a tight or wide stop, or
   continuation, with expected value in points and dollars, expected Asia range, timing, what
   to watch tonight, and invalidation levels.
5. **Honesty box** — out-of-sample quality of every probability and tonight's calibration bucket.

## Run it

```bash
pip install -r asia_premarket/requirements.txt
cd asia_premarket
python run_daily.py --refresh              # pull data, write reports/latest_NQ.md and latest_ES.md
python run_daily.py --sym NQ --date 2026-11-05   # replay any past night
python backtest.py                         # research/backtest_report.md (walk-forward, both symbols)
```

Run it after the 17:00 ET futures close (data is final) and before the 18:00 reopen. A cron
line for 17:20 ET on weekdays (UTC 22:20 in winter, 21:20 in summer):

```
20 22 * * 1-5 cd /path/to/asia_premarket && python run_daily.py --refresh >> logs/run.log 2>&1
```

Each run also writes `reports/<date>_<SYM>_agent_brief.md`: the brief for the daily narrative
agent (see "Agents" below).

## Layout

| File | What it does |
|---|---|
| `sessions.py` | Slices hourly Globex bars (US/Eastern) into RTH 09:00–16:00, post-close 16:00–17:00, Asia 18:00–03:00, Europe 03:00–09:00. Walks the Asia bars hour by hour to resolve target-before-stop outcomes. |
| `features.py` | ~110 features knowable at 18:00 ET, plus direction-framed versions (relative to the RTH move) used by the models. Targets (what Asia did). |
| `calendar_features.py` | Structural calendar (FOMC, opex, roll, witching, holidays) merged with the agent-verified `research/event_calendar.csv`. |
| `model.py` | Rule library (60+ named setups with point-in-time statistics), walk-forward ensemble (regularised logistic + shallow GBM, isotonic calibration) for 9 outcomes, quantile models for the Asia range, nearest-neighbour analogs, trade-plan EV and the geometry guard. |
| `report.py` | The markdown report and the agent brief. |
| `backtest.py` | Walk-forward evaluation, calibration tables, simulated decisions, asymmetry tables, full rule tables. |
| `run_daily.py` | Entry point (refresh data, build reports). |
| `research_catalogue.py` | Loads the agent-built catalogue/narratives into the report. |
| `data/` | Hourly NQ/ES/BTC, 15-minute NQ/ES (60 days), daily cross-asset closes (3 years). Snapshot; refreshed by `--refresh`. |
| `research/` | Agent outputs: `event_calendar.csv` (826 verified events 2024-06 → 2027-01), four quarterly `catalogue_*.csv` (why each big Asia night moved, tagged, with sources), four `narrative_*.md` (regime narratives, testable repeating patterns, live context), `backtest_report.md`. |
| `reports/` | Daily reports and agent briefs. |

## Method

**Decision point.** RTH date D at 18:00 ET. Outcome = the Asia session 18:00 D → 03:00 D+1
(Friday → Sunday 18:00 reopen). Entry reference = 17:00 close.

**Outcomes modelled (each with its own walk-forward classifier):**

- `reverted` — Asia closes against the RTH move (close-to-close). Near coin-flip out of sample;
  reported, not traded.
- `hit_vwap_first`, `hit_r382_first`, `hit_r500_first`, `stopped` — first-hit outcomes for a fade
  with the *tight* stop (RTH extreme + 10% of RTH range).
- the same four with `_w` — with the *wide* stop (max(0.6× recent median Asia range,
  0.3× today's RTH range) from the 17:00 close).

**Training.** Expanding window, retrained monthly, first 150 nights training-only; predictions
are strictly out of sample. Probabilities are averaged across the logistic and GBM models and
calibrated with isotonic regression on the pooled OOS predictions. Features are the compact
direction-framed set (`FEATURE_COLS_COMPACT`).

**Confidence meter.** For every (stop variant × target × side) candidate: EV = P(target first)
× min(target distance, P80 range) − P(stop first) × stop distance + P(scratch) × shrunk expected
reversion. The call is the highest-EV candidate that passes the geometry guard (target ≥ 25%
of expected median range, stop ≤ P80 range, EV ≥ 3% of range, target more likely than stop).
Confidence = P(target first) / (P(target first) + P(stop first)); A ≥ 72, B ≥ 63, C ≥ 56.

**What the backtest says (see `research/backtest_report.md`).** Close-to-close direction is
not predictable here (OOS accuracy ≈ 51–53%, Brier ≈ base rate). The path outcomes are:
P(VWAP before tight stop) OOS accuracy ≈ 80% (Brier 0.146 vs 0.250 base), 38% retrace ≈ 72%,
stop-first ≈ 72%. Much of that skill is geometry (where the levels sit relative to the expected
range), which is exactly what a fade trade needs, but it means the engine says **NO EDGE** on
most nights. That is the honest output: the edge is in selecting nights and sizing stops, not in
calling direction every day.

**Simulated decisions, out of sample (first-hit resolution, no costs), from `research/backtest_report.md`:**

| | NQ Grade A | NQ Grade B | NQ Grade C | ES Grade A | ES Grade B | ES Grade C |
|---|---|---|---|---|---|---|
| nights | 78 | 79 | 39 | 73 | 63 | 41 |
| win rate | 69% | 46% | 49% | 62% | 63% | 46% |
| avg pts / night | +21.3 | −10.0 | −14.3 | +2.7 | +4.0 | −2.1 |

Only Grade A (NQ) and Grade A/B (ES) had positive expectancy out of sample. Treat Grade C as
no-trade and Grade B on NQ as information only until more nights accumulate.

## Findings from the year (research layer + data)

- After a ≥1% RTH selloff Asia reverted ~62% of the time (n≈80); after a ≥2% RTH rally it tended
  to continue (VWAP first 0/9). The asymmetry is the single most robust structural fact.
- US-origin shocks (data, Fed, US earnings) were faded in Asia; Asia-origin shocks (Kospi/Nikkei
  chip routs, circuit breakers at the 19:00–20:00 ET Seoul/Tokyo open) continued. Conditioning
  on the Seoul open is the main path risk on big nights.
- After-the-close mega-cap/semis prints override the RTH direction; the post-close 16:00–17:00
  bar is a leading signal.
- Scheduled US macro (CPI/NFP/FOMC) rarely drove the Asia session by itself; oil/Iran headlines,
  Trump posts 18:00–21:30 ET, and BoJ/MoF yen signals did.
- Sunday reopens gap on weekend headlines regardless of Friday's sign; the gap direction tracked
  Sunday-night Brent in the war months.

## Agents

The system is built to be run with agents, not just scripts:

- **Year-review agents (done, outputs in `research/`)**: four quarterly research agents explained
  the drivers of every large Asia night Nov 2025 → Nov 2026 and wrote testable repeating patterns;
  a calendar agent verified 826 scheduled events from official sources.
- **Daily narrative agent**: each run writes `reports/<date>_<SYM>_agent_brief.md`. Give it to an
  agent with web search before 18:00 ET; it explains today's RTH move, after-hours news, and
  tonight's Asia calendar, states whether the news supports or contradicts the quantitative call,
  and appends to `research/catalogue_live.csv` so the catalogue keeps growing. Prompt template in
  `agent_prompts/daily_narrative.md`.
- **Weekly pattern-refresh agent**: `agent_prompts/weekly_patterns.md` — re-reads the last week's
  reports and outcomes, updates the repeating-patterns list, flags calibration drift.

## Caveats

- 17 months of hourly data (yfinance, 730-day limit for 1h bars); ~330 out-of-sample nights.
  Rare setups are anecdotes. Hourly bars make the first-hit resolution conservative (both levels
  in one bar = stopped).
- No slippage/commissions. Asia Globex liquidity is thin; size for the P80 range.
- Regimes shift: the window contains the Aug-2024 carry unwind, Apr-2025 tariff shock, the 2026
  Iran war, the Jun–Jul 2026 chip unwind and the Nov-5-2026 crash. The honesty box shows when the
  range model is under-covering (recent regime more volatile than the training set).
- Not investment advice. Paper-trade the grades before risking capital.
