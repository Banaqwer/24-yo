"""Independent loaders / stats for the refuter (does not import the lens code)."""
import numpy as np, pandas as pd
from scipy import stats

ROOT = "."
OUT = "research/extremes/scripts/refute_narrative_stats"
ART = {"NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"], "ES": ["2025-12-16", "2025-12-17"]}
SPLIT = pd.Timestamp("2025-09-01")
RNG = np.random.default_rng(123)


def load_x(sym="NQ"):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    x = x[~x.index.isin(pd.to_datetime(ART[sym]))].copy()
    x["half"] = np.where(x.index < SPLIT, "H1", "H2")
    x["last_k"] = x["n_bars"] - 1
    x["any_first_bar"] = ((x.hi_k == 0) | (x.lo_k == 0)).astype(int)
    x["any_last_bar"] = ((x.hi_k == x.last_k) | (x.lo_k == x.last_k)).astype(int)
    x["any_at_tko"] = ((x.hi_k == x.tokyo_open_k) | (x.lo_k == x.tokyo_open_k)).astype(int)
    x["hi_after_tko"] = (x.hi_k >= x.tokyo_open_k).astype(int)
    x["lo_after_tko"] = (x.lo_k >= x.tokyo_open_k).astype(int)
    x["hi_post_tko"] = (x.hi_k > x.tokyo_open_k).astype(int)
    x["lo_post_tko"] = (x.lo_k > x.tokyo_open_k).astype(int)
    x["trend_close"] = ((x.close_loc >= 0.8) | (x.close_loc <= 0.2)).astype(int)
    x["mid_close"] = ((x.close_loc > 0.35) & (x.close_loc < 0.65)).astype(int)
    x["cont"] = (np.sign(x.asia_ret_bp) == np.sign(x.rth_ret_bp)).astype(int)
    x["asia_up"] = (x.asia_ret_bp > 0).astype(int)
    x["abs_ret"] = x.asia_ret_bp.abs()
    x["abs_post"] = x.post_ret.abs() * 1e4
    x["abs_kospi"] = x.kospi_ret.abs() * 100
    x["abs_sox"] = x.sox_ret.abs() * 100
    x["abs_gap"] = x.gap_open_bp.abs()
    x["abs_rth"] = x.rth_ret_bp.abs()
    x["lo_by_tko_and_close_hi"] = ((x.lo_k <= x.tokyo_open_k) & (x.close_loc >= 0.6)).astype(int)
    x["close_hi70"] = (x.close_loc >= 0.7).astype(int)
    x["close_lo30"] = (x.close_loc <= 0.3).astype(int)
    x["revers_close"] = (((x.rth_ret_bp > 0) & (x.close_loc <= 0.3)) | ((x.rth_ret_bp < 0) & (x.close_loc >= 0.7))).astype(int)
    return x


def load_p(sym="NQ"):
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    p = p[~p.date.isin(pd.to_datetime(ART[sym]))].copy()
    p["half"] = np.where(p.date < SPLIT, "H1", "H2")
    return p


def bci(a, f=np.mean, n=4000, alpha=0.10):
    a = np.asarray(pd.Series(a).dropna(), dtype=float)
    if len(a) == 0:
        return (np.nan, np.nan)
    idx = RNG.integers(0, len(a), size=(n, len(a)))
    s = np.array([f(a[i]) for i in idx])
    return (float(np.quantile(s, alpha / 2)), float(np.quantile(s, 1 - alpha / 2)))


def fisher(a_k, a_n, b_k, b_n):
    return float(stats.fisher_exact([[a_k, a_n - a_k], [b_k, b_n - b_k]])[1])


def rate_vs_rest(x, cond, lab, name="", verbose=True):
    """rate under cond vs the COMPLEMENT (proper two-group comparison): Fisher p, exact binomial vs full base, 90% CI, halves."""
    cond = pd.Series(cond, index=x.index).fillna(False).astype(bool)
    s = x.loc[cond, lab].dropna(); r = x.loc[~cond, lab].dropna(); allv = x[lab].dropna()
    k, n = int(s.sum()), len(s); kr, nr = int(r.sum()), len(r)
    out = dict(name=name, label=lab, n=n, k=k, rate=s.mean(), rest_rate=r.mean(), full_base=allv.mean(),
               ci=bci(s.values), p_fisher=fisher(k, n, kr, nr), p_binom_full=float(stats.binomtest(k, n, allv.mean()).pvalue))
    for h in ("H1", "H2"):
        sh = x[cond & (x.half == h)][lab].dropna(); rh = x[(~cond) & (x.half == h)][lab].dropna()
        out[f"{h}"] = (len(sh), round(sh.mean(), 3) if len(sh) else np.nan, round(rh.mean(), 3) if len(rh) else np.nan,
                       round(fisher(int(sh.sum()), len(sh), int(rh.sum()), len(rh)), 3) if len(sh) and len(rh) else np.nan)
    if verbose:
        print(f"  [{name}] {lab}: n={n} k={k} rate={out['rate']:.3f} rest={out['rest_rate']:.3f} full={out['full_base']:.3f} "
              f"CI90=({out['ci'][0]:.3f},{out['ci'][1]:.3f}) p_fisher={out['p_fisher']:.4f} p_binom_full={out['p_binom_full']:.4f} "
              f"H1(n,rate,rest,p)={out['H1']} H2={out['H2']}")
    return out


def cont_vs_rest(x, cond, col, name="", f=np.median, verbose=True):
    cond = pd.Series(cond, index=x.index).fillna(False).astype(bool)
    s = x.loc[cond, col].dropna(); r = x.loc[~cond, col].dropna()
    out = dict(name=name, col=col, n=len(s), value=float(f(s)) if len(s) else np.nan, rest=float(f(r)), full=float(f(x[col].dropna())),
               ci=bci(s.values, f), p_mw=float(stats.mannwhitneyu(s, r, alternative="two-sided").pvalue) if len(s) and len(r) else np.nan)
    for h in ("H1", "H2"):
        sh = x[cond & (x.half == h)][col].dropna(); rh = x[(~cond) & (x.half == h)][col].dropna()
        out[h] = (len(sh), round(float(f(sh)), 1) if len(sh) else np.nan, round(float(f(rh)), 1) if len(rh) else np.nan,
                  round(float(stats.mannwhitneyu(sh, rh, alternative="two-sided").pvalue), 3) if len(sh) > 1 and len(rh) > 1 else np.nan)
    if verbose:
        print(f"  [{name}] {col}: n={out['n']} med={out['value']:.1f} rest={out['rest']:.1f} full={out['full']:.1f} CI90=({out['ci'][0]:.1f},{out['ci'][1]:.1f}) "
              f"p_MW={out['p_mw']:.4f} H1(n,val,rest,p)={out['H1']} H2={out['H2']}")
    return out
