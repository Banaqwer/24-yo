"""Q1: what distinguishes nights whose high/low is set in bar 0 vs bar 8 vs the middle."""
import sys
sys.path.insert(0, "research/extremes/scripts/lens_timing")
import numpy as np, pandas as pd
from common import *

sym = sys.argv[1] if len(sys.argv) > 1 else "NQ"
x, p = load(sym)
x = x[x.n_bars == 9].copy()
print(sym, "full sessions", len(x))

# bar-0 panel stats joined (knowable at close of bar 0)
p0 = p[p.k == 0].set_index("date")[["bar_close_loc", "bar_vol_rel", "bar_rng_rel", "run_hi_above_rth_high", "run_lo_below_rth_low", "pos_in_range"]]
p0.columns = ["b0_close_loc", "b0_vol_rel", "b0_rng_rel", "b0_hi_above_rth", "b0_lo_below_rth", "b0_pos"]
x = x.join(p0)

# outcomes
x["hi_cat"] = np.select([x.hi_k == 0, x.hi_k == 8], ["first", "last"], "middle")
x["lo_cat"] = np.select([x.lo_k == 0, x.lo_k == 8], ["first", "last"], "middle")
# direction-relative: continuation extreme = extreme in the RTH direction (low after a down day, high after an up day)
down = x.is_down == 1
x["cont_k"] = np.where(down, x.lo_k, x.hi_k)       # extreme in RTH direction
x["counter_k"] = np.where(down, x.hi_k, x.lo_k)    # extreme against RTH direction
x["cont_first"] = (x.cont_k == 0).astype(int); x["cont_last"] = (x.cont_k == 8).astype(int)
x["counter_first"] = (x.counter_k == 0).astype(int); x["counter_last"] = (x.counter_k == 8).astype(int)
# first-bar direction-relative: did bar 0 close up?
x["b0_up"] = (x.first_bar_ret_bp > 0).astype(int)
x["b0_ret_abs"] = x.first_bar_ret_bp.abs()

print("\nbase rates (n_bars==9):")
for c in ["high_in_first_bar", "high_in_last_bar", "low_in_first_bar", "low_in_last_bar", "cont_first", "cont_last", "counter_first", "counter_last"]:
    print(f"  {c:20s} {x[c].mean():.3f}  H1 {x[x.half=='H1'][c].mean():.3f}  H2 {x[x.half=='H2'][c].mean():.3f}")
print(pd.crosstab(x.hi_cat, x.lo_cat, normalize=True).round(3))

outcomes = ["high_in_first_bar", "high_in_last_bar", "low_in_first_bar", "low_in_last_bar"]
feat18 = ["is_down", "mag", "rth_ret", "ext_in_dir", "vwap_in_dir", "clv", "post_ret", "post_in_dir", "late_day_rev",
          "rth_range_atr", "vix", "vix_z20", "rv_ratio", "abs_streak", "rth_vol_rel", "asia_rng_med20", "is_dst",
          "sunday_open", "gap_open", "gap_in_dir", "stretch20_in_dir", "ret5_in_dir", "prior_asia_in_dir", "overnight_in_dir",
          "n225_in_dir", "sox_in_dir", "yen_in_dir", "yield_in_dir", "vix_consistent", "close_vs_vwap", "rth_hi_hour", "rth_lo_hour",
          "close_vs_prior_asia_high", "close_vs_prior_asia_low", "dist_20d_high", "dist_20d_low", "z_sma20", "day_ret", "usdjpy_chg", "n225_ret"]
flags18 = ["fomc_today", "fed_minutes_today", "tier1_data_today", "tier2_data_today", "opex_today", "witching_today", "roll_today",
           "megacap_earnings_tonight", "election_today", "politics_today", "boj_tonight", "jp_data_tonight", "cn_data_tonight",
           "cn_policy_tonight", "rba_tonight", "fomc_tomorrow", "tier1_data_tomorrow", "tier2_data_tomorrow", "ecb_tomorrow",
           "boe_tomorrow", "opex_tomorrow", "holiday_tomorrow", "sunday_open", "pre_holiday", "month_end"]
featb0 = ["first_bar_ret_bp", "first_bar_rng_bp", "gap_open_bp", "b0_close_loc", "b0_vol_rel", "b0_rng_rel", "b0_hi_above_rth", "b0_lo_below_rth", "b0_ret_abs"]

rows = []
ncomp = 0
for oc in outcomes:
    base = x[oc].mean()
    for f in feat18 + featb0:
        if f not in x.columns: continue
        v = x[f]
        if v.nunique() <= 2:
            for val in sorted(v.dropna().unique()):
                rows.append(dict(outcome=oc, feature=f, stage="18:00" if f in feat18 else "bar0", **rate_row(v == val, x[oc], base, f"{f}=={val}", x.half))); ncomp += 1
        else:
            q = v.quantile([1/3, 2/3]).values
            for lab, m in [("T1(low)", v <= q[0]), ("T2", (v > q[0]) & (v <= q[1])), ("T3(high)", v > q[1])]:
                rows.append(dict(outcome=oc, feature=f, stage="18:00" if f in feat18 else "bar0", thr=f"{q[0]:.2f}/{q[1]:.2f}", **rate_row(m, x[oc], base, f"{f} {lab}", x.half))); ncomp += 1
    for f in flags18:
        if f not in x.columns: continue
        rows.append(dict(outcome=oc, feature=f, stage="18:00", **rate_row(x[f] == 1, x[oc], base, f"{f}==1", x.half))); ncomp += 1

R = pd.DataFrame(rows)
R["sig"] = (R.p_binom < 0.05) & (R.n >= 30)
R["stable"] = np.sign(R.rate_H1 - R.base) == np.sign(R.rate_H2 - R.base)
R.to_csv(f"{OUT}/q1_{sym}_ushape_scan.csv", index=False)
print(f"\ncomparisons run: {ncomp}")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
cols = ["outcome", "stage", "cond", "n", "base", "rate", "ci90_lo", "ci90_hi", "p_binom", "rate_H1", "rate_H2", "stable"]
print("\n=== significant (p<.05, n>=30), sorted by |lift| ===")
S = R[R.sig].copy(); S["al"] = S.lift.abs()
print(S.sort_values("al", ascending=False)[cols].round(3).head(80).to_string())

# ---- direction-relative outcomes (continuation/counter extreme) ----
rows2 = []
for oc in ["cont_first", "cont_last", "counter_first", "counter_last"]:
    base = x[oc].mean()
    for f in ["mag", "ext_in_dir", "vwap_in_dir", "post_in_dir", "gap_in_dir", "stretch20_in_dir", "ret5_in_dir", "prior_asia_in_dir", "overnight_in_dir", "n225_in_dir", "sox_in_dir", "yen_in_dir", "vix_consistent", "abs_streak", "clv", "late_day_rev", "rth_range_atr", "vix_z20", "rv_ratio"]:
        v = x[f]
        if v.nunique() <= 2:
            for val in sorted(v.dropna().unique()):
                rows2.append(dict(outcome=oc, feature=f, **rate_row(v == val, x[oc], base, f"{f}=={val}", x.half))); ncomp += 1
        else:
            q = v.quantile([1/3, 2/3]).values
            for lab, m in [("T1(low)", v <= q[0]), ("T2", (v > q[0]) & (v <= q[1])), ("T3(high)", v > q[1])]:
                rows2.append(dict(outcome=oc, feature=f, thr=f"{q[0]:.2f}/{q[1]:.2f}", **rate_row(m, x[oc], base, f"{f} {lab}", x.half))); ncomp += 1
    # bar-0 direction relative to RTH direction
    b0_in_dir = np.where(down, -x.first_bar_ret_bp, x.first_bar_ret_bp)
    for lab, m in [("b0_in_dir>0", b0_in_dir > 0), ("b0_in_dir<=0", b0_in_dir <= 0), ("b0_in_dir>10", b0_in_dir > 10), ("b0_in_dir<-10", b0_in_dir < -10)]:
        rows2.append(dict(outcome=oc, feature="b0_in_dir", **rate_row(m, x[oc], base, lab, x.half))); ncomp += 1
R2 = pd.DataFrame(rows2)
R2["sig"] = (R2.p_binom < 0.05) & (R2.n >= 30)
R2["stable"] = np.sign(R2.rate_H1 - R2.base) == np.sign(R2.rate_H2 - R2.base)
R2.to_csv(f"{OUT}/q1_{sym}_ushape_dirrel_scan.csv", index=False)
print(f"\ncomparisons run (cumulative): {ncomp}")
print("\n=== direction-relative, significant ===")
S2 = R2[R2.sig].copy(); S2["al"] = S2.lift.abs()
print(S2.sort_values("al", ascending=False)[["outcome", "cond", "n", "base", "rate", "ci90_lo", "ci90_hi", "p_binom", "rate_H1", "rate_H2", "stable"]].round(3).head(60).to_string())

# ---- bar-0 close-location table (the natural detector input at the close of bar 0) ----
print("\n=== P(low in bar 0), P(high in bar 0) by bar-0 close location and bar-0 return ===")
tab = []
for lab, m in [("close_loc<0.2", x.b0_close_loc < 0.2), ("0.2-0.5", (x.b0_close_loc >= 0.2) & (x.b0_close_loc < 0.5)),
               ("0.5-0.8", (x.b0_close_loc >= 0.5) & (x.b0_close_loc < 0.8)), (">=0.8", x.b0_close_loc >= 0.8)]:
    for oc in ["low_in_first_bar", "high_in_first_bar", "low_in_last_bar", "high_in_last_bar"]:
        tab.append(dict(cond=lab, outcome=oc, **{k: v for k, v in rate_row(m, x[oc], x[oc].mean(), lab, x.half).items() if k != "cond"}))
T = pd.DataFrame(tab); T.to_csv(f"{OUT}/q1_{sym}_bar0_closeloc_table.csv", index=False)
print(T[["cond", "outcome", "n", "base", "rate", "ci90_lo", "ci90_hi", "p_binom", "rate_H1", "rate_H2"]].round(3).to_string())

print("\n=== first_bar_ret_bp signed buckets ===")
tab = []
for lab, m in [("ret<-20", x.first_bar_ret_bp < -20), ("-20..-5", (x.first_bar_ret_bp >= -20) & (x.first_bar_ret_bp < -5)), ("-5..5", x.first_bar_ret_bp.abs() <= 5),
               ("5..20", (x.first_bar_ret_bp > 5) & (x.first_bar_ret_bp <= 20)), (">20", x.first_bar_ret_bp > 20)]:
    for oc in ["low_in_first_bar", "high_in_first_bar"]:
        tab.append(dict(cond=lab, outcome=oc, **{k: v for k, v in rate_row(m, x[oc], x[oc].mean(), lab, x.half).items() if k != "cond"}))
T = pd.DataFrame(tab); T.to_csv(f"{OUT}/q1_{sym}_bar0_ret_table.csv", index=False)
print(T[["cond", "outcome", "n", "base", "rate", "ci90_lo", "ci90_hi", "p_binom", "rate_H1", "rate_H2"]].round(3).to_string())

# ---- first-bar range relative to the ex-ante median Asia range ----
print("\n=== first-bar range / asia_rng_med20 ===")
x["b0_rng_share"] = x.first_bar_rng_bp / (x.asia_rng_med20 * 1e4)
tab = []
for lab, m in [("<0.15", x.b0_rng_share < 0.15), ("0.15-0.3", (x.b0_rng_share >= 0.15) & (x.b0_rng_share < 0.3)), ("0.3-0.5", (x.b0_rng_share >= 0.3) & (x.b0_rng_share < 0.5)), (">=0.5", x.b0_rng_share >= 0.5)]:
    for oc in ["low_in_first_bar", "high_in_first_bar", "low_in_last_bar", "high_in_last_bar"]:
        tab.append(dict(cond=lab, outcome=oc, **{k: v for k, v in rate_row(m, x[oc], x[oc].mean(), lab, x.half).items() if k != "cond"}))
    # either extreme in bar 0
    e0 = ((x.hi_k == 0) | (x.lo_k == 0)).astype(int)
    tab.append(dict(cond=lab, outcome="either_extreme_in_bar0", **{k: v for k, v in rate_row(m, e0, e0.mean(), lab, x.half).items() if k != "cond"}))
T = pd.DataFrame(tab); T.to_csv(f"{OUT}/q1_{sym}_bar0_rngshare_table.csv", index=False)
print(T[["cond", "outcome", "n", "base", "rate", "ci90_lo", "ci90_hi", "p_binom", "rate_H1", "rate_H2"]].round(3).to_string())
print("comparisons total:", ncomp + 4 * 4 + 5 * 2 + 4 * 5)
