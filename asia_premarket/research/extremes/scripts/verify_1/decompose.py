"""Where does the skill come from?  Same walk-forward (module functions), simpler inputs:
  1. level targets: single-feature model (lsd_high / lsd_low only) and a no-ML distance-bucket prior;
  2. shipped p_cal evaluated inside distance subsets (geometry removed);
  3. range / hi / lo quantiles: a no-ML vol-clustering baseline (expanding quantile of y / asia_rng_med20, rescaled)."""
import os, sys
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score

RUN = "research/extremes/scripts/verify_1/run"
sys.path.insert(0, RUN)
import detector_preasia as dp

pd.set_option("display.width", 220)


def brier(p, y): return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))
def pinball(pred, y, q):
    d = np.asarray(y) - np.asarray(pred); return float(np.mean(np.maximum(q * d, (q - 1) * d)))


def skill_ci(p, y, base, n_boot=1000, seed=0):
    p, y, base = map(np.asarray, (p, y, base)); rng = np.random.default_rng(seed); n = len(y)
    b = []
    for _ in range(n_boot):
        i = rng.integers(0, n, n); b.append(1 - brier(p[i], y[i]) / brier(base[i], y[i]))
    return 1 - brier(p, y) / brier(base, y), float(np.percentile(b, 5)), float(np.percentile(b, 95))


def pin_ci(pred, y, base, q, n_boot=1000, seed=0):
    pred, y, base = map(np.asarray, (pred, y, base)); rng = np.random.default_rng(seed); n = len(y)
    b = []
    for _ in range(n_boot):
        i = rng.integers(0, n, n); b.append(1 - pinball(pred[i], y[i], q) / pinball(base[i], y[i], q))
    return 1 - pinball(pred, y, q) / pinball(base, y, q), float(np.percentile(b, 5)), float(np.percentile(b, 95))


BUCKETS = [-np.inf, 0, 10, 25, 50, 100, np.inf]
for sym in ["NQ", "ES"]:
    x = dp.load_extremes(sym); F = dp.make_features(x); dst = x["is_dst"].astype(int)
    o = pd.read_csv(os.path.join(RUN, f"oos_preasia_{sym}.csv"), index_col="date", parse_dates=True)
    h1 = np.asarray(o.index < dp.H1_END)
    dist = {"high_above_rth_high": (x["lvl_rth_high"] / x["ref_close"] - 1) * 1e4,
            "low_below_rth_low": (1 - x["lvl_rth_low"] / x["ref_close"]) * 1e4}
    print(f"\n################ {sym}")
    for t, feat in [("high_above_rth_high", "lsd_high"), ("low_below_rth_low", "lsd_low")]:
        y = o[f"{t}__y"].values; base = o[f"{t}__full__base"].values; pc = o[f"{t}__full__p_cal"].values
        # 1a single-feature model
        o1, _ = dp.walk_forward_binary(F[[feat]], x[t], dst)
        s1 = skill_ci(o1.p_cal, o1.y, o1.base)
        # 1b no-ML distance-bucket prior (fixed bp buckets, cells >= 20)
        cond = pd.Series(np.digitize(dist[t].values, BUCKETS[1:-1]), index=x.index)
        ob = dp.walk_forward_prior(x[t], cond, dst)
        sb = skill_ci(ob.p_cal, ob.y, ob.base)
        # 1c full model vs the bucket prior as baseline
        sfb = skill_ci(pc, y, ob.p_cal.values)
        h1b = np.asarray(ob.index < dp.H1_END)
        print(f"\n[{t}] shipped full model skill {1 - brier(pc, y) / brier(base, y):+.3f} | AUC {roc_auc_score(y, pc):.3f}")
        print(f"  single-feature ({feat}) model : skill {s1[0]:+.3f} CI [{s1[1]:+.3f},{s1[2]:+.3f}] AUC {roc_auc_score(o1.y, o1.p_cal):.3f} "
              f"H1 {1 - brier(o1.p_cal[h1], o1.y[h1]) / brier(o1.base[h1], o1.y[h1]):+.3f} H2 {1 - brier(o1.p_cal[~h1], o1.y[~h1]) / brier(o1.base[~h1], o1.y[~h1]):+.3f}")
        print(f"  no-ML distance-bucket prior   : skill {sb[0]:+.3f} CI [{sb[1]:+.3f},{sb[2]:+.3f}] AUC {roc_auc_score(ob.y, ob.p_cal):.3f} "
              f"H1 {1 - brier(ob.p_cal[h1b], ob.y[h1b]) / brier(ob.base[h1b], ob.y[h1b]):+.3f} H2 {1 - brier(ob.p_cal[~h1b], ob.y[~h1b]) / brier(ob.base[~h1b], ob.y[~h1b]):+.3f}")
        print(f"  full model vs bucket prior    : skill {sfb[0]:+.3f} CI [{sfb[1]:+.3f},{sfb[2]:+.3f}]")
        # 2 subsets of the shipped OOS by distance (knowable at 17:00)
        d = dist[t].loc[o.index].values
        print(f"  subset analysis of the shipped p_cal (dist = 17:00 close -> RTH extreme, bp):")
        for lo_, hi_ in [(-np.inf, 0), (0, 10), (10, 25), (25, 50), (50, 100), (100, np.inf), (10, np.inf), (25, np.inf)]:
            m = (d > lo_) & (d <= hi_)
            if m.sum() < 10: continue
            sk = 1 - brier(pc[m], y[m]) / brier(base[m], y[m]); skb = 1 - brier(pc[m], y[m]) / brier(ob.p_cal.values[m], y[m])
            auc = roc_auc_score(y[m], pc[m]) if 0 < y[m].mean() < 1 else np.nan
            print(f"    dist in ({lo_:>5},{hi_:>5}]: n={m.sum():3d} obs rate {y[m].mean():.3f} mean p {pc[m].mean():.3f} skill vs base {sk:+.3f} vs bucket prior {skb:+.3f} AUC {auc:.3f}")
    # 3 quantiles: vol-clustering baseline
    print("\n[quantiles] no-ML scaled baseline = expanding quantile of (y / asia_rng_med20_bp) x tonight's asia_rng_med20_bp")
    med = F["asia_rng_med20_bp"]
    for t in dp.QUANT_TARGETS:
        y_all = x[t].astype(float)
        ratio = y_all / med
        for q in dp.QUANTILES:
            c = f"q{int(q*100)}"
            preds = []
            for train, test in dp._month_blocks(x.index):
                qq = ratio[train].quantile(q)
                preds.append(pd.Series(qq * med[test].values, index=x.index[test]))
            sc = pd.concat(preds).sort_index().loc[o.index].values
            y = o[f"{t}__y"].values; mdl = o[f"{t}__{c}"].values; base = o[f"{t}__base_{c}"].values
            s_sc = pin_ci(sc, y, base, q); s_m_sc = pin_ci(mdl, y, sc, q)
            print(f"  {t} q{q}: model vs uncond {1 - pinball(mdl, y, q) / pinball(base, y, q):+.3f} | scaled-baseline vs uncond {s_sc[0]:+.3f} CI [{s_sc[1]:+.3f},{s_sc[2]:+.3f}] "
                  f"| model vs scaled-baseline {s_m_sc[0]:+.3f} CI [{s_m_sc[1]:+.3f},{s_m_sc[2]:+.3f}] H1 {1 - pinball(mdl[h1], y[h1], q) / pinball(sc[h1], y[h1], q):+.3f} H2 {1 - pinball(mdl[~h1], y[~h1], q) / pinball(sc[~h1], y[~h1], q):+.3f}")
