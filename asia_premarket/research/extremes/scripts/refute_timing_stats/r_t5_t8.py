"""Independent recompute of T5-T8 (hold-probability claims from the hourly panel)."""
import numpy as np, pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
ROOT = "."
SPLIT = pd.Timestamp("2025-09-01")
BAD = {"NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"],
       "ES": ["2025-12-15", "2025-12-16", "2025-12-17"]}
rng = np.random.default_rng(321)

def load(sym):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    bad = pd.to_datetime(BAD[sym])
    x = x[~x.index.isin(bad)]; p = p[~p.date.isin(bad)]
    x["half"] = np.where(x.index < SPLIT, "H1", "H2")
    p["half"] = np.where(p.date < SPLIT, "H1", "H2")
    return x, p

def ci(v, nb=2000):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    if len(v) < 2: return (np.nan, np.nan)
    b = rng.integers(0, len(v), (nb, len(v)))
    m = v[b].mean(1)
    return (np.quantile(m, .05), np.quantile(m, .95))

# cluster bootstrap by session (rows within a session are correlated)
def ci_cluster(df, mask, ycol, nb=1000):
    sub = df[mask]
    g = sub.groupby("date")[ycol].agg(["sum", "count"])
    if len(g) < 2: return (np.nan, np.nan)
    s = g["sum"].values; c = g["count"].values
    b = rng.integers(0, len(g), (nb, len(g)))
    m = s[b].sum(1) / c[b].sum(1)
    return (np.quantile(m, .05), np.quantile(m, .95))

def rate(df, mask, ycol, base, label, cluster=True):
    m = np.asarray(pd.Series(mask).fillna(False), bool)
    s = df.loc[m, ycol].astype(float); n = len(s); k = int(s.sum()); r = k / n if n else np.nan
    lo, hi = ci_cluster(df, m, ycol) if cluster else ci(s)
    p = stats.binomtest(k, n, base).pvalue if n else np.nan
    h1 = df.loc[m & (df.half == "H1").values, ycol].astype(float); h2 = df.loc[m & (df.half == "H2").values, ycol].astype(float)
    print(f"  {label:52s} n={n:5d} rate={r:.3f} base={base:.3f} CI[{lo:.3f},{hi:.3f}] p={p:.1e} H1={h1.mean():.3f}(n{len(h1)}) H2={h2.mean():.3f}(n{len(h2)})")
    return r

for sym in ["NQ", "ES"]:
    x, p = load(sym)
    P = p[(p.n_bars == 9) & (p.k <= 7)].copy()
    print(f"\n===== {sym}: panel rows k<=7 full sessions n={len(P)}, sessions={P.date.nunique()} =====")
    bk_h = P.groupby("k").high_done.mean(); bk_l = P.groupby("k").low_done.mean()
    print("  P(high_done|k):", bk_h.round(3).tolist()); print("  P(low_done|k):", bk_l.round(3).tolist())

    print("--- T5: pos_in_range buckets per k ---")
    for k in range(8):
        d = P[P.k == k]
        for lab, m in [("pos<0.25", d.pos_in_range < .25), ("pos>=0.75", d.pos_in_range >= .75)]:
            s = d.loc[m, "high_done"]; l = d.loc[m, "low_done"]
            lo, hi = ci(s)
            h1 = d.loc[m & (d.half == "H1"), "high_done"].mean(); h2 = d.loc[m & (d.half == "H2"), "high_done"].mean()
            print(f"  k={k} {lab:10s} n={len(s):3d} high_done={s.mean():.3f} CI[{lo:.3f},{hi:.3f}] (base {bk_h[k]:.3f}) H1={h1:.3f} H2={h2:.3f} | low_done={l.mean():.3f} (base {bk_l[k]:.3f})")
    # logistic OOS H1 -> H2
    P["bsh"] = P.bars_since_hi; P["bsl"] = P.bars_since_lo
    P["rth_hi_flag"] = P.run_hi_above_rth_high.fillna(0); P["rth_lo_flag"] = P.run_lo_below_rth_low.fillna(0)
    def oos(feats, ycol):
        d = P.dropna(subset=feats + [ycol])
        tr = d[d.half == "H1"]; te = d[d.half == "H2"]
        Xtr = pd.get_dummies(tr[feats + ["k"]], columns=["k"]).astype(float); Xte = pd.get_dummies(te[feats + ["k"]], columns=["k"]).astype(float)
        Xte = Xte.reindex(columns=Xtr.columns, fill_value=0)
        m = LogisticRegression(max_iter=2000, C=1.0).fit(Xtr, tr[ycol])
        pr = m.predict_proba(Xte)[:, 1]
        return roc_auc_score(te[ycol], pr), brier_score_loss(te[ycol], pr), len(tr), len(te), dict(zip(Xtr.columns, m.coef_[0].round(2)))
    for ycol, bs in [("high_done", "bsh"), ("low_done", "bsl")]:
        a0 = oos([], ycol); a1 = oos([bs], ycol)
        a2 = oos([bs, "pos_in_range", "bar_close_loc", "bar_vol_rel", "run_rng_vs_med20", "rth_hi_flag", "rth_lo_flag"], ycol)
        a3 = oos([bs, "pos_in_range"], ycol)
        print(f"  OOS {ycol}: k-only AUC {a0[0]:.3f} Brier {a0[1]:.3f}; +bars_since AUC {a1[0]:.3f} Brier {a1[1]:.3f}; +pos only AUC {a3[0]:.3f}; full AUC {a2[0]:.3f} Brier {a2[1]:.3f} (train {a2[2]}, test {a2[3]})")
        print("    full-model coefs:", {k_: v for k_, v in a2[4].items() if not k_.startswith("k_")})
    # mechanical check: pos<0.25 means close is far from run_hi; what's P(high_done) by distance to running high in bp?
    P["dist_to_run_hi"] = P.run_hi_bp - P.cum_ret_bp
    d = P[(P.k >= 2) & (P.k <= 6)]
    for lab, m in [("dist<5bp", d.dist_to_run_hi < 5), ("5-15", (d.dist_to_run_hi >= 5) & (d.dist_to_run_hi < 15)), ("15-30", (d.dist_to_run_hi >= 15) & (d.dist_to_run_hi < 30)), (">=30", d.dist_to_run_hi >= 30)]:
        print(f"  k2-6 high_done | {lab:10s} n={m.sum()} rate={d.loc[m,'high_done'].mean():.3f}")

    print("--- T6: three-condition rules k=2..6 ---")
    d = P[(P.k >= 2) & (P.k <= 6)].copy()
    bh = d.high_done.mean(); bl = d.low_done.mean()
    print(f"  base high_done {bh:.3f}, low_done {bl:.3f}, n={len(d)}")
    rate(d, d.bsh >= 2, "high_done", bh, "bsh>=2")
    rate(d, (d.bsh >= 2) & (d.pos_in_range < .35), "high_done", bh, "bsh>=2 & pos<.35")
    rate(d, (d.bsh >= 2) & (d.pos_in_range < .35) & (d.run_rng_vs_med20 >= 1.0), "high_done", bh, "bsh>=2 & pos<.35 & rng>=1.0")
    rate(d, (d.bsh >= 2) & (d.pos_in_range < .35) & (d.run_rng_vs_med20 < .6), "high_done", bh, "bsh>=2 & pos<.35 & rng<.6")
    rate(d, (d.bsh >= 2) & (d.pos_in_range > .65), "high_done", bh, "bsh>=2 & pos>.65")
    rate(d, d.bsh == 0, "high_done", bh, "bsh==0")
    rate(d, (d.bsh == 0) & (d.run_rng_vs_med20 >= 1.2), "high_done", bh, "bsh==0 & rng>=1.2")
    rate(d, d.bsh == 1, "high_done", bh, "bsh==1")
    rate(d, (d.bsl >= 2) & (d.pos_in_range > .65) & (d.run_rng_vs_med20 >= 1.0), "low_done", bl, "bsl>=2 & pos>.65 & rng>=1.0")
    rate(d, (d.bsl >= 2) & (d.pos_in_range > .65), "low_done", bl, "bsl>=2 & pos>.65")
    rate(d, d.bsl == 0, "low_done", bl, "bsl==0")
    # Is the rng>=1.0 condition adding anything beyond bsh>=2 & pos<.35? compare to rng in [.6,1.0)
    rate(d, (d.bsh >= 2) & (d.pos_in_range < .35) & (d.run_rng_vs_med20 >= .6) & (d.run_rng_vs_med20 < 1.0), "high_done", bh, "bsh>=2 & pos<.35 & .6<=rng<1.0")
    # per k
    for k in range(2, 8):
        dk = P[P.k == k]; m = (dk.bsh >= 2) & (dk.pos_in_range < .35) & (dk.run_rng_vs_med20 >= 1.0)
        s = dk.loc[m, "high_done"]
        print(f"    per k={k}: n={len(s)} high rule rate={s.mean():.3f}")
    # the base rate for bsh>=2 & pos<.35 is .91 -- rule is 'strongest' how much beyond?
    # mechanical note: pos<.35 and bsh>=2 implies the running high is bsh bars old and price far away

    print("--- T7: volume x direction k=1..7 ---")
    d = P[(P.k >= 1) & (P.k <= 7) & P.bar_vol_rel.notna()].copy()
    bh = d.high_done.mean(); bl = d.low_done.mean()
    print(f"  n={len(d)} base high_done {bh:.3f} low_done {bl:.3f}")
    up = d.bar_ret_bp > 0; dn = d.bar_ret_bp < 0; hv = d.bar_vol_rel >= 1.5
    rate(d, hv & dn, "high_done", bh, "vol>=1.5 & down")
    rate(d, ~hv & dn, "high_done", bh, "vol<1.5 & down")
    rate(d, hv & up, "high_done", bh, "vol>=1.5 & up")
    rate(d, ~hv & up, "high_done", bh, "vol<1.5 & up")
    rate(d, hv & up, "low_done", bl, "low: vol>=1.5 & up")
    rate(d, ~hv & up, "low_done", bl, "low: vol<1.5 & up")
    rate(d, hv & dn, "low_done", bl, "low: vol>=1.5 & down")
    rate(d, dn & (d.bar_close_loc < .25), "high_done", bh, "down & close_loc<.25 (no vol)")
    # Confound: high-vol bars are wide bars; does volume add beyond bar range? control bar_rng_rel
    wide = d.bar_rng_rel >= 1.5
    rate(d, dn & wide, "high_done", bh, "down & rng_rel>=1.5 (no vol)")
    rate(d, dn & wide & hv, "high_done", bh, "down & rng_rel>=1.5 & vol>=1.5")
    rate(d, dn & wide & ~hv, "high_done", bh, "down & rng_rel>=1.5 & vol<1.5")
    rate(d, dn & ~wide & hv, "high_done", bh, "down & rng_rel<1.5 & vol>=1.5")
    rate(d, dn & ~wide & ~hv, "high_done", bh, "down & rng_rel<1.5 & vol<1.5")
    # control for pos_in_range (down bars with hi vol likely push pos low)
    for lab, m in [("pos<.35", d.pos_in_range < .35), ("pos>=.35", d.pos_in_range >= .35)]:
        rate(d, dn & hv & m, "high_done", bh, f"down & vol>=1.5 & {lab}")
        rate(d, dn & ~hv & m, "high_done", bh, f"down & vol<1.5 & {lab}")
    # bar_ret_bp magnitude control: hi-vol bars are bigger moves
    big = d.bar_ret_bp.abs() >= 15
    rate(d, dn & big & hv, "high_done", bh, "down>=15bp & vol>=1.5")
    rate(d, dn & big & ~hv, "high_done", bh, "down>=15bp & vol<1.5")
    rate(d, dn & ~big & hv, "high_done", bh, "down<15bp & vol>=1.5")
    rate(d, dn & ~big & ~hv, "high_done", bh, "down<15bp & vol<1.5")
    # Logistic: high_done ~ k + bsh + pos_in_range + bar_close_loc + down*vol interaction
    dd = d.dropna(subset=["pos_in_range", "bar_close_loc", "bar_vol_rel", "bar_rng_rel"]).copy()
    dd["down"] = (dd.bar_ret_bp < 0).astype(float); dd["lv"] = np.log(dd.bar_vol_rel.clip(.05, 20)); dd["lr"] = np.log(dd.bar_rng_rel.clip(.05, 20))
    dd["down_lv"] = dd.down * dd.lv; dd["up_lv"] = (1 - dd.down) * dd.lv
    X = pd.get_dummies(dd[["bsh", "pos_in_range", "bar_close_loc", "down", "lr", "down_lv", "up_lv", "k"]], columns=["k"]).astype(float)
    m = LogisticRegression(max_iter=3000, C=10).fit(X, dd.high_done)
    print("  logit high_done coefs (controls for pos, close_loc, bsh, range):", {c: round(v, 2) for c, v in zip(X.columns, m.coef_[0]) if not c.startswith("k_")})

    print("--- T8: RTH-break flags ---")
    d = P[(P.k >= 2) & (P.k <= 6)].copy()
    bh = d.high_done.mean(); bl = d.low_done.mean()
    rate(d, d.run_hi_above_rth_high == 1, "high_done", bh, "run_hi_above_rth_high=1")
    rate(d, d.run_hi_above_rth_high == 0, "high_done", bh, "run_hi_above_rth_high=0")
    rate(d, (d.run_hi_above_rth_high == 1) & (d.bsh >= 2), "high_done", bh, "break=1 & bsh>=2")
    rate(d, (d.run_hi_above_rth_high == 0) & (d.bsh >= 2), "high_done", bh, "break=0 & bsh>=2")
    rate(d, d.run_lo_below_rth_low == 1, "low_done", bl, "run_lo_below_rth_low=1")
    rate(d, d.run_lo_below_rth_low == 0, "low_done", bl, "run_lo_below_rth_low=0")
    rate(d, (d.run_lo_below_rth_low == 1) & (d.bsl >= 2), "low_done", bl, "lo break=1 & bsl>=2")
    rate(d, (d.run_lo_below_rth_low == 0) & (d.bsl >= 2), "low_done", bl, "lo break=0 & bsl>=2")
    # two-proportion test break vs no break
    a = d[d.run_hi_above_rth_high == 1].high_done; b = d[d.run_hi_above_rth_high == 0].high_done
    print("  chi2 break vs no-break high:", stats.chi2_contingency([[a.sum(), len(a) - a.sum()], [b.sum(), len(b) - b.sum()]])[1])
    a = d[d.run_lo_below_rth_low == 1].low_done; b = d[d.run_lo_below_rth_low == 0].low_done
    print("  chi2 break vs no-break low:", stats.chi2_contingency([[a.sum(), len(a) - a.sum()], [b.sum(), len(b) - b.sum()]])[1])
    # ex post sequels
    X_ = x.copy()
    def med_ci(v):
        v = np.asarray(v, float); v = v[~np.isnan(v)]
        b = rng.integers(0, len(v), (2000, len(v))); m = np.median(v[b], 1)
        return np.median(v), np.quantile(m, .05), np.quantile(m, .95)
    big = X_[X_.hi_vs_rth_high_bp > 15]; near = X_[(X_.hi_vs_rth_high_bp <= 0) & (X_.hi_vs_rth_high_bp > -15)]
    below = X_[X_.hi_vs_rth_high_bp <= -15]
    for lab, s in [("high >15bp above RTH high", big), ("high 0..-15 below RTH high", near), ("high <=-15 below", below), ("all", X_)]:
        print(f"  {lab:30s} n={len(s)} hi_k median {s.hi_k.median():.1f} drop_after_hi med/CI {med_ci(s.drop_after_hi_bp)} close_loc med {s.close_loc.median():.2f} rng_bp med {s.rng_bp.median():.1f} drop/rng {np.median(s.drop_after_hi_bp/s.rng_bp):.2f} H1 drop {s[s.half=='H1'].drop_after_hi_bp.median():.1f} H2 {s[s.half=='H2'].drop_after_hi_bp.median():.1f}")
    # ratio of drop to range for late highs: big-break highs made late -> less room to drop mechanically
    for lab, s in [(">15 above", big), ("<=-15 below", below)]:
        print(f"    {lab}: median hi_k {s.hi_k.median()}, share hi_k>=7 {(s.hi_k>=7).mean():.2f}; drop_after_hi / bars_left mech")
