"""Independent recomputation of the OOS metrics from oos_intrasession_<SYM>.csv.

Usage: python3 metrics.py <oos_csv> <SYM>
Everything here is computed from the stored OOS columns only, except the walk-forward histogram baselines
(section F), which are recomputed from the detector population (panel + extremes) with the same month blocks.
"""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research/extremes/scripts/verify_0/run")
import detector_intrasession as det

CSV, SYM = sys.argv[1], sys.argv[2]
H2 = pd.Timestamp("2025-09-01")
rng = np.random.default_rng(123)

oos = pd.read_csv(CSV, parse_dates=["date"])
oos = oos.sort_values(["date", "k"]).reset_index(drop=True)
print(f"=== {SYM}: {CSV}")
print(f"rows {len(oos)}, sessions {oos['date'].nunique()}, {oos['date'].min().date()} .. {oos['date'].max().date()}, "
      f"k range {oos['k'].min()}..{oos['k'].max()}, refit blocks {oos['refit_block'].nunique()}, calibrated rows {oos['calibrated'].mean():.3f}")
h1m = oos["date"] < H2
print(f"H1 sessions {oos.loc[h1m, 'date'].nunique()}, H2 sessions {oos.loc[~h1m, 'date'].nunique()}")
print("rows per session:", oos.groupby("date").size().value_counts().to_dict())


def brier(y, p):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def logloss(y, p, eps=1e-4):
    p = np.clip(np.asarray(p, float), eps, 1 - eps); y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc(y, p):
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y)
    return float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else np.nan


def pinball(y, q, tau):
    e = np.asarray(y, float) - np.asarray(q, float)
    return float(np.mean(np.maximum(tau * e, (tau - 1) * e)))


def boot_skill(g, ycol, pcol, bcol, n_boot=1000, seed=0):
    """Session-level bootstrap 90% CI of skill = 1 - Brier(p)/Brier(b)."""
    r = np.random.default_rng(seed)
    sess = g["date"].unique()
    idx = {d: np.flatnonzero(g["date"].values == d) for d in sess}
    y = g[ycol].values.astype(float); p = g[pcol].values.astype(float); b = g[bcol].values.astype(float)
    sp = (p - y) ** 2; sb = (b - y) ** 2
    out = []
    for _ in range(n_boot):
        pick = r.choice(sess, size=len(sess), replace=True)
        ii = np.concatenate([idx[d] for d in pick])
        out.append(1 - sp[ii].mean() / sb[ii].mean())
    return float(np.percentile(out, 5)), float(np.percentile(out, 95))


# ------------------------------------------------------------------ A/B. classification tables
for side in ["high", "low"]:
    t = f"{side}_done"
    print(f"\n----- {SYM} {t}: Brier (base / k-only / LR / GB / raw / final), logloss (k-only / raw / final), AUC(final), skill vs k-only [90% CI] -----")
    groups = [(f"k={kk}", oos[oos["k"] == kk]) for kk in range(8)] + [("pool", oos)]
    for name, g in groups:
        y = g[t].values
        b = {c: brier(y, g[c]) for c in [f"base_{side}", f"kbase_{side}", f"p_{side}_lr", f"p_{side}_gb", f"p_{side}_raw", f"p_{side}_done"]}
        ll = {c: logloss(y, g[c]) for c in [f"kbase_{side}", f"p_{side}_raw", f"p_{side}_done"]}
        sk = 1 - b[f"p_{side}_done"] / b[f"kbase_{side}"]
        lo, hi = boot_skill(g, t, f"p_{side}_done", f"kbase_{side}", n_boot=1000 if name == "pool" else 300)
        g1 = g[g["date"] < H2]; g2 = g[g["date"] >= H2]
        s1 = 1 - brier(g1[t], g1[f"p_{side}_done"]) / brier(g1[t], g1[f"kbase_{side}"])
        s2 = 1 - brier(g2[t], g2[f"p_{side}_done"]) / brier(g2[t], g2[f"kbase_{side}"])
        print(f"{name:5s} n={len(g):4d} rate={y.mean():.3f} | " + " ".join(f"{v:.3f}" for v in b.values()) +
              f" | ll " + " ".join(f"{v:.3f}" for v in ll.values()) +
              f" | auc {auc(y, g[f'p_{side}_done']):.3f} | skill {sk:+.3f} [{lo:+.3f},{hi:+.3f}] | H1 {brier(g1[t], g1[f'kbase_{side}']):.3f}/{brier(g1[t], g1[f'p_{side}_done']):.3f}/{s1:+.3f}"
              f" H2 {brier(g2[t], g2[f'kbase_{side}']):.3f}/{brier(g2[t], g2[f'p_{side}_done']):.3f}/{s2:+.3f}")
    # pooled half CIs
    for hn, g in [("H1", oos[oos["date"] < H2]), ("H2", oos[oos["date"] >= H2])]:
        lo, hi = boot_skill(g, t, f"p_{side}_done", f"kbase_{side}", 1000)
        print(f"   {hn} pooled skill CI [{lo:+.3f},{hi:+.3f}]")
    # raw vs final by half
    for hn, g in [("H1", oos[oos["date"] < H2]), ("H2", oos[oos["date"] >= H2])]:
        print(f"   {hn} raw {brier(g[t], g[f'p_{side}_raw']):.4f} vs final {brier(g[t], g[f'p_{side}_done']):.4f}; "
              f"calibrated-only rows: raw {brier(g[g.calibrated==1][t], g[g.calibrated==1][f'p_{side}_raw']):.4f} final {brier(g[g.calibrated==1][t], g[g.calibrated==1][f'p_{side}_done']):.4f} (n={int((g.calibrated==1).sum())})")

    # C. calibration
    for col in [f"p_{side}_done", f"p_{side}_raw"]:
        b = pd.cut(oos[col].clip(0, 1), [0, .2, .4, .6, .8, 1.0], include_lowest=True)
        gg = oos.groupby(b, observed=False)
        tab = pd.DataFrame({"n": gg.size(), "pred": gg[col].mean(), "obs": gg[t].mean()})
        print(f"   calibration {col}: " + " | ".join(f"{int(r.n)} {r.pred:.3f}/{r.obs:.3f}" for r in tab.itertuples()))
        for hn, g in [("H1", oos[oos["date"] < H2]), ("H2", oos[oos["date"] >= H2])]:
            bb = pd.cut(g[col].clip(0, 1), [0, .2, .4, .6, .8, 1.0], include_lowest=True)
            print(f"      {hn} obs: " + "/".join(f"{v:.2f}" for v in g.groupby(bb, observed=False)[t].mean().values))

    # D. decision thresholds
    p = oos[f"p_{side}_done"].values; y = oos[t].values; isH1 = (oos["date"] < H2).values
    for thr in [0.8, 0.9, 0.95]:
        f = p >= thr
        prec = y[f].mean(); rec = f[y == 1].sum() / (y == 1).sum()
        pk = " ".join(f"{y[f & (oos['k'].values == kk)].mean():.2f}" for kk in range(2, 8))
        print(f"   p>={thr:.2f}: flagged {f.mean():.3f} n={f.sum()} precision {prec:.3f} (H1 {y[f & isH1].mean():.3f} / H2 {y[f & ~isH1].mean():.3f}) recall {rec:.3f} per-k k2..7 {pk}")
    for thr in [0.1, 0.2]:
        f = p <= thr
        print(f"   p<={thr:.2f}: flagged {f.mean():.3f} n={f.sum()} observed {y[f].mean():.3f}")

# ------------------------------------------------------------------ E. quantiles
print(f"\n----- {SYM} remaining-move quantiles: pinball skill vs per-k training quantile, coverage (target .5/.8) -----")
for cond in [False, True]:
    print("  conditional '_if_open' on not-yet-in rows" if cond else "  marginal, all rows")
    for side, ycol, sgn, done in [("up", "remaining_up_bp", 1.0, "high_done"), ("dn", "remaining_down_bp", -1.0, "low_done")]:
        base = oos[oos[done] == 0] if cond else oos
        for tau in [0.5, 0.8]:
            tag = f"p{int(tau*100)}"
            mcol = f"rem_{side}_{tag}_if_open" if cond else f"rem_{side}_{tag}"
            kcol = f"kqo_{side}_{tag}" if cond else f"kq_{side}_{tag}"
            res = []
            for name, g in [(f"k{kk}", base[base["k"] == kk]) for kk in range(8)] + [("pool", base)]:
                y = sgn * g[ycol].values; qm = sgn * g[mcol].values; qk = sgn * g[kcol].values
                pm, pk = pinball(y, qm, tau), pinball(y, qk, tau)
                res.append((name, len(g), 1 - pm / pk, np.mean(y <= qm), np.mean(y <= qk), np.median(y), np.median(qm)))
            pool = res[-1]
            print(f"    rem_{side} {tag}: pooled n={pool[1]} skill {pool[2]:+.3f} cov {pool[3]:.3f} (k-only cov {pool[4]:.3f}); med actual {pool[5]:.1f} model {pool[6]:.1f}; "
                  f"per-k skill " + " ".join(f"{r[2]:+.2f}" for r in res[:-1]) + " | per-k cov " + " ".join(f"{r[3]:.2f}" for r in res[:-1]))
            for hn, g in [("H1", base[base["date"] < H2]), ("H2", base[base["date"] >= H2])]:
                y = sgn * g[ycol].values; qm = sgn * g[mcol].values; qk = sgn * g[kcol].values
                print(f"       {hn}: skill {1 - pinball(y, qm, tau)/pinball(y, qk, tau):+.3f} cov {np.mean(y <= qm):.3f}")
# marginal P80 coverage on not-yet-in rows (the claimed ~.6)
for side, ycol, sgn, done in [("up", "remaining_up_bp", 1.0, "high_done"), ("dn", "remaining_down_bp", -1.0, "low_done")]:
    g = oos[oos[done] == 0]; y = sgn * g[ycol].values
    print(f"  marginal P80 coverage on not-yet-in rows rem_{side}: model {np.mean(y <= sgn*g[f'rem_{side}_p80'].values):.3f} k-only {np.mean(y <= sgn*g[f'kq_{side}_p80'].values):.3f} (n={len(g)})")
    g = oos[oos[done] == 1]; y = sgn * g[ycol].values
    print(f"  P50 median abs error on already-in rows rem_{side}: {np.median(np.abs(y - sgn*g[f'rem_{side}_p50'].values)):.2f} bp (n={len(g)})")

# ------------------------------------------------------------------ F. walk-forward histogram baselines
print(f"\n----- {SYM} walk-forward histogram baselines (same month blocks; training rows strictly before the block) -----")
d = det.build_dataset(SYM)
d["bs_hi"] = d["bars_since_hi"].clip(upper=3); d["bs_lo"] = d["bars_since_lo"].clip(upper=3)
d["pos3"] = pd.cut(d["pos_in_range"], [-0.01, 1/3, 2/3, 1.01], labels=False)
dates = np.array(sorted(d["date"].unique()))
blocks = det._month_blocks(dates[det.TRAIN_ONLY_SESSIONS:])
cells = {"hist_k_bs": ["k", "bs_hi"], "hist_k_bs_pos": ["k", "bs_hi", "pos3"]}
cells_lo = {"hist_k_bs": ["k", "bs_lo"], "hist_k_bs_pos": ["k", "bs_lo", "pos3"]}
hb = []
for ym, bd in blocks:
    t0 = pd.Timestamp(bd[0]); tr = d[d["date"] < t0]; te = d[d["date"].isin(bd)].copy()
    for t, cmap in [("high_done", cells), ("low_done", cells_lo)]:
        kr = tr.groupby("k")[t].mean()
        for nm, cols in cmap.items():
            # cell mean with shrinkage toward the k rate (prior weight 10 rows)
            grp = tr.groupby(cols)[t].agg(["sum", "count"]).reset_index()
            te2 = te.merge(grp, on=cols, how="left")
            kp = te2["k"].map(kr).values
            s = te2["sum"].fillna(0).values; c = te2["count"].fillna(0).values
            te[f"{nm}_{t}"] = (s + 10 * kp) / (c + 10)
    hb.append(te[["date", "k", "hist_k_bs_high_done", "hist_k_bs_pos_high_done", "hist_k_bs_low_done", "hist_k_bs_pos_low_done"]])
hb = pd.concat(hb)
m = oos.merge(hb, on=["date", "k"], how="left")
assert m["hist_k_bs_high_done"].notna().all()
for side in ["high", "low"]:
    t = f"{side}_done"
    for nm in ["hist_k_bs", "hist_k_bs_pos"]:
        bcol = f"{nm}_{t}"
        bk = brier(m[t], m[f"kbase_{side}"]); bh = brier(m[t], m[bcol]); bf = brier(m[t], m[f"p_{side}_done"]); br = brier(m[t], m[f"p_{side}_raw"])
        lo, hi = boot_skill(m, t, f"p_{side}_done", bcol, 1000)
        perk = " ".join(f"{1 - brier(g[t], g[f'p_{side}_done'])/brier(g[t], g[bcol]):+.2f}" for kk, g in m.groupby("k"))
        g1 = m[m["date"] < H2]; g2 = m[m["date"] >= H2]
        print(f"  {t} vs {nm:14s}: Brier k-only {bk:.4f} | {nm} {bh:.4f} (skill vs k-only {1-bh/bk:+.3f}) | final {bf:.4f} raw {br:.4f} | "
              f"final skill vs {nm} {1-bf/bh:+.3f} [{lo:+.3f},{hi:+.3f}] per-k {perk} | H1 {1-brier(g1[t], g1[f'p_{side}_done'])/brier(g1[t], g1[bcol]):+.3f} H2 {1-brier(g2[t], g2[f'p_{side}_done'])/brier(g2[t], g2[bcol]):+.3f}")
m.to_csv(CSV.replace(".csv", "_with_hist.csv"), index=False)
