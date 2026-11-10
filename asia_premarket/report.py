"""
Pre-Asia-open report generator.

Produces a markdown report for RTH date D (decision time 18:00 ET) answering:
  1. THE CALL        - direction, confidence meter, grade, EV per target
  2. WHERE PRICE IS  - levels and every factor that put it there
  3. WHY (attribution) - which factors push toward target vs stop, and the
                       historical record of each active rule
  4. WHERE THIS HAPPENED BEFORE - nearest analog nights + research narrative
  5. EXPECTED RANGE  - stop sizing and timing
  6. WHAT TO WATCH   - tonight's/tomorrow's scheduled events, live context
  7. HONESTY BOX     - out-of-sample model quality and today's calibration bucket
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from calendar_features import load_calendar
from model import Engine, RULES, TARGET_DESC, POINT_VALUE, confidence_from_plan
from research_catalogue import load_catalogue, narrative_for, current_context, repeating_patterns

HERE = os.path.dirname(os.path.abspath(__file__))


def _pct(x, d=2):
    return "n/a" if x is None or pd.isna(x) else f"{x*100:+.{d}f}%"


def _num(x, d=2):
    return "n/a" if x is None or pd.isna(x) else f"{x:,.{d}f}"


def _bar(conf: float, width: int = 30) -> str:
    n = int(round(conf / 100 * width))
    return "[" + "#" * n + "-" * (width - n) + f"] {conf:.0f}/100"


FEATURE_LABELS = {
    "mag": "size of RTH move (sigma)", "is_down": "RTH was a down day", "ext_in_dir": "closed at extreme in move direction",
    "vwap_in_dir": "distance beyond VWAP in move direction", "stretch20_in_dir": "move extends stretch from 20d SMA",
    "stretch50_in_dir": "move extends stretch from 50d SMA", "ret5_in_dir": "5d return in move direction",
    "gap_in_dir": "opening gap in move direction", "post_in_dir": "post-close move in move direction",
    "prior_asia_in_dir": "last night's Asia in move direction", "overnight_in_dir": "prior overnight in move direction",
    "n225_in_dir": "Nikkei in move direction", "sox_in_dir": "semis relative strength in move direction",
    "nqes_in_dir": "NQ vs ES in move direction", "yen_in_dir": "yen weakness in move direction",
    "yield_in_dir": "10y yield change in move direction", "vix_consistent": "VIX confirmed the move",
    "vix_z20": "VIX vs its 20d mean (z)", "vix": "VIX level", "rv_ratio": "5d/20d realised vol",
    "rth_range_atr": "RTH range vs ATR", "abs_streak": "length of daily streak", "rth_vol_rel": "RTH volume vs 20d",
    "asia_rng_med20": "recent Asia range (20d median)", "fomc_today": "FOMC today", "tier1_data_today": "CPI/NFP/PCE today",
    "tier1_data_tomorrow": "CPI/NFP/PCE tomorrow", "fomc_tomorrow": "FOMC tomorrow", "megacap_earnings_tonight": "mega-cap earnings tonight",
    "boj_tonight": "BoJ tonight", "opex_today": "opex today", "witching_today": "witching today", "sunday_open": "Sunday reopen",
    "pre_holiday": "US holiday tomorrow", "month_end": "month end",
}


def build_report(eng: Engine, asof=None, catalogue: pd.DataFrame | None = None) -> str:
    asof = pd.Timestamp(asof) if asof is not None else eng.f.index[-1]
    f = eng.f.loc[asof]
    s = eng.s.loc[asof]
    pred = eng.predict(asof)
    plan = pred["trade"]
    call = confidence_from_plan(plan, pred)
    cat = catalogue if catalogue is not None else load_catalogue()
    pv = POINT_VALUE.get(eng.sym, 1.0)
    asia_date = pd.Timestamp(s["asia_gdate"]) if not pd.isna(s.get("asia_gdate")) else None
    if asia_date is None:
        # live mode: the Asia session has not happened yet -> next calendar day (Sunday if Friday)
        asia_date = asof + pd.Timedelta(days=3 if asof.dayofweek == 4 else 1)
    sunday = asof.dayofweek == 4

    L = []
    L.append(f"# {eng.sym} PRE-ASIA REPORT — RTH {asof:%a %Y-%m-%d} → Asia session {asia_date:%a %Y-%m-%d} (18:00–03:00 ET)")
    L.append(f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · decision point 18:00 ET · "
             f"training window {eng.f.index[0]:%Y-%m-%d} → {asof - pd.Timedelta(days=1):%Y-%m-%d} (walk-forward, no look-ahead)_")
    L.append("")

    # ---------------- 1. THE CALL ----------------
    L.append("## 1. THE CALL")
    L.append("")
    L.append(f"**{call['call']}**  ")
    L.append(f"Confidence meter: `{_bar(call['confidence'])}`  → grade **{call['grade']}**  ")
    L.append(f"_Confidence = calibrated probability the called trade wins when it resolves (target vs stop), "
             f"out-of-sample calibrated. Grade A ≥72, B ≥63, C ≥56, else no edge._")
    L.append("")
    L.append(f"- RTH move: **{plan['rth_direction']}** {_pct(f.rth_ret)} ({_num(s.rth_open,2)} → {_num(s.rth_close,2)}), "
             f"{f.rth_ret_z:+.1f}σ of 20d daily vol · closed {'at the extreme' if f.ext_in_dir > 0.6 else 'off the extreme'} "
             f"(CLV {f.clv:+.2f}) · {abs(f.close_vs_vwap_rng):.2f} range-widths {'beyond' if f.vwap_in_dir > 0 else 'back toward'} VWAP")
    L.append(f"- Entry reference (17:00 close): **{_num(plan['entry'])}** · Stop for the fade: **{_num(plan['stop'])}** "
             f"({plan['stop_dist_pts']:.0f} pts = ${plan['stop_dist_pts']*pv:,.0f}/contract)")
    L.append(f"- Expected Asia range: median **{plan['rng_q50_pts']:.0f} pts** ({pred['rng_q50_bp']:.0f} bp), 80th pct "
             f"**{plan['rng_q80_pts']:.0f} pts** ({pred['rng_q80_bp']:.0f} bp) · model expected signed reversion {pred['exp_rev_bp']:+.0f} bp")
    L.append(f"- P(Asia closes against the RTH move) = **{pred['probs']['reverted']['cal']*100:.0f}%** "
             f"(close-to-close direction is near coin-flip historically; the path targets below carry the edge)")
    if sunday:
        L.append("- ⚠ Friday → Sunday 18:00 reopen: weekend headline gap risk; the fade entry is the Sunday open, not Friday's close.")
    L.append("")
    L.append("| Fade target | Stop variant | Target level | Dist (pts) | Stop level | Stop dist | P(target first) | P(stop first) | P(scratch) | Win rate on resolution | EV (pts) | EV ($/contract) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for vname, v in plan["variants"].items():
        for k, lab in [("vwap", "RTH VWAP"), ("r382", "38.2% retrace"), ("r500", "50% retrace")]:
            t = v["targets"][k]
            flag = " (already through)" if t["already_past"] else ""
            L.append(f"| {lab}{flag} | {vname} | {_num(t['level'])} | {t['dist_pts']:.0f} | {_num(v['stop'])} | {v['stop_dist_pts']:.0f} | "
                     f"{t['p_target']*100:.0f}% | {t['p_stop']*100:.0f}% | {t['p_scratch']*100:.0f}% | "
                     f"{t['win_rate_on_resolution']*100:.0f}% | {t['ev_pts']:+.1f} | {t['ev_usd']:+,.0f} |")
    L.append("")
    L.append("_Tight stop = RTH extreme + 10% of RTH range. Wide stop = max(0.6× recent median Asia range, 0.3× today's RTH range) from the 17:00 close. "
             "Scratch = neither target nor stop by 03:00, valued at the model's expected signed reversion return. "
             "Each (target, stop) pair has its own out-of-sample calibrated first-hit model._")
    L.append("")
    g = call.get("geometry") or {}
    if g:
        L.append("**Trade plan implied by the call**")
        L.append("")
        L.append(f"- {g['side']} {eng.sym} from the 18:00 reopen (reference {_num(g['entry'])}); target **{_num(g['target'])}** "
                 f"({g['target_dist']:.0f} pts / ${g['target_dist']*pv:,.0f}); stop **{_num(g['stop'])}** ({g['stop_dist']:.0f} pts / ${g['stop_dist']*pv:,.0f}) "
                 f"· reward:risk {g['target_dist']/max(g['stop_dist'],1e-9):.2f}")
        L.append(f"- P(target first) {g['p_win']*100:.0f}% · P(stop first) {g['p_loss']*100:.0f}% · P(neither by 03:00) {g['scratch']*100:.0f}% · "
                 f"EV **{call['ev_pts']:+.0f} pts** (${call['ev_pts']*pv:+,.0f}/contract) before costs")
        if call["call"].startswith("CONTINUATION"):
            L.append("- Continuation means: price is more likely to trade through the stop level of the fade than to retrace to VWAP first. "
                     "It is a momentum trade with the stop at VWAP, not a forecast of a large trend; use the expected range for runners.")
        if call.get("guard_failed"):
            L.append(f"- ⚠ Geometry guard failed ({'; '.join(call['guard_failed'])}): no candidate had a meaningful target, a plausible stop and positive EV. "
                     "Treat the numbers as information only.")
        L.append("")

    # evidence check: do the active named setups (with real sample sizes) agree with the call?
    rt_all = eng.rule_table(asof)
    call_is_rev = call["call"].startswith("MEAN")
    support, conflict = [], []
    for key in pred["active_rules"]:
        if key not in rt_all.index:
            continue
        r = rt_all.loc[key]
        if pd.isna(r.get("t_stat")) or r.n < 15 or abs(r.t_stat) < 1.5:
            continue
        evidence_rev = r.avg_rev_ret_bp > 0
        txt = f"{RULES[key][0]} (n={int(r.n)}, rev-rate {r.rev_rate*100:.0f}%, avg {r.avg_rev_ret_bp:+.0f} bp, t={r.t_stat:+.1f})"
        (support if evidence_rev == call_is_rev else conflict).append(txt)
    if support or conflict:
        L.append("**Does the setup evidence agree with the call?**")
        L.append("")
        for t_ in support:
            L.append(f"- ✔ supports: {t_}")
        for t_ in conflict:
            L.append(f"- ✖ CONFLICTS: {t_}")
        if conflict and call["grade"] in ("A", "B", "C"):
            L.append("- ⚠ At least one named setup with a meaningful sample points the other way. The probability models are geometry-heavy; "
                     "when a 2-sigma or FOMC-type setup conflicts, cut size or wait for the Seoul/Tokyo open (19:00–20:00 ET) to confirm.")
        L.append("")

    # ---------------- 2. WHERE PRICE IS ----------------
    L.append("## 2. WHERE PRICE IS AND WHAT PUT IT THERE")
    L.append("")
    L.append("**Levels**")
    L.append("")
    L.append("| Level | Price | vs 17:00 close |")
    L.append("|---|---|---|")
    ent = plan["entry"]
    for lab, v in [("17:00 close (entry ref)", s.post_close), ("RTH close 16:00", s.rth_close), ("RTH VWAP", s.rth_vwap),
                   ("RTH high", s.rth_high), ("RTH low", s.rth_low), ("RTH open", s.rth_open),
                   ("Prior settle", s.prev_settle), ("Prior RTH high", s.prev_rth_high), ("Prior RTH low", s.prev_rth_low),
                   ("Last Asia high", s.prior_asia_high), ("Last Asia low", s.prior_asia_low),
                   ("20d SMA", f.lvl_sma20), ("50d SMA", f.lvl_sma50), ("Fade stop", plan["stop"])]:
        if pd.isna(v):
            continue
        L.append(f"| {lab} | {_num(v)} | {v-ent:+.0f} pts ({(v/ent-1)*100:+.2f}%) |")
    L.append(f"| 20d ATR (RTH range) | {_num(f.lvl_atr20, 0)} | today's range = {f.rth_range_atr:.2f}× ATR |")
    L.append("")
    L.append("**Price structure (P)**")
    L.append("")
    L.append(f"- Session: gap at open {_pct(f.gap_open)} ({'filled' if f.gap_filled else 'not filled'}) → RTH {_pct(f.rth_ret)} → "
             f"settle-to-settle {_pct(f.day_ret)} → post-close 16-17h {_pct(f.post_ret)}")
    L.append(f"- Range {f.rth_range_atr:.2f}× ATR, high printed at {int(f.rth_hi_hour):02d}:xx, low at {int(f.rth_lo_hour):02d}:xx ET; "
             f"close location {f.clv:+.2f} (−1 low … +1 high); late-day behaviour: "
             f"{'faded toward VWAP into the close' if f.late_day_rev < -0.15 else 'held the extreme into the close' if f.ext_in_dir > 0.6 else 'neutral'}")
    L.append(f"- Broke prior RTH high: {'yes' if f.close_above_prev_high else 'no'} · below prior RTH low: {'yes' if f.close_below_prev_low else 'no'} · "
             f"vs last Asia high {f.close_vs_prior_asia_high:+.1f} ATR, vs last Asia low {f.close_vs_prior_asia_low:+.1f} ATR")
    L.append("")
    L.append("**Trend / stretch (T)**")
    L.append("")
    L.append(f"- vs 5d SMA {f.z_sma5:+.1f} ATR · vs 20d SMA **{f.z_sma20:+.1f} ATR** · vs 50d SMA **{f.z_sma50:+.1f} ATR** · 20d SMA slope {_pct(f.sma20_slope)}/5d")
    L.append(f"- 5d return {_pct(f.ret_5d)} · 20d return {_pct(f.ret_20d)} · {abs(int(f.streak))}-day {'up' if f.streak > 0 else 'down'} streak · "
             f"{_pct(f.dist_20d_high)} from 20d high · {_pct(f.dist_20d_low)} from 20d low")
    L.append(f"- Today's move **{'extends' if f.stretch20_in_dir > 0 else 'corrects'}** the stretch from the 20d mean "
             f"(stretch-in-direction {f.stretch20_in_dir:+.1f} ATR)")
    L.append("")
    L.append("**Volatility (V)**")
    L.append("")
    L.append(f"- VIX **{_num(f.vix,2)}** ({_pct(f.vix_chg,1)} today, z20 {f.vix_z20:+.1f}) · VVIX {_num(f.get('vvix'),1)} · "
             f"VIX {'CONFIRMED' if f.vix_consistent > 0.02 else 'DIVERGED from' if f.vix_consistent < -0.02 else 'was flat vs'} the equity move")
    L.append(f"- Realised vol 20d {f.rv20*100:.0f}% · 5d {f.rv5*100:.0f}% (ratio {f.rv_ratio:.2f}) · implied−realised {f.vix_minus_rv*100:+.0f} vol pts · "
             f"recent Asia range median {f.asia_rng_med20*1e4:.0f} bp, last night {f.asia_rng_prev*1e4:.0f} bp")
    L.append("")
    L.append("**Cross-asset (X)** — all closes known by 18:00 ET")
    L.append("")
    L.append(f"- Dollar: DXY {_pct(f.dxy_chg)} · USDJPY **{_num(f.usdjpy,2)}** ({_pct(f.usdjpy_chg)} today, {_pct(f.usdjpy_chg5)} 5d) "
             f"{'⚠ yen bid / carry-unwind risk' if f.usdjpy_chg < -0.008 else ''}")
    L.append(f"- Rates: US10Y **{_num(f.us10y,3)}%** ({f.us10y_chg*100:+.0f} bp today, {f.us10y_chg5*100:+.0f} bp 5d) · 3m-10y curve {f.curve_3m10y*100:+.0f} bp")
    L.append(f"- Asia equities (prior session): Nikkei {_pct(f.n225_ret)} (5d {_pct(f.n225_ret5)}) · KOSPI {_pct(f.kospi_ret)} · HSI {_pct(f.hsi_ret)} · Shanghai {_pct(f.sse_ret)} · "
             f"US-after-Tokyo divergence {_pct(f.us_after_tokyo)}")
    L.append(f"- US internals: SOX vs NQ {_pct(f.sox_minus_nq)} · RUT vs NQ {_pct(f.rut_minus_nq)} · NQ vs ES {_pct(f.nq_minus_es)} · Europe (SX5E) {_pct(f.sx5e_ret)}")
    L.append(f"- Commodities/crypto: gold {_pct(f.gold_chg)} · crude {_pct(f.crude_chg)} (5d {_pct(f.crude_chg5)}) · copper {_pct(f.copper_chg)} · BTC during US hours {_pct(f.btc_rth)}")
    L.append("")
    L.append("**Session memory (S)**")
    L.append("")
    L.append(f"- Last night's Asia {_pct(f.prior_asia_ret)} ({'already reverted the prior RTH' if f.prior_asia_reverted else 'continued the prior RTH'}) · "
             f"Europe {_pct(f.prior_eur_ret)} · full overnight into today's open {_pct(f.prior_overnight_ret)} · "
             f"RTH {'fought' if f.rth_vs_overnight < 0 else 'extended'} the overnight · RTH volume {f.rth_vol_rel:.2f}× 20d avg")
    L.append("")
    L.append("**Calendar (C)**")
    L.append("")
    ev_today = f.events_today if isinstance(f.events_today, str) and f.events_today else "none flagged"
    ev_next = f.events_tonight_tomorrow if isinstance(f.events_tonight_tomorrow, str) and f.events_tonight_tomorrow else "none flagged"
    L.append(f"- Today: {ev_today} · tonight/tomorrow: {ev_next} · days to FOMC {int(f.days_to_fomc) if not pd.isna(f.days_to_fomc) else 'n/a'} · "
             f"days since FOMC {int(f.days_since_fomc) if not pd.isna(f.days_since_fomc) else 'n/a'} · "
             f"{'MONTH-END ' if f.month_end else ''}{'PRE-HOLIDAY ' if f.pre_holiday else ''}{'SUNDAY REOPEN ' if sunday else ''}{asof:%A}")
    L.append("")

    # ---------------- 3. WHY: ATTRIBUTION ----------------
    L.append("## 3. WHY — FACTOR ATTRIBUTION")
    L.append("")
    best = plan["best"] or "vwap"
    tkey = f"hit_{best}_first"
    L.append(f"Logistic contributions (log-odds) toward **{TARGET_DESC[tkey]}** — positive pushes toward the target, negative toward the stop:")
    L.append("")
    L.append("| Factor | Tonight's value | Contribution |")
    L.append("|---|---|---|")
    contrib = pred["contrib"][tkey]
    for feat, c in contrib.head(10).items():
        v = f.get(feat)
        vs = _num(v, 3) if isinstance(v, (int, float, np.floating)) and not pd.isna(v) else str(v)
        L.append(f"| {FEATURE_LABELS.get(feat, feat)} | {vs} | {c:+.2f} {'▲' if c > 0 else '▼'} |")
    L.append("")
    cs = pred["contrib"]["stopped"]
    L.append(f"Top factors raising **stop-first** risk: " + ", ".join(f"{FEATURE_LABELS.get(k,k)} ({v:+.2f})" for k, v in cs[cs > 0].head(4).items()) + ".")
    L.append("")
    L.append("**Active setups tonight and their historical record** (data strictly before tonight; outcomes in the reversion direction)")
    L.append("")
    rt = eng.rule_table(asof)
    rt_y = eng.rule_table(asof, lookback_days=365)
    L.append("| Setup | n (all) | Rev-rate | Avg rev (bp) | VWAP first | 38% first | Stopped | Med Asia range (bp) | t | n (1y) | Rev-rate 1y |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    base = eng.o[(eng.o.valid == 1) & (eng.o.index < asof)]
    L.append(f"| _all nights (base rate)_ | {len(base)} | {base.reverted.mean()*100:.0f}% | {base.rev_ret.mean()*1e4:+.1f} | "
             f"{base.hit_vwap_first.mean()*100:.0f}% | {base.hit_r382_first.mean()*100:.0f}% | {base.stopped.mean()*100:.0f}% | "
             f"{base.asia_rng.median()*1e4:.0f} | | | |")
    for key in pred["active_rules"]:
        if key not in rt.index or rt.loc[key, "n"] == 0:
            continue
        r = rt.loc[key]
        ry = rt_y.loc[key] if key in rt_y.index else None
        L.append(f"| {RULES[key][0]} | {int(r.n)} | {r.rev_rate*100:.0f}% | {r.avg_rev_ret_bp:+.1f} | {r.vwap_first*100:.0f}% | {r.r382_first*100:.0f}% | "
                 f"{r.stopped*100:.0f}% | {r.med_rng_bp:.0f} | {r.t_stat:+.1f} | "
                 f"{int(ry.n) if ry is not None and not pd.isna(ry.n) else 0} | "
                 f"{(ry.rev_rate*100) if ry is not None and ry.n > 0 else float('nan'):.0f}% |")
    L.append("")
    L.append("_Read: 'Rev-rate' = share of nights Asia closed against the RTH move; 'VWAP first' = reached RTH VWAP before the stop; "
             "t = t-stat of the average reversion return (|t| > 2 is meaningful; most setups are not)._")
    L.append("")

    # ---------------- 4. ANALOGS ----------------
    L.append("## 4. WHERE THIS HAPPENED BEFORE — NEAREST ANALOG NIGHTS")
    L.append("")
    an = eng.analogs(asof, k=12)
    L.append(f"Nearest {len(an)} nights in setup space (same RTH direction, weighted on move size, close location, VWAP distance, stretch, VIX behaviour):")
    L.append("")
    L.append("| Date | RTH | Asia rev-ret (bp) | Retrace | VWAP first | 38% first | Stopped | Asia range (bp) | What happened (research catalogue) |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for d, r in an.iterrows():
        nar = narrative_for(cat, d) or (f"events: {r.events_today}" if isinstance(r.events_today, str) and r.events_today else "—")
        L.append(f"| {d:%Y-%m-%d %a} | {r.rth_ret*100:+.2f}% | {r.rev_ret*1e4:+.0f} | {r.retrace_frac:.2f} | {int(r.hit_vwap_first) if not pd.isna(r.hit_vwap_first) else '-'} | "
                 f"{int(r.hit_r382_first) if not pd.isna(r.hit_r382_first) else '-'} | {int(r.stopped) if not pd.isna(r.stopped) else '-'} | {r.asia_rng*1e4:.0f} | {nar} |")
    L.append("")
    L.append(f"Analog summary: reverted {an.reverted.mean()*100:.0f}% · avg rev-ret {an.rev_ret.mean()*1e4:+.0f} bp · "
             f"VWAP first {an.hit_vwap_first.mean()*100:.0f}% · stopped {an.stopped.mean()*100:.0f}% · median range {an.asia_rng.median()*1e4:.0f} bp")
    L.append("")

    # ---------------- 5. EXPECTED RANGE / TIMING ----------------
    L.append("## 5. EXPECTED RANGE AND TIMING")
    L.append("")
    hist = eng.o[(eng.o.valid == 1) & (eng.o.index < asof)]
    hv = hist["hour_vwap"].dropna()
    hs = hist["stop_hour"].dropna()
    def _hour_dist(x):
        if len(x) == 0:
            return "n/a"
        order = [18, 19, 20, 21, 22, 23, 0, 1, 2]
        c = x.astype(int).value_counts().reindex(order).fillna(0)
        return ", ".join(f"{h:02d}h {v/len(x)*100:.0f}%" for h, v in c.items() if v > 0)
    L.append(f"- Model Asia range tonight: median **{plan['rng_q50_pts']:.0f} pts** / P80 **{plan['rng_q80_pts']:.0f} pts** "
             f"(vs 20d median {f.asia_rng_med20*ent:.0f} pts). Size stops so that the stop sits outside ~0.6× the P80 range from entry unless the setup justifies the RTH-extreme stop.")
    L.append(f"- Hour the VWAP target was first reached (history): {_hour_dist(hv)}")
    L.append(f"- Hour the stop was hit (history): {_hour_dist(hs)}")
    L.append("- Typical rhythm: 18:00–20:00 reopen impulse & US after-hours news → 19:00/20:00 Tokyo cash open (Nikkei/SoftBank/Advantest), "
             "21:00–22:00 China/HK open and China data, 20:30–23:30 BoJ decisions, 01:00–03:00 pre-London positioning.")
    L.append("")

    # ---------------- 6. WHAT TO WATCH ----------------
    L.append("## 6. WHAT TO WATCH TONIGHT")
    L.append("")
    cal = load_calendar()
    # Asia-local-dated rows (boj/jp/cn/rba) dated D+1 hit tonight; US rows dated D+1 are tomorrow morning.
    win = cal[(cal.date > asof) & (cal.date <= asof + pd.Timedelta(days=4 if sunday else 2))]
    if len(win):
        for _, r in win.iterrows():
            L.append(f"- {r.date:%a %m-%d} **{r.event}** ({r.category}{', ' + str(r.time_et) + ' ET' if isinstance(r.time_et, str) and r.time_et else ''}) {r.notes if isinstance(r.notes, str) else ''}")
    else:
        L.append("- No scheduled tier-1 events in the calendar for tonight/tomorrow.")
    L.append("")
    L.append("**Conditional notes**")
    L.append("")
    notes = []
    if f.boj_tonight:
        notes.append("BoJ decision tonight: historically the yen reaction (not the rate decision) drives NQ in Tokyo hours; a hawkish surprise → USDJPY down → NQ down.")
    if f.tier1_data_tomorrow:
        notes.append("CPI/NFP/PCE tomorrow morning: Asia tends to position rather than trend; expect range compression into 03:00 and fade extremes.")
    if f.fomc_today:
        notes.append("FOMC was today: post-FOMC Asia sessions reverted the RTH move more often than average in this sample (see rule table).")
    if f.megacap_earnings_tonight:
        notes.append("Mega-cap earnings at ~16:05 ET: the after-hours print overrides the RTH narrative; check the 16:00-17:00 bar move (post-close) above before fading.")
    if sunday:
        notes.append("Sunday reopen: weekend headlines (tariffs, geopolitics, Fed speak) gap the open; the fade entry is the 18:00 print, and gaps > 0.5% have tended to extend early before mean-reverting.")
    if f.vix_consistent < -0.03:
        notes.append("VIX diverged from the equity move today: that divergence has historically raised stop-first risk for fades (see attribution).")
    if abs(f.n225_ret) > 0.02:
        notes.append(f"Nikkei moved {_pct(f.n225_ret)} last session: a second-day Tokyo follow-through at 19:00/20:00 ET is the main path risk tonight.")
    if f.usdjpy_chg < -0.008:
        notes.append("Yen strengthened sharply: watch USDJPY 150/155/160 handles and MoF intervention risk in Tokyo hours.")
    if f.rth_ret_z < -2:
        notes.append("Two-sigma down day: these reverted more often than average, but when they didn't (fresh after-hours AI/semis catalyst, Asia-origin chip rout) the losses were large. Confirm Kospi/Nikkei open before adding.")
    if f.rth_ret_z > 2:
        notes.append("Two-sigma up day: these continued more often than they reverted; fading requires a post-close fade or VIX divergence.")
    if not notes:
        notes.append("No special conditional flags; trade the levels and the expected range.")
    for n in notes:
        L.append(f"- {n}")
    L.append("")
    L.append("**Invalidation**")
    L.append("")
    L.append(f"- Fade is wrong if price trades through **{_num(plan['stop'])}** (RTH extreme + 10% range) — especially before 21:00 ET (reopen momentum) or on a Tokyo-open impulse.")
    L.append(f"- Continuation is wrong if price reclaims VWAP **{_num(s.rth_vwap)}** and holds it through the China open (21:30 ET).")
    cc = current_context()
    if cc:
        L.append("")
        L.append("**Live macro context (from the research layer)**")
        L.append("")
        L.append(cc.strip())
    L.append("")

    # ---------------- 7. HONESTY BOX ----------------
    L.append("## 7. HONESTY BOX — HOW GOOD IS THIS MODEL OUT OF SAMPLE?")
    L.append("")
    L.append("| Outcome | OOS n | Base rate | Brier (base) | Brier (model) | Accuracy | Tonight's p | Realised rate in tonight's bucket |")
    L.append("|---|---|---|---|---|---|---|---|")
    for tgt, fit in eng.fits.items():
        e = fit.eval
        p = pred["probs"][tgt]["cal"]
        b = e["buckets"]
        realised = "n/a"
        for iv, r in b.iterrows():
            if p in iv:
                realised = f"{r.realised*100:.0f}% (n={int(r.n)})"
        L.append(f"| {tgt} | {e['n']} | {e['base_rate']*100:.0f}% | {e['base_brier']:.3f} | {e['p_cal_brier']:.3f} | {e['p_cal_acc']*100:.0f}% | {p*100:.0f}% | {realised} |")
    L.append("")
    L.append(f"- Asia-range median model: OOS MAE {eng.regs['rng_q50_oos_mae_bp']:.0f} bp vs naive {eng.regs['rng_q50_naive_mae_bp']:.0f} bp; "
             f"coverage of the median {eng.regs['rng_q50_oos_coverage']*100:.0f}% (should be ≈50%; below it means the recent regime is more volatile than the training window).")
    L.append(f"- Signed-magnitude model (expected reversion return): OOS R² {eng.regs['exp_rev_oos_r2']:+.2f}; "
             f"the scratch outcome in the EV table is therefore weighted by {eng.regs['exp_rev_shrink']:.2f} (0 = no skill, ignored).")
    L.append("- Brier below the base-rate Brier = the model adds information. Close-to-close direction ('reverted') is barely better than a coin flip; "
             "the path outcomes (VWAP/38% first, stopped) are where the edge is. Treat grades below B as information, not a trade.")
    L.append("- Much of the path-outcome skill is geometry: how far the targets and the stop sit from the entry relative to the expected Asia range. "
             "That is exactly what a fade trade needs, but it means a high-confidence CONTINUATION call often says 'the fade stop is too close', not 'a trend is coming'.")
    L.append("- Sample: ~17 months of hourly Globex data; the 'past year' is ~250 nights. Rare setups (n < 15) are anecdotes, not statistics.")
    L.append("")
    pats = repeating_patterns()
    if pats:
        L.append("## 8. REPEATING PATTERNS FROM THE YEAR-LONG RESEARCH LAYER")
        L.append("")
        for p_ in pats[:40]:
            L.append(p_)
        L.append("")
    return "\n".join(L)


def agent_brief(eng: Engine, asof=None) -> str:
    """A brief for the daily narrative agent: what to research before Asia opens."""
    asof = pd.Timestamp(asof) if asof is not None else eng.f.index[-1]
    f = eng.f.loc[asof]
    s = eng.s.loc[asof]
    pred = eng.predict(asof)
    call = confidence_from_plan(pred["trade"], pred)
    L = [f"# Daily narrative brief — {eng.sym} RTH {asof:%Y-%m-%d} (pre-Asia)", "",
         "You are the macro/markets narrative agent. Using web search on today's news (same-day sources), answer:", "",
         f"1. WHY did {eng.sym} move {f.rth_ret*100:+.2f}% in RTH today (open {s.rth_open:,.2f} → close {s.rth_close:,.2f}; high {s.rth_high:,.2f} at {int(f.rth_hi_hour):02d}h, low {s.rth_low:,.2f} at {int(f.rth_lo_hour):02d}h ET)? "
         f"Name the catalysts with timestamps (data prints, Fed speak, earnings, headlines, flows, options/gamma, index rebalances).",
         f"2. What happened after the close (16:00-17:00 move {f.post_ret*100:+.2f}%)? Any earnings, guidance, policy headlines, Treasury/FX moves?",
         f"3. Cross-asset context: VIX {f.vix:.2f} ({f.vix_chg*100:+.1f}%), USDJPY {f.usdjpy:.2f} ({f.usdjpy_chg*100:+.2f}%), US10Y {f.us10y:.3f}% ({f.us10y_chg*100:+.0f} bp), "
         f"DXY {f.dxy_chg*100:+.2f}%, crude {f.crude_chg*100:+.2f}%, gold {f.gold_chg*100:+.2f}%, SOX vs NQ {f.sox_minus_nq*100:+.2f}%, BTC in US hours {f.btc_rth*100:+.2f}%. Which of these is the market's current driver?",
         f"4. What is scheduled in the Asia session tonight and tomorrow morning (BoJ, Japan/China/Korea data, Nikkei/Kospi expectations, US data, Fed speakers, earnings)? "
         f"Calendar flags: {f.events_today or 'none'} | tonight/tomorrow: {f.events_tonight_tomorrow or 'none'}.",
         "5. What are traders/strategists saying about positioning into tonight (CTA/vol-control flows, dealer gamma, buybacks, month-end)?",
         "", f"The quantitative engine's call: **{call['call']}** confidence {call['confidence']}/100 grade {call['grade']}; active setups: {', '.join(pred['active_rules'])}.",
         "State whether the news flow supports or contradicts that call and why. Cite URLs. Do not invent facts; say 'unverified' where you cannot confirm.",
         "", "Write the answer as markdown to reports/<date>_<SYM>_narrative.md and append a one-line entry to research/catalogue_live.csv with columns date,rth_driver,asia_driver,tags,sources (asia_driver = 'pending')."]
    return "\n".join(L)
