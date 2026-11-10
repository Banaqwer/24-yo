import numpy as np, pandas as pd
from scipy import stats
ROOT = "."
for sym in ["NQ", "ES"]:
    m = pd.read_csv(f"{ROOT}/data/{sym}_15m.csv"); m.columns = [c.lower() for c in m.columns]
    m["ts"] = pd.to_datetime(m["datetime"], utc=True).dt.tz_convert("America/New_York"); m = m.sort_values("ts")
    m["h"] = m.ts.dt.hour; m["mi"] = m.ts.dt.minute
    asia = m[(m.h >= 18) | (m.h <= 2)].copy()
    asia["sess"] = np.where(asia.h >= 18, asia.ts.dt.normalize(), (asia.ts - pd.Timedelta(days=1)).dt.normalize())
    asia["sess"] = pd.to_datetime(asia.sess).dt.tz_localize(None)
    asia["k"] = np.where(asia.h >= 18, asia.h - 18, asia.h + 6); asia["slot"] = asia.mi // 15
    rows = []
    for s, d in asia.groupby("sess"):
        if len(d) < 36: continue
        hi_i = d.high.idxmax(); lo_i = d.low.idxmin(); open0 = d.iloc[0].open
        # map Sunday session to Friday RTH date
        sd = s - pd.Timedelta(days=2) if s.dayofweek == 6 else s
        rows.append(dict(sess=sd, hi_k=d.loc[hi_i, "k"], hi_slot=d.loc[hi_i, "slot"], lo_k=d.loc[lo_i, "k"], lo_slot=d.loc[lo_i, "slot"],
                         hi_eq_open=d.loc[hi_i, "high"] == open0, lo_eq_open=d.loc[lo_i, "low"] == open0,
                         hi_eq_first_high=d.loc[hi_i, "high"] == d.iloc[0].high, lo_eq_first_low=d.loc[lo_i, "low"] == d.iloc[0].low))
    r = pd.DataFrame(rows)
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    c = r.set_index("sess").join(x[["hi_k", "lo_k"]], rsuffix="_1h", how="inner")
    print(f"{sym}: n={len(r)}; agreement 15m-derived hi_k vs hourly {(c.hi_k==c.hi_k_1h).mean():.2f}, lo_k {(c.lo_k==c.lo_k_1h).mean():.2f} (n joined {len(c)})")
    b0h = r[r.hi_k == 0]; b0l = r[r.lo_k == 0]; b8h = r[r.hi_k == 8]; b8l = r[r.lo_k == 8]
    print(f"  bar-0 highs n={len(b0h)} slots {b0h.hi_slot.value_counts().reindex(range(4)).fillna(0).astype(int).tolist()}; bar-0 lows n={len(b0l)} slots {b0l.lo_slot.value_counts().reindex(range(4)).fillna(0).astype(int).tolist()}")
    print(f"  extreme == 18:00 open print: highs {int(b0h.hi_eq_open.sum())}/{len(b0h)}, lows {int(b0l.lo_eq_open.sum())}/{len(b0l)}")
    print(f"  bar-8 highs n={len(b8h)} slots {b8h.hi_slot.value_counts().reindex(range(4)).fillna(0).astype(int).tolist()}; bar-8 lows n={len(b8l)} slots {b8l.lo_slot.value_counts().reindex(range(4)).fillna(0).astype(int).tolist()}")
    mid_h = r[(r.hi_k >= 1) & (r.hi_k <= 7)]; mid_l = r[(r.lo_k >= 1) & (r.lo_k <= 7)]
    print(f"  middle highs n={len(mid_h)} slots {mid_h.hi_slot.value_counts().reindex(range(4)).fillna(0).astype(int).tolist()}; middle lows n={len(mid_l)} slots {mid_l.lo_slot.value_counts().reindex(range(4)).fillna(0).astype(int).tolist()}")
    n0 = len(b0h) + len(b0l); k0 = int((b0h.hi_slot == 0).sum() + (b0l.lo_slot == 0).sum())
    kl = int((b8l.lo_slot == 3).sum()); kh = int((b8h.hi_slot == 3).sum())
    print(f"  first-slot share bar-0 extremes {k0}/{n0} p={stats.binomtest(k0, n0, .25).pvalue:.1e}; bar-8 lows last slot {kl}/{len(b8l)} p={stats.binomtest(kl, len(b8l), .25).pvalue:.3f}; bar-8 highs last slot {kh}/{len(b8h)} p={stats.binomtest(kh, len(b8h), .25).pvalue:.3f}")
    # chi-square of middle-bar slot uniformity
    for lab, s in [("mid highs", mid_h.hi_slot), ("mid lows", mid_l.lo_slot)]:
        cnt = s.value_counts().reindex(range(4)).fillna(0).values
        print(f"  {lab} uniformity chi2 p={stats.chisquare(cnt).pvalue:.2f}")
    # pooled bar-0 vs bar-8 slot distribution: is first-slot share of bar-0 extreme just 'open print' effect? check 2nd slot etc.
    print(f"  bar-0 extremes in slot 0 but NOT at the 18:00 open print: {k0 - int(b0h.hi_eq_open.sum()) - int(b0l.lo_eq_open.sum())}")
