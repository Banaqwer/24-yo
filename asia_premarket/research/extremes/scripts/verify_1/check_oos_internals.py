"""Checks done purely from the shipped OOS CSV + extremes table:
 (a) p_cal of month M must equal an isotonic fit on p_raw/y of OOS months < M only (>=80 rows), else p_raw;
 (b) base_dst must equal the expanding DST-conditional rate before the month;
 (c) quantile base columns must equal the expanding unconditional quantile;
 (d) map h* columns = expanding Laplace histogram, hd* = DST-conditional, mix_w = argmin log-loss on PRIOR OOS months;
 (e) dow_prior p = expanding P(y | dow) with cells >= 20, else base."""
import os, sys
import numpy as np, pandas as pd
from sklearn.isotonic import IsotonicRegression

EX = "./research/extremes"
OOS = sys.argv[1] if len(sys.argv) > 1 else "research/extremes/scripts/verify_1/orig"
BIN = ["high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar",
       "high_by_tokyo_open", "low_by_tokyo_open", "high_above_rth_high", "low_below_rth_low", "hi_first"]


def ll(P, yk):
    P = np.clip(P, 1e-6, 1); return float(-np.mean(np.log(P[np.arange(len(yk)), yk])))


for sym in ["NQ", "ES"]:
    o = pd.read_csv(os.path.join(OOS, f"oos_preasia_{sym}.csv"), index_col="date", parse_dates=True).sort_index()
    x = pd.read_csv(os.path.join(EX, f"{sym}_extremes.csv"), index_col="date", parse_dates=True).sort_index()
    splice = {"NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"], "ES": ["2025-12-16", "2025-12-17"]}[sym]
    xf = x[(x["n_bars"] == 9) & ~x.index.isin(pd.to_datetime(splice))]
    pm_all = xf.index.to_period("M"); pm = o.index.to_period("M")
    months = pm.unique()
    print(f"\n### {sym}")
    # (a) calibration
    worst = 0.0; n_cal_rows = 0; n_rows_checked = 0
    for t in BIN:
        for s in ["full", "timing"]:
            pre = f"{t}__{s}__"
            for m in months:
                cur = o[pm == m]; prior = o[pm < m]
                if len(prior) >= 80:
                    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.02, y_max=0.98).fit(prior[pre + "p_raw"].values, prior[f"{t}__y"].values)
                    exp = iso.predict(cur[pre + "p_raw"].values); n_cal_rows += len(cur)
                    assert (cur[pre + "cal_on"] == 1).all()
                else:
                    exp = cur[pre + "p_raw"].values
                    assert (cur[pre + "cal_on"] == 0).all()
                worst = max(worst, float(np.abs(exp - cur[pre + "p_cal"].values).max())); n_rows_checked += len(cur)
    print(f"(a) p_cal == isotonic fitted on PRIOR OOS months only: max abs diff {worst:.2e} over {n_rows_checked} rows ({n_cal_rows} calibrated)")
    # pooled-calibration counterfactual: what would p_cal look like if fitted on ALL OOS (to show it is NOT that)
    t, s = "high_above_rth_high", "full"; pre = f"{t}__{s}__"
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.02, y_max=0.98).fit(o[pre + "p_raw"].values, o[f"{t}__y"].values)
    print(f"    (pooled-isotonic counterfactual for {t}: max |pooled - shipped p_cal| = {np.abs(iso.predict(o[pre + 'p_raw'].values) - o[pre + 'p_cal'].values).max():.3f}, i.e. shipped is NOT pooled)")
    # (b) base_dst, (e) dow_prior
    worst_b = worst_e = 0.0
    for t in BIN:
        for m in months:
            tr = xf[pm_all < m]; cur_idx = o.index[pm == m]
            bd = tr.groupby("is_dst")[t].mean()
            exp = xf.loc[cur_idx, "is_dst"].map(bd).fillna(tr[t].mean()).values
            worst_b = max(worst_b, float(np.abs(exp - o.loc[cur_idx, f"{t}__full__base_dst"].values).max()))
            g = tr.groupby("dow")[t].agg(["mean", "size"]); base = tr[t].mean()
            exp = np.array([g.loc[d, "mean"] if (d in g.index and g.loc[d, "size"] >= 20) else base for d in xf.loc[cur_idx, "dow"]])
            worst_e = max(worst_e, float(np.abs(exp - o.loc[cur_idx, f"{t}__dow_prior__p_cal"].values).max()))
    print(f"(b) base_dst == expanding DST-conditional rate before the month: max abs diff {worst_b:.2e}")
    print(f"(e) dow_prior == expanding P(y|dow) (cells>=20) before the month: max abs diff {worst_e:.2e}")
    # (c) quantile base
    worst_c = 0.0
    for t in ["hi_bp", "lo_bp", "rng_bp"]:
        for q in (0.2, 0.5, 0.8):
            for m in months:
                exp = xf.loc[pm_all < m, t].quantile(q); cur_idx = o.index[pm == m]
                worst_c = max(worst_c, float(np.abs(exp - o.loc[cur_idx, f"{t}__base_q{int(q*100)}"].values).max()))
    print(f"(c) quantile base == expanding unconditional quantile before the month: max abs diff {worst_c:.2e}")
    # (d) map
    worst_h = worst_hd = 0.0; mix_ok = 0; mix_n = 0
    for t in ["hi_k", "lo_k"]:
        pc = [f"{t}__p{i}" for i in range(9)]; hc = [f"{t}__h{i}" for i in range(9)]; hd = [f"{t}__hd{i}" for i in range(9)]
        for m in months:
            tr = xf[pm_all < m]; cur_idx = o.index[pm == m]
            h = np.bincount(tr[t].astype(int).values, minlength=9) + 1.0; h = h / h.sum()
            worst_h = max(worst_h, float(np.abs(o.loc[cur_idx, hc].values - h).max()))
            for d in (0, 1):
                sub = tr[tr["is_dst"] == d]
                hdd = (np.bincount(sub[t].astype(int).values, minlength=9) + 1.0) if len(sub) >= 30 else None
                hdd = hdd / hdd.sum() if hdd is not None else h
                rows_d = cur_idx[xf.loc[cur_idx, "is_dst"].values == d]
                if len(rows_d):
                    worst_hd = max(worst_hd, float(np.abs(o.loc[rows_d, hd].values - hdd).max()))
            prior = o[pm < m]
            if len(prior) >= 80:
                yk = prior[f"{t}__y"].astype(int).values; P = prior[pc].values; H = prior[hc].values
                grid = np.linspace(0, 1, 21); w = grid[int(np.argmin([ll((1 - w) * P + w * H, yk) for w in grid]))]
            else:
                w = 1.0
            mix_n += 1; mix_ok += int(abs(w - o.loc[cur_idx, f"{t}__mix_w"].iloc[0]) < 1e-9)
    print(f"(d) map hist == expanding Laplace histogram: max abs diff {worst_h:.2e}; DST hist: {worst_hd:.2e}; mix_w chosen on PRIOR OOS only: {mix_ok}/{mix_n} months match")
    print("    mix_w by month:", o.groupby(pm)["hi_k__mix_w"].first().round(2).to_dict())
