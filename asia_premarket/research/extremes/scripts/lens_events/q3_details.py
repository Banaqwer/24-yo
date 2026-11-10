"""Details + confound checks for the flag findings: FOMC eve / FOMC night, Sunday reopen (Q5), mega-cap earnings (Q4),
pre-tier1 (Q3), cn_data stratified by Sunday, opex vs other Sundays, short sessions / holiday eves (Q6)."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "research/extremes/scripts/lens_events")
from common import *
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400); pd.set_option("display.max_columns", 50)

tables = {}

def summarise(name, sub, base, props, meds):
    rows = []
    for c in props:
        r = prop_row(c, sub, base, c)
        for h in ("H1", "H2"):
            s_h = sub[sub.half == h]; b_h = base[base.half == h]
            r[f"{h}_n"] = len(s_h); r[f"{h}_rate"] = s_h[c].mean() if len(s_h) else np.nan; r[f"{h}_base"] = b_h[c].mean()
        r["kind"] = "prop"; rows.append(r)
    for c in meds:
        r = med_row(c, sub, base, c)
        for h in ("H1", "H2"):
            s_h = sub[sub.half == h]; b_h = base[base.half == h]
            r[f"{h}_n"] = len(s_h); r[f"{h}_med"] = s_h[c].median() if len(s_h) else np.nan; r[f"{h}_base"] = b_h[c].median()
        r["kind"] = "med"; rows.append(r)
    d = pd.DataFrame(rows); d.insert(0, "group", name)
    tables[name] = d
    print(f"\n=== {name}: n={len(sub)} vs base n={len(base)} ===")
    print(d.round(3).to_string())
    return d

P_ALL = ["high_in_first_bar", "low_in_first_bar", "hi_last", "lo_last", "either_first", "either_last", "high_by_tokyo_open",
         "low_by_tokyo_open", "high_above_rth_high", "low_below_rth_low", "hi_first", "close_loc_ext"]
M_ALL = ["hi_k", "lo_k", "hi_bp", "lo_bp", "rng_bp", "close_loc", "asia_ret_bp", "gap_open_bp", "abs_gap", "first_bar_rng_bp",
         "first_bar_ret_bp", "drop_after_hi_bp", "rally_after_lo_bp", "hi_vs_rth_high_bp", "lo_vs_rth_low_bp"]

for sym in ("NQ", "ES"):
    x = load_extremes(sym)
    print("\n\n################", sym, "n=", len(x))
    # --- FOMC eve and FOMC night
    summarise(f"{sym}_fomc_tomorrow", x[x.fomc_tomorrow == 1], x[x.fomc_tomorrow == 0], P_ALL, M_ALL)
    print(x[x.fomc_tomorrow == 1][["hi_k", "lo_k", "hi_bp", "lo_bp", "close_loc", "asia_ret_bp", "rth_ret_bp"]].round(1).to_string())
    summarise(f"{sym}_fomc_today", x[x.fomc_today == 1], x[x.fomc_today == 0], P_ALL, M_ALL)
    print(x[x.fomc_today == 1][["hi_k", "lo_k", "hi_bp", "lo_bp", "close_loc", "asia_ret_bp", "rth_ret_bp", "gap_open_bp"]].round(1).to_string())
    # --- Sunday reopen (Q5), and opex Sundays vs other Sundays
    sun = x[x.sunday_open == 1]; wk = x[x.sunday_open == 0]
    summarise(f"{sym}_sunday", sun, wk, P_ALL, M_ALL)
    # gap sign and where extremes sit vs Friday RTH range
    g = sun.copy(); g["gap_sign"] = np.sign(g.gap_open_bp)
    print("Sunday gap sign counts:", g.gap_sign.value_counts().to_dict())
    print("Sunday: P(low_in_first_bar | gap<0) =", round(g[g.gap_sign < 0].low_in_first_bar.mean(), 3), "n", (g.gap_sign < 0).sum(),
          "| gap>0:", round(g[g.gap_sign > 0].low_in_first_bar.mean(), 3), "n", (g.gap_sign > 0).sum())
    print("Sunday: P(high_in_first_bar | gap<0) =", round(g[g.gap_sign < 0].high_in_first_bar.mean(), 3),
          "| gap>0:", round(g[g.gap_sign > 0].high_in_first_bar.mean(), 3))
    print("Sunday: asia_ret_bp mean", round(sun.asia_ret_bp.mean(), 1), "median", round(sun.asia_ret_bp.median(), 1), "P(>0)", round((sun.asia_ret_bp > 0).mean(), 3),
          "| weekday mean", round(wk.asia_ret_bp.mean(), 1), "P(>0)", round((wk.asia_ret_bp > 0).mean(), 3))
    print("Sunday: close_bp mean", round(sun.close_bp.mean(), 1), "P(close>ref)", round((sun.close_bp > 0).mean(), 3), "| weekday", round(wk.close_bp.mean(), 1), round((wk.close_bp > 0).mean(), 3))
    # Sunday extremes inside/outside Friday RTH range
    for lab, d in (("sunday", sun), ("weekday", wk)):
        inside = ((d.high_above_rth_high == 0) & (d.low_below_rth_low == 0)).mean()
        print(f"{lab}: P(both extremes inside RTH range)={inside:.3f}  P(high>RTH high)={d.high_above_rth_high.mean():.3f}  P(low<RTH low)={d.low_below_rth_low.mean():.3f}"
              f"  med hi_vs_rth_high={d.hi_vs_rth_high_bp.median():.1f}  med lo_vs_rth_low={d.lo_vs_rth_low_bp.median():.1f}")
    summarise(f"{sym}_opex_sunday_vs_other_sundays", sun[sun.opex_today == 1], sun[sun.opex_today == 0], P_ALL, M_ALL)
    # --- mega-cap earnings (Q4)
    me = x[x.megacap_earnings_tonight == 1]; nme = x[x.megacap_earnings_tonight == 0]
    summarise(f"{sym}_megacap", me, nme, P_ALL + ["both_first"], M_ALL)
    print("megacap hi_k hist:", me.hi_k.value_counts(normalize=True).sort_index().round(3).to_dict())
    print("megacap lo_k hist:", me.lo_k.value_counts(normalize=True).sort_index().round(3).to_dict())
    print("megacap: P(first-bar extreme in gap direction): gap>0 & high_in_first_bar:", round(me[me.gap_open_bp > 0].high_in_first_bar.mean(), 3), "n", (me.gap_open_bp > 0).sum(),
          "; gap<0 & low_in_first_bar:", round(me[me.gap_open_bp < 0].low_in_first_bar.mean(), 3), "n", (me.gap_open_bp < 0).sum())
    print("base: gap>0 & high_in_first_bar:", round(nme[nme.gap_open_bp > 0].high_in_first_bar.mean(), 3), "; gap<0 & low_in_first_bar:", round(nme[nme.gap_open_bp < 0].low_in_first_bar.mean(), 3))
    # megacap and the NQ high above RTH high: is it the gap?
    print("megacap: P(high>RTH high | gap>0)", round(me[me.gap_open_bp > 0].high_above_rth_high.mean(), 3), "| gap<0", round(me[me.gap_open_bp < 0].high_above_rth_high.mean(), 3))
    print("megacap: P(low<RTH low | gap<0)", round(me[me.gap_open_bp < 0].low_below_rth_low.mean(), 3), "| gap>0", round(me[me.gap_open_bp > 0].low_below_rth_low.mean(), 3))
    # --- pre-tier1 (Q3)
    summarise(f"{sym}_tier1_tomorrow", x[x.tier1_data_tomorrow == 1], x[x.tier1_data_tomorrow == 0], P_ALL, M_ALL)
    summarise(f"{sym}_tier1_tomorrow_nonSunday", x[(x.tier1_data_tomorrow == 1) & (x.sunday_open == 0)], x[(x.tier1_data_tomorrow == 0) & (x.sunday_open == 0)], P_ALL, M_ALL)
    summarise(f"{sym}_tier1_today", x[x.tier1_data_today == 1], x[x.tier1_data_today == 0], P_ALL, M_ALL)
    # --- cn_data stratified by Sunday
    summarise(f"{sym}_cn_data_nonSunday", x[(x.cn_data_tonight == 1) & (x.sunday_open == 0)], x[(x.cn_data_tonight == 0) & (x.sunday_open == 0)], P_ALL, M_ALL)
    summarise(f"{sym}_cn_data_Sunday", x[(x.cn_data_tonight == 1) & (x.sunday_open == 1)], x[(x.cn_data_tonight == 0) & (x.sunday_open == 1)], P_ALL, M_ALL)
    print("cn_data & sunday overlap:", pd.crosstab(x.cn_data_tonight, x.sunday_open).to_dict())
    # --- short sessions / holiday eves (Q6)
    sh = x[x.n_bars < 9]
    print(f"\nshort sessions n={len(sh)}: hi_frac med {sh.hi_frac.median():.2f} lo_frac med {sh.lo_frac.median():.2f}; "
          f"P(hi first bar)={sh.high_in_first_bar.mean():.2f} P(lo first bar)={sh.low_in_first_bar.mean():.2f} "
          f"P(hi last)={sh.hi_last.mean():.2f} P(lo last)={sh.lo_last.mean():.2f} rng med {sh.rng_bp.median():.1f}")
    print(sh[["n_bars", "hi_k", "lo_k", "rng_bp", "pre_holiday", "holiday_tomorrow", "events_tonight_tomorrow"]].to_string())
    summarise(f"{sym}_holiday_tomorrow", x[x.holiday_tomorrow == 1], x[x.holiday_tomorrow == 0], P_ALL, M_ALL)
    summarise(f"{sym}_pre_holiday", x[x.pre_holiday == 1], x[x.pre_holiday == 0], P_ALL, M_ALL)
    # --- jp_data, boj, rba, ecb_tomorrow quick medians
    for f in ("jp_data_tonight", "boj_tonight", "rba_tonight", "ecb_tomorrow", "fed_minutes_today", "month_end", "roll_today"):
        summarise(f"{sym}_{f}", x[x[f] == 1], x[x[f] == 0], P_ALL, ["hi_k", "lo_k", "hi_bp", "lo_bp", "rng_bp", "close_loc", "abs_gap"])

pd.concat(tables.values()).to_csv(f"{OUT}/q3_q6_details.csv", index=False)
