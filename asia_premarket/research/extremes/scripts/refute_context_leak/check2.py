import numpy as np, pandas as pd
from scipy import stats
pd.set_option("display.width", 250)
ROOT = "."
LC = "research/extremes/scripts/lens_context"
ext = pd.read_csv(f"{ROOT}/research/extremes/NQ_extremes.csv", index_col="date", parse_dates=True)
fr = pd.read_csv(f"{LC}/frame_NQ.csv", index_col=0, parse_dates=True)
ext["gap_days"] = (pd.to_datetime(ext["asia_gdate"]) - ext.index.to_series()).dt.days
odd = ext[(ext.gap_days != 1) & (ext.index.dayofweek != 4)]
print("odd-gap sessions:\n", odd[["asia_gdate", "gap_days", "n_bars", "dow", "sunday_open"]])
print("in frame:", [d in fr.index for d in odd.index])
# USDJPY timing: does usdjpy_chg(D) correlate with the NQ 18:00-19:00 bar beyond RTH?
pan = pd.read_csv(f"{ROOT}/research/extremes/NQ_hourly_panel.csv", parse_dates=["date"])
b0 = pan[pan.k == 0].set_index("date")["bar_ret_bp"].reindex(fr.index)
x = pd.DataFrame({"usdjpy": fr["usdjpy_chg"], "rth": fr["rth_ret"], "bar0": b0, "post": fr["post_ret"], "n225": fr["n225_ret"], "dxy": fr["dxy_chg"], "gold": fr["gold_chg"]}).dropna()
for c in ["usdjpy", "dxy", "gold", "n225"]:
    r_rth = stats.spearmanr(x[c], x.rth)[0]; r_b0 = stats.spearmanr(x[c], x.bar0)[0]
    # partial: residual of bar0 after rth and post
    import numpy.linalg as la
    A = np.column_stack([np.ones(len(x)), x.rth, x.post]); res = x.bar0 - A @ la.lstsq(A, x.bar0, rcond=None)[0]
    print(f"{c}: rho with rth_ret {r_rth:.3f}, with Asia bar0 ret {r_b0:.3f}, with bar0 residual (after rth,post) {stats.spearmanr(x[c], res)[0]:.3f} p={stats.spearmanr(x[c], res)[1]:.3g}")
# daily_close USDJPY date stamps
dc = pd.read_csv(f"{ROOT}/data/daily_close.csv", index_col=0)
print(dc.index[:3].tolist(), "...", dc.index[-3:].tolist())
# wf_quant levels-set vs claim's input list; compact set
wq = pd.read_csv(f"{LC}/wf_quant_NQ.csv")
print(wq[(wq.target == "rng_bp")].pivot_table(index="tau", columns="model", values="skill").round(3))
print(wq[(wq.target == "hi_bp")].pivot_table(index="tau", columns="model", values="skill").round(3))
print(wq[(wq.target == "lo_bp")].pivot_table(index="tau", columns="model", values="skill").round(3))
# ES replication tables
print(pd.read_csv(f"{LC}/tab_scaled_buckets.csv").to_string())
# C11: expanding base rate as a knowable encoding - does expanding P(low_in_first) track the second half?
for t in ["low_in_first_bar", "high_in_first_bar"]:
    e = fr[t].expanding().mean().shift(1); r = fr[t].rolling(100).mean().shift(1)
    y = fr[t]
    m = y.index >= "2025-09-01"
    print(t, "H2 realised", y[m].mean().round(3), "expanding forecast mean", e[m].mean().round(3), "Brier exp", ((e[m]-y[m])**2).mean().round(4), "Brier roll100", ((r[m]-y[m])**2).mean().round(4))
