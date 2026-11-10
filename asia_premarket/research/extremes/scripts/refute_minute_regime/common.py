import numpy as np, pandas as pd
from scipy.stats import binomtest, fisher_exact, mannwhitneyu, chi2

ROOT = "."
LENS = "research/extremes/scripts/lens_minute"
OUT = "research/extremes/scripts/refute_minute_regime"
rng = np.random.default_rng(2026)

# sessions whose Asia bars (or the 17:00 ref close) are contaminated by a contract splice
SPLICE = {"NQ": [pd.Timestamp("2025-09-16")],
          "ES": [pd.Timestamp("2025-12-15"), pd.Timestamp("2025-12-16"), pd.Timestamp("2025-12-17")]}
CRASH_WEEK = pd.date_range("2026-11-02", "2026-11-06")      # midterms + Nov-5 crash (EST sessions)


def boot_ci(v, stat=np.mean, B=4000):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    if len(v) == 0: return (np.nan, np.nan)
    idx = rng.integers(0, len(v), (B, len(v)))
    s = np.array([stat(v[i]) for i in idx])
    return tuple(np.round(np.percentile(s, [5, 95]), 3))


def prop(v):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    n = len(v); k = int(v.sum())
    return n, k, (k / n if n else np.nan)


def fp(v):
    n, k, p = prop(v)
    ci = boot_ci(v)
    return f"{k}/{n}={p:.2f} CI[{ci[0]:.2f},{ci[1]:.2f}]"


def fp_short(v):
    n, k, p = prop(v)
    return f"{k}/{n}={p:.2f}" if n else "0/0"


def binom_p(k, n, p0):
    return binomtest(int(k), int(n), p0).pvalue if n else np.nan


def fisher(a1, n1, a0, n0):
    return fisher_exact([[a1, n1 - a1], [a0, n0 - a0]])[1]


def chisq_uniform(counts):
    counts = np.asarray(counts, float); n = counts.sum(); m = len(counts)
    exp = n / m
    stat = ((counts - exp) ** 2 / exp).sum()
    return stat, 1 - chi2.cdf(stat, m - 1)


def load_q15(sym):
    s = pd.read_csv(f"{LENS}/{sym}_q15_sessions_aug.csv", index_col=0, parse_dates=True)
    s = s[s.n_q == 36].sort_index()
    b = pd.read_csv(f"{LENS}/{sym}_q15_bars.csv", parse_dates=["date"]); b = b[b.date.isin(s.index)].copy()
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col=0, parse_dates=True)
    s["sunday_open"] = x.loc[s.index, "sunday_open"].values
    s["period"] = np.where(s.index < "2026-10-01", "2026Q3", "2026Q4")
    s["crash_week"] = s.index.isin(CRASH_WEEK).astype(int)
    return s, b


def load_pop(sym):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col=0, parse_dates=True)
    x = x[x.n_bars == 9].copy()
    x = x[~x.index.isin(SPLICE[sym])]
    x["quarter"] = x.index.to_period("Q").astype(str)
    x["half"] = np.where(x.index < "2025-09-01", "H1", "H2")
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    p = p[p.date.isin(x.index)].copy()
    p["quarter"] = p.date.dt.to_period("Q").astype(str)
    p["half"] = np.where(p.date < "2025-09-01", "H1", "H2")
    return x, p


class Log:
    def __init__(self, path):
        self.path = path; self.lines = []
    def __call__(self, *a):
        s = " ".join(str(x) for x in a); print(s); self.lines.append(s)
    def close(self):
        with open(self.path, "w") as f: f.write("\n".join(self.lines))
