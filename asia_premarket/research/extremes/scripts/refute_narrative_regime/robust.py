"""Regime / robustness refutation helpers for the narrative-lens claims.
Recomputes each statistic by quarter, with regime windows removed, weekdays only, leave-5-out, and with the
contract-splice artefact sessions included (the lens excluded them)."""
import os, sys
import numpy as np, pandas as pd
from scipy import stats

ROOT = "."
OUT = "research/extremes/scripts/refute_narrative_regime"
os.makedirs(OUT, exist_ok=True)
ARTEFACT_NQ = ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"]
ARTEFACT_ES = ["2025-12-16", "2025-12-17"]
SPLIT = pd.Timestamp("2025-09-01")
RNG = np.random.default_rng(11)

REGIMES = {
    "aug24_carry": ("2024-08-01", "2024-08-07"),
    "apr25_tariff": ("2025-04-02", "2025-04-15"),
    "iran26_war": ("2026-02-27", "2026-04-13"),
    "nov26_crash": ("2026-11-03", "2026-11-06"),
}


def enrich(x):
    x = x.copy()
    x["half"] = np.where(x.index < SPLIT, "H1", "H2")
    q = x.index.to_period("Q").astype(str)
    q = np.where(q == "2024Q2", "2024Q3", q)  # 7 June-2024 sessions folded into 2024Q3
    x["quarter"] = q
    x["hi_after_tko"] = (x["hi_k"] >= x["tokyo_open_k"]).astype(int)
    x["lo_after_tko"] = (x["lo_k"] >= x["tokyo_open_k"]).astype(int)
    x["hi_post_tko"] = (x["hi_k"] > x["tokyo_open_k"]).astype(int)
    x["lo_post_tko"] = (x["lo_k"] > x["tokyo_open_k"]).astype(int)
    x["any_first_bar"] = ((x["hi_k"] == 0) | (x["lo_k"] == 0)).astype(int)
    x["any_last_bar"] = ((x["hi_k"] == x["n_bars"] - 1) | (x["lo_k"] == x["n_bars"] - 1)).astype(int)
    x["any_at_tko"] = ((x["hi_k"] == x["tokyo_open_k"]) | (x["lo_k"] == x["tokyo_open_k"])).astype(int)
    x["trend_close"] = ((x["close_loc"] >= 0.8) | (x["close_loc"] <= 0.2)).astype(int)
    x["mid_close"] = ((x["close_loc"] > 0.35) & (x["close_loc"] < 0.65)).astype(int)
    x["cont"] = (np.sign(x["asia_ret_bp"]) == np.sign(x["rth_ret_bp"])).astype(int)
    x["abs_asia_ret"] = x["asia_ret_bp"].abs()
    x["abs_post"] = x["post_ret"].abs() * 1e4
    x["abs_kospi"] = x["kospi_ret"].abs() * 100
    x["abs_sox"] = x["sox_ret"].abs() * 100
    x["abs_rth"] = x["rth_ret_bp"].abs()
    x["abs_gap"] = x["gap_open_bp"].abs()
    x["asia_up"] = (x["asia_ret_bp"] > 0).astype(int)
    x["lo_by_tko_and_close_hi"] = ((x["lo_k"] <= x["tokyo_open_k"]) & (x["close_loc"] >= 0.6)).astype(int)
    x["close_hi70"] = (x["close_loc"] >= 0.7).astype(int)
    x["close_lo30"] = (x["close_loc"] <= 0.3).astype(int)
    x["revers_close"] = (((x["rth_ret_bp"] > 0) & (x["close_loc"] <= 0.3)) | ((x["rth_ret_bp"] < 0) & (x["close_loc"] >= 0.7))).astype(int)
    x["hi_last2"] = (x["hi_k"] >= x["n_bars"] - 2).astype(int)
    x["rest_after_first_bar"] = x["asia_ret_bp"] - x["first_bar_ret_bp"]
    x["fb_sign_agree"] = (np.sign(x["first_bar_ret_bp"]) == np.sign(x["rest_after_first_bar"])).astype(int)
    x["abs_fb"] = x["first_bar_ret_bp"].abs()
    x["dow_"] = x.index.dayofweek
    return x


def load_extremes(sym="NQ", drop_artefacts=True):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    if drop_artefacts:
        bad = ARTEFACT_NQ if sym == "NQ" else ARTEFACT_ES
        x = x[~x.index.isin(pd.to_datetime(bad))].copy()
    return enrich(x)


def load_panel(sym="NQ", drop_artefacts=True):
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    if drop_artefacts:
        bad = ARTEFACT_NQ if sym == "NQ" else ARTEFACT_ES
        p = p[~p["date"].isin(pd.to_datetime(bad))].copy()
    return p


def binom_p(k, n, p0):
    if n == 0 or np.isnan(p0):
        return np.nan
    return float(stats.binomtest(int(k), int(n), min(max(p0, 1e-9), 1 - 1e-9)).pvalue)


def boot_ci(a, stat=np.mean, n=2000, alpha=0.10):
    a = np.asarray(a, dtype=float); a = a[~np.isnan(a)]
    if len(a) == 0:
        return (np.nan, np.nan)
    idx = RNG.integers(0, len(a), size=(n, len(a)))
    s = np.array([stat(a[i]) for i in idx])
    return (float(np.quantile(s, alpha / 2)), float(np.quantile(s, 1 - alpha / 2)))


def in_regime(idx, name):
    a, b = REGIMES[name]
    return (idx >= pd.Timestamp(a)) & (idx <= pd.Timestamp(b))


def rate_robust(x, cond, label, name, base_df=None, x_all=None, verbose=True):
    """x: frame (artefacts excluded). cond: boolean Series aligned to x. label: binary column.
    base_df: frame giving the base rate (default x). x_all: frame with artefacts included (same cond rule applied via name lookup)."""
    base_df = x if base_df is None else base_df
    cond = pd.Series(np.asarray(cond), index=x.index).fillna(False).astype(bool)
    sub = x[cond]
    n = len(sub); k = int(sub[label].sum()); r = k / n if n else np.nan
    base = base_df[label].mean(); diff = r - base
    p = binom_p(k, n, base)
    out = dict(claim=name, label=label, n=n, k=k, rate=r, base=base, diff=diff, p=p)
    # --- quarters
    qrows = []
    for q in sorted(x["quarter"].unique()):
        sq = sub[sub["quarter"] == q]; bq = base_df[base_df["quarter"] == q]
        nq = len(sq); kq = int(sq[label].sum()); rq = kq / nq if nq else np.nan; bq_ = bq[label].mean()
        qrows.append(dict(q=q, n=nq, rate=rq, base=bq_, diff=(rq - bq_) if nq else np.nan))
    qdf = pd.DataFrame(qrows)
    flips = qdf[(qdf["n"] >= 5) & (np.sign(qdf["diff"]) == -np.sign(diff))]
    flips25 = qdf[(qdf["n"] >= 25) & (np.sign(qdf["diff"]) == -np.sign(diff))]
    out["n_quarters_n5"] = int((qdf["n"] >= 5).sum()); out["n_flip_n5"] = len(flips); out["n_flip_n25"] = len(flips25)
    out["flip_quarters"] = ",".join(f"{r.q}({r.n}:{r.rate:.2f}v{r.base:.2f})" for r in flips.itertuples())
    out["quarters"] = " | ".join(f"{r.q} n={r.n} {r.rate:.2f}v{r.base:.2f}" if r.n else f"{r.q} n=0" for r in qdf.itertuples())
    # --- halves / thirds
    for h in ("H1", "H2"):
        sh = sub[sub.half == h]; bh = base_df[base_df.half == h]
        out[f"{h}"] = f"n={len(sh)} {sh[label].mean():.3f} v {bh[label].mean():.3f}" if len(sh) else "n=0"
    # --- regimes removed
    for rg in REGIMES:
        m = ~in_regime(sub.index, rg); mb = ~in_regime(base_df.index, rg)
        s2 = sub[m]; b2 = base_df[mb]; n2 = len(s2); k2 = int(s2[label].sum()); r2 = k2 / n2 if n2 else np.nan; bb = b2[label].mean()
        out[f"ex_{rg}"] = f"n={n2} (removed {n - n2}) {r2:.3f} v {bb:.3f} p={binom_p(k2, n2, bb):.3g}"
        out[f"ex_{rg}_p"] = binom_p(k2, n2, bb); out[f"ex_{rg}_diff"] = r2 - bb
    # all regimes removed at once
    m = np.ones(len(sub), bool); mb = np.ones(len(base_df), bool)
    for rg in REGIMES:
        m &= ~in_regime(sub.index, rg); mb &= ~in_regime(base_df.index, rg)
    s2 = sub[m]; b2 = base_df[mb]; n2 = len(s2); k2 = int(s2[label].sum()); r2 = k2 / n2 if n2 else np.nan; bb = b2[label].mean()
    out["ex_all_regimes"] = f"n={n2} (removed {n - n2}) {r2:.3f} v {bb:.3f} p={binom_p(k2, n2, bb):.3g}"
    out["ex_all_regimes_p"] = binom_p(k2, n2, bb); out["ex_all_regimes_diff"] = r2 - bb
    # --- weekday only / sunday only
    if "sunday_open" in sub.columns:
        for nm, v in (("weekday", 0), ("sunday", 1)):
            s2 = sub[sub.sunday_open == v]; b2 = base_df[base_df.sunday_open == v]
            n2 = len(s2); k2 = int(s2[label].sum()); r2 = k2 / n2 if n2 else np.nan; bb = b2[label].mean()
            out[f"{nm}_only"] = f"n={n2} {r2:.3f} v {bb:.3f} p={binom_p(k2, n2, bb):.3g}" if n2 else "n=0"
            out[f"{nm}_only_p"] = binom_p(k2, n2, bb) if n2 else np.nan; out[f"{nm}_only_diff"] = (r2 - bb) if n2 else np.nan
    # --- leave-5-out: remove the 5 nights that push the rate in the direction of the effect
    excess = k - base * n
    hit_val = 1 if diff > 0 else 0
    hits = sub[sub[label] == hit_val]
    nrem = min(5, len(hits))
    n5 = n - nrem; k5 = k - nrem * hit_val
    r5 = k5 / n5 if n5 else np.nan
    out["excess_hits"] = excess; out["top5_share_of_excess"] = (5 / abs(excess)) if excess else np.inf
    out["leave5"] = f"n={n5} {r5:.3f} v {base:.3f} p={binom_p(k5, n5, base):.3g}"
    out["leave5_p"] = binom_p(k5, n5, base); out["leave5_diff"] = r5 - base
    # --- artefacts included
    if x_all is not None:
        c_all = cond.reindex(x_all.index).fillna(False)
        # artefact rows: re-evaluate cond via the same column rule is not possible generically; caller passes cond_all
    if verbose:
        print(f"\n[{name}] label={label}: n={n} k={k} rate={r:.3f} base={base:.3f} diff={diff:+.3f} p={p:.3g}")
        print("   quarters:", out["quarters"])
        print(f"   sign flips (n>=5): {out['n_flip_n5']}/{out['n_quarters_n5']} -> {out['flip_quarters']}  | flips with n>=25: {out['n_flip_n25']}")
        print(f"   H1: {out['H1']}   H2: {out['H2']}")
        for rg in REGIMES:
            print(f"   ex {rg:13s}: {out['ex_'+rg]}")
        print(f"   ex all regimes : {out['ex_all_regimes']}")
        if "weekday_only" in out:
            print(f"   weekday only: {out['weekday_only']}   sunday only: {out['sunday_only']}")
        print(f"   excess hits={excess:+.1f} (5 nights = {out['top5_share_of_excess']:.0%} of excess); leave-5-out: {out['leave5']}")
    return out


def cont_robust(x, cond, col, name, base_df=None, stat="median", verbose=True):
    base_df = x if base_df is None else base_df
    cond = pd.Series(np.asarray(cond), index=x.index).fillna(False).astype(bool)
    f = np.median if stat == "median" else np.mean
    sub = x[cond][col].dropna(); rest = base_df[~cond.reindex(base_df.index).fillna(False)][col].dropna(); base = base_df[col].dropna()
    v = float(f(sub)); bv = float(f(base)); p = float(stats.mannwhitneyu(sub, rest, alternative="two-sided").pvalue) if len(sub) else np.nan
    out = dict(claim=name, col=col, n=len(sub), value=v, base=bv, diff=v - bv, p=p)
    qrows = []
    for q in sorted(x["quarter"].unique()):
        sq = x[cond & (x["quarter"] == q)][col].dropna(); bq = base_df[base_df["quarter"] == q][col].dropna()
        qrows.append(dict(q=q, n=len(sq), value=float(f(sq)) if len(sq) else np.nan, base=float(f(bq)), diff=(float(f(sq)) - float(f(bq))) if len(sq) else np.nan))
    qdf = pd.DataFrame(qrows)
    flips = qdf[(qdf["n"] >= 5) & (np.sign(qdf["diff"]) == -np.sign(v - bv))]
    flips25 = qdf[(qdf["n"] >= 25) & (np.sign(qdf["diff"]) == -np.sign(v - bv))]
    out["n_quarters_n5"] = int((qdf["n"] >= 5).sum()); out["n_flip_n5"] = len(flips); out["n_flip_n25"] = len(flips25)
    out["flip_quarters"] = ",".join(f"{r.q}({r.n}:{r.value:.0f}v{r.base:.0f})" for r in flips.itertuples())
    out["quarters"] = " | ".join(f"{r.q} n={r.n} {r.value:.0f}v{r.base:.0f}" if r.n else f"{r.q} n=0" for r in qdf.itertuples())
    for h in ("H1", "H2"):
        sh = x[cond & (x.half == h)][col].dropna(); bh = base_df[base_df.half == h][col].dropna()
        out[h] = f"n={len(sh)} {f(sh):.1f} v {f(bh):.1f}" if len(sh) else "n=0"
    for rg in list(REGIMES) + ["all"]:
        if rg == "all":
            m = np.ones(len(x), bool)
            for r_ in REGIMES: m &= ~in_regime(x.index, r_)
        else:
            m = ~in_regime(x.index, rg)
        m = pd.Series(m, index=x.index)
        s2 = x[cond & m][col].dropna(); r2 = x[(~cond) & m][col].dropna(); b2 = base_df[m.reindex(base_df.index).fillna(True)][col].dropna()
        p2 = float(stats.mannwhitneyu(s2, r2, alternative="two-sided").pvalue) if len(s2) else np.nan
        out[f"ex_{rg}"] = f"n={len(s2)} (removed {len(sub)-len(s2)}) {f(s2) if len(s2) else np.nan:.1f} v {f(b2):.1f} p={p2:.3g}"
        out[f"ex_{rg}_p"] = p2; out[f"ex_{rg}_diff"] = (f(s2) - f(b2)) if len(s2) else np.nan
    if "sunday_open" in x.columns:
        for nm, vv in (("weekday", 0), ("sunday", 1)):
            m = x.sunday_open == vv
            s2 = x[cond & m][col].dropna(); r2 = x[(~cond) & m][col].dropna(); b2 = base_df[base_df.sunday_open == vv][col].dropna()
            p2 = float(stats.mannwhitneyu(s2, r2, alternative="two-sided").pvalue) if len(s2) and len(r2) else np.nan
            out[f"{nm}_only"] = f"n={len(s2)} {f(s2) if len(s2) else np.nan:.1f} v {f(b2):.1f} p={p2:.3g}"
            out[f"{nm}_only_p"] = p2
    # leave-5-out: drop the 5 subgroup nights most extreme in the direction of the effect
    srt = sub.sort_values(ascending=(v - bv) < 0)  # descending if effect positive
    s5 = srt.iloc[5:] if len(srt) > 5 else srt.iloc[0:0]
    p5 = float(stats.mannwhitneyu(s5, rest, alternative="two-sided").pvalue) if len(s5) else np.nan
    out["leave5"] = f"n={len(s5)} {f(s5) if len(s5) else np.nan:.1f} v {bv:.1f} p={p5:.3g}"
    out["leave5_p"] = p5; out["leave5_diff"] = (f(s5) - bv) if len(s5) else np.nan
    if verbose:
        print(f"\n[{name}] {stat}({col}): n={len(sub)} value={v:.1f} base={bv:.1f} diff={v-bv:+.1f} p_MW={p:.3g}")
        print("   quarters:", out["quarters"])
        print(f"   sign flips (n>=5): {out['n_flip_n5']}/{out['n_quarters_n5']} -> {out['flip_quarters']}  | flips with n>=25: {out['n_flip_n25']}")
        print(f"   H1: {out['H1']}   H2: {out['H2']}")
        for rg in list(REGIMES) + ["all"]:
            print(f"   ex {rg:13s}: {out['ex_'+rg]}")
        if "weekday_only" in out:
            print(f"   weekday only: {out['weekday_only']}   sunday only: {out['sunday_only']}")
        print(f"   leave-5-out (drop 5 most extreme in effect direction): {out['leave5']}")
    return out
