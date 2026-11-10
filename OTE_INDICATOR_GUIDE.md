# OTE (Optimal Trade Entry) Indicator

Built from the video **"How To Properly Use OTE. (Optimal Trade Entry)"** by *The Source*
(YouTube channel @jaelandfaiz, published 13 Aug 2026, about 14 minutes, charts on the Micro
Nasdaq futures in TradingView).

Files

| File | What it is |
| --- | --- |
| `ote_indicator.py` | Python indicator (pandas/numpy), CLI, chart export, naive forward evaluation |
| `ote_indicator.pine` | TradingView Pine Script v5 version with the same rules, alerts and a status table |
| `test_ote_indicator.py` | 8 tests: level math, long/short detection, trap rejection, no look-ahead, HTF filter |
| `ote_results/` | Sample output: charts and setup tables for NQ 15m, EURUSD 1h, BTC 1h |

> How the video content was recovered: YouTube blocks transcript downloads from this cloud
> environment, so the spoken audio could not be read. The chapter markers, the on-screen
> checklist and the chapter thumbnails were recovered from the watch page. Everything in
> the "What the video teaches" section that is marked *(inferred)* is standard ICT OTE
> teaching that fills in what those frames show but the audio would have spelled out.

---

## 1. What the video teaches

### Chapters

| Time | Chapter | What is on screen |
| --- | --- | --- |
| 0:00 | Introduction to OTE | |
| 0:37 | Defining OTE range mechanics | Hand-drawn zig-zag, then one impulsive leg down; a box is drawn over the *whole* leg (swing high to swing low) with the entry levels marked inside |
| 1:53 | Short position example | Micro Nasdaq, intraday |
| 4:22 | Long position example | Micro Nasdaq; the leg's high is marked with a horizontal line, price later rallies back to it |
| 7:22 | Avoiding OTE traps | A fib drawn on a leg near the top of a larger move, with a long position that gets stopped |
| 9:13 | OTE trading checklist | The six-line checklist below |
| 13:06 | Final thoughts and closing | |

### The checklist (verbatim from the screen)

1. **Confirm your HTF bias**
2. **Mark out a proper OTE zone**
3. **Wait patiently for market to** reach the zone
4. **Wait for consolidation before** entering
5. **Target expansions or scalps**
6. "ez win"

### The mechanics, step by step

**The range.** OTE is a Fibonacci retracement drawn across one *impulsive* leg, wick to wick.
For a long: anchor 1.0 at the swing low where the move started and 0.0 at the swing high
where it ended. For a short: 1.0 at the swing high, 0.0 at the swing low. The retracement
levels are measured back from the 0.0 extreme toward the origin:

```
price(ratio) = extreme - (extreme - origin) * ratio
```

| Ratio | Role |
| --- | --- |
| 0.0 | Leg extreme. First target ("scalp"). |
| 0.5 | Equilibrium. Above it (for a long) the pullback is still "premium"; OTE sits below it. |
| 0.62 | Start of the OTE zone |
| **0.705** | Sweet spot, the ideal entry |
| 0.79 | End of the OTE zone. Beyond here the leg is being fully retraced |
| 1.0 | Leg origin. The stop goes just beyond this |
| -0.27, -0.62, -1.0 | Expansion targets. -1.0 is the "symmetrical price swing" |

**What makes a zone "proper"** *(inferred from the mechanics frame and the traps chapter)*:

- The leg must be impulsive, not a drift. A displacement leg is large relative to recent
  bars and usually leaves imbalance (fair value gaps) behind it.
- The leg should **break structure**: a bullish leg takes out the previous swing high
  (break of structure / market structure shift). A leg that fails to do that is just a
  bounce inside a range, and its OTE has no edge.
- Ideally the origin of the leg **swept liquidity**: the low where the rally started took
  out an earlier low first (stop raid), then price displaced the other way.
- The fib is drawn on the *most recent* leg. If price makes a new high before pulling back
  into the zone, the zone is redrawn from the new high. Old zones are stale.

**Waiting for the tap.** The zone is only an area of interest until price trades into it.
Entering before the 0.62 level means buying a premium, which is the opposite of what OTE
is for.

**Waiting for consolidation.** This is the point the video stresses. Price reaching 0.705
is not the entry. The entry is when price *stops making new lows inside the zone* for a
couple of candles (or closes back above the 0.62 level). This filters the "trap": a leg
that is simply being retraced in full, where price slices through 0.62, 0.705, 0.79 and the
origin in one go.

**Targets.** Either a scalp back to the leg extreme (ratio 0.0) or the expansions at
-0.27, -0.62 and -1.0, or an obvious pool of liquidity (old high/low) in the direction of
the HTF bias.

**The traps** *(inferred)*: trading OTE against the HTF bias; drawing it on a leg that did
not break structure; entering at the first touch with no confirmation; keeping a stale zone
after price has already made a new high; using candle bodies instead of wicks for the
anchors.

---

## 2. How the indicator replicates it

| Checklist step | Python (`OTEConfig`) | Pine input |
| --- | --- | --- |
| 1. HTF bias | `htf="1h"`, `bias_mode="structure"` (or `"range"` for premium/discount, `"none"` to disable) | *Filter by higher-timeframe bias*, *Higher timeframe* |
| 2. Proper zone | `swing_len`, `min_leg_atr=1.5`, `require_structure_break=True`, `require_sweep=False` | *Pivot strength*, *Min leg size*, *Require structure break*, *Require liquidity sweep* |
| 3. Wait for the tap | state machine `armed -> tapped`; `max_wait_bars` expires untouched zones; a new extreme supersedes the zone | same logic, zone box drawn only after the pivot confirms |
| 4. Consolidation | `confirm_mode="consolidation"`, `confirm_bars=2` (also `"reclaim"` and `"touch"`) | *Confirmation*, *Consolidation bars* |
| 5. Targets | `tp_levels=(0.0, -0.27, -0.62, -1.0)`, `eval_tp_index=1` | TP1..TP4 ratios |

### Setup life cycle

```
pivot confirmed  ->  armed  ->  tapped (price in 0.62-0.79)  ->  entered  ->  win / loss / timeout
                       |            |
                       |            +-- invalidated : traded through the origin before confirming (the trap)
                       |            +-- missed      : left the zone and made a new extreme without confirming
                       +-- superseded : new extreme before the tap, zone redrawn from the new pivot
                       +-- expired    : never tapped within max_wait_bars
```

A swing point is only known `swing_len` bars after it prints, so a leg is only "marked out"
once its extreme is confirmed. The bars between the pivot and its confirmation are replayed
(their prices are already known at that moment) so a zone that was already tapped shows as
tapped, but an entry can never be back-dated. `test_no_lookahead` checks that computing the
indicator on a truncated series gives exactly the same states and signals as the prefix of
the full run.

### HTF bias (`structure` mode)

The bars are resampled to the higher timeframe. On that series a bullish break (close above
the last confirmed HTF pivot high) sets the bias to +1, a bearish break sets it to -1. Each
HTF bar's value is only used after that bar has closed. Long zones are only created while
the bias is +1, short zones while it is -1.

### Output columns (Python)

`ote_dir` (+1/-1/0), `ote_state`, `ote_signal` (+1 long entry, -1 short entry on that bar),
`lv_0`, `lv_50`, `lv_62`, `lv_705`, `lv_79`, `lv_100`, `ote_sl`, `ote_tp1..tp4`,
`htf_bias`, `pivot_high`, `pivot_low`, `atr`. `OTEResult.setups` holds every leg with its
state, levels, entry/exit and R multiple; `OTEResult.summary()` aggregates them.

---

## 3. Usage

```bash
# NQ futures, 15-minute bars, 1-hour bias, chart of the last 400 bars
python ote_indicator.py --symbol NQ=F --interval 15m --period 30d --htf 1h --plot --last 400

# FX pair, 1-hour bars, 4-hour bias, entry only on a close back above/below 0.62
python ote_indicator.py --symbol EURUSD=X --interval 1h --period 60d --htf 4h --confirm reclaim

# Your own bars (CSV with a datetime index and open/high/low/close columns)
python ote_indicator.py --csv bars.csv --htf 4h --sweep --session 09:30-11:00

# Tests
python test_ote_indicator.py
```

```python
from ote_indicator import OTEConfig, compute_ote, plot_ote
res = compute_ote(df, OTEConfig(swing_len=5, htf="1h", confirm_mode="consolidation"))
res.frame[["close", "ote_dir", "ote_state", "lv_62", "lv_705", "lv_79", "ote_sl", "ote_signal"]].tail(20)
res.summary()
plot_ote(res, last=300, path="chart.png")
```

TradingView: open the Pine editor, paste `ote_indicator.pine`, add to chart. Blue boxes are
long zones, pink boxes short zones, the dashed line is 0.705. Boxes turn more opaque when
tapped. Triangles mark confirmed entries, with stop (red) and target (teal) lines. Four
alerts are provided: zone armed, zone tapped, long entry, short entry. The top-right table
shows the current HTF bias and the state of each zone.

---

## 4. Validation result (10 Nov 2026)

The indicator was run through the same four pillars as the Hurst system
(`ote_validation_pipeline.py`, mirroring `hurst_validation_pipeline.py`): backtest with
costs and 1% risk per trade, buy-and-hold benchmark, 1000-path bootstrap Monte Carlo, and
two walk-forward tests (default rules on 4 sequential out-of-sample periods, plus a real
walk-forward optimisation over 144 parameter sets). 16 market/timeframe combinations:
9 hourly (2 years, 4h bias: NQ, ES, GC, CL, EURUSD, GBPUSD, USDJPY, BTC, ETH) and 7 daily
(15 years, weekly bias: SPY, QQQ, GLD, TLT, NVDA, AAPL, BTC).

**Verdict: the OTE rules as taught do not have a demonstrable edge. 0 of 16 markets pass.**

| | Default rules, all markets |
| --- | --- |
| Trades | 1717 |
| Trade-weighted average net R | -0.10 R |
| Total net R | -173 R |
| Markets with positive expectancy | 4 of 16 (BTC 1h, SPY, QQQ, BTC daily, all small) |
| Win rate | 33% to 46%, median 36% |
| Monte Carlo: markets ≥ 70% profitable paths | 1 of 16 (SPY daily, 75%) |
| Walk-forward: markets with ≥ 2 of 4 OOS periods positive | 5 of 16 |
| Walk-forward optimisation: OOS positive in both windows | 3 of 16 |

The sensitivity study (`ote_sensitivity.py`) checks that this is not a modelling artefact:

- **Fill assumption**: only 1 of 1717 trades hit stop and target on the same bar, so the
  conservative stop-first rule changes nothing.
- **Parameter grid, in-sample**: across 144 settings the median parameter set loses on 14 of
  16 markets. The best in-sample set per market is positive, as always, but the walk-forward
  optimisation shows those picks do not carry forward.
- **Rule ablation**: removing the HTF bias or the structure-break requirement makes results
  *worse* (-221 R and -262 R versus -173 R), so those two checklist items do filter bad
  trades. Requiring a liquidity sweep at the origin cuts trades by two thirds and halves the
  loss (-88 R) but does not make it positive. The least bad target is the -1.0 symmetrical
  expansion (-23 R in total, positive on 8 of 16 markets); scalping to the range extreme is
  the worst (-284 R).
- **Session filter** (index futures, New York morning): NQ turns slightly positive in the
  09:00-12:00 ET window (+6.5 R on 61 trades), ES does not. Too few trades to mean anything.

Reports: `ote_validation_results/OTE_VALIDATION_REPORT.md` (per-market detail) and
`ote_validation_results/OTE_SENSITIVITY.md`.

What this means in practice: use the indicator as what it is, a structured way to mark the
0.62-0.79 retracement of a displacement leg and to wait for the tap and the consolidation.
As a standalone signal generator it has not earned capital. If you want to keep working on
it, the two directions the data points at are (a) requiring the liquidity sweep plus the
HTF bias and taking the -1.0 symmetrical target, and (b) adding confluence the indicator
does not yet see (fair value gaps, order blocks, session timing), then re-running the
pipeline.

---

## 5. Parameters worth tuning

- `swing_len`: 3 for very fast intraday structure, 5 default, 8-10 for swing legs.
- `min_leg_atr`: raise to 2-3 to only keep clear displacement legs.
- `require_sweep=True`: the strictest "proper zone" definition (sweep then displacement).
- `confirm_bars`: 2 default; 3 is more patient, 1 is close to trading the first touch.
- `eval_tp_index`: 0 scalps to the leg extreme, 1 to 3 target the expansions.
- `session`: e.g. `("09:30","11:00")` to restrict entries to the New York morning on index futures.
