"""Shuffle test: permute the label block of each session among the sessions of the same calendar month
(session-level permutation keeps the k-structure of the labels, so the k-only baseline keeps its information
while any feature->label link is destroyed), then re-run the same walk-forward (LR + GB + ensemble + prior-OOS
isotonic). Skill vs k-only must vanish.  Also a row-level permutation within month (destroys k-structure too):
skill vs the pooled base rate must vanish.

Usage: python3 shuffle_test.py <SYM> <seed> <session|row>
"""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "research/extremes/scripts/verify_0/run")
import detector_intrasession as det

SYM, SEED, MODE = sys.argv[1], int(sys.argv[2]), sys.argv[3]
H2 = pd.Timestamp("2025-09-01")
LABELS = ["high_done", "low_done"]
rng = np.random.default_rng(SEED)

d = det.build_dataset(SYM)
assert (d.groupby("date").size() == 8).all()
d["ym"] = d["date"].dt.year * 100 + d["date"].dt.month
orig = d[LABELS].copy()
if MODE == "session":
    # permute whole sessions' label blocks within month
    for ym, g in d.groupby("ym"):
        sess = g["date"].unique()
        perm = rng.permutation(sess)
        mapping = dict(zip(sess, perm))
        src_rows = {s: g[g["date"] == s].sort_values("k").index.values for s in sess}
        for s in sess:
            dst = src_rows[s]; src = src_rows[mapping[s]]
            d.loc[dst, LABELS] = orig.loc[src, LABELS].values
else:
    for ym, g in d.groupby("ym"):
        idx = g.index.values
        perm = rng.permutation(idx)
        d.loc[idx, LABELS] = orig.loc[perm, LABELS].values
print(f"{SYM} seed {SEED} mode {MODE}: labels changed on {(d[LABELS].values != orig.values).any(axis=1).mean():.3f} of rows; "
      f"per-k mean high_done after: {d.groupby('k')['high_done'].mean().round(2).tolist()}")


def fit(tr):
    X = tr[det.FEATURES]; D = det.lr_design(tr); m = {}
    for t in LABELS:
        y = tr[t].values
        m[f"lr_{t}"] = det._lr().fit(D, y); m[f"gb_{t}"] = det._gb().fit(X, y)
        m[f"base_{t}"] = float(y.mean()); m[f"kbase_{t}"] = tr.groupby("k")[t].mean()
    return m


def predict(m, te):
    X = te[det.FEATURES]; D = det.lr_design(te)
    out = te[["date", "k"] + LABELS].copy()
    for t in LABELS:
        s = t.split("_")[0]
        out[f"p_{s}_lr"] = m[f"lr_{t}"].predict_proba(D)[:, 1]
        out[f"p_{s}_gb"] = m[f"gb_{t}"].predict_proba(X)[:, 1]
        out[f"p_{s}_raw"] = 0.5 * (out[f"p_{s}_lr"] + out[f"p_{s}_gb"])
        out[f"base_{s}"] = m[f"base_{t}"]; out[f"kbase_{s}"] = te["k"].map(m[f"kbase_{t}"]).values
    return out


dates = np.array(sorted(d["date"].unique()))
preds, hist = [], None
for ym, bd in det._month_blocks(dates[det.TRAIN_ONLY_SESSIONS:]):
    t0 = pd.Timestamp(bd[0]); tr = d[d["date"] < t0]; te = d[d["date"].isin(bd)]
    m = fit(tr)
    out = det.apply_calibrators(predict(m, te), det.fit_calibrators(hist))
    preds.append(out); hist = pd.concat(preds, ignore_index=True)
oos = pd.concat(preds, ignore_index=True)


def brier(y, p):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


from sklearn.metrics import roc_auc_score
print(f"OOS rows {len(oos)} sessions {oos['date'].nunique()}")
for s in ["high", "low"]:
    t = f"{s}_done"; y = oos[t]
    bb, bk, br, bf = brier(y, oos[f"base_{s}"]), brier(y, oos[f"kbase_{s}"]), brier(y, oos[f"p_{s}_raw"]), brier(y, oos[f"p_{s}_done"])
    perk = " ".join(f"{1 - brier(g[t], g[f'p_{s}_done'])/brier(g[t], g[f'kbase_{s}']):+.2f}" for kk, g in oos.groupby("k"))
    g1 = oos[oos["date"] < H2]; g2 = oos[oos["date"] >= H2]
    print(f"  {t}: Brier base {bb:.4f} k-only {bk:.4f} raw {br:.4f} final {bf:.4f} | skill final vs k-only {1-bf/bk:+.4f} vs base {1-bf/bb:+.4f} "
          f"| AUC final {roc_auc_score(y, oos[f'p_{s}_done']):.3f} | per-k skill vs k-only {perk} | H1 {1-brier(g1[t], g1[f'p_{s}_done'])/brier(g1[t], g1[f'kbase_{s}']):+.3f} H2 {1-brier(g2[t], g2[f'p_{s}_done'])/brier(g2[t], g2[f'kbase_{s}']):+.3f}")
oos.to_csv(f"research/extremes/scripts/verify_0/shuffle_{SYM}_{MODE}_{SEED}.csv", index=False)
