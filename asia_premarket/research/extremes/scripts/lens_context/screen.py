"""Univariate screen: every 18:00-knowable feature x every target.

Binary targets   : tercile (continuous feature) or 0/1 (flag) conditional rates, 90% bootstrap CI,
                   Mann-Whitney (continuous) / Fisher exact (flag) p-value, rate by half.
Continuous targets: Spearman rho + p, tercile medians, by half.
Writes screen_bin_<SYM>.csv, screen_cont_<SYM>.csv and n_comparisons.
"""
import sys, warnings
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
OUT = "research/extremes/scripts/lens_context"
sys.path.insert(0, OUT)
from prep import FEATS, BIN_TARGETS, CONT_TARGETS

rng = np.random.default_rng(0)
FLAGS = {"is_down", "sunday_open", "pre_holiday", "month_end", "fomc_today", "tier1_data_today", "tier2_data_today",
         "opex_today", "witching_today", "roll_today", "megacap_earnings_tonight", "boj_tonight", "jp_data_tonight",
         "cn_data_tonight", "rba_tonight", "fomc_tomorrow", "tier1_data_tomorrow", "holiday_tomorrow",
         "prior_asia_reverted", "is_dst"}


def boot_mean_ci(x, B=2000):
    x = np.asarray(x, float)
    if len(x) < 5:
        return (np.nan, np.nan)
    idx = rng.integers(0, len(x), (B, len(x)))
    m = x[idx].mean(1)
    return tuple(np.quantile(m, [0.05, 0.95]))


def boot_diff_ci(a, b, B=2000):
    a = np.asarray(a, float); b = np.asarray(b, float)
    if len(a) < 5 or len(b) < 5:
        return (np.nan, np.nan)
    ia = rng.integers(0, len(a), (B, len(a))); ib = rng.integers(0, len(b), (B, len(b)))
    d = a[ia].mean(1) - b[ib].mean(1)
    return tuple(np.quantile(d, [0.05, 0.95]))


def groups_for(df, f):
    """Return a Series of group labels for feature f."""
    x = df[f]
    if f in FLAGS or f == "dow":
        return x.astype("Int64").astype(str)
    if x.nunique() < 6:
        return x.astype(str)
    try:
        return pd.qcut(x, 3, labels=["T1", "T2", "T3"]).astype(str)
    except ValueError:
        return pd.qcut(x.rank(method="first"), 3, labels=["T1", "T2", "T3"]).astype(str)


def run(sym):
    df = pd.read_csv(f"{OUT}/frame_{sym}.csv", index_col=0, parse_dates=True)
    rows_b, rows_c = [], []
    ncomp = 0
    for f in FEATS:
        if f not in df.columns:
            continue
        g_all = groups_for(df.dropna(subset=[f]), f)
        for t in BIN_TARGETS:
            sub = df.dropna(subset=[f, t])
            if len(sub) < 50:
                continue
            g = g_all.reindex(sub.index)
            ncomp += 1
            # overall test
            if f in FLAGS or f == "dow" or sub[f].nunique() < 6:
                ct = pd.crosstab(g, sub[t])
                if ct.shape == (2, 2):
                    p = stats.fisher_exact(ct.values)[1]
                else:
                    p = stats.chi2_contingency(ct.values)[1] if ct.shape[0] > 1 else np.nan
            else:
                a = sub.loc[sub[t] == 1, f]; b = sub.loc[sub[t] == 0, f]
                p = stats.mannwhitneyu(a, b).pvalue if len(a) > 5 and len(b) > 5 else np.nan
            base = sub[t].mean()
            labels = sorted(g.unique())
            lab_lo, lab_hi = labels[0], labels[-1]
            x_lo = sub.loc[g == lab_lo, t]; x_hi = sub.loc[g == lab_hi, t]
            dlo, dhi = boot_diff_ci(x_hi, x_lo)
            for lab in labels:
                m = g == lab
                x = sub.loc[m, t]
                lo, hi = boot_mean_ci(x)
                h1 = sub.loc[m & (sub["half"] == "H1"), t]; h2 = sub.loc[m & (sub["half"] == "H2"), t]
                rows_b.append(dict(sym=sym, feature=f, target=t, group=lab, n=int(m.sum()), base=base,
                                   rate=x.mean(), ci_lo=lo, ci_hi=hi, n_h1=len(h1), rate_h1=h1.mean(),
                                   n_h2=len(h2), rate_h2=h2.mean(), p_overall=p,
                                   diff_hi_lo=x_hi.mean() - x_lo.mean(), diff_ci_lo=dlo, diff_ci_hi=dhi))
        for t in CONT_TARGETS:
            sub = df.dropna(subset=[f, t])
            if len(sub) < 50:
                continue
            ncomp += 1
            rho, p = stats.spearmanr(sub[f], sub[t])
            h1 = sub[sub["half"] == "H1"]; h2 = sub[sub["half"] == "H2"]
            rho1 = stats.spearmanr(h1[f], h1[t])[0] if len(h1) > 20 else np.nan
            rho2 = stats.spearmanr(h2[f], h2[t])[0] if len(h2) > 20 else np.nan
            g = g_all.reindex(sub.index)
            meds = {lab: sub.loc[g == lab, t].median() for lab in sorted(g.unique())}
            means = {lab: sub.loc[g == lab, t].mean() for lab in sorted(g.unique())}
            ns = {lab: int((g == lab).sum()) for lab in sorted(g.unique())}
            rows_c.append(dict(sym=sym, feature=f, target=t, n=len(sub), rho=rho, p=p, rho_h1=rho1, rho_h2=rho2,
                               groups=";".join(f"{k}:n={ns[k]},med={meds[k]:.3g},mean={means[k]:.3g}" for k in meds)))
    b = pd.DataFrame(rows_b); c = pd.DataFrame(rows_c)
    b.to_csv(f"{OUT}/screen_bin_{sym}.csv", index=False)
    c.to_csv(f"{OUT}/screen_cont_{sym}.csv", index=False)
    print(sym, "comparisons:", ncomp, "bin rows", len(b), "cont rows", len(c))
    # BH-FDR on the overall p-values (one per feature x target)
    pb = b.drop_duplicates(["feature", "target"])[["feature", "target", "p_overall"]].dropna()
    pc = c[["feature", "target", "p"]].rename(columns={"p": "p_overall"})
    allp = pd.concat([pb, pc]).sort_values("p_overall").reset_index(drop=True)
    m = len(allp)
    allp["bh_q"] = (allp["p_overall"] * m / (np.arange(m) + 1))[::-1].cummin()[::-1]
    allp.to_csv(f"{OUT}/screen_pvalues_{sym}.csv", index=False)
    print("  tests with BH q<0.10:", int((allp["bh_q"] < 0.10).sum()), "of", m)
    print(allp.head(40).to_string())


if __name__ == "__main__":
    for sym in sys.argv[1:] or ["NQ", "ES"]:
        run(sym)
