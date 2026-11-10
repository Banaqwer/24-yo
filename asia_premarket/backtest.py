"""
Walk-forward backtest and research report for the Asia-session mean-reversion engine.
Writes research/backtest_report.md (NQ and ES).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

from model import Engine, RULES, TARGET_DESC, POINT_VALUE, confidence_from_plan

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "research", "backtest_report.md")


def simulate(eng: Engine, start: str | None = None) -> pd.DataFrame:
    """Replay the daily decision using only out-of-sample probabilities (walk-forward)."""
    rows = []
    oos_idx = eng.fits["stopped"].oos.index
    for d in oos_idx:
        if start and d < pd.Timestamp(start):
            continue
        s, f, o = eng.s.loc[d], eng.f.loc[d], eng.o.loc[d]
        if d not in eng.fits["stopped_w"].oos.index:
            continue
        probs = {t: {"cal": float(eng.fits[t].oos.loc[d, "p_cal"])} for t in eng.fits}
        # range quantiles are needed by the geometry guard; use the in-sample quantile model (range, not direction)
        X = eng.f.loc[[d], eng.cols].astype(float)
        pred = {"probs": probs, "rng_q50_bp": float(eng.regs["rng_q50"].predict(X)[0]),
                "rng_q80_bp": float(eng.regs["rng_q80"].predict(X)[0]), "exp_rev_bp": float(eng.regs["exp_rev_bp"].predict(X)[0])}
        plan = eng.trade_plan(d, pred)
        call = confidence_from_plan(plan, pred)
        g = call.get("geometry") or {}
        # realised P&L of the called trade (points), resolved by first-hit logic from the recorded outcomes
        pnl = np.nan
        if call["grade"] != "NO EDGE" and g:
            sfx = "_w" if g["variant"] == "wide" else ""
            if call["call"].startswith("MEAN"):
                hit = o[f"hit_{g['target_key']}_first{sfx}"]
                if hit == 1:
                    pnl = g["target_dist"]
                elif o[f"stopped{sfx}"] == 1:
                    pnl = -g["stop_dist"]
                else:  # scratch at 03:00: close-to-open return in the reversion direction
                    pnl = o["rev_ret"] * plan["entry"]
            else:  # continuation: enter with the move, target = the fade's stop level, stop = VWAP
                if o[f"stopped{sfx}"] == 1:
                    pnl = g["target_dist"]
                elif o[f"hit_vwap_first{sfx}"] == 1:
                    pnl = -g["stop_dist"]
                else:
                    pnl = -o["rev_ret"] * plan["entry"]
        rows.append(dict(date=d, call=call["call"].split(":")[0], grade=call["grade"], confidence=call["confidence"],
                         ev_pts=call.get("ev_pts", np.nan), variant=g.get("variant"), best=g.get("target_key"), pnl_pts=pnl,
                         rth_ret=f.rth_ret, rev_ret_bp=o.rev_ret * 1e4, stopped=o.stopped, vwap_first=o.hit_vwap_first))
    return pd.DataFrame(rows).set_index("date")


def md_table(df: pd.DataFrame, floatfmt="{:.3f}") -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join([df.index.name or ""] + [str(c) for c in cols]) + " |", "|" + "---|" * (len(cols) + 1)]
    for i, r in df.iterrows():
        vals = []
        for c in cols:
            v = r[c]
            vals.append(floatfmt.format(v) if isinstance(v, (float, np.floating)) and not pd.isna(v) else str(v))
        out.append("| " + " | ".join([str(i)] + vals) + " |")
    return "\n".join(out)


def main(syms=("NQ", "ES")):
    L = ["# Asia-session mean-reversion engine — walk-forward backtest report", "",
         "Decision at 18:00 ET on RTH date D; outcome = Asia session 18:00 D → 03:00 D+1. "
         "Every probability below is out-of-sample: models are retrained each month on data strictly before that month "
         "(expanding window, first 150 nights are training only). Isotonic calibration is fitted on the pooled OOS predictions.", ""]
    for sym in syms:
        eng = Engine(sym).train()
        pv = POINT_VALUE[sym]
        L.append(f"## {sym}")
        L.append("")
        L.append(f"Data: hourly Globex bars {eng.f.index[0]:%Y-%m-%d} → {eng.f.index[-1]:%Y-%m-%d}, {len(eng.f)} RTH days, "
                 f"{int((eng.o.valid==1).sum())} nights with an RTH move ≥ 0.15%.")
        L.append("")
        L.append("### Out-of-sample probability quality")
        L.append("")
        L.append("| Outcome | description | OOS n | base rate | Brier base | Brier logit | Brier GBM | Brier calibrated | accuracy |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for t, fit in eng.fits.items():
            e = fit.eval
            L.append(f"| {t} | {TARGET_DESC[t]} | {e['n']} | {e['base_rate']*100:.0f}% | {e['base_brier']:.3f} | {e['p_logit_brier']:.3f} | "
                     f"{e['p_gbm_brier']:.3f} | **{e['p_cal_brier']:.3f}** | {e['p_cal_acc']*100:.0f}% |")
        L.append("")
        L.append("Calibration buckets (calibrated p vs realised):")
        L.append("")
        for t, fit in eng.fits.items():
            b = fit.eval["buckets"].copy()
            b.index = [str(i) for i in b.index]
            b.index.name = f"{t} bucket"
            L.append(md_table(b, "{:.2f}"))
            L.append("")
        L.append("### Simulated decisions (OOS, first-hit resolution, no slippage)")
        L.append("")
        sim = simulate(eng)
        sim.to_csv(os.path.join(HERE, "research", f"backtest_trades_{sym}.csv"))
        traded = sim[sim.grade != "NO EDGE"]
        L.append(f"- Nights evaluated: {len(sim)} · nights with a graded call: {len(traded)} ({len(traded)/max(len(sim),1)*100:.0f}%)")
        for g in ["A", "B", "C"]:
            tg = traded[traded.grade == g]
            if len(tg):
                L.append(f"- Grade {g}: n={len(tg)}, win rate {(tg.pnl_pts>0).mean()*100:.0f}%, avg {tg.pnl_pts.mean():+.1f} pts "
                         f"(${tg.pnl_pts.mean()*pv:+,.0f}/contract), total {tg.pnl_pts.sum():+.0f} pts, worst {tg.pnl_pts.min():+.0f} pts")
        for c in ["MEAN REVERSION", "CONTINUATION"]:
            tc = traded[traded.call == c]
            if len(tc):
                L.append(f"- {c}: n={len(tc)}, win rate {(tc.pnl_pts>0).mean()*100:.0f}%, avg {tc.pnl_pts.mean():+.1f} pts, total {tc.pnl_pts.sum():+.0f} pts")
        yr = traded[traded.index >= "2025-11-01"]
        if len(yr):
            L.append(f"- Past year only (from 2025-11-01): n={len(yr)}, win rate {(yr.pnl_pts>0).mean()*100:.0f}%, avg {yr.pnl_pts.mean():+.1f} pts, total {yr.pnl_pts.sum():+.0f} pts")
        L.append("")
        m = traded.groupby(traded.index.to_period("M")).agg(n=("pnl_pts", "size"), win=("pnl_pts", lambda x: (x > 0).mean()),
                                                           total_pts=("pnl_pts", "sum"), avg_pts=("pnl_pts", "mean"))
        m.index = [str(i) for i in m.index]
        m.index.name = "month"
        L.append(md_table(m, "{:.2f}"))
        L.append("")
        L.append("### Asymmetries and findings (full sample, nights with |RTH| ≥ 0.15%)")
        L.append("")
        o, f = eng.o, eng.f
        v = (o.valid == 1) & o.reverted.notna()
        def stat(mask, label):
            sub = o[v & mask]
            return (f"| {label} | {len(sub)} | {sub.reverted.mean()*100:.0f}% | {sub.rev_ret.mean()*1e4:+.1f} | {sub.hit_vwap_first.mean()*100:.0f}% | "
                    f"{sub.hit_r382_first.mean()*100:.0f}% | {sub.stopped.mean()*100:.0f}% | {sub.asia_rng.median()*1e4:.0f} |")
        L.append("| Condition | n | reverted | avg rev (bp) | VWAP first | 38% first | stopped | med range (bp) |")
        L.append("|---|---|---|---|---|---|---|---|")
        L.append(stat(pd.Series(True, index=o.index), "all"))
        L.append(stat(f.rth_ret < 0, "RTH down"))
        L.append(stat(f.rth_ret > 0, "RTH up"))
        for lo, hi in [(0.0015, 0.005), (0.005, 0.01), (0.01, 0.02), (0.02, 1)]:
            L.append(stat((f.rth_ret <= -lo) & (f.rth_ret > -hi), f"RTH down {lo*100:.1f}–{hi*100:.0f}%"))
        for lo, hi in [(0.0015, 0.005), (0.005, 0.01), (0.01, 0.02), (0.02, 1)]:
            L.append(stat((f.rth_ret >= lo) & (f.rth_ret < hi), f"RTH up {lo*100:.1f}–{hi*100:.0f}%"))
        L.append(stat(f.ext_in_dir > 0.6, "closed at extreme (trend close)"))
        L.append(stat(f.ext_in_dir < 0.2, "closed off the extreme"))
        L.append(stat(f.vix_consistent > 0.03, "VIX confirmed move"))
        L.append(stat(f.vix_consistent < -0.03, "VIX diverged"))
        L.append(stat(f.stretch20_in_dir > 1.5, "move extends >1.5 ATR stretch"))
        L.append(stat(f.stretch20_in_dir < -1.5, "move corrects >1.5 ATR stretch"))
        L.append(stat(f.sunday_open == 1, "Friday → Sunday reopen"))
        L.append(stat(f.fomc_today == 1, "FOMC day"))
        L.append(stat(f.tier1_data_tomorrow == 1, "CPI/NFP/PCE tomorrow"))
        L.append(stat(f.boj_tonight == 1, "BoJ tonight"))
        L.append(stat(f.megacap_earnings_tonight == 1, "mega-cap earnings tonight"))
        L.append(stat(f.vix > 25, "VIX > 25"))
        L.append(stat(f.vix < 15, "VIX < 15"))
        L.append("")
        L.append("### Full rule table (all history)")
        L.append("")
        rt = eng.rule_table().sort_values("n", ascending=False)
        rt = rt[rt.n > 0][["desc", "n", "rev_rate", "avg_rev_ret_bp", "vwap_first", "r382_first", "stopped", "med_rng_bp", "t_stat"]]
        rt.index.name = "rule"
        L.append(md_table(rt.round(3), "{:.3f}"))
        L.append("")
        L.append("### Rule table — past 365 days only")
        L.append("")
        rt = eng.rule_table(lookback_days=365).sort_values("n", ascending=False)
        rt = rt[rt.n > 0][["desc", "n", "rev_rate", "avg_rev_ret_bp", "vwap_first", "r382_first", "stopped", "med_rng_bp", "t_stat"]]
        rt.index.name = "rule"
        L.append(md_table(rt.round(3), "{:.3f}"))
        L.append("")
        L.append("### Average logistic coefficients (standardised features; + = toward outcome)")
        L.append("")
        for t in ["hit_vwap_first", "stopped", "reverted"]:
            c = eng.fits[t].coef.sort_values(key=np.abs, ascending=False).head(12)
            L.append(f"- **{t}**: " + ", ".join(f"{k} {v:+.2f}" for k, v in c.items()))
        L.append("")
    L.append("## Caveats")
    L.append("")
    L.append("- 17 months of hourly data; ~330 OOS nights. Rare calendar setups are anecdotes.")
    L.append("- First-hit resolution uses hourly bars: if target and stop are both inside one bar it counts as stopped (conservative).")
    L.append("- No slippage/commissions; Globex Asia liquidity is thin (NQ 1-2 tick spread but shallow depth), so size accordingly.")
    L.append("- The close-to-close reversion probability is close to coin-flip out of sample. The edge is in path outcomes and in sizing from the range model.")
    L.append("- Regime risk: the training window contains the Aug-2024 yen-carry unwind, the Apr-2025 tariff shock, the Mar-Apr 2026 and Jun-Jul 2026 stress episodes and Nov-2026 crash; a new regime can break the calibration.")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print("wrote", OUT)


if __name__ == "__main__":
    main(tuple(sys.argv[1:]) or ("NQ", "ES"))
