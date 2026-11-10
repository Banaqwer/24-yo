"""Independent recompute of T1-T4 (bar-0 statistics, U-shape vs 18:00 features)."""
import numpy as np, pandas as pd
from scipy import stats
ROOT = "."
SPLIT = pd.Timestamp("2025-09-01")
BAD = {"NQ": ["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"],
       "ES": ["2025-12-15", "2025-12-16", "2025-12-17"]}
rng = np.random.default_rng(123)

def load(sym):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    bad = pd.to_datetime(BAD[sym])
    x = x[~x.index.isin(bad)]; p = p[~p.date.isin(bad)]
    x["half"] = np.where(x.index < SPLIT, "H1", "H2")
    p["half"] = np.where(p.date < SPLIT, "H1", "H2")
    return x, p

def ci(v, nb=3000):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    if len(v) < 2: return (np.nan, np.nan)
    b = rng.integers(0, len(v), (nb, len(v)))
    m = v[b].mean(1)
    return (np.quantile(m, .05), np.quantile(m, .95))

def rate(mask, y, half, base, label):
    m = np.asarray(mask.fillna(False), bool); yy = np.asarray(y, float)
    s = yy[m]; n = len(s); k = int(np.nansum(s)); r = k / n if n else np.nan
    lo, hi = ci(s)
    p = stats.binomtest(k, n, base).pvalue if n else np.nan
    h = np.asarray(half)
    r1 = yy[m & (h == "H1")].mean() if (m & (h == "H1")).sum() else np.nan
    r2 = yy[m & (h == "H2")].mean() if (m & (h == "H2")).sum() else np.nan
    n1 = int((m & (h == "H1")).sum()); n2 = int((m & (h == "H2")).sum())
    print(f"  {label:48s} n={n:4d} rate={r:.3f} base={base:.3f} CI[{lo:.3f},{hi:.3f}] p={p:.2e} H1={r1:.3f}(n{n1}) H2={r2:.3f}(n{n2})")
    return r

for sym in ["NQ", "ES"]:
    x, p = load(sym)
    full = x[x.n_bars == 9].copy()
    print(f"\n===== {sym}: full sessions n={len(full)} =====")
    k0 = p[(p.k == 0) & (p.n_bars == 9)].set_index("date")
    full = full.join(k0[["bar_close_loc", "pos_in_range", "bar_ret_bp", "bar_rng_bp", "bar_vol_rel"]], rsuffix="_k0")
    hi0 = (full.hi_k == 0).astype(float); lo0 = (full.lo_k == 0).astype(float)
    bh, bl = hi0.mean(), lo0.mean()
    print(f"base: high in bar0 {bh:.3f}, low in bar0 {bl:.3f}")
    # sanity: high_in_first_bar col
    print("  check high_in_first_bar==hi_k==0:", (full.high_in_first_bar == (full.hi_k == 0)).mean())
    print("  bar_close_loc vs pos_in_range at k0 identical?:", np.allclose(full.bar_close_loc, full.pos_in_range, equal_nan=True))

    print("--- T1: bar_close_loc buckets at k=0 ---")
    cl = full.bar_close_loc
    for lab, m in [(">=0.8", cl >= .8), ("0.5-0.8", (cl >= .5) & (cl < .8)), ("0.2-0.5", (cl >= .2) & (cl < .5)), ("<0.2", cl < .2)]:
        rate(m, lo0, full.half, bl, f"low in bar0 | close_loc {lab}")
        rate(m, hi0, full.half, bh, f"high in bar0 | close_loc {lab}")

    print("--- T2: first_bar_ret_bp buckets ---")
    r = full.first_bar_ret_bp
    print("  check first_bar_ret_bp == bar_ret_bp(k0):", np.allclose(full.first_bar_ret_bp, full.bar_ret_bp, equal_nan=True))
    for lab, m in [(">+20", r > 20), ("<-20", r < -20), ("|r|<=5", r.abs() <= 5), ("-20..-5", (r < -5) & (r >= -20)), ("+5..+20", (r > 5) & (r <= 20))]:
        rate(m, lo0, full.half, bl, f"low in bar0 | ret {lab}")
        rate(m, hi0, full.half, bh, f"high in bar0 | ret {lab}")
    # direction relative
    isdn = full.is_down.astype(int)
    counter0 = np.where(isdn == 1, hi0, lo0)  # counter-trend extreme: after down day the HIGH is counter
    cont0 = np.where(isdn == 1, lo0, hi0)
    bc, bk = counter0.mean(), cont0.mean()
    print(f"  base counter in bar0 {bc:.3f}, continuation in bar0 {bk:.3f}")
    rid = r * np.where(isdn == 1, -1, 1)  # positive = with the RTH direction
    full["counter0"] = counter0; full["cont0"] = cont0
    rate(rid < -10, pd.Series(counter0, index=full.index), full.half, bc, "counter extreme in bar0 | bar0 against RTH >10")
    rate(rid < -10, pd.Series(cont0, index=full.index), full.half, bk, "cont extreme in bar0 | bar0 against RTH >10")
    rate(rid > 10, pd.Series(cont0, index=full.index), full.half, bk, "cont extreme in bar0 | bar0 with RTH >10")
    rate(rid > 10, pd.Series(counter0, index=full.index), full.half, bc, "counter extreme in bar0 | bar0 with RTH >10")
    # Is T2 just T1 restated? Compare within close_loc buckets
    print("  T2 incremental over T1: among close_loc>=0.8, low in bar0 by ret>20 vs ret<=20")
    rate((cl >= .8) & (r > 20), lo0, full.half, bl, "low bar0 | cl>=.8 & ret>20")
    rate((cl >= .8) & (r <= 20), lo0, full.half, bl, "low bar0 | cl>=.8 & ret<=20")
    rate((cl < .8) & (r > 20), lo0, full.half, bl, "low bar0 | cl<.8 & ret>20")
    rate((cl < .2) & (r < -20), hi0, full.half, bh, "high bar0 | cl<.2 & ret<-20")
    rate((cl < .2) & (r >= -20), hi0, full.half, bh, "high bar0 | cl<.2 & ret>=-20")
    rate((cl >= .2) & (r < -20), hi0, full.half, bh, "high bar0 | cl>=.2 & ret<-20")

    print("--- T3: first bar range share of med20 ---")
    share = full.first_bar_rng_bp / (full.asia_rng_med20 * 1e4)
    print("  check first_bar_rng_bp == bar_rng_bp(k0):", np.allclose(full.first_bar_rng_bp, full.bar_rng_bp, equal_nan=True))
    either = ((full.hi_k == 0) | (full.lo_k == 0)).astype(float)
    sub = share.notna()
    be = either[sub].mean()
    print(f"  n with med20: {sub.sum()}, base either {be:.3f}, high {hi0[sub].mean():.3f}, low {lo0[sub].mean():.3f}")
    for lab, m in [(">=0.5", share >= .5), ("0.3-0.5", (share >= .3) & (share < .5)), ("0.15-0.3", (share >= .15) & (share < .3)), ("<0.15", share < .15)]:
        rate(m, either, full.half, be, f"either in bar0 | share {lab}")
        rate(m, hi0, full.half, hi0[sub].mean(), f"high in bar0 | share {lab}")
        rate(m, lo0, full.half, lo0[sub].mean(), f"low in bar0 | share {lab}")
    # combination with T1
    rate((share >= .5) & (cl >= .8), lo0, full.half, bl, "low in bar0 | share>=.5 & cl>=.8")
    rate((share < .3) & (cl >= .8), lo0, full.half, bl, "low in bar0 | share<.3 & cl>=.8")
    rate((share >= .5) & (cl < .2), hi0, full.half, bh, "high in bar0 | share>=.5 & cl<.2")
    # is T3 mechanical: wide bar -> run_rng is big
    # alt: raw first_bar_rng_bp terciles
    q = full.first_bar_rng_bp.quantile([1/3, 2/3])
    rate(full.first_bar_rng_bp >= q.iloc[1], either, full.half, be, "either | raw rng top tercile")
    rate(full.first_bar_rng_bp < q.iloc[0], either, full.half, be, "either | raw rng bottom tercile")

    print("--- T4: sunday_open and 18:00 features ---")
    hi8 = (full.hi_k == 8).astype(float); lo8 = (full.lo_k == 8).astype(float)
    print(f"  base high bar8 {hi8.mean():.3f}, low bar8 {lo8.mean():.3f}")
    rate(full.sunday_open == 1, lo0, full.half, bl, "low in bar0 | sunday_open")
    rate(full.sunday_open == 0, lo0, full.half, bl, "low in bar0 | not sunday")
    rate(full.sunday_open == 1, hi0, full.half, bh, "high in bar0 | sunday_open")
    rate(full.sunday_open == 1, hi8, full.half, hi8.mean(), "high in bar8 | sunday_open")
    rate(full.sunday_open == 1, lo8, full.half, lo8.mean(), "low in bar8 | sunday_open")
    # Fisher exact for sunday vs not
    a = int(lo0[full.sunday_open == 1].sum()); b = int((full.sunday_open == 1).sum()) - a
    c = int(lo0[full.sunday_open == 0].sum()); d = int((full.sunday_open == 0).sum()) - c
    print("  Fisher sunday vs not (low bar0):", stats.fisher_exact([[a, b], [c, d]]))
    # scan: 40 continuous features terciles x 4 outcomes + flags; count hits p<.05 and p<.01
    cont_feats = ['rth_ret', 'mag', 'ext_in_dir', 'vwap_in_dir', 'stretch20_in_dir', 'stretch50_in_dir', 'ret5_in_dir', 'gap_in_dir',
                  'post_in_dir', 'prior_asia_in_dir', 'overnight_in_dir', 'n225_in_dir', 'sox_in_dir', 'nqes_in_dir', 'yen_in_dir',
                  'yield_in_dir', 'vix', 'vix_z20', 'rv_ratio', 'rth_range_atr', 'abs_streak', 'rth_vol_rel', 'asia_rng_med20',
                  'dxy_chg', 'usdjpy_chg', 'us10y_chg', 'n225_ret', 'kospi_ret', 'hsi_ret', 'sse_ret', 'sx5e_ret', 'sox_ret',
                  'gold_chg', 'crude_chg', 'btc_rth', 'rth_hi_hour', 'rth_lo_hour', 'clv', 'z_sma20', 'vix_chg']
    flags = ['fomc_today', 'fed_minutes_today', 'tier1_data_today', 'tier2_data_today', 'opex_today', 'witching_today', 'roll_today',
             'megacap_earnings_tonight', 'election_today', 'politics_today', 'boj_tonight', 'jp_data_tonight', 'cn_data_tonight',
             'cn_policy_tonight', 'rba_tonight', 'fomc_tomorrow', 'tier1_data_tomorrow', 'tier2_data_tomorrow', 'ecb_tomorrow',
             'boe_tomorrow', 'opex_tomorrow', 'holiday_tomorrow', 'sunday_open', 'pre_holiday', 'month_end']
    outs = {"hi0": hi0, "lo0": lo0, "hi8": hi8, "lo8": lo8}
    hits05 = []; hits01 = []; ntest = 0; maxshift = 0
    for f in cont_feats:
        if f not in full: continue
        v = full[f]
        t = v.quantile([1/3, 2/3])
        for lab, m in [("lo", v <= t.iloc[0]), ("hi", v > t.iloc[1])]:
            for on, y in outs.items():
                ntest += 1
                s = y[m & v.notna()]; base = y[v.notna()].mean()
                pv = stats.binomtest(int(s.sum()), len(s), base).pvalue
                sh = abs(s.mean() - base)
                maxshift = max(maxshift, sh)
                if pv < .05: hits05.append((f, lab, on, len(s), round(s.mean(), 3), round(base, 3), round(pv, 4)))
                if pv < .01: hits01.append((f, lab, on, len(s), round(s.mean(), 3), round(base, 3), round(pv, 4)))
    for f in flags:
        if f not in full: continue
        m = full[f] == 1
        if m.sum() < 10: continue
        for on, y in outs.items():
            ntest += 1
            s = y[m]; base = y.mean()
            pv = stats.binomtest(int(s.sum()), len(s), base).pvalue
            maxshift = max(maxshift, abs(s.mean() - base))
            if pv < .05: hits05.append((f, "flag", on, len(s), round(s.mean(), 3), round(base, 3), round(pv, 4)))
            if pv < .01: hits01.append((f, "flag", on, len(s), round(s.mean(), 3), round(base, 3), round(pv, 4)))
    print(f"  scan: {ntest} tests, {len(hits05)} at p<.05 (expect {ntest*.05:.0f}), {len(hits01)} at p<.01 (expect {ntest*.01:.1f}), max shift {maxshift:.3f}")
    for h in hits05: print("    ", h)
