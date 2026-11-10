"""Knowability checks: short sessions, holiday flags, calendar DST, fed/earnings entries, E7 mechanical break."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "research/extremes/scripts/lens_events")
from common import load_extremes, load_panel, load_calendar, binom_p, boot_ci
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500); pd.set_option("display.max_columns", 60)

ev = load_calendar()
x = load_extremes("NQ"); xe = load_extremes("ES")

print("=== 1. short sessions (n_bars<9) NQ: are they schedule-predictable? ===")
sh = x[x.n_bars < 9]
print(sh[["asia_gdate", "n_bars", "is_dst", "hi_k", "lo_k", "rng_bp", "pre_holiday", "holiday_tomorrow", "sunday_open", "events_tonight_tomorrow"]].to_string())
print("\nES short sessions:")
she = xe[xe.n_bars < 9]
print(she[["asia_gdate", "n_bars", "is_dst", "hi_k", "lo_k", "rng_bp", "pre_holiday", "holiday_tomorrow", "sunday_open"]].to_string())

# which hours are present in the short sessions? read the raw hourly file
sys.path.insert(0, "."); from sessions import load_hourly
h = load_hourly("./data/NQ_1h.csv")
print("\nhours present in each short NQ session:")
for d, r in sh.iterrows():
    gd = pd.Timestamp(r["asia_gdate"])
    start = (gd - pd.Timedelta(days=1)).replace(hour=18)
    seg = h[(h.index >= pd.Timestamp(start, tz="America/New_York")) & (h.index < pd.Timestamp(gd.replace(hour=3), tz="America/New_York"))]
    print(d.date(), "->", gd.date(), "hours:", list(seg.index.hour))

print("\n=== 2. holiday_tomorrow / pre_holiday sessions ===")
print(x[(x.holiday_tomorrow == 1) | (x.pre_holiday == 1)][["asia_gdate", "n_bars", "rng_bp", "pre_holiday", "holiday_tomorrow", "events_tonight_tomorrow"]].to_string())

print("\n=== 3. 'fed' category rows in research calendar ===")
print(ev[ev.category == "fed"][["date", "event", "time_et"]].to_string())
print("\n=== earnings rows ===")
print(ev[ev.category == "earnings"][["date", "event", "time_et", "notes"]].head(90).to_string())

print("\n=== 4. calendar time_et DST consistency for Asia-hours events ===")
a = ev[ev.time_et.notna()].copy()
a["hour"] = a.time_et.str[:2].astype(int); a["minute"] = a.time_et.str[3:5].astype(int)
a = a[(a.hour >= 18) | (a.hour < 3)]
# expected ET hour from the local release time: CN 09:30/09:45/10:00 CST -> 20:30/20:45/21:00 EST, +1h EDT ; JP 08:30 JST -> 18:30 EST / 19:30 EDT
def is_dst_et(d):
    ts = pd.Timestamp(d).tz_localize("America/New_York")
    return ts.dst() != pd.Timedelta(0)
a["dst"] = a.date.apply(is_dst_et)
for evn, grp in a.groupby("event"):
    print(evn, "n", len(grp), "times by dst:", grp.groupby("dst").time_et.agg(lambda s: sorted(set(s))).to_dict())

print("\n=== 5. E7 mechanical component: is the 17:00 close / 18:00 open already beyond the RTH extreme on megacap nights? ===")
for sym, xx in (("NQ", x), ("ES", xe)):
    me = xx[xx.megacap_earnings_tonight == 1].copy()
    me["ref_above_rth_high"] = (me.lvl_post_close > me.lvl_rth_high).astype(int)
    me["ref_below_rth_low"] = (me.lvl_post_close < me.lvl_rth_low).astype(int)
    me["open_above_rth_high"] = (me.asia_open > me.lvl_rth_high).astype(int)
    me["open_below_rth_low"] = (me.asia_open < me.lvl_rth_low).astype(int)
    up = me[me.post_ret > 0]; dn = me[me.post_ret < 0]
    print(f"{sym} megacap post_ret>0 n={len(up)}: P(high>RTH high)={up.high_above_rth_high.mean():.3f}; 17:00 close already above RTH high: {up.ref_above_rth_high.mean():.3f}; 18:00 open above: {up.open_above_rth_high.mean():.3f}")
    print(f"   among those with ref<=RTH high (n={(up.ref_above_rth_high==0).sum()}): P(high>RTH high)={up[up.ref_above_rth_high==0].high_above_rth_high.mean():.3f}")
    print(f"   among those with 18:00 open<=RTH high (n={(up.open_above_rth_high==0).sum()}): P(high>RTH high)={up[up.open_above_rth_high==0].high_above_rth_high.mean():.3f}")
    print(f"{sym} megacap post_ret<0 n={len(dn)}: P(low<RTH low)={dn.low_below_rth_low.mean():.3f}; 17:00 close already below RTH low: {dn.ref_below_rth_low.mean():.3f}; 18:00 open below: {dn.open_below_rth_low.mean():.3f}")
    print(f"   among those with ref>=RTH low (n={(dn.ref_below_rth_low==0).sum()}): P(low<RTH low)={dn[dn.ref_below_rth_low==0].low_below_rth_low.mean():.3f}")
    print(f"   among those with 18:00 open>=RTH low (n={(dn.open_below_rth_low==0).sum()}): P(low<RTH low)={dn[dn.open_below_rth_low==0].low_below_rth_low.mean():.3f}")
    # same for base
    nme = xx[xx.megacap_earnings_tonight == 0].copy()
    nme["ref_above_rth_high"] = (nme.lvl_post_close > nme.lvl_rth_high).astype(int)
    nme["ref_below_rth_low"] = (nme.lvl_post_close < nme.lvl_rth_low).astype(int)
    bu = nme[nme.post_ret > 0]; bd = nme[nme.post_ret < 0]
    print(f"   base post_ret>0 n={len(bu)}: ref above RTH high {bu.ref_above_rth_high.mean():.3f}; P(high>RTH high)={bu.high_above_rth_high.mean():.3f}; among ref<=high: {bu[bu.ref_above_rth_high==0].high_above_rth_high.mean():.3f}")
    print(f"   base post_ret<0 n={len(bd)}: ref below RTH low {bd.ref_below_rth_low.mean():.3f}; P(low<RTH low)={bd.low_below_rth_low.mean():.3f}; among ref>=low: {bd[bd.ref_below_rth_low==0].low_below_rth_low.mean():.3f}")
    # dir-side break where ref is NOT already beyond the level
    me["dir_break"] = np.where(me.post_ret > 0, me.high_above_rth_high, me.low_below_rth_low)
    me["ref_beyond"] = np.where(me.post_ret > 0, me.ref_above_rth_high, me.ref_below_rth_low)
    me["open_beyond"] = np.where(me.post_ret > 0, me.open_above_rth_high, me.open_below_rth_low)
    nme["dir_break"] = np.where(nme.post_ret > 0, nme.high_above_rth_high, nme.low_below_rth_low)
    nme["ref_beyond"] = np.where(nme.post_ret > 0, nme.ref_above_rth_high, nme.ref_below_rth_low)
    k = int(me[me.ref_beyond == 0].dir_break.sum()); n = int((me.ref_beyond == 0).sum())
    p0 = nme[nme.ref_beyond == 0].dir_break.mean()
    print(f"   {sym} dir_break overall {me.dir_break.mean():.3f} (n={len(me)}); ref already beyond level: {me.ref_beyond.mean():.3f}; open already beyond: {me.open_beyond.mean():.3f}")
    print(f"   {sym} dir_break | ref NOT beyond: {k}/{n}={k/n:.3f} vs base {p0:.3f} (n_base={(nme.ref_beyond==0).sum()}), exact p={binom_p(k, n, p0):.4f}, CI {boot_ci(me[me.ref_beyond==0].dir_break.values)}")
    k2 = int(me[me.open_beyond == 0].dir_break.sum()); n2 = int((me.open_beyond == 0).sum())
    print(f"   {sym} dir_break | 18:00 open NOT beyond: {k2}/{n2}={k2/n2 if n2 else np.nan:.3f}")
    # distance of ref to the level on the post_ret side (bp)
    me["dist_dir_bp"] = np.where(me.post_ret > 0, (me.lvl_rth_high / me.lvl_post_close - 1) * 1e4, (1 - me.lvl_rth_low / me.lvl_post_close) * 1e4)
    nme["dist_dir_bp"] = np.where(nme.post_ret > 0, (nme.lvl_rth_high / nme.lvl_post_close - 1) * 1e4, (1 - nme.lvl_rth_low / nme.lvl_post_close) * 1e4)
    print(f"   {sym} median distance 17:00 close -> level on post_ret side: megacap {me.dist_dir_bp.median():.1f} bp vs base {nme.dist_dir_bp.median():.1f} bp")
