"""Final encoding tables: scaled level-distance buckets (detector lookup), Sunday/Monday by DST and half,
Sunday open gap, and the count of comparisons run."""
import sys, warnings
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
OUT = "research/extremes/scripts/lens_context"
rng = np.random.default_rng(4)
pd.set_option("display.width", 250)


def ci(x, B=2000):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 5:
        return (np.nan, np.nan)
    idx = rng.integers(0, len(x), (B, len(x)))
    return tuple(np.quantile(x[idx].mean(1), [0.05, 0.95]))


rows = []
for sym in ["NQ", "ES"]:
    df = pd.read_csv(f"{OUT}/frame_{sym}.csv", index_col=0, parse_dates=True).sort_index()
    raw = pd.read_csv(f"./research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    df = df.join(raw[["open_bp", "first_bar_ret_bp", "close_bp"]])
    med = df["asia_rng_med20"] * 1e4
    df["sd_high"] = df["dist_rth_high0"] / med
    df["sd_low"] = -df["dist_rth_low0"] / med
    edges = [-np.inf, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, np.inf]
    labels = ["<=0.10", "0.10-0.25", "0.25-0.50", "0.50-0.75", "0.75-1.0", "1.0-1.5", ">1.5"]
    for f, t in [("sd_high", "high_above_rth_high"), ("sd_low", "low_below_rth_low")]:
        sub = df.dropna(subset=[f, t])
        b = pd.cut(sub[f], edges, labels=labels)
        for lab in labels:
            s = sub[b == lab]
            lo, hi = ci(s[t])
            rows.append(dict(sym=sym, feature=f, bucket=lab, target=t, n=len(s), rate=s[t].mean(), ci_lo=lo, ci_hi=hi,
                             n_h1=(s.half == "H1").sum(), rate_h1=s[s.half == "H1"][t].mean(), n_h2=(s.half == "H2").sum(), rate_h2=s[s.half == "H2"][t].mean(),
                             base=sub[t].mean()))
    # Sunday / Monday by DST and by half
    for lab, m in [("sunday", df.dow == 4), ("monday", df.dow == 0), ("tue-thu", df.dow.isin([1, 2, 3]))]:
        for dst in [0, 1]:
            s = df[m & (df.is_dst == dst)]
            print(f"{sym} {lab} is_dst={dst} (tokyo_open_k={1 + dst}): n={len(s)} low_in_first {s.low_in_first_bar.mean():.3f} low_by_tokyo {s.low_by_tokyo_open.mean():.3f} "
                  f"high_in_first {s.high_in_first_bar.mean():.3f} high_by_tokyo {s.high_by_tokyo_open.mean():.3f} hi_first {s.hi_first.mean():.3f} low_in_last {s.low_in_last_bar.mean():.3f}")
    sun = df[df.dow == 4]
    print(f"{sym} Sunday: n={len(sun)} median open_bp {sun.open_bp.median():.1f} P(open_bp<0) {(sun.open_bp < 0).mean():.3f} median first_bar_ret {sun.first_bar_ret_bp.median():.1f} "
          f"median close_bp {sun.close_bp.median():.1f} P(close_bp>0) {(sun.close_bp > 0).mean():.3f} | rest: median close_bp {df[df.dow != 4].close_bp.median():.1f} P(close_bp>0) {(df[df.dow != 4].close_bp > 0).mean():.3f}")
    print(f"{sym} Sunday low_in_first_bar | open gap<0: {sun[sun.open_bp < 0].low_in_first_bar.mean():.3f} (n={(sun.open_bp < 0).sum()}) | gap>=0: {sun[sun.open_bp >= 0].low_in_first_bar.mean():.3f} (n={(sun.open_bp >= 0).sum()})")
    print(f"{sym} Sunday high_in_first_bar | open gap<0: {sun[sun.open_bp < 0].high_in_first_bar.mean():.3f} | gap>=0: {sun[sun.open_bp >= 0].high_in_first_bar.mean():.3f}")
    mon = df[df.dow == 0]
    print(f"{sym} Monday: median close_bp {mon.close_bp.median():.1f} P(close_bp>0) {(mon.close_bp > 0).mean():.3f} median hi_bp {mon.hi_bp.median():.1f} lo_bp {mon.lo_bp.median():.1f}")
    # Monday vs rest: Fisher for low_in_first_bar and hi_first, binomial exact vs base
    for t in ["low_in_first_bar", "low_by_tokyo_open", "hi_first", "high_in_first_bar"]:
        ct = pd.crosstab(df.dow == 0, df[t]).values
        print(f"{sym} Monday {t}: {mon[t].mean():.3f} vs rest {df[df.dow != 0][t].mean():.3f} fisher p={stats.fisher_exact(ct)[1]:.4f}")
    for t in ["low_in_first_bar", "low_by_tokyo_open", "hi_first"]:
        ct = pd.crosstab(df.dow == 4, df[t]).values
        print(f"{sym} Sunday {t}: {sun[t].mean():.3f} vs rest {df[df.dow != 4][t].mean():.3f} fisher p={stats.fisher_exact(ct)[1]:.4f}")
    # FOMC-eve by half
    fe = df[df.fomc_tomorrow == 1]
    print(f"{sym} FOMC-eve n={len(fe)}: hi_first {fe.hi_first.sum():.0f}/{len(fe)} close_top20 {fe.close_top20.sum():.0f}/{len(fe)} close_bot20 {fe.close_bot20.sum():.0f}/{len(fe)} "
          f"low_in_first {fe.low_in_first_bar.sum():.0f} high_in_last {fe.high_in_last_bar.sum():.0f} median close_bp {fe.close_bp.median():.1f} P(close_bp>0) {(fe.close_bp > 0).mean():.3f} "
          f"binom p(hi_first<= {fe.hi_first.sum():.0f} | p={df.hi_first.mean():.3f}) = {stats.binomtest(int(fe.hi_first.sum()), len(fe), df.hi_first.mean(), alternative='less').pvalue:.2e}")
    print(f"{sym} FOMC-eve dates: {[d.date().isoformat() for d in fe.index]}")
T = pd.DataFrame(rows); T.to_csv(f"{OUT}/tab_scaled_buckets.csv", index=False)
print(T.round(3).to_string(index=False))

# comparisons count
n_screen = 2408 * 2
wl = pd.read_csv(f"{OUT}/wf_logit_NQ.csv"); we = pd.read_csv(f"{OUT}/wf_extra_NQ.csv"); wq = pd.read_csv(f"{OUT}/wf_quant_NQ.csv")
n_wf = (len(wl[wl.model != "base"]) + len(wl[wl.model != "base"]) + len(we) + len(wq) * 2)
print("comparisons: univariate screen", n_screen, "| walk-forward model-target pairs (NQ+ES)", n_wf)
