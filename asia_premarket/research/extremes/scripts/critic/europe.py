"""Does the Asia extreme survive the Europe open (03:00-08:59 ET)?  Missing analysis: the 02:00 bar
extreme may be the start of a Europe trend rather than a session extreme."""
import sys; sys.path.insert(0, "research/extremes/scripts/critic")
from common import *

for sym in ["NQ", "ES"]:
    x = load_x(sym)
    h = load_1h(sym)
    h["hour"] = h.index.hour
    rows = []
    for d, r in x.iterrows():
        gd = pd.Timestamp(r["asia_gdate"])
        day = h[(h.index.date == gd.date())]
        eur = day[day.hour.between(3, 8)]
        e1 = day[day.hour == 3]
        rth = day[day.hour.between(9, 15)]
        if len(eur) < 5:
            continue
        rows.append(dict(date=d, hi_k=r.hi_k, lo_k=r.lo_k, ref=r.ref_close, asia_high=r.asia_high, asia_low=r.asia_low,
                         eur_high=eur.High.max(), eur_low=eur.Low.min(), e1_high=e1.High.max() if len(e1) else np.nan,
                         e1_low=e1.Low.min() if len(e1) else np.nan,
                         rth_high=rth.High.max() if len(rth) >= 5 else np.nan, rth_low=rth.Low.min() if len(rth) >= 5 else np.nan,
                         eur_close=eur.Close.iloc[-1], asia_close=r.asia_close, rng_bp=r.rng_bp, sunday=r.sunday_open,
                         high_in_last=r.high_in_last_bar, low_in_last=r.low_in_last_bar))
    e = pd.DataFrame(rows).set_index("date")
    e["eur_breaks_high"] = (e.eur_high > e.asia_high).astype(int)
    e["eur_breaks_low"] = (e.eur_low < e.asia_low).astype(int)
    e["e1_breaks_high"] = (e.e1_high > e.asia_high).astype(int)
    e["e1_breaks_low"] = (e.e1_low < e.asia_low).astype(int)
    e["eur_break_hi_bp"] = (e.eur_high / e.asia_high - 1) * 1e4
    e["eur_break_lo_bp"] = (e.eur_low / e.asia_low - 1) * 1e4
    e["day_high_is_asia"] = ((e.asia_high >= e.eur_high) & (e.asia_high >= e.rth_high.fillna(-np.inf))).astype(int)
    e["day_low_is_asia"] = ((e.asia_low <= e.eur_low) & (e.asia_low <= e.rth_low.fillna(np.inf))).astype(int)
    print(f"\n===== {sym}: n={len(e)} sessions with a following Europe session =====")
    print(f" Europe (03:00-08:59) trades above the Asia high: {fmt(ci_prop(e.eur_breaks_high))}; below the Asia low: {fmt(ci_prop(e.eur_breaks_low))}; both {((e.eur_breaks_high==1)&(e.eur_breaks_low==1)).mean():.3f}; neither {((e.eur_breaks_high==0)&(e.eur_breaks_low==0)).mean():.3f}")
    print(f" first Europe bar (03:00) alone breaks the Asia high {e.e1_breaks_high.mean():.3f}, low {e.e1_breaks_low.mean():.3f}")
    print(f" Asia high is the whole-day (18:00-16:00) high {e.day_high_is_asia.mean():.3f}; Asia low is the day low {e.day_low_is_asia.mean():.3f}")
    for nm, ee in zip(["H1", "H2"], halves(e)):
        print(f"  {nm}: eur breaks high {ee.eur_breaks_high.mean():.3f} low {ee.eur_breaks_low.mean():.3f} (n={len(ee)})")
    print(" P(Europe breaks the Asia HIGH | hi_k):")
    g = e.groupby("hi_k").eur_breaks_high.agg(["size", "mean"]); print("   n   ", g["size"].tolist()); print("   rate", g["mean"].round(2).tolist())
    g1 = e.groupby("hi_k").e1_breaks_high.mean(); print("   03:00 bar alone", g1.round(2).tolist())
    print(" P(Europe breaks the Asia LOW | lo_k):")
    g = e.groupby("lo_k").eur_breaks_low.agg(["size", "mean"]); print("   n   ", g["size"].tolist()); print("   rate", g["mean"].round(2).tolist())
    g1 = e.groupby("lo_k").e1_breaks_low.mean(); print("   03:00 bar alone", g1.round(2).tolist())
    last_h = e[e.hi_k == 8]; oth_h = e[e.hi_k < 8]
    last_l = e[e.lo_k == 8]; oth_l = e[e.lo_k < 8]
    print(f" high in bar 8: Europe breaks it {fmt(ci_prop(last_h.eur_breaks_high))} (n={len(last_h)}) vs hi_k<8 {fmt(ci_prop(oth_h.eur_breaks_high))}; H1/H2 {last_h[last_h.index<H2].eur_breaks_high.mean():.2f}/{last_h[last_h.index>=H2].eur_breaks_high.mean():.2f}; p={binom_p(last_h.eur_breaks_high.sum(), len(last_h), oth_h.eur_breaks_high.mean()):.2e}")
    print(f" low  in bar 8: Europe breaks it {fmt(ci_prop(last_l.eur_breaks_low))} (n={len(last_l)}) vs lo_k<8 {fmt(ci_prop(oth_l.eur_breaks_low))}; H1/H2 {last_l[last_l.index<H2].eur_breaks_low.mean():.2f}/{last_l[last_l.index>=H2].eur_breaks_low.mean():.2f}; p={binom_p(last_l.eur_breaks_low.sum(), len(last_l), oth_l.eur_breaks_low.mean()):.2e}")
    print(f"   within the 03:00 bar: high-in-bar-8 broken {last_h.e1_breaks_high.mean():.2f} vs {oth_h.e1_breaks_high.mean():.2f}; low-in-bar-8 broken {last_l.e1_breaks_low.mean():.2f} vs {oth_l.e1_breaks_low.mean():.2f}")
    # bar 7 too
    b7h = e[e.hi_k == 7]; b7l = e[e.lo_k == 7]
    print(f" high in bar 7: broken by Europe {b7h.eur_breaks_high.mean():.2f} (n={len(b7h)}); low in bar 7: {b7l.eur_breaks_low.mean():.2f} (n={len(b7l)})")
    # size of the break
    bh = e[e.eur_breaks_high == 1]; bl = e[e.eur_breaks_low == 1]
    print(f" when broken, median excess above the Asia high {bh.eur_break_hi_bp.median():.1f} bp (p75 {bh.eur_break_hi_bp.quantile(.75):.1f}); below the Asia low {bl.eur_break_lo_bp.median():.1f} bp (p25 {bl.eur_break_lo_bp.quantile(.25):.1f})")
    # the 18:00-08:59 'overnight' extreme: which session holds it?
    e["on_high_in_asia"] = (e.asia_high >= e.eur_high).astype(int); e["on_low_in_asia"] = (e.asia_low <= e.eur_low).astype(int)
    print(f" overnight (18:00-08:59) high set in Asia {e.on_high_in_asia.mean():.3f}, low set in Asia {e.on_low_in_asia.mean():.3f}")
    e.to_csv(f"research/extremes/scripts/critic/europe_{sym}.csv")
