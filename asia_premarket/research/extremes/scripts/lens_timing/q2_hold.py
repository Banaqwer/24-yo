"""Q2: P(high_done / low_done | close of bar k, running-state features). Conditional tables for a detector."""
import sys
sys.path.insert(0, "research/extremes/scripts/lens_timing")
import numpy as np, pandas as pd
from common import *
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

sym = sys.argv[1] if len(sys.argv) > 1 else "NQ"
x, p = load(sym)
p = p[(p.n_bars == 9) & (p.k <= 7)].copy()
p = p.join(x[["is_down", "mag", "rth_range_atr", "vix_z20", "sunday_open"]], on="date")
print(sym, "panel rows (n_bars=9, k<=7):", len(p), "sessions:", p.date.nunique())
ncomp = 0

def table(df, cond_name, cond_fn, ks=range(0, 8), label_col="high_done"):
    """P(label | k, cond buckets)"""
    global ncomp
    out = []
    for k in ks:
        d = df[df.k == k]
        base = d[label_col].mean()
        for lab, m in cond_fn(d):
            r = rate_row(m, d[label_col], base, lab, d.half); r.update(k=k, cond_name=cond_name, label=label_col)
            out.append(r); ncomp += 1
    return pd.DataFrame(out)

def bsh(d, col):
    return [("0", d[col] == 0), ("1", d[col] == 1), ("2", d[col] == 2), (">=3", d[col] >= 3)]
def pos(d, col="pos_in_range"):
    return [("<0.25", d[col] < 0.25), ("0.25-0.5", (d[col] >= 0.25) & (d[col] < 0.5)), ("0.5-0.75", (d[col] >= 0.5) & (d[col] < 0.75)), (">=0.75", d[col] >= 0.75)]
def rr(d, col="run_rng_vs_med20"):
    return [("<0.5", d[col] < 0.5), ("0.5-0.8", (d[col] >= 0.5) & (d[col] < 0.8)), ("0.8-1.2", (d[col] >= 0.8) & (d[col] < 1.2)), (">=1.2", d[col] >= 1.2)]
def cl(d, col="bar_close_loc"):
    return [("<0.25", d[col] < 0.25), ("0.25-0.75", (d[col] >= 0.25) & (d[col] < 0.75)), (">=0.75", d[col] >= 0.75)]
def vol(d, col="bar_vol_rel"):
    return [("<0.7", d[col] < 0.7), ("0.7-1.5", (d[col] >= 0.7) & (d[col] < 1.5)), (">=1.5", d[col] >= 1.5)]
def flag(d, col):
    return [("0", d[col] == 0), ("1", d[col] == 1)]

tabs = []
for lab_col, bsh_col, pos_fn, abv in [("high_done", "bars_since_hi", lambda d: pos(d), "run_hi_above_rth_high"), ("low_done", "bars_since_lo", lambda d: pos(d), "run_lo_below_rth_low")]:
    tabs.append(table(p, bsh_col, lambda d, c=bsh_col: bsh(d, c), label_col=lab_col))
    tabs.append(table(p, "pos_in_range", pos_fn, label_col=lab_col))
    tabs.append(table(p, "run_rng_vs_med20", rr, label_col=lab_col))
    tabs.append(table(p, "bar_close_loc", cl, label_col=lab_col))
    tabs.append(table(p, "bar_vol_rel", vol, label_col=lab_col))
    tabs.append(table(p, abv, lambda d, c=abv: flag(d, c), label_col=lab_col))
    tabs.append(table(p, "after_tokyo_open", lambda d: flag(d, "after_tokyo_open"), label_col=lab_col))
T = pd.concat(tabs)
T.to_csv(f"{OUT}/q2_{sym}_hold_tables.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)

def pivot(T, cond_name, label):
    t = T[(T.cond_name == cond_name) & (T.label == label)]
    pv = t.pivot(index="cond", columns="k", values="rate").round(2)
    pn = t.pivot(index="cond", columns="k", values="n")
    return pv, pn

for label in ["high_done", "low_done"]:
    print(f"\n######## {label} ########")
    for cn in T.cond_name.unique():
        if label == "high_done" and cn in ("bars_since_lo", "run_lo_below_rth_low"): continue
        if label == "low_done" and cn in ("bars_since_hi", "run_hi_above_rth_high"): continue
        pv, pn = pivot(T, cn, label)
        print(f"\n-- P({label} | k, {cn}) --"); print(pv.to_string()); print("n:"); print(pn.to_string())

# ---- combined rules: bars_since >= 2 & pos_in_range & range-vs-median  ----
print("\n=== combined rules at k=2..6 (pooled) ===")
rows = []
for lab_col, bsh_col, posdir in [("high_done", "bars_since_hi", "low"), ("low_done", "bars_since_lo", "high")]:
    d = p[(p.k >= 2) & (p.k <= 6)]
    base = d[lab_col].mean()
    far = (d.pos_in_range < 0.35) if posdir == "low" else (d.pos_in_range > 0.65)
    near = (d.pos_in_range > 0.65) if posdir == "low" else (d.pos_in_range < 0.35)
    rules = {
        "all": np.ones(len(d), bool),
        "bsh>=2": d[bsh_col] >= 2,
        "bsh>=2 & far(pos)": (d[bsh_col] >= 2) & far,
        "bsh>=2 & far & rng>=1.0": (d[bsh_col] >= 2) & far & (d.run_rng_vs_med20 >= 1.0),
        "bsh>=2 & far & rng<0.6": (d[bsh_col] >= 2) & far & (d.run_rng_vs_med20 < 0.6),
        "bsh>=2 & near(pos)": (d[bsh_col] >= 2) & near,
        "bsh==0": d[bsh_col] == 0,
        "bsh==0 & rng>=1.2": (d[bsh_col] == 0) & (d.run_rng_vs_med20 >= 1.2),
        "bsh==0 & rng<0.6": (d[bsh_col] == 0) & (d.run_rng_vs_med20 < 0.6),
        "bsh==1 & far": (d[bsh_col] == 1) & far,
        "bsh==1 & near": (d[bsh_col] == 1) & near,
        "rng>=1.2": d.run_rng_vs_med20 >= 1.2,
        "rng<0.5": d.run_rng_vs_med20 < 0.5,
    }
    for lab, m in rules.items():
        r = rate_row(m, d[lab_col], base, lab, d.half); r.update(label=lab_col); rows.append(r); ncomp += 1
C = pd.DataFrame(rows); C.to_csv(f"{OUT}/q2_{sym}_combined_rules_k2to6.csv", index=False)
print(C[["label", "cond", "n", "base", "rate", "ci90_lo", "ci90_hi", "p_binom", "rate_H1", "rate_H2"]].round(3).to_string())

# per-k version of the two strongest rules
print("\n=== per-k: bsh>=2 & far & rng>=1.0  vs  bsh==0 ===")
rows = []
for lab_col, bsh_col, posdir in [("high_done", "bars_since_hi", "low"), ("low_done", "bars_since_lo", "high")]:
    for k in range(1, 8):
        d = p[p.k == k]; base = d[lab_col].mean()
        far = (d.pos_in_range < 0.35) if posdir == "low" else (d.pos_in_range > 0.65)
        for lab, m in [("bsh>=2&far&rng>=1", (d[bsh_col] >= 2) & far & (d.run_rng_vs_med20 >= 1.0)), ("bsh>=2&far", (d[bsh_col] >= 2) & far), ("bsh==0", d[bsh_col] == 0), ("bsh==0&rng<0.6", (d[bsh_col] == 0) & (d.run_rng_vs_med20 < 0.6))]:
            r = rate_row(m, d[lab_col], base, lab, d.half); r.update(label=lab_col, k=k); rows.append(r); ncomp += 1
K = pd.DataFrame(rows); K.to_csv(f"{OUT}/q2_{sym}_rules_per_k.csv", index=False)
print(K[["label", "k", "cond", "n", "base", "rate", "ci90_lo", "ci90_hi", "rate_H1", "rate_H2"]].round(2).to_string())

# ---- remaining move when the extreme is NOT in ----
print("\n=== remaining_up_bp when high not done, by k (median, p25, p75) ===")
rem = []
for k in range(0, 8):
    d = p[(p.k == k) & (p.high_done == 0)]
    rem.append(dict(k=k, label="remaining_up_bp|high not done", n=len(d), p25=d.remaining_up_bp.quantile(.25), med=d.remaining_up_bp.median(), p75=d.remaining_up_bp.quantile(.75),
                    med_H1=d[d.half == "H1"].remaining_up_bp.median(), med_H2=d[d.half == "H2"].remaining_up_bp.median()))
    d = p[(p.k == k) & (p.low_done == 0)]
    rem.append(dict(k=k, label="remaining_down_bp|low not done", n=len(d), p25=d.remaining_down_bp.quantile(.25), med=d.remaining_down_bp.median(), p75=d.remaining_down_bp.quantile(.75),
                    med_H1=d[d.half == "H1"].remaining_down_bp.median(), med_H2=d[d.half == "H2"].remaining_down_bp.median()))
REM = pd.DataFrame(rem); REM.to_csv(f"{OUT}/q2_{sym}_remaining_move.csv", index=False); print(REM.round(1).to_string())

# ---- logistic summary: train H1, test H2, per label; features knowable at bar k ----
feats = ["k", "bars_since_hi", "bars_since_lo", "pos_in_range", "run_rng_vs_med20", "bar_close_loc", "bar_vol_rel", "run_hi_above_rth_high", "run_lo_below_rth_low",
         "cum_ret_bp", "bar_ret_bp", "after_tokyo_open", "dist_rth_high_bp", "dist_rth_low_bp", "run_hi_bp", "run_lo_bp"]
d = p.dropna(subset=feats).copy()
print("\n=== logistic (H1 -> H2 out-of-sample) ===")
res = []
for lab in ["high_done", "low_done"]:
    tr = d[d.half == "H1"]; te = d[d.half == "H2"]
    # baseline: per-k base rate from H1
    bk = tr.groupby("k")[lab].mean(); pb = te.k.map(bk)
    auc_b = roc_auc_score(te[lab], pb); br_b = brier_score_loss(te[lab], pb)
    # bars-since only
    m1 = LogisticRegression(max_iter=2000, C=1.0).fit(tr[["k", "bars_since_hi" if lab == "high_done" else "bars_since_lo"]], tr[lab])
    p1 = m1.predict_proba(te[["k", "bars_since_hi" if lab == "high_done" else "bars_since_lo"]])[:, 1]
    m2 = LogisticRegression(max_iter=5000, C=1.0).fit(tr[feats], tr[lab]); p2 = m2.predict_proba(te[feats])[:, 1]
    res.append(dict(label=lab, auc_base_k=auc_b, brier_base_k=br_b, auc_k_bsh=roc_auc_score(te[lab], p1), brier_k_bsh=brier_score_loss(te[lab], p1),
                    auc_full=roc_auc_score(te[lab], p2), brier_full=brier_score_loss(te[lab], p2), n_train=len(tr), n_test=len(te)))
    coef = pd.Series(m2.coef_[0], index=feats).sort_values(); print(lab, "coefs (unscaled):"); print(coef.round(3).to_string())
RES = pd.DataFrame(res); RES.to_csv(f"{OUT}/q2_{sym}_logit_oos.csv", index=False); print(RES.round(3).to_string())
print("\ncomparisons run in q2:", ncomp)
