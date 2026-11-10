"""E9: independent event-bar mapping and clustering test; also DST-consistency audit of the calendar's time_et."""
import numpy as np
import pandas as pd
from scipy import stats

ROOT = "."
SPLIT = pd.Timestamp("2025-09-01")
EXCLUDE = {"NQ": [pd.Timestamp("2025-09-16")], "ES": [pd.Timestamp("2025-12-16"), pd.Timestamp("2025-12-17")]}
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)

ev = pd.read_csv(f"{ROOT}/research/event_calendar.csv"); ev["date"] = pd.to_datetime(ev["date"])
asia = ev[ev.time_et.notna()].copy()
asia["hour"] = asia.time_et.str[:2].astype(int); asia["minute"] = asia.time_et.str[3:5].astype(int)
asia = asia[(asia.hour >= 18) | (asia.hour < 3)].copy()
asia["ke"] = np.where(asia.hour >= 18, asia.hour - 18, asia.hour + 6)
print("Asia-window timed events:", len(asia)); print(asia.groupby(["category", "event"]).size())

FAM = {"CN_0930CST": ["CN_CPI", "CN_PMI_NBS"], "CN_0945CST": ["CN_PMI_CAIXIN", "CN_PMI_CAIXIN_SVC"], "CN_1000CST": ["CN_ACTIVITY"],
       "CN_TRADE": ["CN_TRADE"], "JP_0830JST": ["JP_CPI"], "JP_TANKAN": ["TANKAN"], "RBA": ["RBA"]}
CN_ANY = ["CN_CPI", "CN_PMI_NBS", "CN_PMI_CAIXIN", "CN_PMI_CAIXIN_SVC", "CN_ACTIVITY", "CN_TRADE"]


def wilson(k, n, z=1.645):
    p = k / n; den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


for sym in ("NQ", "ES"):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    x = x[~x.index.isin(EXCLUDE[sym])].copy(); x["asia_gdate"] = pd.to_datetime(x.asia_gdate)
    x["half"] = np.where(x.index < SPLIT, "H1", "H2"); x["last_k"] = x.n_bars - 1
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    p = p[~p.date.isin(EXCLUDE[sym])].copy(); p["half"] = np.where(p.date < SPLIT, "H1", "H2")
    by_g = x.reset_index().set_index("asia_gdate")
    print(f"\n================= {sym} =================")

    # --- DST consistency audit: for 09:30 CST / 09:45 CST events, ke should equal china_open_k of the session ---
    e = asia[asia.event.isin(FAM["CN_0930CST"] + FAM["CN_0945CST"])].copy()
    e = e[e.date.isin(by_g.index)]
    s = by_g.loc[e.date.values]; e["china_open_k"] = s.china_open_k.values; e["is_dst"] = s.is_dst.values
    mism = e[e.ke != e.china_open_k]
    print(f"CN 09:30/09:45 CST events mapped to sessions: {len(e)}; ke != china_open_k: {len(mism)}")
    if len(mism): print(mism[["date", "event", "time_et", "ke", "china_open_k", "is_dst"]].to_string())
    e = asia[asia.event.isin(["JP_CPI"])].copy(); e = e[e.date.isin(by_g.index)]
    s = by_g.loc[e.date.values]; e["tokyo_open_k"] = s.tokyo_open_k.values
    print(f"JP_CPI events: {len(e)}; ke != tokyo_open_k-1: {int((e.ke != e.tokyo_open_k - 1).sum())}")
    e = asia[asia.event == "CN_ACTIVITY"].copy(); e = e[e.date.isin(by_g.index)]
    s = by_g.loc[e.date.values]; e["china_open_k"] = s.china_open_k.values
    print(f"CN_ACTIVITY: {len(e)}; ke != china_open_k+1: {int((e.ke != e.china_open_k + 1).sum())}")

    # --- pooled clustering test, my own loop ---
    rows = []
    pooled = {"event_bar": [0, 0.0, 0], "event_or_next": [0, 0.0, 0]}
    pooled_h = {"H1": {"event_bar": [0, 0.0, 0]}, "H2": {"event_bar": [0, 0.0, 0]}}
    for fam, names in FAM.items():
        e = asia[asia.event.isin(names)].copy(); e = e[e.date.isin(by_g.index)].sort_values("ke").drop_duplicates("date")
        sess = by_g.loc[e.date.values].copy(); sess["ke"] = e.ke.values; sess = sess[sess.ke <= sess.last_k]
        ctrl_all = x[~x.index.isin(sess.date)]
        for which in ("hi_k", "lo_k"):
            for win_name, win in (("event_bar", 0), ("event_or_next", 1), ("prev_bar", -1)):
                hits = 0; exp = 0.0; n = 0
                for _, r in sess.iterrows():
                    ke = int(r.ke); ks = {ke} if win == 0 else ({ke, ke + 1} if win == 1 else {ke - 1})
                    ks = {k for k in ks if 0 <= k <= r.last_k}
                    if not ks: continue
                    hit = int(r[which] in ks)
                    ctrl = ctrl_all[(ctrl_all.is_dst == r.is_dst) & (ctrl_all.n_bars == r.n_bars)]
                    p0 = ctrl[which].isin(ks).mean(); hits += hit; exp += p0; n += 1
                    if win_name in pooled:
                        pooled[win_name][0] += hit; pooled[win_name][1] += p0; pooled[win_name][2] += 1
                        if win_name == "event_bar":
                            hh = pooled_h[r.half]["event_bar"]; hh[0] += hit; hh[1] += p0; hh[2] += 1
                if n == 0: continue
                rows.append(dict(fam=fam, which=which, win=win_name, n=n, hits=hits, rate=hits / n, base=exp / n,
                                 p=stats.binomtest(hits, n, exp / n).pvalue))
    out = pd.DataFrame(rows)
    print(out.round(3).to_string())
    for w, (h, ex, n) in pooled.items():
        lo, hi = wilson(h, n)
        print(f"POOLED (hi+lo) {w}: hits={h} n={n} rate={h/n:.3f} base={ex/n:.3f} CI90=[{lo:.3f},{hi:.3f}] p={stats.binomtest(h, n, ex/n).pvalue:.3f}")
    for hh in ("H1", "H2"):
        h, ex, n = pooled_h[hh]["event_bar"]; print(f"  {hh} pooled event_bar: {h}/{n}={h/n:.3f} vs base {ex/n:.3f}")
    # Note: the lens's n=380 is "event-sessions pooled over 7 families", hits are summed over hi and lo; here n counts
    # (session, extreme) pairs, so n is doubled; rate is equivalent.

    # --- CN_0930 next-bar range (rel to prior-20 median of that ET hour), control = same k and is_dst, non-event ---
    for fam, names in (("CN_0930CST", FAM["CN_0930CST"]), ("CN_ANY", CN_ANY), ("JP_0830JST", ["JP_CPI"]), ("RBA", ["RBA"])):
        e = asia[asia.event.isin(names)].copy(); e = e[e.date.isin(by_g.index)].sort_values("ke").drop_duplicates("date")
        sess = by_g.loc[e.date.values].copy(); sess["ke"] = e.ke.values
        pp = p.merge(sess[["date", "ke"]], on="date")
        for lab, off in (("event_bar", 0), ("next_bar", 1)):
            d = pp[pp.k == pp.ke + off]
            cm = p[~p.date.isin(sess.date)].merge(d[["k", "is_dst"]].drop_duplicates(), on=["k", "is_dst"])
            a = d.bar_rng_rel.dropna(); b = cm.bar_rng_rel.dropna()
            av = d.bar_vol_rel.dropna(); bv = cm.bar_vol_rel.dropna()
            rng = np.random.default_rng(0); idx = rng.integers(0, len(a), size=(4000, len(a))); ci = np.quantile(np.median(a.values[idx], axis=1), [0.05, 0.95])
            print(f"  {fam:10s} {lab:9s} n={len(a):3d} rng_rel med={a.median():.3f} base={b.median():.3f} CI90=[{ci[0]:.3f},{ci[1]:.3f}] MW_p={stats.mannwhitneyu(a, b).pvalue:.3f} | vol_rel {av.median():.3f} vs {bv.median():.3f} p={stats.mannwhitneyu(av, bv).pvalue:.3f} | "
                  f"H1 {d[d.half=='H1'].bar_rng_rel.median():.2f} vs {cm[cm.half=='H1'].bar_rng_rel.median():.2f}; H2 {d[d.half=='H2'].bar_rng_rel.median():.2f} vs {cm[cm.half=='H2'].bar_rng_rel.median():.2f}")

    # --- BoJ ---
    boj = ev[ev.category == "boj"]; boj = boj[boj.date.isin(by_g.index)]
    sess = by_g.loc[boj.date.values].copy(); ctrl_all = x[~x.index.isin(sess.date)]
    print(f"  BoJ sessions n={len(sess)}; is_dst mix {sess.is_dst.value_counts().to_dict()}")
    for which in ("hi_k", "lo_k"):
        for win_name, ksf in (("decision_4_5", lambda r: {4, 5}), ("presser_last2", lambda r: {r.last_k - 1, r.last_k})):
            hits = 0; exp = 0.0; n = 0
            for _, r in sess.iterrows():
                ks = ksf(r); hit = int(r[which] in ks)
                ctrl = ctrl_all[(ctrl_all.is_dst == r.is_dst) & (ctrl_all.n_bars == r.n_bars)]
                hits += hit; exp += ctrl[which].isin(ks).mean(); n += 1
            print(f"  BoJ {which} {win_name}: {hits}/{n}={hits/n:.3f} vs base {exp/n:.3f} p={stats.binomtest(hits, n, exp/n).pvalue:.3f}")
    pp = p[p.date.isin(sess.date)]
    for k in (4, 5):
        d = pp[pp.k == k]; cm = p[(~p.date.isin(sess.date)) & (p.k == k)]
        print(f"  BoJ bar k{k} rng_rel {d.bar_rng_rel.median():.2f} vs {cm.bar_rng_rel.median():.2f} p={stats.mannwhitneyu(d.bar_rng_rel.dropna(), cm.bar_rng_rel.dropna()).pvalue:.3f} (n={len(d)})")
