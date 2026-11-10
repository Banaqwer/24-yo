"""Q2: event-time clustering.  Map each Asia-window scheduled event to (session RTH date D, bar index ke)
and test whether hi_k / lo_k fall in {ke} or {ke, ke+1} more often than in sessions without that event
(base = sessions with the same DST regime -> same bar index for the event hour, and no event in that bar).
Also: the event bar's range/volume relative to the prior-20 median (hourly panel)."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "research/extremes/scripts/lens_events")
from common import *

ev = load_calendar()
asia = ev[ev["time_et"].notna()].copy()
asia["hour"] = asia["time_et"].str[:2].astype(int)
asia["minute"] = asia["time_et"].str[3:5].astype(int)
asia = asia[(asia["hour"] >= 18) | (asia["hour"] < 3)].copy()
asia["ke"] = np.where(asia["hour"] >= 18, asia["hour"] - 18, asia["hour"] + 6)
# local date L = asia_gdate of the session (ET morning date) for both evening (L-1 ET) and after-midnight events
asia["gdate"] = asia["date"]
# BoJ decision rows have no time; decision ~22:00-23:30 ET -> bars 4..5 ; presser 01:30/02:30 ET -> bar 7 (EST) / 8 (EDT)
boj = ev[ev["category"] == "boj"].copy()
boj["gdate"] = boj["date"]

# event families
FAM = {
    "CN_0930CST": ["CN_CPI", "CN_PMI_NBS"],             # 09:30 CST = bar china_open_k (20:30 EST / 21:30 EDT)
    "CN_0945CST": ["CN_PMI_CAIXIN", "CN_PMI_CAIXIN_SVC"],  # 09:45 CST, same bar
    "CN_1000CST": ["CN_ACTIVITY"],                       # 10:00 CST = bar china_open_k + 1
    "CN_TRADE": ["CN_TRADE"],                            # ~10-11 CST, irregular
    "JP_0830JST": ["JP_CPI"],                            # 08:30 JST = bar tokyo_open_k - 1
    "JP_TANKAN": ["TANKAN"],                             # 08:50 JST
    "RBA": ["RBA"],
    "CN_ANY": ["CN_CPI", "CN_PMI_NBS", "CN_PMI_CAIXIN", "CN_PMI_CAIXIN_SVC", "CN_ACTIVITY", "CN_TRADE"],
}

rows = []; n_comp = 0
panel_rows = []
for sym in ("NQ", "ES"):
    x = load_extremes(sym)
    p = load_panel(sym)
    by_g = x.reset_index().set_index("asia_gdate")
    for fam, names in FAM.items():
        e = asia[asia["event"].isin(names)].copy()
        e = e[e["gdate"].isin(by_g.index)]
        # one row per session (if several events same family same night keep the earliest bar)
        e = e.sort_values("ke").drop_duplicates("gdate")
        sess = by_g.loc[e["gdate"].values].copy()
        sess["ke"] = e["ke"].values
        sess = sess[sess["ke"] <= sess["last_k"]]
        # sanity: DST consistency of the event clock vs session is_dst (bars shift with DST)
        # control: sessions without this family, matched on is_dst; compare P(hi_k == ke) with base P(hi_k == ke | is_dst)
        for which in ("hi_k", "lo_k"):
            for win_name, win in (("event_bar", 0), ("event_or_next", 1), ("prev_bar", -1)):
                hits = 0; exp = 0.0; n = 0; h_hits = {"H1": [0, 0.0, 0], "H2": [0, 0.0, 0]}
                ctrl_all = x[~x.index.isin(sess["date"])]
                for _, r in sess.iterrows():
                    ke = int(r["ke"])
                    if win == 0: ks = {ke}
                    elif win == 1: ks = {ke, ke + 1}
                    else: ks = {ke - 1}
                    ks = {k for k in ks if 0 <= k <= r["last_k"]}
                    if not ks:
                        continue
                    hit = int(r[which] in ks)
                    ctrl = ctrl_all[(ctrl_all["is_dst"] == r["is_dst"]) & (ctrl_all["n_bars"] == r["n_bars"])]
                    p0 = ctrl[which].isin(ks).mean()
                    hits += hit; exp += p0; n += 1
                    hh = h_hits[r["half"]]; hh[0] += hit; hh[1] += p0; hh[2] += 1
                if n == 0:
                    continue
                p_base = exp / n
                rows.append(dict(sym=sym, family=fam, extreme=which, window=win_name, n=n, hits=hits, rate=hits / n,
                                 base=p_base, ci_lo=boot_ci(np.r_[np.ones(hits), np.zeros(n - hits)])[0],
                                 ci_hi=boot_ci(np.r_[np.ones(hits), np.zeros(n - hits)])[1],
                                 p=binom_p(hits, n, p_base),
                                 H1_n=h_hits["H1"][2], H1_rate=h_hits["H1"][0] / max(h_hits["H1"][2], 1), H1_base=h_hits["H1"][1] / max(h_hits["H1"][2], 1),
                                 H2_n=h_hits["H2"][2], H2_rate=h_hits["H2"][0] / max(h_hits["H2"][2], 1), H2_base=h_hits["H2"][1] / max(h_hits["H2"][2], 1)))
                n_comp += 1
        # panel: event bar range / volume relative, and P(extreme in next bar | close of bar ke-1)
        pp = p.merge(sess[["date", "ke"]], on="date")
        eb = pp[pp["k"] == pp["ke"]]
        nb = pp[pp["k"] == pp["ke"] + 1]
        ctrl_p = p[~p["date"].isin(sess["date"])]
        for lab, d in (("event_bar", eb), ("next_bar", nb)):
            if len(d) == 0:
                continue
            # control: same k and same is_dst
            cm = ctrl_p.merge(d[["k", "is_dst"]].drop_duplicates(), on=["k", "is_dst"])
            panel_rows.append(dict(sym=sym, family=fam, bar=lab, n=len(d),
                                   med_rng_rel=d["bar_rng_rel"].median(), base_rng_rel=cm["bar_rng_rel"].median(),
                                   rng_rel_ci=boot_ci(d["bar_rng_rel"].values, np.median), p_rng=mw_p(d["bar_rng_rel"], cm["bar_rng_rel"]),
                                   med_vol_rel=d["bar_vol_rel"].median(), base_vol_rel=cm["bar_vol_rel"].median(),
                                   p_vol=mw_p(d["bar_vol_rel"], cm["bar_vol_rel"]),
                                   med_bar_rng_bp=d["bar_rng_bp"].median(), base_bar_rng_bp=cm["bar_rng_bp"].median(),
                                   H1_rng_rel=d[d.half == "H1"]["bar_rng_rel"].median(), H2_rng_rel=d[d.half == "H2"]["bar_rng_rel"].median(),
                                   H1_base=cm[cm.half == "H1"]["bar_rng_rel"].median(), H2_base=cm[cm.half == "H2"]["bar_rng_rel"].median()))
            n_comp += 2

    # BoJ: decision bars 4-5 and presser bars (7 EST / 8 EDT)
    e = boj[boj["gdate"].isin(by_g.index)]
    sess = by_g.loc[e["gdate"].values].copy()
    ctrl_all = x[~x.index.isin(sess["date"])]
    for which in ("hi_k", "lo_k"):
        for win_name, ksf in (("decision_4_5", lambda r: {4, 5}), ("decision_3_6", lambda r: {3, 4, 5, 6}),
                              ("presser_last2", lambda r: {r["last_k"] - 1, r["last_k"]})):
            hits = 0; exp = 0.0; n = 0; hh = {"H1": [0, 0.0, 0], "H2": [0, 0.0, 0]}
            for _, r in sess.iterrows():
                ks = ksf(r); hit = int(r[which] in ks)
                ctrl = ctrl_all[(ctrl_all["is_dst"] == r["is_dst"]) & (ctrl_all["n_bars"] == r["n_bars"])]
                p0 = ctrl[which].isin(ks).mean(); hits += hit; exp += p0; n += 1
                hh[r["half"]][0] += hit; hh[r["half"]][1] += p0; hh[r["half"]][2] += 1
            rows.append(dict(sym=sym, family="BOJ", extreme=which, window=win_name, n=n, hits=hits, rate=hits / n, base=exp / n,
                             ci_lo=boot_ci(np.r_[np.ones(hits), np.zeros(n - hits)])[0], ci_hi=boot_ci(np.r_[np.ones(hits), np.zeros(n - hits)])[1],
                             p=binom_p(hits, n, exp / n),
                             H1_n=hh["H1"][2], H1_rate=hh["H1"][0] / max(hh["H1"][2], 1), H1_base=hh["H1"][1] / max(hh["H1"][2], 1),
                             H2_n=hh["H2"][2], H2_rate=hh["H2"][0] / max(hh["H2"][2], 1), H2_base=hh["H2"][1] / max(hh["H2"][2], 1)))
            n_comp += 1
    pp = p[p["date"].isin(sess["date"])]
    for k in (4, 5, 6):
        d = pp[pp["k"] == k]; cm = p[(~p["date"].isin(sess["date"])) & (p["k"] == k)]
        panel_rows.append(dict(sym=sym, family="BOJ", bar=f"k{k}", n=len(d), med_rng_rel=d["bar_rng_rel"].median(), base_rng_rel=cm["bar_rng_rel"].median(),
                               rng_rel_ci=boot_ci(d["bar_rng_rel"].values, np.median), p_rng=mw_p(d["bar_rng_rel"], cm["bar_rng_rel"]),
                               med_vol_rel=d["bar_vol_rel"].median(), base_vol_rel=cm["bar_vol_rel"].median(), p_vol=mw_p(d["bar_vol_rel"], cm["bar_vol_rel"]),
                               med_bar_rng_bp=d["bar_rng_bp"].median(), base_bar_rng_bp=cm["bar_rng_bp"].median(),
                               H1_rng_rel=d[d.half == "H1"]["bar_rng_rel"].median(), H2_rng_rel=d[d.half == "H2"]["bar_rng_rel"].median(),
                               H1_base=cm[cm.half == "H1"]["bar_rng_rel"].median(), H2_base=cm[cm.half == "H2"]["bar_rng_rel"].median()))
        n_comp += 2

out = pd.DataFrame(rows); out.to_csv(f"{OUT}/q2_event_bar_clustering.csv", index=False)
pr = pd.DataFrame(panel_rows); pr.to_csv(f"{OUT}/q2_event_bar_panel.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
print("comparisons:", n_comp)
print(out.round(3).to_string())
print(pr.round(3).to_string())
