"""Shared helpers for the regime/robustness refutation of the lens_context claims."""
import numpy as np
import pandas as pd
from scipy import stats

LENS = "research/extremes/scripts/lens_context"
OUT = "research/extremes/scripts/refute_context_regime"
RNG = np.random.default_rng(7)

REGIMES = {
    "tariff_Apr25": ("2025-04-02", "2025-04-30"),
    "iran_war_MarApr26": ("2026-02-27", "2026-04-10"),
    "crash_Nov26": ("2026-11-03", "2026-11-06"),
}
QUARTERS = ["2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2", "2026Q3", "2026Q4"]


def load(sym):
    f = pd.read_csv(f"{LENS}/frame_{sym}.csv", parse_dates=["date"]).set_index("date").copy()
    q = f.index.to_period("Q").astype(str)
    q = np.where(f.index < pd.Timestamp("2024-07-01"), "2024Q3", q)  # fold 2024-06-18..30 into 2024Q3
    add = pd.DataFrame(index=f.index)
    add["quarter"] = q
    add["sunday"] = (f["dow"] == 4).astype(int)
    add["monday"] = (f["dow"] == 0).astype(int)
    med = f["asia_rng_med20"] * 1e4  # fraction -> bp, as in final_tables.py
    add["scaled_high"] = f["dist_rth_high0"] / med   # signed: negative when the 17:00 close is above the RTH high
    add["scaled_low"] = -f["dist_rth_low0"] / med
    add["regime"] = "normal"
    f = pd.concat([f, add], axis=1)
    for k, (a, b) in REGIMES.items():
        m = (f.index >= pd.Timestamp(a)) & (f.index <= pd.Timestamp(b))
        f.loc[m, "regime"] = k
    return f


def boot_ci(x, fn=np.mean, B=2000, alpha=0.10):
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return (np.nan, np.nan)
    idx = RNG.integers(0, len(x), size=(B, len(x)))
    s = np.array([fn(x[i]) for i in idx])
    return (np.quantile(s, alpha / 2), np.quantile(s, 1 - alpha / 2))


def boot_diff_ci(a, b, B=2000, alpha=0.10):
    a = np.asarray(a, float); b = np.asarray(b, float)
    a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    if len(a) == 0 or len(b) == 0:
        return (np.nan, np.nan)
    ia = RNG.integers(0, len(a), size=(B, len(a))); ib = RNG.integers(0, len(b), size=(B, len(b)))
    s = a[ia].mean(1) - b[ib].mean(1)
    return (np.quantile(s, alpha / 2), np.quantile(s, 1 - alpha / 2))


def fisher(a, b):
    """a, b: 0/1 arrays. Returns p-value of Fisher exact test on the 2x2."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    t = [[int(a.sum()), int(len(a) - a.sum())], [int(b.sum()), int(len(b) - b.sum())]]
    return stats.fisher_exact(t)[1]


def rate_diff(df, mask_a, mask_b, t):
    a = df.loc[mask_a, t].dropna(); b = df.loc[mask_b, t].dropna()
    if len(a) == 0 or len(b) == 0:
        return dict(n_a=len(a), n_b=len(b), p_a=np.nan, p_b=np.nan, diff=np.nan, p=np.nan)
    return dict(n_a=len(a), n_b=len(b), p_a=a.mean(), p_b=b.mean(), diff=a.mean() - b.mean(), p=fisher(a, b))


def rate_diff_by_quarter(df, mask_a, mask_b, t, label=""):
    rows = []
    for q in QUARTERS:
        m = df["quarter"] == q
        r = rate_diff(df, mask_a & m, mask_b & m, t)
        r["quarter"] = q
        rows.append(r)
    tab = pd.DataFrame(rows).set_index("quarter")
    return tab


def rate_diff_by_regime(df, mask_a, mask_b, t):
    rows = []
    for k in REGIMES:
        m = df["regime"] == k
        r_in = rate_diff(df, mask_a & m, mask_b & m, t); r_in["set"] = f"in:{k}"
        r_ex = rate_diff(df, mask_a & ~m, mask_b & ~m, t); r_ex["set"] = f"ex:{k}"
        rows += [r_in, r_ex]
    s = df["sunday"] == 1
    r = rate_diff(df, mask_a & s, mask_b & s, t); r["set"] = "sunday_only"; rows.append(r)
    r = rate_diff(df, mask_a & ~s, mask_b & ~s, t); r["set"] = "ex_sunday"; rows.append(r)
    allx = df["regime"] != "normal"
    r = rate_diff(df, mask_a & ~allx, mask_b & ~allx, t); r["set"] = "ex_all_regimes"; rows.append(r)
    return pd.DataFrame(rows).set_index("set")


def leave5_rate_diff(df, mask_a, mask_b, t, k=5):
    """Greedy removal of the k nights that most support the rate difference p_a - p_b (sign-aware)."""
    a = df.loc[mask_a, t].dropna().copy(); b = df.loc[mask_b, t].dropna().copy()
    d0 = a.mean() - b.mean()
    sign = 1 if d0 >= 0 else -1
    removed = []
    for _ in range(k):
        # candidate removals: in a, remove an obs equal to (sign>0: 1 else 0); in b remove obs equal to (sign>0: 0 else 1)
        best = None
        va = 1 if sign > 0 else 0
        vb = 0 if sign > 0 else 1
        cand = []
        if (a == va).any() and len(a) > 1:
            a2 = a.drop(a[a == va].index[0]); cand.append(("a", a[a == va].index[0], sign * (a2.mean() - b.mean())))
        if (b == vb).any() and len(b) > 1:
            b2 = b.drop(b[b == vb].index[0]); cand.append(("b", b[b == vb].index[0], sign * (a.mean() - b2.mean())))
        if not cand:
            break
        best = min(cand, key=lambda c: c[2])
        if best[0] == "a":
            a = a.drop(best[1])
        else:
            b = b.drop(best[1])
        removed.append(best[1])
    d5 = a.mean() - b.mean()
    return dict(diff0=d0, diff_minus5=d5, p_minus5=fisher(a, b), n_a5=len(a), n_b5=len(b), removed=[str(pd.Timestamp(r).date()) for r in removed])


def spearman(x, y):
    m = ~(np.isnan(x) | np.isnan(y))
    if m.sum() < 5:
        return (np.nan, np.nan, int(m.sum()))
    r, p = stats.spearmanr(x[m], y[m])
    return (r, p, int(m.sum()))


def spearman_by_quarter(df, xcol, ycol):
    rows = []
    for q in QUARTERS:
        s = df[df["quarter"] == q]
        r, p, n = spearman(s[xcol].values.astype(float), s[ycol].values.astype(float))
        rows.append(dict(quarter=q, n=n, rho=r, p=p))
    return pd.DataFrame(rows).set_index("quarter")


def spearman_by_regime(df, xcol, ycol):
    rows = []
    for k in REGIMES:
        m = df["regime"] == k
        r, p, n = spearman(df.loc[m, xcol].values.astype(float), df.loc[m, ycol].values.astype(float)); rows.append(dict(set=f"in:{k}", n=n, rho=r, p=p))
        r, p, n = spearman(df.loc[~m, xcol].values.astype(float), df.loc[~m, ycol].values.astype(float)); rows.append(dict(set=f"ex:{k}", n=n, rho=r, p=p))
    s = df["sunday"] == 1
    r, p, n = spearman(df.loc[s, xcol].values.astype(float), df.loc[s, ycol].values.astype(float)); rows.append(dict(set="sunday_only", n=n, rho=r, p=p))
    r, p, n = spearman(df.loc[~s, xcol].values.astype(float), df.loc[~s, ycol].values.astype(float)); rows.append(dict(set="ex_sunday", n=n, rho=r, p=p))
    allx = df["regime"] != "normal"
    r, p, n = spearman(df.loc[~allx, xcol].values.astype(float), df.loc[~allx, ycol].values.astype(float)); rows.append(dict(set="ex_all_regimes", n=n, rho=r, p=p))
    return pd.DataFrame(rows).set_index("set")


def leave5_spearman(df, xcol, ycol, k=5):
    """Remove the k points with the largest same-sign contribution to the rank covariance."""
    s = df[[xcol, ycol]].dropna()
    x = s[xcol].rank().values; y = s[ycol].rank().values
    r0 = stats.spearmanr(x, y)[0]
    contrib = (x - x.mean()) * (y - y.mean()) * np.sign(r0)
    drop = np.argsort(-contrib)[:k]
    keep = np.ones(len(s), bool); keep[drop] = False
    r5, p5 = stats.spearmanr(x[keep], y[keep])
    return dict(rho0=r0, rho_minus5=r5, p_minus5=p5, removed=[str(d.date()) for d in s.index[drop]])


def skill_from_preds(y, p, pb):
    m = ~(np.isnan(y) | np.isnan(p) | np.isnan(pb))
    if m.sum() == 0:
        return np.nan, 0
    b = np.mean((p[m] - y[m]) ** 2); bb = np.mean((pb[m] - y[m]) ** 2)
    return 1 - b / bb, int(m.sum())


def skill_by_quarter(df, y, p, pb):
    rows = []
    for q in QUARTERS:
        m = (df["quarter"] == q).values
        s, n = skill_from_preds(y[m], p[m], pb[m])
        rows.append(dict(quarter=q, n=n, skill=s))
    return pd.DataFrame(rows).set_index("quarter")


def skill_top5(df, y, p, pb, k=5):
    """Share of the total Brier improvement from the k best nights; skill after removing them."""
    m = ~(np.isnan(y) | np.isnan(p) | np.isnan(pb))
    yy, pp, bb = y[m], p[m], pb[m]
    gain = (bb - yy) ** 2 - (pp - yy) ** 2
    tot = gain.sum()
    order = np.argsort(-gain)
    top = gain[order[:k]].sum()
    keep = np.ones(len(yy), bool); keep[order[:k]] = False
    s5 = 1 - np.sum((pp[keep] - yy[keep]) ** 2) / np.sum((bb[keep] - yy[keep]) ** 2)
    dates = df.index[m][order[:k]]
    return dict(top5_share=top / tot if tot != 0 else np.nan, skill_minus5=s5, removed=[str(d.date()) for d in dates])


def pinball(y, q, tau):
    d = y - q
    return np.mean(np.maximum(tau * d, (tau - 1) * d))


def pin_skill(y, q, qb, tau):
    m = ~(np.isnan(y) | np.isnan(q) | np.isnan(qb))
    if m.sum() == 0:
        return np.nan, 0
    return 1 - pinball(y[m], q[m], tau) / pinball(y[m], qb[m], tau), int(m.sum())


def pin_skill_by_quarter(df, y, q, qb, tau):
    rows = []
    for qq in QUARTERS:
        m = (df["quarter"] == qq).values
        s, n = pin_skill(y[m], q[m], qb[m], tau)
        rows.append(dict(quarter=qq, n=n, skill=s))
    return pd.DataFrame(rows).set_index("quarter")


def pin_top5(df, y, q, qb, tau, k=5):
    m = ~(np.isnan(y) | np.isnan(q) | np.isnan(qb))
    yy, qq, bb = y[m], q[m], qb[m]
    def pl(y_, q_):
        d = y_ - q_; return np.maximum(tau * d, (tau - 1) * d)
    gain = pl(yy, bb) - pl(yy, qq)
    tot = gain.sum(); order = np.argsort(-gain)
    keep = np.ones(len(yy), bool); keep[order[:k]] = False
    s5 = 1 - pl(yy[keep], qq[keep]).sum() / pl(yy[keep], bb[keep]).sum()
    return dict(top5_share=gain[order[:k]].sum() / tot if tot != 0 else np.nan, skill_minus5=s5,
                removed=[str(d.date()) for d in df.index[m][order[:k]]])


def fmt(tab):
    with pd.option_context("display.width", 200, "display.max_columns", 30, "display.float_format", "{:.3f}".format):
        return str(tab)
