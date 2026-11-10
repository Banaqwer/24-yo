"""Shared loaders / stats helpers for the narrative lens."""
import glob
import os

import numpy as np
import pandas as pd
from scipy import stats

ROOT = "."
OUT = "research/extremes/scripts/lens_narrative"
os.makedirs(OUT, exist_ok=True)

ARTEFACT_NQ = ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"]
ARTEFACT_ES = ["2025-12-16", "2025-12-17"]
SPLIT = pd.Timestamp("2025-09-01")
RNG = np.random.default_rng(7)


def load_extremes(sym="NQ"):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    bad = ARTEFACT_NQ if sym == "NQ" else ARTEFACT_ES
    x = x[~x.index.isin(pd.to_datetime(bad))].copy()
    x["half"] = np.where(x.index < SPLIT, "H1", "H2")
    # derived labels
    x["hi_after_tko"] = (x["hi_k"] >= x["tokyo_open_k"]).astype(int)   # at or after the Tokyo open bar
    x["lo_after_tko"] = (x["lo_k"] >= x["tokyo_open_k"]).astype(int)
    x["hi_post_tko"] = (x["hi_k"] > x["tokyo_open_k"]).astype(int)     # strictly after
    x["lo_post_tko"] = (x["lo_k"] > x["tokyo_open_k"]).astype(int)
    x["any_first_bar"] = ((x["hi_k"] == 0) | (x["lo_k"] == 0)).astype(int)
    x["any_last_bar"] = ((x["hi_k"] == x["n_bars"] - 1) | (x["lo_k"] == x["n_bars"] - 1)).astype(int)
    x["any_at_tko"] = ((x["hi_k"] == x["tokyo_open_k"]) | (x["lo_k"] == x["tokyo_open_k"])).astype(int)
    x["any_at_cno"] = ((x["hi_k"] == x["china_open_k"]) | (x["lo_k"] == x["china_open_k"])).astype(int)
    x["trend_close"] = ((x["close_loc"] >= 0.8) | (x["close_loc"] <= 0.2)).astype(int)
    x["mid_close"] = ((x["close_loc"] > 0.35) & (x["close_loc"] < 0.65)).astype(int)
    x["cont"] = (np.sign(x["asia_ret_bp"]) == np.sign(x["rth_ret_bp"])).astype(int)
    x["abs_asia_ret"] = x["asia_ret_bp"].abs()
    x["rng_vs_med20"] = x["rng_bp"] / x["asia_rng_med20"] / 1e4 if x["asia_rng_med20"].abs().max() < 1 else x["rng_bp"] / x["asia_rng_med20"]
    # extreme-in-the-last-two-bars (late trend into Europe)
    x["hi_last2"] = (x["hi_k"] >= x["n_bars"] - 2).astype(int)
    x["lo_last2"] = (x["lo_k"] >= x["n_bars"] - 2).astype(int)
    # the "first extreme" bar and whether the first extreme was in bar 0
    x["first_ext_k"] = x[["hi_k", "lo_k"]].min(axis=1)
    x["last_ext_k"] = x[["hi_k", "lo_k"]].max(axis=1)
    return x


def load_panel(sym="NQ"):
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    bad = ARTEFACT_NQ if sym == "NQ" else ARTEFACT_ES
    p = p[~p["date"].isin(pd.to_datetime(bad))].copy()
    p["half"] = np.where(p["date"] < SPLIT, "H1", "H2")
    return p


def load_catalogue():
    frames = [pd.read_csv(f) for f in sorted(glob.glob(f"{ROOT}/research/catalogue_*.csv"))]
    c = pd.concat(frames, ignore_index=True)
    c["date"] = pd.to_datetime(c["date"])
    return c.set_index("date").sort_index()


def boot_ci(a, stat=np.mean, n=2000, alpha=0.10):
    a = np.asarray(a, dtype=float)
    a = a[~np.isnan(a)]
    if len(a) == 0:
        return (np.nan, np.nan)
    idx = RNG.integers(0, len(a), size=(n, len(a)))
    s = np.array([stat(a[i]) for i in idx])
    return (float(np.quantile(s, alpha / 2)), float(np.quantile(s, 1 - alpha / 2)))


def rate(mask_series):
    s = pd.Series(mask_series).dropna().astype(float)
    return float(s.mean()), int(s.sum()), int(len(s))


def binom_p(k, n, p0):
    """two-sided exact binomial p-value of k/n vs p0"""
    if n == 0:
        return np.nan
    return float(stats.binomtest(int(k), int(n), p0).pvalue)


def cond_table(x, cond, label, cond_name, base_df=None):
    """rate of binary `label` under `cond` vs base, with CI, p, split halves."""
    base_df = x if base_df is None else base_df
    base, bk, bn = rate(base_df[label])
    sub = x[cond]
    r, k, n = rate(sub[label])
    lo, hi = boot_ci(sub[label].dropna().values)
    out = dict(cond=cond_name, label=label, n=n, k=k, rate=r, ci_lo=lo, ci_hi=hi, base_n=bn, base_rate=base,
               diff=r - base, p_binom=binom_p(k, n, base))
    for h in ("H1", "H2"):
        sh = sub[sub["half"] == h]
        bh = base_df[base_df["half"] == h]
        rh, kh, nh = rate(sh[label]) if len(sh) else (np.nan, 0, 0)
        brh, _, _ = rate(bh[label])
        out[f"{h}_n"] = nh; out[f"{h}_rate"] = rh; out[f"{h}_base"] = brh
    return out


def cont_table(x, cond, col, cond_name, base_df=None, stat="median"):
    """continuous column: median (or mean) under cond vs base + bootstrap CI, Mann-Whitney p, halves."""
    base_df = x if base_df is None else base_df
    f = np.median if stat == "median" else np.mean
    sub = x[cond][col].dropna(); base = base_df[col].dropna()
    lo, hi = boot_ci(sub.values, f)
    try:
        p = float(stats.mannwhitneyu(sub, base_df[~cond][col].dropna(), alternative="two-sided").pvalue)
    except Exception:
        p = np.nan
    out = dict(cond=cond_name, col=col, stat=stat, n=len(sub), value=float(f(sub)) if len(sub) else np.nan,
               ci_lo=lo, ci_hi=hi, base_n=len(base), base_value=float(f(base)), p_mw=p)
    for h in ("H1", "H2"):
        sh = x[cond & (x["half"] == h)][col].dropna(); bh = base_df[base_df["half"] == h][col].dropna()
        out[f"{h}_n"] = len(sh); out[f"{h}_value"] = float(f(sh)) if len(sh) else np.nan
        out[f"{h}_base"] = float(f(bh)) if len(bh) else np.nan
    return out
