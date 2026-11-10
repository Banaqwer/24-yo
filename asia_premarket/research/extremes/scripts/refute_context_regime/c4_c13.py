"""C4 (vol regime -> range/tails), C12 (with/against symmetry), C13 (mag does not scale the range)."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "research/extremes/scripts/refute_context_regime")
from common import *

for sym in ("NQ", "ES"):
    f = load(sym)
    qp = pd.read_csv(f"{LENS}/wf_quant_preds_{sym}.csv", index_col=0, parse_dates=True).reindex(f.index)
    print(f"\n==================== {sym}  n={len(f)} ====================")
    # ---------------- C4 -----------------
    print("\n----- C4: vol regime -> rng_bp / tails -----")
    for xc in ("vix", "dist_20d_high", "asia_rng_prev", "rth_range_bp", "asia_rng_med20", "abs_post"):
        print(f"\nSpearman({xc}, rng_bp) by quarter:")
        print(fmt(spearman_by_quarter(f, xc, "rng_bp").T))
        print(fmt(spearman_by_regime(f, xc, "rng_bp").T))
        print("leave-5:", leave5_spearman(f, xc, "rng_bp"))
    # VIX terciles by quarter: median range
    f["_vt"] = pd.qcut(f["vix"], 3, labels=["T1", "T2", "T3"])
    print("\nmedian rng_bp by VIX tercile x quarter:")
    print(fmt(f.groupby(["_vt", "quarter"], observed=True)["rng_bp"].median().unstack("quarter").reindex(columns=QUARTERS)))
    print(fmt(f.groupby(["_vt", "quarter"], observed=True)["rng_bp"].count().unstack("quarter").reindex(columns=QUARTERS)))
    # quantile skill by quarter, levels model (and scale+vol), key cells
    for t, tau in (("rng_bp", 0.5), ("rng_bp", 0.1), ("rng_bp", 0.9), ("hi_bp", 0.9), ("hi_bp", 0.75), ("lo_bp", 0.1), ("lo_bp", 0.25),
                   ("hi_bp", 0.5), ("lo_bp", 0.5)):
        y = f[t].values.astype(float); qb = qp[f"{t}|{tau}|base"].values
        for mdl in ("levels", "scale+vol", "scale"):
            q = qp[f"{t}|{tau}|{mdl}"].values
            s, n = pin_skill(y, q, qb, tau)
            tab = pin_skill_by_quarter(f, y, q, qb, tau)
            t5 = pin_top5(f, y, q, qb, tau)
            reg = {k: round(pin_skill(y[(f.regime == k).values], q[(f.regime == k).values], qb[(f.regime == k).values], tau)[0], 3) for k in REGIMES}
            regx = {k: round(pin_skill(y[(f.regime != k).values], q[(f.regime != k).values], qb[(f.regime != k).values], tau)[0], 3) for k in REGIMES}
            sun = pin_skill(y[(f.sunday == 1).values], q[(f.sunday == 1).values], qb[(f.sunday == 1).values], tau)[0]
            nsun = pin_skill(y[(f.sunday == 0).values], q[(f.sunday == 0).values], qb[(f.sunday == 0).values], tau)[0]
            print(f"\n{t} tau={tau} {mdl}: skill {s:.3f} (n={n}) | by quarter: " +
                  " ".join(f"{qq[2:]}:{v:.2f}" for qq, v in tab["skill"].items() if not np.isnan(v)) +
                  f" | top5 share {t5['top5_share']:.2f} skill-5 {t5['skill_minus5']:.3f} {t5['removed']} | in-regime {reg} ex-regime {regx} | sunday {sun:.3f} ex-sunday {nsun:.3f}")

    # ---------------- C12 -----------------
    print("\n----- C12: with vs against extension symmetric -----")
    f["_wa"] = (f["with_ext_bp"] > f["against_ext_bp"]).astype(float)
    f.loc[f["with_ext_bp"] == f["against_ext_bp"], "_wa"] = np.nan
    print("overall P(with>against):", f["_wa"].mean().round(3), "n", f["_wa"].count(), "CI", boot_ci(f["_wa"].dropna().values))
    tab = f.groupby("quarter")["_wa"].agg(["mean", "count"]).reindex(QUARTERS)
    tab["p_binom"] = [stats.binomtest(int(f.loc[(f.quarter == q), "_wa"].sum()), int(f.loc[(f.quarter == q), "_wa"].count()), 0.5).pvalue for q in QUARTERS]
    print(fmt(tab.T))
    print("by quarter x is_down (P(with>against)):")
    print(fmt(f.groupby(["is_down", "quarter"])["_wa"].mean().unstack("quarter").reindex(columns=QUARTERS)))
    print(fmt(f.groupby(["is_down", "quarter"])["_wa"].count().unstack("quarter").reindex(columns=QUARTERS)))
    for k in REGIMES:
        m = f.regime == k
        print(f"  {k}: in {f.loc[m, '_wa'].mean():.3f} (n={f.loc[m, '_wa'].count()})  ex {f.loc[~m, '_wa'].mean():.3f}")
    print(f"  sunday {f.loc[f.sunday == 1, '_wa'].mean():.3f} (n={int(f.loc[f.sunday == 1, '_wa'].count())}) ex-sunday {f.loc[f.sunday == 0, '_wa'].mean():.3f}")
    print("  median with_ext/against_ext by quarter:")
    print(fmt(f.groupby("quarter")[["with_ext_bp", "against_ext_bp"]].median().reindex(QUARTERS).T))
    # paired sign test by quarter of with-against
    f["_d"] = f["with_ext_bp"] - f["against_ext_bp"]
    print("  mean(with-against) by quarter:", f.groupby("quarter")["_d"].mean().reindex(QUARTERS).round(1).to_dict())
    print("  Spearman(is_down, with_ext_bp) by quarter:"); print(fmt(spearman_by_quarter(f, "is_down", "with_ext_bp").T))

    # ---------------- C13 -----------------
    print("\n----- C13: mag does not scale the range -----")
    for xc, yc in (("mag", "rng_bp"), ("mag", "hi_bp"), ("mag", "lo_bp"), ("ext_in_dir", "rng_bp"), ("vwap_in_dir", "rng_bp"), ("post_in_dir", "rng_bp"),
                   ("abs_post", "rng_bp"), ("is_down", "rng_bp"), ("rth_ret_z", "rng_bp")):
        print(f"\nSpearman({xc}, {yc}): overall", spearman(f[xc].values.astype(float), f[yc].values.astype(float)))
        print(fmt(spearman_by_quarter(f, xc, yc).T))
        print(fmt(spearman_by_regime(f, xc, yc).T))
    # partial: mag vs rng controlling for vix (rank regression residuals)
    d = f[["mag", "rng_bp", "vix", "abs_post", "asia_rng_med20"]].dropna()
    X = np.column_stack([np.ones(len(d)), d[["vix", "asia_rng_med20"]].rank().values])
    def resid(v):
        b, *_ = np.linalg.lstsq(X, v, rcond=None); return v - X @ b
    r_y = resid(d["rng_bp"].rank().values); r_x = resid(d["mag"].rank().values)
    print("partial Spearman(mag, rng | vix, asia_rng_med20):", stats.pearsonr(r_x, r_y))
    r_x2 = resid(d["abs_post"].rank().values)
    print("partial Spearman(abs_post, rng | vix, asia_rng_med20):", stats.pearsonr(r_x2, r_y))
    # mag terciles median rng by quarter
    f["_mt"] = pd.qcut(f["mag"], 3, labels=["T1", "T2", "T3"])
    print("median rng_bp by mag tercile x quarter:")
    print(fmt(f.groupby(["_mt", "quarter"], observed=True)["rng_bp"].median().unstack("quarter").reindex(columns=QUARTERS)))
    # large-move nights: |rth_ret_z| > 2 or mag top decile
    big = f["mag"] >= f["mag"].quantile(0.9)
    print(f"mag top decile (n={big.sum()}): median rng {f.loc[big,'rng_bp'].median():.1f} vs rest {f.loc[~big,'rng_bp'].median():.1f}; MWU p={stats.mannwhitneyu(f.loc[big,'rng_bp'].dropna(), f.loc[~big,'rng_bp'].dropna()).pvalue:.3g}")
    big = f["mag"] >= f["mag"].quantile(0.95)
    print(f"mag top 5% (n={big.sum()}): median rng {f.loc[big,'rng_bp'].median():.1f} vs rest {f.loc[~big,'rng_bp'].median():.1f}; MWU p={stats.mannwhitneyu(f.loc[big,'rng_bp'].dropna(), f.loc[~big,'rng_bp'].dropna()).pvalue:.3g}")
    print("mag deciles -> median rng_bp:", f.groupby(pd.qcut(f["mag"], 10, labels=False), observed=True)["rng_bp"].median().round(1).to_dict())
