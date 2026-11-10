"""Shared loaders / statistics for the events lens."""
import numpy as np
import pandas as pd
from scipy import stats

ROOT = "."
OUT = "research/extremes/scripts/lens_events"
SPLIT = pd.Timestamp("2025-09-01")

# sessions whose bars (or RTH/ref inputs) sit inside a known contract-splice artefact
EXCLUDE = {
    "NQ": [pd.Timestamp("2025-09-16")],
    "ES": [pd.Timestamp("2025-12-16"), pd.Timestamp("2025-12-17")],
}

FLAGS = ["fomc_today", "fed_minutes_today", "tier1_data_today", "tier1_data_tomorrow", "fomc_tomorrow",
         "megacap_earnings_tonight", "boj_tonight", "jp_data_tonight", "cn_data_tonight", "cn_policy_tonight",
         "rba_tonight", "opex_today", "witching_today", "roll_today", "sunday_open", "pre_holiday", "month_end",
         "holiday_tomorrow", "ecb_tomorrow"]


def load_extremes(sym):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    x = x[~x.index.isin(EXCLUDE[sym])].copy()
    x["asia_gdate"] = pd.to_datetime(x["asia_gdate"])
    x["half"] = np.where(x.index < SPLIT, "H1", "H2")
    x["last_k"] = x["n_bars"] - 1
    x["hi_last"] = (x["hi_k"] == x["last_k"]).astype(int)
    x["lo_last"] = (x["lo_k"] == x["last_k"]).astype(int)
    x["hi_frac"] = x["hi_k"] / x["last_k"]
    x["lo_frac"] = x["lo_k"] / x["last_k"]
    x["either_first"] = ((x["hi_k"] == 0) | (x["lo_k"] == 0)).astype(int)
    x["both_first"] = ((x["hi_k"] == 0) & (x["lo_k"] == 0)).astype(int)
    x["either_last"] = ((x["hi_last"] == 1) | (x["lo_last"] == 1)).astype(int)
    x["abs_gap"] = x["gap_open_bp"].abs()
    x["abs_asia_ret"] = x["asia_ret_bp"].abs()
    x["close_loc_ext"] = ((x["close_loc"] > 0.8) | (x["close_loc"] < 0.2)).astype(int)
    return x


def load_panel(sym):
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    p = p[~p["date"].isin(EXCLUDE[sym])].copy()
    p["half"] = np.where(p["date"] < SPLIT, "H1", "H2")
    return p


def load_calendar():
    ev = pd.read_csv(f"{ROOT}/research/event_calendar.csv")
    ev["date"] = pd.to_datetime(ev["date"])
    return ev


def boot_ci(a, stat=np.mean, B=4000, seed=0, alpha=0.10):
    a = np.asarray(a, float)
    a = a[~np.isnan(a)]
    if len(a) == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(B, len(a)))
    s = stat(a[idx], axis=1)
    return tuple(np.quantile(s, [alpha / 2, 1 - alpha / 2]))


def boot_diff_ci(a, b, stat=np.median, B=4000, seed=0, alpha=0.10):
    a = np.asarray(a, float); a = a[~np.isnan(a)]
    b = np.asarray(b, float); b = b[~np.isnan(b)]
    rng = np.random.default_rng(seed)
    ia = rng.integers(0, len(a), size=(B, len(a)))
    ib = rng.integers(0, len(b), size=(B, len(b)))
    d = stat(a[ia], axis=1) - stat(b[ib], axis=1)
    return tuple(np.quantile(d, [alpha / 2, 1 - alpha / 2]))


def binom_p(k, n, p0):
    if n == 0 or np.isnan(p0):
        return np.nan
    return stats.binomtest(int(k), int(n), float(p0), alternative="two-sided").pvalue


def mw_p(a, b):
    a = np.asarray(a, float); a = a[~np.isnan(a)]
    b = np.asarray(b, float); b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return np.nan
    return stats.mannwhitneyu(a, b, alternative="two-sided").pvalue


def prop_row(name, sub, base, col):
    """conditional proportion vs base proportion (complement) with CI + exact p."""
    n = int(sub[col].notna().sum()); k = int(sub[col].sum())
    p = k / n if n else np.nan
    p0 = base[col].mean()
    lo, hi = boot_ci(sub[col].values) if n else (np.nan, np.nan)
    return dict(stat=name, n=n, k=k, rate=p, base=p0, ci_lo=lo, ci_hi=hi, p=binom_p(k, n, p0))


def med_row(name, sub, base, col):
    a = sub[col].dropna().values; b = base[col].dropna().values
    lo, hi = boot_ci(a, stat=np.median) if len(a) else (np.nan, np.nan)
    dlo, dhi = boot_diff_ci(a, b) if len(a) > 1 else (np.nan, np.nan)
    return dict(stat=name, n=len(a), med=np.median(a) if len(a) else np.nan, base_med=np.median(b),
                ci_lo=lo, ci_hi=hi, diff_ci_lo=dlo, diff_ci_hi=dhi, p=mw_p(a, b))
