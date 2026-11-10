"""C1-C3: level distances and direction -> P(high above RTH high), P(low below RTH low)."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "research/extremes/scripts/refute_context_regime")
from common import *

for sym in ("NQ", "ES"):
    f = load(sym)
    preds = pd.read_csv(f"{LENS}/wf_logit_preds_{sym}.csv", index_col=0, parse_dates=True).reindex(f.index)
    print(f"\n==================== {sym}  n={len(f)} ====================")
    print("quarter counts:", f["quarter"].value_counts().reindex(QUARTERS).to_dict())
    print("regime counts:", f["regime"].value_counts().to_dict(), " sundays:", int(f["sunday"].sum()))

    for side, t, sc, raw in (("HIGH (C1)", "high_above_rth_high", "scaled_high", "dist_rth_high0"),
                             ("LOW (C2)", "low_below_rth_low", "scaled_low", "dist_rth_low0")):
        print(f"\n----- {side}: {t} vs {sc} -----")
        near = f[sc] <= 0.25; far = f[sc] >= 1.0
        rawd = f[raw] if side.startswith("HIGH") else -f[raw]   # signed, as in the lens tables
        print("overall near(<=0.25) vs far(>=1.0):", rate_diff(f, near, far, t))
        print("raw <=10bp:", f.loc[rawd <= 10, t].agg(["mean", "count"]).round(3).to_dict(),
              " raw >50bp:", f.loc[rawd > 50, t].agg(["mean", "count"]).round(3).to_dict())
        print("\nby quarter (near vs far):")
        print(fmt(rate_diff_by_quarter(f, near, far, t)))
        print("\nby quarter Spearman(scaled, target):")
        print(fmt(spearman_by_quarter(f, sc, t)))
        print("\nby regime (near vs far):")
        print(fmt(rate_diff_by_regime(f, near, far, t)))
        print("\nleave-5 near vs far:", leave5_rate_diff(f, near, far, t))
        print("leave-5 Spearman:", leave5_spearman(f, sc, t))
        # OOS skill by quarter for the one-feature and the levels model
        y = f[t].values.astype(float); pb = preds[f"{t}|base"].values
        for mdl in (f"uni:{raw}", "levels"):
            p = preds[f"{t}|{mdl}"].values
            s, n = skill_from_preds(y, p, pb)
            print(f"\nOOS skill {mdl}: {s:.3f} (n_oos={n})")
            print(fmt(skill_by_quarter(f, y, p, pb).T))
            print("top5:", skill_top5(f, y, p, pb))
            # by regime
            for k in REGIMES:
                m = (f["regime"] == k).values
                print(f"   in {k}: skill {skill_from_preds(y[m], p[m], pb[m])}  ex: {skill_from_preds(y[~m], p[~m], pb[~m])}")
            m = (f["sunday"] == 1).values
            print(f"   sunday_only: {skill_from_preds(y[m], p[m], pb[m])}  ex_sunday: {skill_from_preds(y[~m], p[~m], pb[~m])}")
        # scaled buckets by half and by quarter (the 'mechanical' claim)
        if side.startswith("HIGH"):
            bins = [-np.inf, 0.10, 0.25, 0.5, 0.75, 1.0, 1.5, np.inf]
        else:
            bins = [-np.inf, 0.10, 0.25, 0.5, 0.75, 1.0, 1.5, np.inf]
        f["_b"] = pd.cut(f[sc], bins)
        print("\nscaled buckets x quarter: rate (n)")
        tab = f.groupby(["_b", "quarter"], observed=True)[t].agg(["mean", "count"])
        piv = tab["mean"].unstack("quarter").reindex(columns=QUARTERS).round(2)
        cnt = tab["count"].unstack("quarter").reindex(columns=QUARTERS)
        print(fmt(piv)); print(fmt(cnt))
        # the extreme buckets: <=0.10 and >1.5 by regime
        for lab, mm in (("<=0.10", f[sc] <= 0.10), (">1.5", f[sc] > 1.5)):
            print(f"bucket {lab}: overall {f.loc[mm, t].mean():.3f} (n={mm.sum()});",
                  "; ".join(f"{k}: in {f.loc[mm & (f.regime==k), t].mean():.2f}(n={(mm & (f.regime==k)).sum()}) ex {f.loc[mm & (f.regime!=k), t].mean():.3f}" for k in REGIMES),
                  f"; sunday {f.loc[mm & (f.sunday==1), t].mean():.2f}(n={(mm & (f.sunday==1)).sum()})")
            print("   by half:", f.loc[mm].groupby("half")[t].agg(["mean", "count"]).round(3).to_dict())

    # ---------------- C3: direction -----------------
    print("\n----- C3: is_down -> high_above / low_below -----")
    up = f["is_down"] == 0; dn = f["is_down"] == 1
    for t in ("high_above_rth_high", "low_below_rth_low"):
        print(f"\n{t}: overall", rate_diff(f, up, dn, t))
        print(fmt(rate_diff_by_quarter(f, up, dn, t)))
        print(fmt(rate_diff_by_regime(f, up, dn, t)))
        print("leave-5:", leave5_rate_diff(f, up, dn, t))
        y = f[t].values.astype(float); pb = preds[f"{t}|base"].values; p = preds[f"{t}|uni:is_down"].values
        s, n = skill_from_preds(y, p, pb)
        print(f"OOS skill uni:is_down {s:.3f}"); print(fmt(skill_by_quarter(f, y, p, pb).T)); print("top5:", skill_top5(f, y, p, pb))
    # does is_down add on top of the scaled distances?  (in-sample logistic, by half)  -- check the 'tie-breaker' part
    from sklearn.linear_model import LogisticRegression
    for t, sc in (("high_above_rth_high", "scaled_high"), ("low_below_rth_low", "scaled_low")):
        d = f[[t, sc, "is_down"]].dropna()
        d = d[np.isfinite(d[sc])]
        X1 = np.log1p(np.clip(d[[sc]].values, 0, None)); X2 = np.column_stack([X1, d["is_down"].values])
        for lab, X in (("scaled only", X1), ("scaled + is_down", X2)):
            m = LogisticRegression(C=1.0, max_iter=1000).fit(X, d[t]); pr = m.predict_proba(X)[:, 1]
            print(f"  in-sample {t} {lab}: Brier {np.mean((pr - d[t].values) ** 2):.4f} coef {m.coef_.round(3)}")
