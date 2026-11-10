"""Shared loaders + statistics helpers for the timing lens."""
import os
import numpy as np
import pandas as pd
from scipy import stats

ROOT = "."
OUT = "research/extremes/scripts/lens_timing"
os.makedirs(OUT, exist_ok=True)
SPLIT = pd.Timestamp("2025-09-01")
# contract-splice artefacts (RTH date D whose Asia session / ref close is contaminated)
BAD = {
    "NQ": [pd.Timestamp("2024-06-21"), pd.Timestamp("2024-12-20"), pd.Timestamp("2025-03-21"), pd.Timestamp("2025-09-16")],
    "ES": [pd.Timestamp("2025-12-15"), pd.Timestamp("2025-12-16"), pd.Timestamp("2025-12-17")],
}
RNG = np.random.default_rng(7)


def load(sym="NQ", drop_bad=True):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    if drop_bad:
        x = x[~x.index.isin(BAD[sym])]
        p = p[~p["date"].isin(BAD[sym])]
    x["half"] = np.where(x.index < SPLIT, "H1", "H2")
    p["half"] = np.where(p["date"] < SPLIT, "H1", "H2")
    return x, p


def boot_ci(v, fn=np.mean, n_boot=2000, alpha=0.10):
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) < 2:
        return (np.nan, np.nan)
    idx = RNG.integers(0, len(v), size=(n_boot, len(v)))
    b = np.array([fn(v[i]) for i in idx])
    return (float(np.quantile(b, alpha / 2)), float(np.quantile(b, 1 - alpha / 2)))


def boot_ci_diff(a, b, fn=np.mean, n_boot=2000, alpha=0.10):
    a = np.asarray(a, dtype=float); a = a[~np.isnan(a)]
    b = np.asarray(b, dtype=float); b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return (np.nan, np.nan)
    ia = RNG.integers(0, len(a), size=(n_boot, len(a)))
    ib = RNG.integers(0, len(b), size=(n_boot, len(b)))
    d = np.array([fn(a[i]) - fn(b[j]) for i, j in zip(ia, ib)])
    return (float(np.quantile(d, alpha / 2)), float(np.quantile(d, 1 - alpha / 2)))


def binom_p(k, n, p0):
    """two-sided exact binomial p-value of k successes in n vs base rate p0"""
    if n == 0 or np.isnan(p0):
        return np.nan
    return float(stats.binomtest(int(k), int(n), p0).pvalue)


def rate_row(mask, y, base, label, half=None):
    """conditional rate of binary y within mask, with CI, exact binomial p vs base, and H1/H2 split."""
    y = np.asarray(pd.Series(y).values, dtype=float)
    m = np.asarray(pd.Series(mask).fillna(False).values, dtype=bool)
    sub = y[m]
    n = int(len(sub)); k = int(np.nansum(sub))
    rate = k / n if n else np.nan
    lo, hi = boot_ci(sub) if n >= 2 else (np.nan, np.nan)
    row = dict(cond=label, n=n, rate=rate, base=base, lift=rate - base if n else np.nan,
               ci90_lo=lo, ci90_hi=hi, p_binom=binom_p(k, n, base))
    if half is not None:
        h = np.asarray(pd.Series(half).values)
        for hh in ("H1", "H2"):
            s2 = y[m & (h == hh)]
            row[f"n_{hh}"] = int(len(s2)); row[f"rate_{hh}"] = float(s2.mean()) if len(s2) else np.nan
    return row


def fmt_pct(v):
    return "nan" if pd.isna(v) else f"{100*v:.0f}%"
