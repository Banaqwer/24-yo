import numpy as np, pandas as pd
V = "research/extremes/scripts/verify_0"
R = "./research/extremes"
def brier(y, p): return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))
def pinball(y, q, tau):
    e = np.asarray(y, float) - np.asarray(q, float); return float(np.mean(np.maximum(tau * e, (tau - 1) * e)))
for sym in ["NQ", "ES"]:
    x = pd.read_csv(f"{R}/{sym}_extremes.csv", index_col="date", parse_dates=True)
    oos = pd.read_csv(f"{V}/orig/oos_intrasession_{sym}.csv", parse_dates=["date"])
    m = oos.merge(x[["is_dst", "tokyo_open_k"]], left_on="date", right_index=True, how="left")
    print(f"\n=== {sym} DST diagnostic (OOS rows) ===")
    print("  sessions by is_dst:", m.groupby("is_dst")["date"].nunique().to_dict())
    for s in ["high", "low"]:
        t = f"{s}_done"
        print(f"  {t} OOS done-rate by k, EST(is_dst=0): " + " ".join(f"{v:.2f}" for v in m[m.is_dst==0].groupby('k')[t].mean()) +
              " | EDT(is_dst=1): " + " ".join(f"{v:.2f}" for v in m[m.is_dst==1].groupby('k')[t].mean()))
        for dst, g in m.groupby("is_dst"):
            bk = brier(g[t], g[f"kbase_{s}"]); bf = brier(g[t], g[f"p_{s}_done"])
            # DST-aware k-only baseline computed walk-forward is not stored; use the OOS-realised per-(k,dst) rate as an in-sample oracle to bound its possible gain
            orc = g.groupby("k")[t].transform("mean")
            print(f"    is_dst={dst}: n={len(g)} k-only {bk:.4f} final {bf:.4f} skill {1-bf/bk:+.3f} | in-sample per-(k,dst) oracle Brier {brier(g[t], orc):.4f}")
    # in-sample oracle per-k quantile on not-yet-in rows vs the marginal P80 (the claim: 7.00 vs 7.67 up, 10.68 vs 10.89 dn for NQ)
    for side, ycol, sgn, done in [("up", "remaining_up_bp", 1.0, "high_done"), ("dn", "remaining_down_bp", -1.0, "low_done")]:
        g = oos[oos[done] == 0]; y = sgn * g[ycol].values
        orc = sgn * g.groupby("k")[ycol].transform(lambda s: s.quantile(0.8 if sgn > 0 else 0.2)).values
        print(f"  not-yet-in rows rem_{side}: pinball(P80 marginal model) {pinball(y, sgn*g[f'rem_{side}_p80'].values, .8):.2f} vs in-sample per-k oracle {pinball(y, orc, .8):.2f} vs P80_if_open {pinball(y, sgn*g[f'rem_{side}_p80_if_open'].values, .8):.2f} vs k-only-open {pinball(y, sgn*g[f'kqo_{side}_p80'].values, .8):.2f}")
