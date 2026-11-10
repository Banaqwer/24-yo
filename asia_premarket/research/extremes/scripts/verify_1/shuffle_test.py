"""Shuffle test: permute the labels WITHIN calendar month (of the RTH date) and re-run the module's own
walk-forward functions.  Skill must vanish.  Also: seed=None reproduces the shipped OOS columns exactly
(an independent check that the walk-forward is deterministic and that my call path equals the module's).
Usage: python3 shuffle_test.py SYM N_SEEDS"""
import os, sys, time
import numpy as np, pandas as pd

RUN = "research/extremes/scripts/verify_1/run"
sys.path.insert(0, RUN)
import detector_preasia as dp   # the verbatim copy of the module

sym = sys.argv[1] if len(sys.argv) > 1 else "NQ"
N_SEEDS = int(sys.argv[2]) if len(sys.argv) > 2 else 10
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"shuffle_{sym}.csv")

x = dp.load_extremes(sym)
F = dp.make_features(x)
dst = x["is_dst"].astype(int)
dow = x["dow"].astype(int)
orig = pd.read_csv(os.path.join(RUN, f"oos_preasia_{sym}.csv"), index_col="date", parse_dates=True)


def permute_within_month(y: pd.Series, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    out = y.copy()
    for _, idx in y.groupby(y.index.to_period("M")).groups.items():
        v = y.loc[idx].values.copy(); rng.shuffle(v); out.loc[idx] = v
    return out


def brier(p, y): return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))
def pinball(pred, y, q):
    d = np.asarray(y) - np.asarray(pred); return float(np.mean(np.maximum(q * d, (q - 1) * d)))


rows = []
t0 = time.time()
# ---- seed None = no permutation: must reproduce the shipped CSV exactly ----
for t, sname in [("high_above_rth_high", "full"), ("low_below_rth_low", "full"), ("low_by_tokyo_open", "timing")]:
    o, _ = dp.walk_forward_binary(F[dp.FEATURE_SETS[sname]], x[t], dst)
    d = np.abs(o["p_cal"].values - orig[f"{t}__{sname}__p_cal"].values).max()
    print(f"[reproduce] {sym} {t}/{sname}: max |p_cal - shipped| = {d:.2e}; skill = {1 - brier(o.p_cal, o.y) / brier(o.base, o.y):+.4f}")
o = dp.walk_forward_quantile(F[dp.FEATURES_QUANT], x["rng_bp"])
print(f"[reproduce] {sym} rng_bp q50: max |q50 - shipped| = {np.abs(o['q50'].values - orig['rng_bp__q50'].values).max():.2e}")
o = dp.walk_forward_map(F[dp.FEATURES_TIMING], x["hi_k"], dst)
print(f"[reproduce] {sym} hi_k map: max |m0 - shipped| = {np.abs(o['m0'].values - orig['hi_k__m0'].values).max():.2e}")

# ---- permutations ----
for seed in range(N_SEEDS):
    for t, sname in [("high_above_rth_high", "full"), ("low_below_rth_low", "full"), ("low_by_tokyo_open", "timing"), ("low_by_tokyo_open", "dow_prior")]:
        yp = permute_within_month(x[t], seed)
        if sname == "dow_prior":
            o = dp.walk_forward_prior(yp, dow, dst)
        else:
            o, _ = dp.walk_forward_binary(F[dp.FEATURE_SETS[sname]], yp, dst)
        h1 = np.asarray(o.index < dp.H1_END)
        rows.append(dict(kind="binary", target=t, set=sname, seed=seed,
                         skill=1 - brier(o.p_cal, o.y) / brier(o.base, o.y),
                         skill_raw=1 - brier(o.p_raw, o.y) / brier(o.base, o.y),
                         skill_H1=1 - brier(o.p_cal[h1], o.y[h1]) / brier(o.base[h1], o.y[h1]),
                         skill_H2=1 - brier(o.p_cal[~h1], o.y[~h1]) / brier(o.base[~h1], o.y[~h1])))
    for t in dp.QUANT_TARGETS:
        yp = permute_within_month(x[t].astype(float), seed)
        o = dp.walk_forward_quantile(F[dp.FEATURES_QUANT], yp)
        for q in dp.QUANTILES:
            c = f"q{int(q*100)}"
            rows.append(dict(kind="quantile", target=t, set=str(q), seed=seed,
                             skill=1 - pinball(o[c], o.y, q) / pinball(o[f"base_{c}"], o.y, q)))
    if seed < 5:
        for t in dp.MAP_TARGETS:
            yp = permute_within_month(x[t].astype(int), seed)
            o = dp.walk_forward_map(F[dp.FEATURES_TIMING], yp, dst)
            yk = o["y"].astype(int).values
            P = o[[f"m{i}" for i in range(9)]].values; H = o[[f"h{i}" for i in range(9)]].values; M = o[[f"p{i}" for i in range(9)]].values
            rows.append(dict(kind="map", target=t, set="mixed", seed=seed, skill=1 - dp._ll(P, yk) / dp._ll(H, yk),
                             skill_raw=1 - dp._ll(M, yk) / dp._ll(H, yk)))
    print(f"seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)

r = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(f"\n=== {sym} shuffle-test null distribution (labels permuted within month), {N_SEEDS} seeds ===")
print(r.groupby(["kind", "target", "set"])["skill"].agg(["count", "mean", "std", "min", "max"]).round(4).to_string())
if "skill_raw" in r:
    print("\nraw (uncalibrated) skill:")
    print(r.dropna(subset=["skill_raw"]).groupby(["kind", "target", "set"])["skill_raw"].agg(["mean", "min", "max"]).round(4).to_string())
