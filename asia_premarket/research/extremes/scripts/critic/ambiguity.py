"""Hourly-bar ambiguity: same-bar extremes, hi_first coding, within-bar position of the extreme from the
15-minute window, and the bars_since==0 hold rate by k."""
import sys; sys.path.insert(0, "research/extremes/scripts/critic")
from common import *

for sym in ["NQ", "ES"]:
    x = load_x(sym)
    sb = x[x.same_bar_extremes == 1]
    print(f"\n===== {sym} =====")
    print(f" same-bar extremes {sb.shape[0]}/{len(x)} = {len(sb)/len(x):.3f}; coded hi_first=0 for all of them (hi_k<lo_k is False); bars_between==1: {(x.bars_between==1).mean():.3f}")
    print(f" hi_first excluding same-bar: {x[x.same_bar_extremes==0].hi_first.mean():.3f} vs reported {x.hi_first.mean():.3f}")
    # which bars are the same-bar cases
    print(" same-bar cases by k:", sb.hi_k.value_counts().sort_index().to_dict(), "| median rng of those nights", sb.rng_bp.median().round(0), "vs", x.rng_bp.median().round(0))
    p = load_panel(sym); p = p[p.k <= 7]
    g = p[p.bars_since_hi == 0].groupby("k").high_done.agg(["size", "mean"])
    print(" P(high_done | bars_since_hi==0, k):", g["mean"].round(2).tolist(), "n", g["size"].tolist())
    g = p[p.bars_since_lo == 0].groupby("k").low_done.agg(["size", "mean"])
    print(" P(low_done  | bars_since_lo==0, k):", g["mean"].round(2).tolist(), "n", g["size"].tolist())
    # within-bar: a new running high set in bar k whose bar closes in its lower half
    nh = p[p.bars_since_hi == 0]
    lo_close = nh[nh.bar_close_loc < 0.5]; hi_close = nh[nh.bar_close_loc >= 0.5]
    print(f" new running high, bar closes lower half: P(high_done) {lo_close.high_done.mean():.3f} (n={len(lo_close)}) vs upper half {hi_close.high_done.mean():.3f} (n={len(hi_close)})")

# 15-minute window: where inside the hourly extreme bar does the extreme print?
for sym in ["NQ", "ES"]:
    m = pd.read_csv(f"./data/{sym}_15m.csv", index_col=0)
    m.index = pd.to_datetime(m.index, utc=True).tz_convert("America/New_York")
    m = m[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    m = m[~m.index.duplicated(keep="last")].sort_index()
    hr = m.index.hour
    asia = m[(hr >= 18) | (hr <= 2)].copy()
    gd = pd.Series(asia.index.date, index=asia.index)
    sh = asia.index.hour >= 18
    gd[sh] = (asia.index[sh] + pd.Timedelta(days=1)).date
    asia["gdate"] = gd.values
    rows = []
    for g_, grp in asia.groupby("gdate"):
        if len(grp) < 34:
            continue
        hi_i = grp.High.values.argmax(); lo_i = grp.Low.values.argmin()
        thi = grp.index[hi_i]; tlo = grp.index[lo_i]
        # hourly bar index k of each extreme and the 15m slot inside it
        def kk(t):
            return (t.hour - 18) % 24 if t.hour >= 18 else t.hour + 6
        rows.append(dict(gdate=g_, hi_k=kk(thi), lo_k=kk(tlo), hi_slot=thi.minute // 15, lo_slot=tlo.minute // 15,
                         hi_first_15m=int(thi < tlo), same_hour=int(kk(thi) == kk(tlo)), same_slot=int(thi == tlo)))
    r = pd.DataFrame(rows)
    print(f"\n {sym} 15m window: n={len(r)} sessions; same hourly bar {r.same_hour.sum()}; of those, hi first at 15m: {r[r.same_hour==1].hi_first_15m.tolist()}")
    print(f"  slot of the HIGH inside its hourly bar (0=first 15m): {r.hi_slot.value_counts().sort_index().to_dict()}; LOW: {r.lo_slot.value_counts().sort_index().to_dict()}")
    mid = r[(r.hi_k > 0) & (r.hi_k < 8)]
    print(f"  interior-bar highs: slot {mid.hi_slot.value_counts().sort_index().to_dict()}; interior lows: {r[(r.lo_k>0)&(r.lo_k<8)].lo_slot.value_counts().sort_index().to_dict()}")
    print(f"  extreme in the LAST 15m of its hourly bar (slot 3): high {(r.hi_slot==3).mean():.2f} low {(r.lo_slot==3).mean():.2f} (uniform null 0.25)")
