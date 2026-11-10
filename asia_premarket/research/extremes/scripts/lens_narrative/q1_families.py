"""Q1: catalogue nights grouped by asia_driver family (EX POST) -> hi_k / lo_k / close_loc / Tokyo-open / China-open."""
import sys
sys.path.insert(0, "research/extremes/scripts/lens_narrative")
import numpy as np, pandas as pd
from common import *

# Primary family = first-named driver in the catalogue asia_driver text (hand-coded from the text; EX POST).
# ASIA_CHIP = Asia-origin chip/Kospi/Nikkei move; BOJ_YEN = BoJ/yen/JGB; HEADLINE = Iran/oil/Trump/weekend headline;
# AH_PRINT = after-hours US print (or an in-window print such as ASML ~01:00 ET); US_MACRO = Fed/CPI/NFP/rates/election;
# NO_NEWS = unverified / no catalyst identified.
FAM = {
 "2025-11-03":"AH_PRINT","2025-11-04":"ASIA_CHIP","2025-11-14":"ASIA_CHIP","2025-11-17":"ASIA_CHIP","2025-11-19":"AH_PRINT",
 "2025-11-20":"ASIA_CHIP","2025-11-28":"BOJ_YEN","2025-12-10":"AH_PRINT","2025-12-12":"NO_NEWS","2025-12-15":"ASIA_CHIP",
 "2025-12-18":"BOJ_YEN","2026-01-02":"HEADLINE","2026-01-09":"HEADLINE","2026-01-12":"BOJ_YEN","2026-01-16":"HEADLINE",
 "2026-01-21":"HEADLINE","2026-01-23":"BOJ_YEN","2026-01-27":"AH_PRINT","2026-01-28":"AH_PRINT","2026-01-29":"US_MACRO",
 "2026-02-20":"NO_NEWS","2026-02-25":"AH_PRINT","2026-02-27":"HEADLINE","2026-03-02":"HEADLINE","2026-03-03":"HEADLINE",
 "2026-03-06":"HEADLINE","2026-03-09":"HEADLINE","2026-03-11":"HEADLINE","2026-03-13":"HEADLINE","2026-03-17":"ASIA_CHIP",
 "2026-03-18":"HEADLINE","2026-03-20":"HEADLINE","2026-03-24":"HEADLINE","2026-03-26":"NO_NEWS","2026-03-27":"HEADLINE",
 "2026-03-30":"HEADLINE","2026-03-31":"HEADLINE","2026-04-01":"HEADLINE","2026-04-02":"HEADLINE","2026-04-07":"HEADLINE",
 "2026-04-08":"HEADLINE","2026-04-10":"HEADLINE","2026-04-13":"HEADLINE","2026-04-21":"HEADLINE","2026-04-28":"AH_PRINT",
 "2026-05-07":"HEADLINE","2026-05-11":"HEADLINE","2026-05-14":"ASIA_CHIP","2026-05-20":"AH_PRINT","2026-05-27":"HEADLINE",
 "2026-05-29":"ASIA_CHIP","2026-06-03":"AH_PRINT","2026-06-04":"ASIA_CHIP","2026-06-05":"HEADLINE","2026-06-08":"HEADLINE",
 "2026-06-10":"HEADLINE","2026-06-15":"BOJ_YEN","2026-06-16":"HEADLINE","2026-06-17":"HEADLINE","2026-06-18":"NO_NEWS",
 "2026-06-22":"ASIA_CHIP","2026-06-23":"ASIA_CHIP","2026-06-24":"AH_PRINT","2026-06-25":"ASIA_CHIP","2026-07-02":"ASIA_CHIP",
 "2026-07-06":"ASIA_CHIP","2026-07-08":"ASIA_CHIP","2026-07-10":"HEADLINE","2026-07-14":"ASIA_CHIP","2026-07-15":"ASIA_CHIP",
 "2026-07-16":"ASIA_CHIP","2026-07-20":"HEADLINE","2026-07-21":"HEADLINE","2026-07-22":"AH_PRINT","2026-07-27":"ASIA_CHIP",
 "2026-07-29":"AH_PRINT","2026-07-30":"AH_PRINT","2026-08-03":"HEADLINE","2026-08-04":"AH_PRINT","2026-08-07":"NO_NEWS",
 "2026-08-12":"NO_NEWS","2026-08-17":"HEADLINE","2026-08-19":"NO_NEWS","2026-08-26":"AH_PRINT","2026-08-28":"NO_NEWS",
 "2026-09-04":"NO_NEWS","2026-09-10":"US_MACRO","2026-09-11":"NO_NEWS","2026-09-16":"US_MACRO","2026-09-17":"BOJ_YEN",
 "2026-09-18":"HEADLINE","2026-09-23":"US_MACRO","2026-09-25":"HEADLINE","2026-09-30":"AH_PRINT","2026-10-02":"NO_NEWS",
 "2026-10-12":"ASIA_CHIP","2026-10-14":"ASIA_CHIP","2026-10-16":"HEADLINE","2026-10-21":"AH_PRINT","2026-10-23":"HEADLINE",
 "2026-10-28":"AH_PRINT","2026-10-29":"BOJ_YEN","2026-11-03":"US_MACRO","2026-11-04":"AH_PRINT","2026-11-05":"ASIA_CHIP",
 "2026-11-06":"HEADLINE","2026-11-09":"ASIA_CHIP",
}
# EX POST secondary flag: the catalogue text reports a Kospi or Nikkei cash move of >= 3% during the night
BIG_ASIA_CASH = {"2025-11-04","2025-11-17","2025-11-19","2025-12-15","2026-01-12","2026-03-02","2026-03-03","2026-03-06",
 "2026-03-09","2026-03-17","2026-03-20","2026-03-24","2026-03-27","2026-03-30","2026-03-31","2026-04-01","2026-04-07",
 "2026-04-13","2026-05-14","2026-05-29","2026-06-04","2026-06-05","2026-06-08","2026-06-10","2026-06-22","2026-06-23",
 "2026-06-25","2026-07-02","2026-07-06","2026-07-10","2026-07-14","2026-07-16","2026-07-20","2026-07-21","2026-07-27",
 "2026-07-30","2026-08-04","2026-09-30","2026-10-12","2026-10-14","2026-10-21","2026-10-29","2026-11-03","2026-11-04",
 "2026-11-05","2026-11-09"}
# EX POST: catalogue text says the catalyst landed at/just after the 18:00 ET reopen (gap) vs. inside the session
EVENT_AT_OPEN = {"2025-12-10","2026-01-09","2026-01-16","2026-02-27","2026-03-06","2026-03-13","2026-03-20","2026-03-27",
 "2026-04-02","2026-04-07","2026-04-10","2026-04-21","2026-06-05","2026-07-10","2026-09-25","2026-10-16","2026-10-23",
 "2026-11-06","2025-11-19","2026-06-03","2026-07-29","2026-10-21","2026-10-28","2026-11-04","2026-06-24","2026-08-04",
 "2026-02-25","2026-05-20","2026-08-26","2026-09-30","2026-04-28","2026-01-28","2025-11-03"}
EVENT_IN_SESSION = {"2026-03-02","2026-03-03","2026-03-09","2026-03-11","2026-03-17","2026-03-18","2026-03-30","2026-03-31",
 "2026-04-01","2026-04-08","2026-05-07","2026-06-10","2026-06-22","2026-06-25","2026-07-06","2026-07-27","2026-11-05",
 "2025-12-18","2026-09-17","2026-10-29","2026-06-15","2025-11-28","2026-01-27","2026-01-23","2026-01-12","2026-07-30",
 "2026-11-03","2026-10-12","2026-10-14","2026-07-16","2026-06-04","2026-07-02","2026-07-08","2026-07-14","2026-07-15",
 "2026-05-14","2026-05-29","2026-06-23","2026-11-09","2025-11-04","2025-11-17","2025-11-20","2025-12-15","2026-03-24",
 "2026-04-13","2026-07-20","2026-07-21","2026-08-17","2026-05-11","2026-05-27","2026-06-08","2026-06-16","2026-06-17",
 "2026-08-03","2026-09-10","2026-09-16","2026-09-23","2026-01-29","2026-01-21","2026-01-02","2026-09-18","2026-03-26"}

if __name__ == "__main__":
    x = load_extremes("NQ"); c = load_catalogue()
    c["family"] = [FAM.get(d.strftime("%Y-%m-%d"), "UNMAPPED") for d in c.index]
    c["big_asia_cash"] = [int(d.strftime("%Y-%m-%d") in BIG_ASIA_CASH) for d in c.index]
    c["event_at_open"] = [int(d.strftime("%Y-%m-%d") in EVENT_AT_OPEN) for d in c.index]
    print("unmapped:", c[c.family == "UNMAPPED"].index.tolist())
    j = c.join(x, how="inner")
    print("catalogue rows", len(c), "joined", len(j), "missing:", sorted(set(c.index) - set(j.index)))
    j["is_cat"] = 1
    x["is_cat"] = x.index.isin(j.index).astype(int)
    x["family"] = x.index.map(lambda d: FAM.get(d.strftime("%Y-%m-%d"), "none"))
    x["big_asia_cash"] = x.index.map(lambda d: int(d.strftime("%Y-%m-%d") in BIG_ASIA_CASH))
    x["event_at_open"] = x.index.map(lambda d: int(d.strftime("%Y-%m-%d") in EVENT_AT_OPEN))
    x.to_csv(f"{OUT}/NQ_extremes_with_family.csv")
    j.to_csv(f"{OUT}/catalogue_joined.csv")

    # ---- per-family descriptives (ex post) ----
    cols = ["hi_k", "lo_k", "close_loc", "rng_bp", "asia_ret_bp", "abs_asia_ret", "rth_ret_bp"]
    rows = []
    base = x[x.index >= "2025-11-01"]  # same window as the catalogue, for the base rate of the non-catalogue nights
    for fam, g in list(j.groupby("family")) + [("ALL_CATALOGUE", j), ("WINDOW_ALL(Nov25-Nov26)", base), ("FULL_579", x)]:
        r = dict(family=fam, n=len(g),
                 hi_first_bar=g["high_in_first_bar"].mean(), lo_first_bar=g["low_in_first_bar"].mean(),
                 hi_at_tko=g["high_at_tokyo_open"].mean(), lo_at_tko=g["low_at_tokyo_open"].mean(),
                 hi_by_tko=g["high_by_tokyo_open"].mean(), lo_by_tko=g["low_by_tokyo_open"].mean(),
                 hi_at_cno=g["high_at_china_open"].mean(), lo_at_cno=g["low_at_china_open"].mean(),
                 hi_last_bar=g["high_in_last_bar"].mean(), lo_last_bar=g["low_in_last_bar"].mean(),
                 any_first_bar=g["any_first_bar"].mean(), any_last_bar=g["any_last_bar"].mean(),
                 any_at_tko=g["any_at_tko"].mean(), any_at_cno=g["any_at_cno"].mean(),
                 trend_close=g["trend_close"].mean(), mid_close=g["mid_close"].mean(),
                 cont=g["cont"].mean(), hi_first=g["hi_first"].mean(),
                 med_rng=g["rng_bp"].median(), med_abs_ret=g["abs_asia_ret"].median(),
                 med_close_loc=g["close_loc"].median(),
                 hi_k_hist=np.bincount(g["hi_k"].astype(int), minlength=9).tolist(),
                 lo_k_hist=np.bincount(g["lo_k"].astype(int), minlength=9).tolist(),
                 hi_above_rth=g["high_above_rth_high"].mean(), lo_below_rth=g["low_below_rth_low"].mean())
        rows.append(r)
    fam_tab = pd.DataFrame(rows)
    fam_tab.to_csv(f"{OUT}/q1_family_table.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 50)
    print(fam_tab.drop(columns=["hi_k_hist", "lo_k_hist"]).round(2).to_string())
    print(fam_tab[["family", "n", "hi_k_hist", "lo_k_hist"]].to_string())

    # catalogue vs non-catalogue in the same window: are the catalogue nights different (they are the BIG nights)?
    w = base.copy(); w["is_cat"] = w.index.isin(j.index).astype(int)
    print("\nwindow: catalogue vs other nights (ex post selection)")
    for lab in ["any_first_bar", "any_last_bar", "any_at_tko", "trend_close", "hi_after_tko", "lo_after_tko"]:
        a = w[w.is_cat == 1][lab].mean(); b = w[w.is_cat == 0][lab].mean()
        print(f"  {lab:14s} cat={a:.2f} (n={w.is_cat.sum()})  other={b:.2f} (n={(w.is_cat==0).sum()})")
    print("  med rng cat", w[w.is_cat == 1]["rng_bp"].median(), "other", w[w.is_cat == 0]["rng_bp"].median())

    # Big-Asia-cash nights (Kospi/Nikkei >=3% reported) vs the rest of the catalogue: where is the extreme?
    print("\nbig_asia_cash (ex post) within the catalogue")
    for flag, g in j.groupby("big_asia_cash"):
        print(f"  big_asia_cash={flag} n={len(g)} hi_at_tko={g.high_at_tokyo_open.mean():.2f} lo_at_tko={g.low_at_tokyo_open.mean():.2f} "
              f"any_at_tko={g.any_at_tko.mean():.2f} any_first={g.any_first_bar.mean():.2f} any_last={g.any_last_bar.mean():.2f} "
              f"trend={g.trend_close.mean():.2f} med_rng={g.rng_bp.median():.0f} hi_first={g.hi_first.mean():.2f}")
    print("\nevent_at_open (ex post) within the catalogue")
    for flag, g in j.groupby("event_at_open"):
        print(f"  event_at_open={flag} n={len(g)} any_first={g.any_first_bar.mean():.2f} hi_first_bar={g.high_in_first_bar.mean():.2f} "
              f"lo_first_bar={g.low_in_first_bar.mean():.2f} any_at_tko={g.any_at_tko.mean():.2f} any_last={g.any_last_bar.mean():.2f} "
              f"trend={g.trend_close.mean():.2f} med_rng={g.rng_bp.median():.0f} |gap|med={g.gap_open_bp.abs().median():.0f}")

    # per family: where in the session the LAST extreme lands (session resolves) -> late trend into Europe
    print("\nfamily: last extreme in last 2 bars (late trend into Europe), first extreme in bar 0")
    for fam, g in j.groupby("family"):
        last2 = (g["last_ext_k"] >= g["n_bars"] - 2).mean(); first0 = (g["first_ext_k"] == 0).mean()
        print(f"  {fam:10s} n={len(g):3d} last_ext_in_last2={last2:.2f} first_ext_in_bar0={first0:.2f} "
              f"hi_last2={g.hi_last2.mean():.2f} lo_last2={g.lo_last2.mean():.2f}")
    print("  FULL_579  last_ext_in_last2=%.2f first_ext_in_bar0=%.2f" % (((x.last_ext_k >= x.n_bars - 2).mean()), (x.first_ext_k == 0).mean()))
