"""Relation between the Asia extremes and the mean-reversion engine's targets / stops.
Engine (backtest.py / sessions.path_outcomes): entry at the 18:00 open AGAINST the RTH move on nights
with |rth_ret| >= 0.15%; targets RTH VWAP, 38.2% and 50% retrace of the RTH move; tight stop = RTH extreme
in the move's direction + 10% of the RTH range; wide stop = max(0.6 x med20 Asia range, 0.3 x RTH range)
from the 17:00 close.  Adverse extreme = the Asia extreme in the RTH direction (high after an up day).
"""
import sys; sys.path.insert(0, "research/extremes/scripts/critic")
from common import *

for sym in ["NQ", "ES"]:
    x = load_x(sym)
    x = x[x.rth_ret.abs() >= 0.0015]
    up = x.is_down == 0
    # adverse / favourable extreme bars and sizes
    x["adv_k"] = np.where(up, x.hi_k, x.lo_k); x["fav_k"] = np.where(up, x.lo_k, x.hi_k)
    x["adv_first"] = (x.adv_k < x.fav_k).astype(int)
    x["same"] = (x.adv_k == x.fav_k).astype(int)
    x["adv_bp"] = np.where(up, x.hi_bp, -x.lo_bp)      # adverse excursion from the 17:00 close, bp, >=0
    x["fav_bp"] = np.where(up, -x.lo_bp, x.hi_bp)      # favourable excursion
    move = x.lvl_rth_close - x.lvl_rth_open
    rng = x.lvl_rth_high - x.lvl_rth_low
    tight = np.where(up, x.lvl_rth_high + 0.1 * rng, x.lvl_rth_low - 0.1 * rng)
    med = x.asia_rng_med20 * x.lvl_rth_open  # approx points; features.py uses the point range directly
    wide_d = np.maximum(0.6 * x.asia_rng_med20 * x.ref_close, 0.3 * rng)
    wide = np.where(up, x.ref_close + wide_d, x.ref_close - wide_d)
    vwap = x.lvl_rth_vwap; r382 = x.lvl_rth_close - 0.382 * move; r500 = x.lvl_rth_close - 0.5 * move
    adv_px = np.where(up, x.asia_high, x.asia_low); fav_px = np.where(up, x.asia_low, x.asia_high)
    x["adv_beyond_tight"] = np.where(up, adv_px > tight, adv_px < tight).astype(int)
    x["adv_beyond_wide"] = np.where(up, adv_px > wide, adv_px < wide).astype(int)
    x["adv_beyond_rth_ext"] = np.where(up, x.high_above_rth_high, x.low_below_rth_low)
    x["fav_reaches_vwap"] = np.where(up, fav_px <= vwap, fav_px >= vwap).astype(int)
    x["fav_reaches_r382"] = np.where(up, fav_px <= r382, fav_px >= r382).astype(int)
    x["fav_reaches_r500"] = np.where(up, fav_px <= r500, fav_px >= r500).astype(int)
    x["ref_beyond_vwap"] = np.where(up, x.ref_close <= vwap, x.ref_close >= vwap).astype(int)
    x["adv_vs_tight_bp"] = (np.abs(adv_px - tight) / x.ref_close * 1e4) * np.where(x.adv_beyond_tight == 1, 1, -1)
    print(f"\n===== {sym}: engine universe |rth_ret|>=0.15%, n={len(x)} (up {up.sum()}, down {(~up).sum()}) =====")
    print(f" adverse extreme first {fmt(ci_prop(x.adv_first))} (same bar {x.same.mean():.3f}); after up {x[up].adv_first.mean():.3f} after down {x[~up].adv_first.mean():.3f}; H1/H2 {halves(x)[0].adv_first.mean():.3f}/{halves(x)[1].adv_first.mean():.3f}")
    print(" bar of the ADVERSE extreme %:", (x.adv_k.value_counts(normalize=True).sort_index() * 100).round(1).tolist())
    print(" bar of the FAVOURABLE extreme %:", (x.fav_k.value_counts(normalize=True).sort_index() * 100).round(1).tolist())
    print(f" adverse excursion from the 17:00 close: median {x.adv_bp.median():.0f} bp, p75 {x.adv_bp.quantile(.75):.0f}, p90 {x.adv_bp.quantile(.9):.0f}; favourable median {x.fav_bp.median():.0f} p75 {x.fav_bp.quantile(.75):.0f}")
    print(f" adverse extreme beyond the RTH extreme {fmt(ci_prop(x.adv_beyond_rth_ext))}; beyond the TIGHT stop {fmt(ci_prop(x.adv_beyond_tight))}; beyond the WIDE stop {fmt(ci_prop(x.adv_beyond_wide))}")
    print(f"   H1/H2 beyond tight {halves(x)[0].adv_beyond_tight.mean():.3f}/{halves(x)[1].adv_beyond_tight.mean():.3f}; beyond wide {halves(x)[0].adv_beyond_wide.mean():.3f}/{halves(x)[1].adv_beyond_wide.mean():.3f}")
    print(f" favourable extreme reaches VWAP {fmt(ci_prop(x.fav_reaches_vwap))} (17:00 close already beyond VWAP {x.ref_beyond_vwap.mean():.3f}), 38.2% {fmt(ci_prop(x.fav_reaches_r382))}, 50% {fmt(ci_prop(x.fav_reaches_r500))}")
    # distance of the adverse extreme to the tight stop
    print(f" adverse extreme vs tight stop (bp, + = through the stop): p10 {x.adv_vs_tight_bp.quantile(.1):.0f} p25 {x.adv_vs_tight_bp.quantile(.25):.0f} p50 {x.adv_vs_tight_bp.quantile(.5):.0f} p75 {x.adv_vs_tight_bp.quantile(.75):.0f}")
    # by the bar of the adverse extreme: does an early adverse extreme mean the target is reached?
    print(" P(fav reaches VWAP | adverse extreme bar k):")
    g = x.groupby("adv_k").fav_reaches_vwap.agg(["size", "mean"]); print("   n", g["size"].tolist()); print("   rate", g["mean"].round(2).tolist())
    e0 = x[x.adv_k == 0]; e8 = x[x.adv_k == 8]
    print(f"   adverse in bar 0: VWAP {fmt(ci_prop(e0.fav_reaches_vwap))}, stopped(tight) {e0.adv_beyond_tight.mean():.3f}; adverse in bar 8: VWAP {fmt(ci_prop(e8.fav_reaches_vwap))}, stopped {e8.adv_beyond_tight.mean():.3f}")
    print(f"   adverse first: VWAP {x[x.adv_first==1].fav_reaches_vwap.mean():.3f} (n={int((x.adv_first==1).sum())}) vs favourable first {x[x.adv_first==0].fav_reaches_vwap.mean():.3f}")

    # ---- intra-session bridge: at the close of bar k, detector says the adverse extreme is in (p>=0.9) ----
    p = load_panel(sym); p = p[p.k <= 7]
    o = pd.read_csv(os.path.join(EXT, f"oos_intrasession_{sym}.csv"), parse_dates=["date"])
    h = load_1h(sym); h["hour"] = h.index.hour
    # future path after bar k: max high / min low of bars k+1..8 and whether VWAP / stop is touched after k
    fut = []
    for d, r in x.iterrows():
        gd = pd.Timestamp(r.asia_gdate)
        g = h[(h.index.hour >= 18) & (h.index.date == (gd - pd.Timedelta(days=1)).date()) | (h.index.hour <= 2) & (h.index.date == gd.date())]
        g = g.sort_index()
        if len(g) != 9:
            continue
        H = g.High.values; L = g.Low.values
        for k in range(8):
            fut.append(dict(date=d, k=k, fut_high=H[k + 1:].max(), fut_low=L[k + 1:].min(), run_high=H[:k + 1].max(), run_low=L[:k + 1].min()))
    fut = pd.DataFrame(fut)
    m = fut.merge(x[["is_down", "lvl_rth_vwap", "lvl_rth_high", "lvl_rth_low", "ref_close", "asia_rng_med20"]], left_on="date", right_index=True)
    m = m.merge(o[["date", "k", "p_high_done", "p_low_done", "high_done", "low_done"]], on=["date", "k"], how="inner")
    upm = m.is_down == 0
    rng_m = m.lvl_rth_high - m.lvl_rth_low
    tight_m = np.where(upm, m.lvl_rth_high + 0.1 * rng_m, m.lvl_rth_low - 0.1 * rng_m)
    m["p_adv_done"] = np.where(upm, m.p_high_done, m.p_low_done)
    m["adv_done"] = np.where(upm, m.high_done, m.low_done)
    m["vwap_hit_by_k"] = np.where(upm, m.run_low <= m.lvl_rth_vwap, m.run_high >= m.lvl_rth_vwap)
    m["vwap_hit_after_k"] = np.where(upm, m.fut_low <= m.lvl_rth_vwap, m.fut_high >= m.lvl_rth_vwap)
    m["stop_hit_by_k"] = np.where(upm, m.run_high > tight_m, m.run_low < tight_m)
    m["stop_hit_after_k"] = np.where(upm, m.fut_high > tight_m, m.fut_low < tight_m)
    live = m[(~m.vwap_hit_by_k) & (~m.stop_hit_by_k)]      # trade still open, target not yet reached, not stopped
    print(f"\n Intra-session bridge (OOS rows, trade open: VWAP not yet touched, tight stop not yet hit): n={len(live)} rows, {live.date.nunique()} sessions")
    for lo, hi, lab in [(0, .5, "p_adv_done<0.5"), (.5, .9, "0.5-0.9"), (.9, 1.01, "p_adv_done>=0.9")]:
        s = live[(live.p_adv_done >= lo) & (live.p_adv_done < hi)]
        print(f"   {lab:16s} n={len(s):4d}: P(VWAP touched later) {s.vwap_hit_after_k.mean():.3f}  P(tight stop hit later) {s.stop_hit_after_k.mean():.3f}  (adverse actually in {s.adv_done.mean():.3f})")
    s9 = live[live.p_adv_done >= .9]; s1 = live[live.p_adv_done < .5]
    print(f"   VWAP-later: {fmt(ci_prop(s9.vwap_hit_after_k))} vs {fmt(ci_prop(s1.vwap_hit_after_k))}; stop-later {fmt(ci_prop(s9.stop_hit_after_k))} vs {fmt(ci_prop(s1.stop_hit_after_k))}")
    for nm, ss in [("H1", live[live.date < H2]), ("H2", live[live.date >= H2])]:
        a = ss[ss.p_adv_done >= .9]; b = ss[ss.p_adv_done < .5]
        print(f"   {nm}: p>=.9 VWAP-later {a.vwap_hit_after_k.mean():.3f} stop-later {a.stop_hit_after_k.mean():.3f} (n={len(a)}); p<.5 {b.vwap_hit_after_k.mean():.3f} / {b.stop_hit_after_k.mean():.3f} (n={len(b)})")
    print("   by k, p>=0.9: n / P(VWAP later) / P(stop later):")
    for k in range(1, 8):
        a = s9[s9.k == k]
        print(f"     k={k}: {len(a):3d} / {a.vwap_hit_after_k.mean():.2f} / {a.stop_hit_after_k.mean():.2f}   (all open rows at k: {len(live[live.k==k])} / {live[live.k==k].vwap_hit_after_k.mean():.2f} / {live[live.k==k].stop_hit_after_k.mean():.2f})")
