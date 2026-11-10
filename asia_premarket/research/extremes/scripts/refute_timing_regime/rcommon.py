"""Regime/robustness refuter helpers: quarters, regime windows, leave-5-out, Sunday split."""
import os
import numpy as np
import pandas as pd
from scipy import stats

ROOT = "."
OUT = "research/extremes/scripts/refute_timing_regime"
os.makedirs(OUT, exist_ok=True)
SPLIT = pd.Timestamp("2025-09-01")
BAD = {
    "NQ": [pd.Timestamp("2024-06-21"), pd.Timestamp("2024-12-20"), pd.Timestamp("2025-03-21"), pd.Timestamp("2025-09-16")],
    "ES": [pd.Timestamp("2025-12-15"), pd.Timestamp("2025-12-16"), pd.Timestamp("2025-12-17")],
}
# regime windows on the RTH date D (the Asia session that follows D)
REGIMES = {
    "tariff_apr25": (pd.Timestamp("2025-04-02"), pd.Timestamp("2025-04-30")),
    "iran_war_acute": (pd.Timestamp("2026-02-27"), pd.Timestamp("2026-04-10")),
    "nov5_crash": (pd.Timestamp("2026-11-04"), pd.Timestamp("2026-11-09")),
}
RNG = np.random.default_rng(11)


def quarter_label(dates):
    d = pd.DatetimeIndex(dates)
    q = d.to_period("Q").astype(str)
    q = np.where(q == "2024Q2", "2024Q3", q)   # 9 sessions of June 2024 folded into 2024Q3
    return pd.Series(q, index=dates if isinstance(dates, pd.Index) else None).values


def load(sym="NQ", drop_bad=True):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    if drop_bad:
        x = x[~x.index.isin(BAD[sym])]
        p = p[~p["date"].isin(BAD[sym])]
    x["half"] = np.where(x.index < SPLIT, "H1", "H2")
    p["half"] = np.where(p["date"] < SPLIT, "H1", "H2")
    x["q"] = quarter_label(x.index)
    p["q"] = quarter_label(p["date"])
    x["regime"] = "normal"
    p["regime"] = "normal"
    for name, (a, b) in REGIMES.items():
        x.loc[(x.index >= a) & (x.index <= b), "regime"] = name
        p.loc[(p.date >= a) & (p.date <= b), "regime"] = name
    p = p.join(x[["sunday_open"]], on="date")
    return x, p


def binom_p(k, n, p0):
    if n == 0 or np.isnan(p0) or p0 <= 0 or p0 >= 1:
        return np.nan
    return float(stats.binomtest(int(k), int(n), p0).pvalue)


def boot_ci(v, fn=np.mean, n_boot=2000, alpha=0.10):
    v = np.asarray(v, dtype=float); v = v[~np.isnan(v)]
    if len(v) < 2:
        return (np.nan, np.nan)
    idx = RNG.integers(0, len(v), size=(n_boot, len(v)))
    b = np.array([fn(v[i]) for i in idx])
    return (float(np.quantile(b, alpha / 2)), float(np.quantile(b, 1 - alpha / 2)))


def rate(mask, y):
    m = np.asarray(pd.Series(mask).fillna(False).values, dtype=bool)
    yy = np.asarray(pd.Series(y).values, dtype=float)[m]
    yy = yy[~np.isnan(yy)]
    return (float(yy.mean()) if len(yy) else np.nan, int(len(yy)), int(np.nansum(yy)))


def rate_check(df, cond, ycol, label, unit_col="date", base_mask=None, min_n=25):
    """Full robustness block for a binary conditional rate.
    df: DataFrame with columns q, regime, sunday_open, half, and unit_col (session id).
    cond: boolean Series aligned with df. ycol: binary outcome column.
    base = rate of y over base_mask (default: all rows of df).
    Returns dict with overall, per-quarter signs, leave-5-out, regime exclusions, sunday split."""
    cond = pd.Series(np.asarray(cond, bool), index=df.index)
    bm = pd.Series(True, index=df.index) if base_mask is None else pd.Series(np.asarray(base_mask, bool), index=df.index)
    y = df[ycol]
    base, nb, _ = rate(bm, y)
    r, n, k = rate(cond, y)
    lift = r - base
    sign = np.sign(lift)
    out = dict(claim=label, n=n, k=k, rate=r, base=base, lift=lift, p=binom_p(k, n, base))
    # per quarter
    flips = []; qrows = []
    for q in sorted(df.q.unique()):
        dq = df.q == q
        bq, _, _ = rate(bm & dq, y)
        rq, nq, kq = rate(cond & dq, y)
        qrows.append((q, nq, rq, bq))
        if nq >= min_n and not np.isnan(rq) and np.sign(rq - bq) == -sign and abs(rq - bq) > 0:
            flips.append(q)
    out["quarters"] = " | ".join(f"{q}:{rq:.2f}({nq})vs{bq:.2f}" if not np.isnan(rq) else f"{q}:na({nq})" for q, nq, rq, bq in qrows)
    out["n_quarters_same_sign"] = sum(1 for q, nq, rq, bq in qrows if not np.isnan(rq) and np.sign(rq - bq) == sign)
    out["n_quarters_eval"] = sum(1 for q, nq, rq, bq in qrows if not np.isnan(rq))
    out["flip_quarters_n>=%d" % min_n] = ",".join(flips)
    out["n_flips"] = len(flips)
    # leave-5-out: remove the 5 sessions that contribute most to the lift
    # contribution of a session = sum over its rows in cond of (y - base)*sign
    sub = df[cond]
    contrib = ((sub[ycol] - base) * sign).groupby(sub[unit_col]).sum().sort_values(ascending=False)
    drop5 = contrib.index[:5]
    keep = ~df[unit_col].isin(drop5)
    r5, n5, k5 = rate(cond & keep, y)
    base5, _, _ = rate(bm & keep, y)
    out["l5o_rate"] = r5; out["l5o_n"] = n5; out["l5o_p"] = binom_p(k5, n5, base5); out["l5o_base"] = base5
    out["l5o_kills"] = bool((np.sign(r5 - base5) != sign) or (out["l5o_p"] > 0.05))
    out["top5_sessions"] = ",".join(str(pd.Timestamp(d).date()) for d in drop5)
    out["top5_share_of_lift"] = float(contrib.iloc[:5].sum() / contrib.sum()) if contrib.sum() > 0 else np.nan
    # how many sessions must be removed to kill (p>0.05)
    killed = np.nan
    cum = 0
    for i in range(min(len(contrib), 60)):
        keep_i = ~df[unit_col].isin(contrib.index[: i + 1])
        ri, ni, ki = rate(cond & keep_i, y); bi, _, _ = rate(bm & keep_i, y)
        if np.isnan(ri) or np.sign(ri - bi) != sign or binom_p(ki, ni, bi) > 0.05:
            killed = i + 1; break
    out["sessions_to_kill"] = killed
    # regime exclusions and within-regime
    for name in REGIMES:
        ex = df.regime != name
        re_, ne, ke = rate(cond & ex, y); be, _, _ = rate(bm & ex, y)
        ri, ni, ki = rate(cond & ~ex, y); bi, _, _ = rate(bm & ~ex, y)
        out[f"ex_{name}"] = f"{re_:.3f} vs {be:.3f} (n={ne}, p={binom_p(ke, ne, be):.2g})"
        out[f"in_{name}"] = f"{ri:.2f} vs {bi:.2f} (n={ni})" if ni else "n=0"
    allx = ~df.regime.isin(list(REGIMES))
    ra, na, ka = rate(cond & allx, y); ba, _, _ = rate(bm & allx, y)
    out["ex_all_regimes"] = f"{ra:.3f} vs {ba:.3f} (n={na}, p={binom_p(ka, na, ba):.2g})"
    # Sunday split
    sun = df.sunday_open == 1
    rs, ns, ks = rate(cond & sun, y); bs, _, _ = rate(bm & sun, y)
    rw, nw, kw = rate(cond & ~sun, y); bw, _, _ = rate(bm & ~sun, y)
    out["sunday_only"] = f"{rs:.3f} vs {bs:.3f} (n={ns}, p={binom_p(ks, ns, bs):.2g})"
    out["weekday_only"] = f"{rw:.3f} vs {bw:.3f} (n={nw}, p={binom_p(kw, nw, bw):.2g})"
    # halves
    for hh in ("H1", "H2"):
        hm = df.half == hh
        rh, nh, kh = rate(cond & hm, y); bh, _, _ = rate(bm & hm, y)
        out[hh] = f"{rh:.3f} vs {bh:.3f} (n={nh})"
    out["verdict_rule"] = "REFUTE(flips>1)" if len(flips) > 1 else ("REFUTE(l5o)" if out["l5o_kills"] else "holds")
    return out


def median_check(df, cond_a, cond_b, col, label, unit_col="date", min_n=25):
    """Difference of medians between two groups, by quarter, leave-5-out, regime, Sunday."""
    a = pd.Series(np.asarray(cond_a, bool), index=df.index); b = pd.Series(np.asarray(cond_b, bool), index=df.index)
    v = df[col]
    ma, mb = v[a].median(), v[b].median()
    sign = np.sign(ma - mb)
    out = dict(claim=label, n_a=int(a.sum()), n_b=int(b.sum()), med_a=ma, med_b=mb, diff=ma - mb,
               p_mw=float(stats.mannwhitneyu(v[a].dropna(), v[b].dropna()).pvalue) if a.sum() > 1 and b.sum() > 1 else np.nan)
    flips = []; qrows = []
    for q in sorted(df.q.unique()):
        dq = df.q == q
        xa = v[a & dq].dropna(); xb = v[b & dq].dropna()
        d = xa.median() - xb.median() if len(xa) and len(xb) else np.nan
        qrows.append((q, len(xa), len(xb), d))
        if len(xa) >= min_n and len(xb) >= min_n and not np.isnan(d) and np.sign(d) == -sign:
            flips.append(q)
    out["quarters"] = " | ".join(f"{q}:{d:+.1f}({na}/{nb})" if not np.isnan(d) else f"{q}:na" for q, na, nb, d in qrows)
    out["n_quarters_same_sign"] = sum(1 for q, na, nb, d in qrows if not np.isnan(d) and np.sign(d) == sign)
    out["n_quarters_eval"] = sum(1 for q, na, nb, d in qrows if not np.isnan(d))
    out["flip_quarters"] = ",".join(flips); out["n_flips"] = len(flips)
    # leave-5-out: drop the 5 sessions in group a with the most extreme values in the claimed direction
    sub = df[a]
    contrib = ((sub[col] - mb) * sign).groupby(sub[unit_col]).sum().sort_values(ascending=False)
    drop5 = contrib.index[:5]
    keep = ~df[unit_col].isin(drop5)
    xa5 = v[a & keep].dropna(); xb5 = v[b & keep].dropna()
    out["l5o_diff"] = xa5.median() - xb5.median()
    out["l5o_p_mw"] = float(stats.mannwhitneyu(xa5, xb5).pvalue) if len(xa5) > 1 and len(xb5) > 1 else np.nan
    out["l5o_kills"] = bool(np.sign(out["l5o_diff"]) != sign or out["l5o_p_mw"] > 0.05)
    out["top5_sessions"] = ",".join(str(pd.Timestamp(d).date()) for d in drop5)
    for name in REGIMES:
        ex = df.regime != name
        xa_ = v[a & ex].dropna(); xb_ = v[b & ex].dropna()
        out[f"ex_{name}"] = f"{xa_.median() - xb_.median():+.2f} (p={stats.mannwhitneyu(xa_, xb_).pvalue:.2g})" if len(xa_) > 1 and len(xb_) > 1 else "na"
    allx = ~df.regime.isin(list(REGIMES))
    xa_ = v[a & allx].dropna(); xb_ = v[b & allx].dropna()
    out["ex_all_regimes"] = f"{xa_.median() - xb_.median():+.2f} (p={stats.mannwhitneyu(xa_, xb_).pvalue:.2g})"
    sun = df.sunday_open == 1
    for lab, m in [("sunday_only", sun), ("weekday_only", ~sun)]:
        xa_ = v[a & m].dropna(); xb_ = v[b & m].dropna()
        out[lab] = f"{xa_.median() - xb_.median():+.2f} (n={len(xa_)}/{len(xb_)}, p={stats.mannwhitneyu(xa_, xb_).pvalue:.2g})" if len(xa_) > 1 and len(xb_) > 1 else "na"
    for hh in ("H1", "H2"):
        hm = df.half == hh
        xa_ = v[a & hm].dropna(); xb_ = v[b & hm].dropna()
        out[hh] = f"{xa_.median():.2f} vs {xb_.median():.2f} ({len(xa_)}/{len(xb_)})"
    out["verdict_rule"] = "REFUTE(flips>1)" if len(flips) > 1 else ("REFUTE(l5o)" if out["l5o_kills"] else "holds")
    return out


def show(d, keys=None):
    for k, v in d.items():
        if keys and k not in keys: continue
        if isinstance(v, float):
            print(f"  {k:28s} {v:.4g}")
        else:
            print(f"  {k:28s} {v}")
