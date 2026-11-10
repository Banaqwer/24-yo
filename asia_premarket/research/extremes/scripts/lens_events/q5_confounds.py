"""Confound checks and exact p-values for the headline claims."""
import sys
import numpy as np
import pandas as pd
from scipy import stats
sys.path.insert(0, "research/extremes/scripts/lens_events")
from common import *
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
rows = []

def rep(sym, name, sub, base, col, kind="prop"):
    if kind == "prop":
        r = prop_row(col, sub, base, col)
    else:
        r = med_row(col, sub, base, col)
    r.update(sym=sym, group=name, kind=kind)
    for h in ("H1", "H2"):
        s_h = sub[sub.half == h]; b_h = base[base.half == h]
        r[f"{h}_n"] = len(s_h)
        r[f"{h}_val"] = (s_h[col].mean() if kind == "prop" else s_h[col].median()) if len(s_h) else np.nan
        r[f"{h}_base"] = (b_h[col].mean() if kind == "prop" else b_h[col].median()) if len(b_h) else np.nan
    rows.append(r)
    return r

for sym in ("NQ", "ES"):
    x = load_extremes(sym)
    x["abs_close_bp"] = x.close_bp.abs()
    x["asia_up"] = (x.asia_ret_bp > 0).astype(int)
    x["close_above_ref"] = (x.close_bp > 0).astype(int)
    print(f"\n######## {sym}")
    # overlap of flags with Sunday
    print("flag x sunday overlap:")
    for f in ["tier1_data_today", "tier1_data_tomorrow", "megacap_earnings_tonight", "cn_data_tonight", "opex_today", "fomc_today", "fomc_tomorrow", "month_end", "jp_data_tonight"]:
        print(f"  {f}: n={int(x[f].sum())}, of which Sunday={int(((x[f] == 1) & (x.sunday_open == 1)).sum())}")
    # --- tier1_today stratified by Sunday
    for lab, m in (("tier1_today_nonSunday", x.sunday_open == 0), ("tier1_today_Sunday", x.sunday_open == 1)):
        sub = x[(x.tier1_data_today == 1) & m]; base = x[(x.tier1_data_today == 0) & m]
        print(f"\n{lab}: n={len(sub)} base={len(base)}")
        for c in ["low_below_rth_low", "high_above_rth_high", "low_by_tokyo_open", "either_first"]:
            r = rep(sym, lab, sub, base, c); print(f"  {c}: {r['rate']:.3f} vs {r['base']:.3f} p={r['p']:.3f} H1 {r['H1_val']:.2f}/{r['H1_base']:.2f} H2 {r['H2_val']:.2f}/{r['H2_base']:.2f}")
        for c in ["first_bar_rng_bp", "abs_gap", "rng_bp", "rally_after_lo_bp"]:
            r = rep(sym, lab, sub, base, c, "med"); print(f"  {c}: {r['med']:.1f} vs {r['base_med']:.1f} p={r['p']:.3f} H1 {r['H1_val']:.1f}/{r['H1_base']:.1f} H2 {r['H2_val']:.1f}/{r['H2_base']:.1f}")
    # --- megacap: which side breaks, by the sign of the 16-17h bar (post_ret) and the 18:00 gap
    me = x[x.megacap_earnings_tonight == 1]; nme = x[x.megacap_earnings_tonight == 0]
    print("\nmegacap: post_ret sign vs break side (post_ret = 16:00-17:00 bar return, knowable at 18:00)")
    for lab, m in (("post_ret>0", me.post_ret > 0), ("post_ret<0", me.post_ret < 0)):
        d = me[m]
        print(f"  {lab}: n={len(d)} P(high>RTH high)={d.high_above_rth_high.mean():.3f} P(low<RTH low)={d.low_below_rth_low.mean():.3f} "
              f"P(hi_first)={d.hi_first.mean():.3f} med asia_ret={d.asia_ret_bp.median():.1f} med close_loc={d.close_loc.median():.2f}")
    for lab, m in (("post_ret>0", nme.post_ret > 0), ("post_ret<0", nme.post_ret < 0)):
        d = nme[m]
        print(f"  base {lab}: n={len(d)} P(high>RTH high)={d.high_above_rth_high.mean():.3f} P(low<RTH low)={d.low_below_rth_low.mean():.3f} P(hi_first)={d.hi_first.mean():.3f}")
    # post_ret magnitude on megacap nights
    print("  megacap |post_ret| med", round(me.post_ret.abs().median() * 1e4, 1), "bp vs base", round(nme.post_ret.abs().median() * 1e4, 1))
    # megacap: in-direction break: does the extreme in the post_ret direction come late or early?
    me2 = me.copy(); me2["dir_k"] = np.where(me2.post_ret > 0, me2.hi_k, me2.lo_k); me2["opp_k"] = np.where(me2.post_ret > 0, me2.lo_k, me2.hi_k)
    nme2 = nme.copy(); nme2["dir_k"] = np.where(nme2.post_ret > 0, nme2.hi_k, nme2.lo_k); nme2["opp_k"] = np.where(nme2.post_ret > 0, nme2.lo_k, nme2.hi_k)
    print("  megacap: extreme in post_ret direction: med k", me2.dir_k.median(), "P(k=0)", round((me2.dir_k == 0).mean(), 3), "P(last)", round((me2.dir_k == me2.last_k).mean(), 3),
          "| opposite extreme: med k", me2.opp_k.median(), "P(k=0)", round((me2.opp_k == 0).mean(), 3), "P(last)", round((me2.opp_k == me2.last_k).mean(), 3))
    print("  base   : extreme in post_ret direction: med k", nme2.dir_k.median(), "P(k=0)", round((nme2.dir_k == 0).mean(), 3), "P(last)", round((nme2.dir_k == nme2.last_k).mean(), 3),
          "| opposite extreme: med k", nme2.opp_k.median(), "P(k=0)", round((nme2.opp_k == 0).mean(), 3), "P(last)", round((nme2.opp_k == nme2.last_k).mean(), 3))
    rep(sym, "megacap", me, nme, "high_in_first_bar"); rep(sym, "megacap", me, nme, "low_in_first_bar"); rep(sym, "megacap", me, nme, "either_first")
    rep(sym, "megacap", me, nme, "either_last"); rep(sym, "megacap", me, nme, "high_above_rth_high"); rep(sym, "megacap", me, nme, "low_below_rth_low")
    rep(sym, "megacap", me, nme, "rng_bp", "med"); rep(sym, "megacap", me, nme, "first_bar_rng_bp", "med"); rep(sym, "megacap", me, nme, "abs_gap", "med")
    # --- tier1_tomorrow: non-trending?
    t1 = x[x.tier1_data_tomorrow == 1]; nt1 = x[x.tier1_data_tomorrow == 0]
    print("\ntier1_tomorrow: lo_k hist", t1.lo_k.value_counts(normalize=True).sort_index().round(3).to_dict())
    print("tier1_tomorrow: hi_k hist", t1.hi_k.value_counts(normalize=True).sort_index().round(3).to_dict())
    for c in ["abs_close_bp", "abs_asia_ret", "rng_bp", "close_loc", "hi_bp", "lo_bp", "hi_vs_rth_high_bp", "lo_vs_rth_low_bp"]:
        r = rep(sym, "tier1_tomorrow", t1, nt1, c, "med"); print(f"  {c}: {r['med']:.2f} vs {r['base_med']:.2f} p={r['p']:.3f} diffCI [{r['diff_ci_lo']:.2f},{r['diff_ci_hi']:.2f}] H1 {r['H1_val']:.2f}/{r['H1_base']:.2f} H2 {r['H2_val']:.2f}/{r['H2_base']:.2f}")
    for c in ["close_loc_ext", "low_by_tokyo_open", "high_by_tokyo_open", "either_last", "high_above_rth_high", "low_below_rth_low"]:
        r = rep(sym, "tier1_tomorrow", t1, nt1, c); print(f"  {c}: {r['rate']:.3f} vs {r['base']:.3f} p={r['p']:.4f} CI [{r['ci_lo']:.3f},{r['ci_hi']:.3f}] H1 {r['H1_val']:.2f}/{r['H1_base']:.2f} H2 {r['H2_val']:.2f}/{r['H2_base']:.2f}")
    # same for fomc_tomorrow + tier1 tomorrow combined "pre-US-event"
    pre = x[(x.tier1_data_tomorrow == 1) | (x.fomc_tomorrow == 1)]; npre = x[(x.tier1_data_tomorrow == 0) & (x.fomc_tomorrow == 0)]
    r = rep(sym, "pre_event_any", pre, npre, "close_loc_ext"); print(f"pre_event_any (n={len(pre)}): close_loc_ext {r['rate']:.3f} vs {r['base']:.3f} p={r['p']:.4f}")
    # --- Sunday: exact p and lo_k hist, asia_up
    sun = x[x.sunday_open == 1]; wk = x[x.sunday_open == 0]
    print("\nSunday lo_k hist", sun.lo_k.value_counts(normalize=True).sort_index().round(3).to_dict())
    print("weekday lo_k hist", wk.lo_k.value_counts(normalize=True).sort_index().round(3).to_dict())
    print("Sunday hi_k hist", sun.hi_k.value_counts(normalize=True).sort_index().round(3).to_dict())
    for c in ["low_by_tokyo_open", "low_in_first_bar", "high_in_first_bar", "high_by_tokyo_open", "either_first", "asia_up", "close_above_ref", "hi_first", "close_loc_ext"]:
        r = rep(sym, "sunday", sun, wk, c); print(f"  {c}: {r['rate']:.3f} vs {r['base']:.3f} p={r['p']:.2e} CI [{r['ci_lo']:.3f},{r['ci_hi']:.3f}] H1 {r['H1_val']:.2f}/{r['H1_base']:.2f} H2 {r['H2_val']:.2f}/{r['H2_base']:.2f}")
    for c in ["first_bar_rng_bp", "abs_gap", "hi_bp", "lo_bp", "rng_bp", "asia_ret_bp", "first_bar_ret_bp", "rally_after_lo_bp", "drop_after_hi_bp", "lo_k", "hi_k"]:
        r = rep(sym, "sunday", sun, wk, c, "med"); print(f"  {c}: {r['med']:.2f} vs {r['base_med']:.2f} p={r['p']:.2e} diffCI [{r['diff_ci_lo']:.2f},{r['diff_ci_hi']:.2f}] H1 {r['H1_val']:.2f}/{r['H1_base']:.2f} H2 {r['H2_val']:.2f}/{r['H2_base']:.2f}")
    # Sunday low-early: is it explained by first-bar range? compare weekday sessions with first_bar_rng_bp >= Sunday median
    thr = sun.first_bar_rng_bp.median()
    wk_big = wk[wk.first_bar_rng_bp >= thr]; wk_small = wk[wk.first_bar_rng_bp < thr]
    print(f"  weekday with first_bar_rng >= {thr:.1f} (n={len(wk_big)}): low_in_first_bar {wk_big.low_in_first_bar.mean():.3f}, low_by_tokyo {wk_big.low_by_tokyo_open.mean():.3f}; "
          f"small (n={len(wk_small)}): {wk_small.low_in_first_bar.mean():.3f}, {wk_small.low_by_tokyo_open.mean():.3f}")
    sun_big = sun[sun.first_bar_rng_bp >= thr]; sun_small = sun[sun.first_bar_rng_bp < thr]
    print(f"  Sunday big first bar (n={len(sun_big)}): low_in_first_bar {sun_big.low_in_first_bar.mean():.3f}, low_by_tokyo {sun_big.low_by_tokyo_open.mean():.3f}; small (n={len(sun_small)}): {sun_small.low_in_first_bar.mean():.3f}, {sun_small.low_by_tokyo_open.mean():.3f}")
    # Sunday by RTH direction (Friday)
    for lab, m in (("fri_down", sun.is_down == 1), ("fri_up", sun.is_down == 0)):
        d = sun[m]; print(f"  Sunday after {lab} (n={len(d)}): low_by_tokyo {d.low_by_tokyo_open.mean():.3f} high_by_tokyo {d.high_by_tokyo_open.mean():.3f} asia_up {d.asia_up.mean():.3f} hi_first {d.hi_first.mean():.3f}")
    # --- FOMC eve / night exact
    for f in ("fomc_tomorrow", "fomc_today"):
        sub = x[x[f] == 1]; base = x[x[f] == 0]
        print(f"\n{f} n={len(sub)}")
        for c in ["hi_first", "hi_last", "lo_last", "low_in_first_bar", "asia_up", "close_above_ref", "close_loc_ext", "either_last", "high_above_rth_high"]:
            r = rep(sym, f, sub, base, c); print(f"  {c}: {r['k']}/{r['n']}={r['rate']:.3f} vs {r['base']:.3f} p={r['p']:.2e} H1 {r['H1_val']:.2f}/{r['H1_base']:.2f} H2 {r['H2_val']:.2f}/{r['H2_base']:.2f}")
        for c in ["hi_k", "lo_k", "close_loc", "asia_ret_bp", "hi_bp", "lo_bp", "rng_bp", "drop_after_hi_bp", "rally_after_lo_bp"]:
            r = rep(sym, f, sub, base, c, "med"); print(f"  {c}: {r['med']:.2f} vs {r['base_med']:.2f} p={r['p']:.2e} diffCI [{r['diff_ci_lo']:.2f},{r['diff_ci_hi']:.2f}] H1 {r['H1_val']:.2f}/{r['H1_base']:.2f} H2 {r['H2_val']:.2f}/{r['H2_base']:.2f}")
    # --- cn_data non-Sunday either_last exact
    a = x[(x.cn_data_tonight == 1) & (x.sunday_open == 0)]; b = x[(x.cn_data_tonight == 0) & (x.sunday_open == 0)]
    for c in ["either_last", "hi_last", "lo_last"]:
        r = rep(sym, "cn_data_nonSunday", a, b, c); print(f"cn_data nonSunday {c}: {r['k']}/{r['n']}={r['rate']:.3f} vs {r['base']:.3f} p={r['p']:.3f} H1 {r['H1_val']:.2f}/{r['H1_base']:.2f} H2 {r['H2_val']:.2f}/{r['H2_base']:.2f}")
    # --- month_end / opex gap
    for f in ("month_end", "opex_today"):
        sub = x[x[f] == 1]; base = x[(x[f] == 0) & (x.sunday_open == (1 if f == "opex_today" else 0))]
        r = rep(sym, f + ("_vs_otherSundays" if f == "opex_today" else "_vs_weekday"), sub, base, "abs_gap", "med")
        print(f"{f}: abs_gap {r['med']:.2f} vs {r['base_med']:.2f} p={r['p']:.3f} n={r['n']}")
        r = rep(sym, f + ("_vs_otherSundays" if f == "opex_today" else "_vs_weekday"), sub, base, "lo_last")
        print(f"{f}: lo_last {r['rate']:.3f} vs {r['base']:.3f} p={r['p']:.3f}")
    # --- short sessions
    sh = x[x.n_bars < 9]; fu = x[x.n_bars == 9]
    r = rep(sym, "short_sessions", sh, fu, "rng_bp", "med"); print(f"short sessions n={len(sh)}: rng {r['med']:.1f} vs {r['base_med']:.1f} p={r['p']:.4f}")
    r = rep(sym, "short_sessions", sh, fu, "low_in_first_bar"); print(f"  low_in_first_bar {r['rate']:.3f} vs {r['base']:.3f} p={r['p']:.3f}")
    r = rep(sym, "short_sessions", sh, fu, "high_in_first_bar"); print(f"  high_in_first_bar {r['rate']:.3f} vs {r['base']:.3f} p={r['p']:.3f}")
    r = rep(sym, "short_sessions", sh, fu, "either_first"); print(f"  either_first {r['rate']:.3f} vs {r['base']:.3f} p={r['p']:.3f}")

pd.DataFrame(rows).to_csv(f"{OUT}/q5_confounds.csv", index=False)
