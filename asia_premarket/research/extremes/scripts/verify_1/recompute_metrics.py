"""Independent recomputation of every OOS metric from oos_preasia_<SYM>.csv (no module code used).
Usage: python3 recompute_metrics.py <path_to_oos_dir> [NQ ES]"""
import os, sys
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score

OOS_DIR = sys.argv[1]
SYMS = sys.argv[2:] or ["NQ", "ES"]
EX = "./research/extremes"
H1_END = pd.Timestamp("2025-09-01")
BIN = ["high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar",
       "high_by_tokyo_open", "low_by_tokyo_open", "high_above_rth_high", "low_below_rth_low", "hi_first"]
SETS = ["full", "timing", "dow_prior"]
QT = ["hi_bp", "lo_bp", "rng_bp"]; QS = [0.2, 0.5, 0.8]
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50)


def brier(p, y): return float(np.mean((p - y) ** 2))
def pinball(pred, y, q):
    d = y - pred; return float(np.mean(np.maximum(q * d, (q - 1) * d)))
def ll(P, yk):
    P = np.clip(P, 1e-6, 1); return float(-np.mean(np.log(P[np.arange(len(yk)), yk])))


def boot_ci(fn, n, n_boot=1000, seed=0):
    rng = np.random.default_rng(seed); out = []
    for _ in range(n_boot):
        i = rng.integers(0, n, n); out.append(fn(i))
    return float(np.nanpercentile(out, 5)), float(np.nanpercentile(out, 95))


for sym in SYMS:
    o = pd.read_csv(os.path.join(OOS_DIR, f"oos_preasia_{sym}.csv"), index_col="date", parse_dates=True).sort_index()
    x = pd.read_csv(os.path.join(EX, f"{sym}_extremes.csv"), index_col="date", parse_dates=True).sort_index()
    h1 = np.asarray(o.index < H1_END); h2 = ~h1
    print(f"\n######## {sym}: OOS n={len(o)} {o.index.min().date()}..{o.index.max().date()}  H1={h1.sum()} H2={h2.sum()}")
    # --- structural checks ---
    print("n_bars of OOS sessions:", x.loc[o.index, "n_bars"].value_counts().to_dict())
    splice = {"NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"], "ES": ["2025-12-16", "2025-12-17"]}[sym]
    print("splice sessions in OOS:", [d for d in splice if pd.Timestamp(d) in o.index])
    print("duplicate dates:", int(o.index.duplicated().sum()))
    # labels in OOS must equal the extremes table
    for t in BIN:
        assert (o[f"{t}__y"].values == x.loc[o.index, t].values).all(), t
    for t in QT:
        assert np.allclose(o[f"{t}__y"].values, x.loc[o.index, t].values), t
    for t in ["hi_k", "lo_k"]:
        assert (o[f"{t}__y"].values == x.loc[o.index, t].values).all(), t
    print("labels match extremes table: OK")
    # base rate column must equal the expanding mean of y over sessions strictly before the month, on the filtered table
    xf = x[(x["n_bars"] == 9) & ~x.index.isin(pd.to_datetime(splice))]
    per = xf.index.to_period("M")
    bad = 0
    for t in BIN:
        for p in o.index.to_period("M").unique():
            tr = xf.loc[per < p, t].mean()
            got = o.loc[o.index.to_period("M") == p, f"{t}__full__base"].iloc[0]
            if abs(tr - got) > 1e-9: bad += 1
    print("base-rate column == expanding mean of y before the test month (all targets x months):", "OK" if bad == 0 else f"{bad} MISMATCHES")
    # first OOS position
    pos = int(np.searchsorted(xf.index.values, o.index[0].to_datetime64()))
    print(f"first OOS session is position {pos} of the filtered table (0-based), i.e. {pos} training sessions before it")
    cal_on = o["high_above_rth_high__full__cal_on"]
    print(f"cal_on share: {cal_on.mean():.3f}; first calibrated date {o.index[cal_on == 1].min().date()}")
    # --- binary ---
    rows = []
    for t in BIN:
        y = o[f"{t}__y"].values.astype(float)
        for s in SETS:
            pre = f"{t}__{s}__"
            pc, pr, base, bd = (o[pre + c].values for c in ("p_cal", "p_raw", "base", "base_dst"))
            sk = 1 - brier(pc, y) / brier(base, y)
            lo, hi = boot_ci(lambda i: 1 - brier(pc[i], y[i]) / brier(base[i], y[i]), len(y))
            rows.append(dict(target=t, set=s, n=len(y), base=y.mean(), Br_base=brier(base, y), Br_konly=brier(bd, y),
                             Br_raw=brier(pr, y), Br_cal=brier(pc, y), skill=sk, ci_lo=lo, ci_hi=hi,
                             skill_konly=1 - brier(pc, y) / brier(bd, y), auc=roc_auc_score(y, pc),
                             H1=1 - brier(pc[h1], y[h1]) / brier(base[h1], y[h1]),
                             H2=1 - brier(pc[h2], y[h2]) / brier(base[h2], y[h2])))
    b = pd.DataFrame(rows)
    b["verdict"] = np.where((b.ci_lo > 0) & (b.H1 > 0) & (b.H2 > 0), "SKILL", np.where(b.ci_lo > 0, "skill(one half<=0)", "none"))
    print("\n== binary ==")
    print(b.round(4).to_string(index=False))
    b.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), f"recomputed_binary_{sym}.csv"), index=False)
    # --- quantiles ---
    qrows = []
    for t in QT:
        y = o[f"{t}__y"].values.astype(float)
        for q in QS:
            c = f"q{int(q*100)}"; pred, base = o[f"{t}__{c}"].values, o[f"{t}__base_{c}"].values
            sk = 1 - pinball(pred, y, q) / pinball(base, y, q)
            lo, hi = boot_ci(lambda i: 1 - pinball(pred[i], y[i], q) / pinball(base[i], y[i], q), len(y))
            qrows.append(dict(target=t, q=q, pin_model=pinball(pred, y, q), pin_base=pinball(base, y, q), skill=sk, ci_lo=lo, ci_hi=hi,
                              cov_model=np.mean(y <= pred), cov_base=np.mean(y <= base),
                              H1=1 - pinball(pred[h1], y[h1], q) / pinball(base[h1], y[h1], q),
                              H2=1 - pinball(pred[h2], y[h2], q) / pinball(base[h2], y[h2], q)))
    qd = pd.DataFrame(qrows)
    qd["verdict"] = np.where((qd.ci_lo > 0) & (qd.H1 > 0) & (qd.H2 > 0), "SKILL", np.where(qd.ci_lo > 0, "skill(one half<=0)", "none"))
    print("\n== quantiles ==")
    print(qd.round(4).to_string(index=False))
    # --- map ---
    print("\n== map ==")
    for t in ["hi_k", "lo_k"]:
        yk = o[f"{t}__y"].astype(int).values
        P = {k: o[[f"{t}__{k}{i}" for i in range(9)]].values for k in ("p", "h", "hd", "m")}
        skm = 1 - ll(P["m"], yk) / ll(P["h"], yk)
        lo, hi = boot_ci(lambda i: 1 - ll(P["m"][i], yk[i]) / ll(P["h"][i], yk[i]), len(yk))
        print(f"{t}: LL model {ll(P['p'], yk):.4f} mixed {ll(P['m'], yk):.4f} hist {ll(P['h'], yk):.4f} hist_dst {ll(P['hd'], yk):.4f} "
              f"mix_w med {o[f'{t}__mix_w'].median():.2f} skill_mixed {skm:+.4f} CI [{lo:+.4f},{hi:+.4f}] "
              f"H1 {1 - ll(P['m'][h1], yk[h1]) / ll(P['h'][h1], yk[h1]):+.4f} H2 {1 - ll(P['m'][h2], yk[h2]) / ll(P['h'][h2], yk[h2]):+.4f} "
              f"model_vs_hist {1 - ll(P['p'], yk) / ll(P['h'], yk):+.4f}")
        obs = np.bincount(yk, minlength=9) / len(yk)
        print("   OOS observed share by bar:", np.round(obs, 3).tolist())
        print("   mean mixed p by bar      :", np.round(P["m"].mean(0), 3).tolist())
        pb = [1 - brier(P["m"][:, i], (yk == i).astype(float)) / brier(P["h"][:, i], (yk == i).astype(float)) for i in range(9)]
        print("   per-bar one-vs-rest skill:", np.round(pb, 3).tolist())
    # --- calibration tables (primary set) ---
    print("\n== calibration (5 quantile buckets of p_cal, primary set) ==")
    for t, s in [("high_above_rth_high", "full"), ("low_below_rth_low", "full"), ("low_by_tokyo_open", "timing"), ("high_in_first_bar", "timing")]:
        p = o[f"{t}__{s}__p_cal"]; y = o[f"{t}__y"]
        try: bins = pd.qcut(p, 5, duplicates="drop")
        except ValueError: bins = pd.cut(p, 5)
        g = pd.DataFrame({"p": p, "y": y}).groupby(bins, observed=True).agg(n=("y", "size"), pred=("p", "mean"), obs=("y", "mean")).round(3)
        print(f"[{t}/{s}] " + " | ".join(f"{iv.left:.2f}-{iv.right:.2f} {r.n}/{r.pred:.3f}/{r.obs:.3f}" for iv, r in g.iterrows()))
