import os, numpy as np, pandas as pd
ROOT = "."
EXT = os.path.join(ROOT, "research", "extremes")
H2 = pd.Timestamp("2025-09-01")
SPLICE = {"NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16", "2025-12-16", "2025-12-17"],
          "ES": ["2025-12-16", "2025-12-17"]}


def load_x(sym, full=True, drop_splice=True):
    x = pd.read_csv(os.path.join(EXT, f"{sym}_extremes.csv"), index_col="date", parse_dates=True).sort_index()
    if drop_splice:
        x = x[~x.index.isin(pd.to_datetime(SPLICE[sym]))]
    if full:
        x = x[x.n_bars == 9]
    return x


def load_panel(sym, full=True, drop_splice=True):
    p = pd.read_csv(os.path.join(EXT, f"{sym}_hourly_panel.csv"), parse_dates=["date"])
    if drop_splice:
        p = p[~p.date.isin(pd.to_datetime(SPLICE[sym]))]
    if full:
        p = p[p.n_bars == 9]
    return p


def load_1h(sym):
    h = pd.read_csv(os.path.join(ROOT, "data", f"{sym}_1h.csv"), index_col=0)
    h.index = pd.to_datetime(h.index, utc=True).tz_convert("America/New_York")
    h = h[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    h = h[~h.index.duplicated(keep="last")].sort_index()
    h = h[h.index.minute == 0]
    return h


def ci_prop(y, n_boot=2000, seed=0):
    y = np.asarray(y, float)
    if len(y) == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    b = [rng.choice(y, len(y), replace=True).mean() for _ in range(n_boot)]
    return (y.mean(), np.percentile(b, 5), np.percentile(b, 95))


def ci_med(y, n_boot=2000, seed=0):
    y = np.asarray(y, float)
    rng = np.random.default_rng(seed)
    b = [np.median(rng.choice(y, len(y), replace=True)) for _ in range(n_boot)]
    return (np.median(y), np.percentile(b, 5), np.percentile(b, 95))


def ci_diff(a, b, n_boot=2000, seed=0):
    a = np.asarray(a, float); b = np.asarray(b, float)
    rng = np.random.default_rng(seed)
    d = [rng.choice(a, len(a)).mean() - rng.choice(b, len(b)).mean() for _ in range(n_boot)]
    return (a.mean() - b.mean(), np.percentile(d, 5), np.percentile(d, 95))


def fmt(t, pct=True):
    m, lo, hi = t
    if pct:
        return f"{m:.3f} [{lo:.3f}, {hi:.3f}]"
    return f"{m:.1f} [{lo:.1f}, {hi:.1f}]"


def halves(x):
    return x[x.index < H2], x[x.index >= H2]


def binom_p(k, n, p0):
    from scipy.stats import binomtest
    return binomtest(int(k), int(n), p0).pvalue
