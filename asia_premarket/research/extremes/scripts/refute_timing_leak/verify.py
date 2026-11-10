"""Knowability / leakage audit of the timing-lens claims T1..T15."""
import sys, os
sys.path.insert(0, ".")
sys.path.insert(0, "research/extremes/scripts/lens_timing")
import numpy as np, pandas as pd
from scipy import stats
from common import load, boot_ci, binom_p, rate_row, SPLIT
from sessions import load_hourly, ASIA_HOURS
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
OUT = "research/extremes/scripts/refute_timing_leak"
ROOT = "."

def hdr(s): print("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)

# ---------------------------------------------------------------- A. panel definition audit
hdr("A. recompute bar-k state from raw 1h bars (NQ) and compare with the panel: are bars_since/pos_in_range/high_done ex-ante?")
x, p = load("NQ")
h = load_hourly(f"{ROOT}/data/NQ_1h.csv")
h["hour"] = h.index.hour
g = pd.Series(h.index.date, index=h.index); sh = h.index.hour >= 18
g[sh] = (h.index[sh] + pd.Timedelta(days=1)).date
h["gdate"] = g.values
a = h[h.hour.isin(ASIA_HOURS)]
groups = {pd.Timestamp(gd): grp.sort_index() for gd, grp in a.groupby("gdate") if len(grp) >= 6}
mism = {"bars_since_hi": 0, "pos_in_range": 0, "bar_close_loc": 0, "high_done": 0, "low_done": 0, "run_hi_above_rth_high": 0}; nrows = 0
first_hour = []
for d, r in x.iterrows():
    gd = pd.Timestamp(r["asia_gdate"]); grp = groups[gd]
    first_hour.append(grp.index[0].hour)
    run_hi = -np.inf; run_lo = np.inf; khi = klo = 0
    sess_hi = grp.High.max(); sess_lo = grp.Low.min()
    pr = p[p.date == d].set_index("k")
    for k in range(len(grp)):
        b = grp.iloc[k]
        if b.High > run_hi: run_hi = b.High; khi = k
        if b.Low < run_lo: run_lo = b.Low; klo = k
        rr = run_hi - run_lo
        row = pr.loc[k]; nrows += 1
        if row.bars_since_hi != k - khi: mism["bars_since_hi"] += 1
        if abs(row.pos_in_range - ((b.Close - run_lo) / rr if rr > 0 else .5)) > 1e-9: mism["pos_in_range"] += 1
        if abs(row.bar_close_loc - ((b.Close - b.Low) / (b.High - b.Low) if b.High > b.Low else .5)) > 1e-9: mism["bar_close_loc"] += 1
        if row.high_done != int(run_hi >= sess_hi - 1e-9): mism["high_done"] += 1
        if row.low_done != int(run_lo <= sess_lo + 1e-9): mism["low_done"] += 1
        if row.run_hi_above_rth_high != int(run_hi > r["lvl_rth_high"]): mism["run_hi_above_rth_high"] += 1
print("rows checked:", nrows, "mismatches:", mism)
print("first bar hour of every session (should be 18):", pd.Series(first_hour).value_counts().to_dict())
# pos_in_range == bar_close_loc at k=0 ?
p0 = p[p.k == 0]
print("k=0: max |pos_in_range - bar_close_loc| =", float((p0.pos_in_range - p0.bar_close_loc).abs().max()))
# ex-ante check of the volume/range medians: rebuild vol_med20 for hour 18 and compare with panel bar_vol_rel at k=0
print("bar_vol_rel NaN share by k:", p[p.n_bars == 9].groupby("k").bar_vol_rel.apply(lambda v: v.isna().mean()).round(3).to_dict())
allb = pd.concat(groups.values()); allb = allb[allb.index.hour == 19].sort_index()
vm = allb.Volume.shift(1).rolling(20, min_periods=10).median()
chk = p[p.k == 1].set_index("date").join(x[["asia_gdate"]])
ratio = []
for d, r in chk.iterrows():
    grp = groups[pd.Timestamp(r.asia_gdate)]
    if grp.index[1].hour != 19: continue
    ts = grp.index[1]
    if ts in vm.index and pd.notna(vm.loc[ts]) and vm.loc[ts] > 0 and pd.notna(r.bar_vol_rel):
        ratio.append(abs(r.bar_vol_rel - grp.Volume.iloc[1] / vm.loc[ts]))
print("k=1 (19:00) bar_vol_rel vs ex-ante (shift(1).rolling(20)) recompute: max abs diff =", max(ratio), "n =", len(ratio))
# T11 volume-share benchmark: bar 0 has zero volume in most sessions -> uniform over bars with volume is 1/8 not 1/9
xf = x[x.n_bars == 9]
print("T11: median hi_bar_vol_share", round(xf.hi_bar_vol_share.median(), 4), "lo", round(xf.lo_bar_vol_share.median(), 4), "| excluding extremes in bar 0: hi", round(xf[xf.hi_k > 0].hi_bar_vol_share.median(), 4), "lo", round(xf[xf.lo_k > 0].lo_bar_vol_share.median(), 4), "| 1/8 =", round(1 / 8, 4), "1/9 =", round(1 / 9, 4))
print("T11: median ordinary-bar volume share (k=1..8, non-extreme bars):", end=" ")
vs = []
for d, r in xf.iterrows():
    grp = groups[pd.Timestamp(r.asia_gdate)]; tot = grp.Volume.sum()
    for k in range(1, 9):
        if k != r.hi_k and k != r.lo_k: vs.append(grp.Volume.iloc[k] / tot)
print(round(float(np.median(vs)), 4))
# asia_rng_med20 ex-ante check: compare with median of prior 20 realised ranges (rng_bp relative to asia_open) from the extremes table itself
own = ((x.asia_high - x.asia_low) / x.asia_open)
rec = own.shift(1).rolling(20, min_periods=10).median()
print("asia_rng_med20 vs recompute from the extremes table (shift(1) rolling 20 median): max abs diff =", float((x.asia_rng_med20 - rec).abs().max()),
      "| corr with TONIGHT's own range =", round(float(x.asia_rng_med20.corr(own)), 3), "| corr of tonight with last night =", round(float(own.corr(own.shift(1))), 3))
# would asia_rng_med20 contain tonight if unshifted? check equality with unshifted
rec0 = own.rolling(20, min_periods=10).median()
print("   max abs diff vs UNshifted rolling median (should be > 0 if ex-ante):", float((x.asia_rng_med20 - rec0).abs().max()))

# ---------------------------------------------------------------- B. T10 negative distance
hdr("B. T10: the '<10 bp' bucket -- how much of it is the 17:00 close ALREADY beyond the RTH extreme (mechanical)?")
rows = []
for sym in ["NQ", "ES"]:
    x, p = load(sym)
    x["dh"] = (x.lvl_rth_high / x.ref_close - 1) * 1e4
    x["dl"] = -(x.lvl_rth_low / x.ref_close - 1) * 1e4
    x["gap0"] = x.gap_open_bp
    for side, dcol, ycol in [("high", "dh", "high_above_rth_high"), ("low", "dl", "low_below_rth_low")]:
        base = x[ycol].mean()
        for lab, m in [("<0 (ref already beyond)", x[dcol] < 0), ("0-5", (x[dcol] >= 0) & (x[dcol] < 5)), ("5-10", (x[dcol] >= 5) & (x[dcol] < 10)), ("0-10", (x[dcol] >= 0) & (x[dcol] < 10)), ("<10 (as claimed)", x[dcol] < 10)]:
            r = rate_row(m, x[ycol], base, lab, x.half); r.update(sym=sym, side=side)
            # share of the 'break' that is already true at the 18:00 OPEN print (open beyond level)
            if side == "high":
                r["open_already_beyond"] = float((x.loc[m, "asia_open"] > x.loc[m, "lvl_rth_high"]).mean()) if m.sum() else np.nan
            else:
                r["open_already_beyond"] = float((x.loc[m, "asia_open"] < x.loc[m, "lvl_rth_low"]).mean()) if m.sum() else np.nan
            rows.append(r)
B = pd.DataFrame(rows); B.to_csv(f"{OUT}/t10_negative_distance.csv", index=False)
print(B[["sym", "side", "cond", "n", "base", "rate", "ci90_lo", "ci90_hi", "rate_H1", "rate_H2", "open_already_beyond"]].round(3).to_string())
# does the post-RTH 16:00 bar range explain the negatives? (RTH high defined on 09:00-15:59 bars, excludes the 16:00 bar)
x, p = load("NQ"); print("NQ: share of sessions with ref_close > rth_high:", round(float((x.ref_close > x.lvl_rth_high).mean()), 3), "; ref_close < rth_low:", round(float((x.ref_close < x.lvl_rth_low).mean()), 3))

# ---------------------------------------------------------------- C. T7 per-k confound
hdr("C. T7: vol>=1.5 & bar down -> high_done, per k vs the per-k base (pooled base .546 hides the k gradient)")
for sym in ["NQ", "ES"]:
    x, p = load(sym); d = p[(p.n_bars == 9) & (p.k >= 1) & (p.k <= 7)].copy()
    out = []
    for k in range(1, 8):
        dk = d[d.k == k]; base = dk.high_done.mean()
        m = (dk.bar_vol_rel >= 1.5) & (dk.bar_ret_bp < 0); m2 = (dk.bar_vol_rel < 1.5) & (dk.bar_ret_bp < 0)
        m3 = (dk.bar_ret_bp < 0) & (dk.bar_close_loc < .25)
        out.append(dict(k=k, base=base, n_hv_down=int(m.sum()), p_hv_down=dk[m].high_done.mean(), n_lv_down=int(m2.sum()), p_lv_down=dk[m2].high_done.mean(), p_down_cl25=dk[m3].high_done.mean(),
                        lift_hv_vs_lv=dk[m].high_done.mean() - dk[m2].high_done.mean()))
    O = pd.DataFrame(out); print(sym); print(O.round(3).to_string())
    # Mantel-Haenszel style: weighted mean lift
    w = O.n_hv_down; print(f"  {sym} n-weighted mean per-k lift (hv-down minus lv-down): {float((O.lift_hv_vs_lv * w).sum() / w.sum()):.3f}; share of hv-down bars at k>=5: {float(w[O.k >= 5].sum() / w.sum()):.2f}")
    # does the hv-down rule add to pos_in_range? P(high_done | hv down) within pos buckets
    d["posb"] = pd.cut(d.pos_in_range, [-.01, .25, .5, .75, 1.01], labels=["<.25", ".25-.5", ".5-.75", ">=.75"])
    hv = (d.bar_vol_rel >= 1.5) & (d.bar_ret_bp < 0); lv = (d.bar_vol_rel < 1.5) & (d.bar_ret_bp < 0)
    t = pd.DataFrame({"P(hd|hv down)": d[hv].groupby("posb").high_done.mean(), "n_hv": d[hv].groupby("posb").size(), "P(hd|lv down)": d[lv].groupby("posb").high_done.mean(), "n_lv": d[lv].groupby("posb").size()})
    print(f"  {sym} within pos_in_range buckets:"); print(t.round(3).to_string())

# ---------------------------------------------------------------- D. T8 knowable vs ex post
hdr("D. T8: the 'what follows a break' sequel is ex post (conditions on the SESSION high). Knowable version: at bar k, run_hi_above_rth_high & bars_since_hi==0 -> remaining_down / high_done")
for sym in ["NQ", "ES"]:
    x, p = load(sym); d = p[(p.n_bars == 9) & (p.k >= 1) & (p.k <= 6)].copy()
    # knowable: just-probed bar (bsh==0) above RTH high vs just-made-new-high but below RTH high
    for lab, m in [("bsh==0 & run_hi above RTH high", (d.bars_since_hi == 0) & (d.run_hi_above_rth_high == 1)), ("bsh==0 & run_hi below RTH high", (d.bars_since_hi == 0) & (d.run_hi_above_rth_high == 0))]:
        s = d[m]
        # drop from the running high to the eventual session low after this bar: min over remaining bars; use remaining_down_bp from close as proxy, and the ex-post drop measured from run_hi
        print(f"{sym} {lab:36s} n={len(s):4d} P(high_done)={s.high_done.mean():.3f} (H1 {s[s.half=='H1'].high_done.mean():.3f} H2 {s[s.half=='H2'].high_done.mean():.3f}) median remaining_down_bp={s.remaining_down_bp.median():.1f} median remaining_up_bp={s.remaining_up_bp.median():.1f}")
    # mechanical link in the ex-post sequel: drop_after_hi vs hi_k (bars left)
    xx = x[x.n_bars == 9]
    print(f"{sym} ex post: median drop_after_hi_bp by hi_k:", xx.groupby("hi_k").drop_after_hi_bp.median().round(1).to_dict())
    print(f"{sym} ex post: median close_loc by hi_k:", xx.groupby("hi_k").close_loc.median().round(2).to_dict())
    hv = xx.hi_vs_rth_high_bp
    brk = xx[hv > 15]; nb = xx[hv <= -15]
    print(f"{sym} break>15 (n={len(brk)}): median hi_k {brk.hi_k.median()}, drop {brk.drop_after_hi_bp.median():.1f}; no-break<=-15 (n={len(nb)}): hi_k {nb.hi_k.median()}, drop {nb.drop_after_hi_bp.median():.1f}")
    # same comparison hi_k-matched: drop after high for break vs no-break at the same hi_k
    mm = xx.assign(brk=(hv > 15).astype(int)).groupby(["hi_k", "brk"]).drop_after_hi_bp.median().unstack()
    print(f"{sym} drop_after_hi median by hi_k x break(>15bp):"); print(mm.round(1).to_string())

# ---------------------------------------------------------------- E. T11 forward inversion
hdr("E. T11: signature is P(features | low bar). Forward use: P(this bar is the low bar) and P(low_done) given the signature at bar k")
for sym in ["NQ", "ES"]:
    x, p = load(sym); d = p[(p.n_bars == 9) & (p.k <= 7)].copy()
    d["is_lo_bar"] = (d.k == d.lo_k).astype(int); d["is_hi_bar"] = (d.k == d.hi_k).astype(int)
    sig = (d.bar_rng_rel >= 1.3) & (d.bar_vol_rel >= 1.3) & (d.bar_close_loc >= 0.5)
    sig_hi = (d.bar_rng_rel >= 1.3) & (d.bar_vol_rel >= 1.3) & (d.bar_close_loc < 0.5)
    for lab, m, ycol in [("LOW signature (rng>=1.3,vol>=1.3,close upper half)", sig, "is_lo_bar"), ("HIGH mirror (close lower half)", sig_hi, "is_hi_bar")]:
        base = d[ycol].mean(); r = rate_row(m, d[ycol], base, lab, d.half)
        done = "low_done" if ycol == "is_lo_bar" else "high_done"; r2 = rate_row(m, d[done], d[done].mean(), lab, d.half)
        print(f"{sym} {lab:50s} n={r['n']:4d} P({ycol})={r['rate']:.3f} base {base:.3f} (H1 {r['rate_H1']:.3f} H2 {r['rate_H2']:.3f}) | P({done})={r2['rate']:.3f} base {r2['base']:.3f}")
    # per-k precision of the low signature
    pk = d[sig].groupby("k").agg(n=("is_lo_bar", "size"), p_is_lo_bar=("is_lo_bar", "mean"), p_low_done=("low_done", "mean"))
    pk["base_is_lo_bar"] = d.groupby("k").is_lo_bar.mean(); pk["base_low_done"] = d.groupby("k").low_done.mean()
    print(pk.round(3).to_string())
    # the bar-up & close_loc>=.75 rule (T7-like) vs the signature: how much does the signature add?
    up75 = (d.bar_ret_bp >= 0) & (d.bar_close_loc >= .75)
    print(f"{sym} P(low_done | bar up & close_loc>=.75)={d[up75].low_done.mean():.3f} n={int(up75.sum())}; with rng>=1.3&vol>=1.3 added: {d[up75 & (d.bar_rng_rel>=1.3) & (d.bar_vol_rel>=1.3)].low_done.mean():.3f} n={int((up75 & (d.bar_rng_rel>=1.3) & (d.bar_vol_rel>=1.3)).sum())}")

# ---------------------------------------------------------------- F. T12 DST audit
hdr("F. T12: DST audit -- is_dst / tokyo_open_k on the sessions around each US DST transition")
x, p = load("NQ")
for t in ["2024-11-03", "2025-03-09", "2025-11-02", "2026-03-08", "2026-11-01"]:
    t = pd.Timestamp(t); w = x[(x.index >= t - pd.Timedelta(days=4)) & (x.index <= t + pd.Timedelta(days=2))]
    print(t.date(), w[["asia_gdate", "is_dst", "tokyo_open_k", "china_open_k", "n_bars", "hi_hour_et", "hi_hour_jst"]].to_string())
# JST-hour consistency: hour_jst - hour_et should be 13 in summer, 14 in winter
chk = ((p.hour_jst - p.hour_et) % 24)
print("hour_jst - hour_et by is_dst:", p.groupby("is_dst").apply(lambda d: ((d.hour_jst - d.hour_et) % 24).unique().tolist()).to_dict())

# ---------------------------------------------------------------- G. T14 15m alignment
hdr("G. T14: 15m data alignment and the 'open print' test")
for sym in ["NQ", "ES"]:
    m = pd.read_csv(f"{ROOT}/data/{sym}_15m.csv"); m["ts"] = pd.to_datetime(m.Datetime, utc=True).dt.tz_convert("America/New_York"); m = m.set_index("ts").sort_index()
    print(sym, "15m rows", len(m), "range", m.index.min(), "->", m.index.max(), "minute slots:", sorted(m.index.minute.unique().tolist()))
    e = m[(m.index.hour == 18) & (m.index.minute == 0)]
    print(f"   18:00 15m bars: {len(e)}; share with High==Open: {(e.High==e.Open).mean():.3f}; Low==Open: {(e.Low==e.Open).mean():.3f}; (High==Open)|(Low==Open): {((e.High==e.Open)|(e.Low==e.Open)).mean():.3f}")
    # compare 15m-derived hourly extremes with the hourly table hi_k on the overlap
    g = pd.Series(m.index.date, index=m.index); sh = m.index.hour >= 18; g[sh] = (m.index[sh] + pd.Timedelta(days=1)).date; m["gdate"] = g.values
    a = m[m.index.hour.isin(ASIA_HOURS)]
    x, _ = load(sym)
    agree = []; n = 0
    for gd, grp in a.groupby("gdate"):
        if len(grp) < 30: continue
        kh = (grp.index[int(np.argmax(grp.High.values))].hour - 18) % 24
        rr = x[x.asia_gdate == str(pd.Timestamp(gd).date())] if x.asia_gdate.dtype == object else x[pd.to_datetime(x.asia_gdate) == pd.Timestamp(gd)]
        if len(rr): n += 1; agree.append(int(rr.hi_k.iloc[0] == kh))
    print(f"   hi_k from 15m vs hourly table agree on {sum(agree)}/{n} sessions")

# ---------------------------------------------------------------- H. T1/T2/T3 spot re-computation and mechanical component
hdr("H. T1-T3 spot checks (NQ full sessions): numbers, and how much of T1 is the mechanical 'distance to breach' effect")
x, p = load("NQ"); x = x[x.n_bars == 9].copy()
p0 = p[p.k == 0].set_index("date")[["bar_close_loc", "bar_rng_bp", "bar_vol_rel"]]; x = x.join(p0)
for lab, m in [(">=0.8", x.bar_close_loc >= .8), ("<0.2", x.bar_close_loc < .2)]:
    s = x[m]; print(f"T1 close_loc {lab}: n={len(s)} low_in_bar0={s.low_in_first_bar.mean():.3f} high_in_bar0={s.high_in_first_bar.mean():.3f}")
# mechanical: distance from bar-0 close to bar-0 low (bp) for close_loc>=.8 vs the typical later downside
x["dist_close_to_b0low_bp"] = x.bar_close_loc * x.bar_rng_bp
print("median distance close->bar0 low (bp): close_loc>=.8:", round(x[x.bar_close_loc >= .8].dist_close_to_b0low_bp.median(), 1), "| 0.2-0.5:", round(x[(x.bar_close_loc >= .2) & (x.bar_close_loc < .5)].dist_close_to_b0low_bp.median(), 1))
# within close_loc>=.8, does the ABSOLUTE distance (bp) matter? split by bar_rng_bp median
s = x[x.bar_close_loc >= .8]; med = s.bar_rng_bp.median()
print(f"close_loc>=.8 & bar0 range < median({med:.0f}bp): low_in_bar0={s[s.bar_rng_bp < med].low_in_first_bar.mean():.3f} n={int((s.bar_rng_bp < med).sum())}; >= median: {s[s.bar_rng_bp >= med].low_in_first_bar.mean():.3f}")
for lab, m in [("ret>+20", x.first_bar_ret_bp > 20), ("ret<-20", x.first_bar_ret_bp < -20)]:
    s = x[m]; print(f"T2 {lab}: n={len(s)} low_in_bar0={s.low_in_first_bar.mean():.3f} high_in_bar0={s.high_in_first_bar.mean():.3f}")
x["share"] = x.first_bar_rng_bp / (x.asia_rng_med20 * 1e4); e0 = ((x.hi_k == 0) | (x.lo_k == 0)).astype(int)
for lab, m in [(">=0.5", x.share >= .5), ("0.15-0.3", (x.share >= .15) & (x.share < .3))]:
    print(f"T3 share {lab}: n={int(m.sum())} either_in_bar0={e0[m].mean():.3f}")

# ---------------------------------------------------------------- I. T4 count of 18:00 comparisons & T5/T6 spot
hdr("I. T4 comparison count; T5/T6 spot values")
for sym in ["NQ", "ES"]:
    R = pd.read_csv(f"research/extremes/scripts/lens_timing/q1_{sym}_ushape_scan.csv")
    R18 = R[R.stage == "18:00"]; R18n = R18[R18.n >= 30]
    print(sym, "18:00-stage rows:", len(R18), "with n>=30:", len(R18n), "p<.05:", int((R18n.p_binom < .05).sum()), "p<.01:", int((R18n.p_binom < .01).sum()), "max|lift|:", round(R18n.lift.abs().max(), 3))
    print("   any ex-post feature names in the 18:00 stage list?", sorted(set(R18.feature) & {"hi_k", "lo_k", "hi_bp", "lo_bp", "close_loc", "drop_after_hi_bp", "gap_open_bp", "first_bar_ret_bp", "first_bar_rng_bp"}))
x, p = load("NQ"); d = p[(p.n_bars == 9) & (p.k >= 2) & (p.k <= 6)]
m = (d.bars_since_hi >= 2) & (d.pos_in_range < .35) & (d.run_rng_vs_med20 >= 1.0)
print(f"T6 NQ rule: n={int(m.sum())} P(high_done)={d[m].high_done.mean():.3f}; median remaining_up_bp among the failures: {d[m & (d.high_done==0)].remaining_up_bp.median():.1f} bp (n={int((m & (d.high_done==0)).sum())})")
print("T6: median distance (bp) from close to running high under the rule:", round(float(((d[m].run_hi_bp - d[m].cum_ret_bp)).median()), 1), "vs all k=2..6 rows:", round(float((d.run_hi_bp - d.cum_ret_bp).median()), 1))
