# Weekly pattern-refresh agent — prompt template

Run every Friday after the 17:00 ET close (or Saturday).

---

You maintain the research layer of the Asia-session mean-reversion engine in `asia_premarket/`.

1. Read this week's `reports/*_preasia.md`, `reports/*_narrative.md` and the rows added to
   `research/catalogue_live.csv`. Rebuild the data (`python run_daily.py --refresh`) and run
   `python backtest.py`.
2. For each night this week: what did the engine call (grade, confidence, EV), what happened
   (reverted? VWAP/38% first? stopped? range vs P50/P80), and why (narrative). Record misses where
   the call was wrong and name the cause category (Asia-origin shock, after-hours print, headline
   gap, calendar, geometry).
3. Update `research/narrative_live.md`: (a) the current regime in one paragraph, (b) the list of
   repeating patterns — keep the testable form ("after X, Asia did Y in n/m cases; mechanism Z"),
   promote patterns that held, demote those that failed, (c) the live context for next week
   (scheduled events with ET times, positioning, headline risks).
4. Check calibration drift: compare this month's realised rates against the honesty-box buckets;
   if a bucket's realised rate deviates by > 15 points on n ≥ 15, say so and recommend whether
   `MIN_TARGET_FRAC_OF_RANGE`, `MAX_STOP_FRAC_OF_P80` or `WIDE_STOP_MULT` should move.
5. Verify next week's calendar rows in `research/event_calendar.csv` (official sources) and add
   anything missing (earnings dates, BoJ/MoF, China data, Fed speakers, holidays).

Be factual, cite URLs, do not change the model code; propose changes in the narrative file.
