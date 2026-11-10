"""Supplement: (a) 18:00-feature negative result, (b) RTH-break effect on hold with CI, (c) 18:00 distance ladder -> timing, (d) sunday_open on ES, (e) vol x direction rule with CI."""
import sys
sys.path.insert(0, "research/extremes/scripts/lens_timing")
import numpy as np, pandas as pd
from common import *
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
ncomp = 0

# (a) 18:00-feature negative result: best 18:00-stage conditionals from the Q1 scans, both symbols
print("=== (a) best 18:00-knowable conditionals for first/last-bar outcomes (n>=30), by |lift|, both symbols ===")
for sym in ["NQ", "ES"]:
    R = pd.read_csv(f"{OUT}/q1_{sym}_ushape_scan.csv")
    R = R[(R.stage == "18:00") & (R.n >= 30)].copy(); R["al"] = R.lift.abs()
    print(sym, "n 18:00 conditionals:", len(R), "| with p<.05:", int((R.p_binom < .05).sum()), "| p<.05 & stable:", int(((R.p_binom < .05) & R.stable).sum()), "| p<.01 & stable:", int(((R.p_binom < .01) & R.stable).sum()), "| max |lift|:", round(R.al.max(), 3))
    print(R.sort_values("al", ascending=False)[["outcome", "cond", "n", "base", "rate", "ci90_lo", "ci90_hi", "p_binom", "rate_H1", "rate_H2", "stable"]].round(3).head(12).to_string())
    # expected false positives at p<.05 among this many tests
    print(f"  expected p<.05 by chance ~ {0.05*len(R):.0f}")
    Rb = pd.read_csv(f"{OUT}/q1_{sym}_ushape_scan.csv"); Rb = Rb[(Rb.stage == "bar0") & (Rb.n >= 30)]
    print(f"  bar0-stage conditionals: {len(Rb)}, p<.05 & stable: {int(((Rb.p_binom < .05) & Rb.stable).sum())}")

# (b) RTH-break effect on hold, pooled k=2..6, with CI & halves; and the vol x direction rule
print("\n=== (b) pooled k=2..6: run_hi_above_rth_high / run_lo_below_rth_low vs hold; vol x direction ===")
rows = []
for sym in ["NQ", "ES"]:
    x, p = load(sym); d = p[(p.n_bars == 9) & (p.k >= 2) & (p.k <= 6)].copy()
    for lab_col, flag in [("high_done", "run_hi_above_rth_high"), ("low_done", "run_lo_below_rth_low")]:
        base = d[lab_col].mean()
        for v in [0, 1]:
            r = rate_row(d[flag] == v, d[lab_col], base, f"{flag}=={v}", d.half); r.update(sym=sym, label=lab_col); rows.append(r); ncomp += 1
        # same, holding bars_since fixed at >=2 (the break happened >=2 bars ago) and ==0 (the break bar itself)
        bsh = "bars_since_hi" if lab_col == "high_done" else "bars_since_lo"
        for v in [0, 1]:
            for blab, bm in [("bsh==0", d[bsh] == 0), ("bsh>=2", d[bsh] >= 2)]:
                m = (d[flag] == v) & bm; base2 = d[bm][lab_col].mean()
                r = rate_row(m, d[lab_col], base2, f"{flag}=={v} & {blab}", d.half); r.update(sym=sym, label=lab_col); rows.append(r); ncomp += 1
    d1 = p[(p.n_bars == 9) & (p.k >= 1) & (p.k <= 7)].copy()
    for lab_col in ["high_done", "low_done"]:
        base = d1[lab_col].mean()
        for lab, m in [("vol>=1.5 & bar down", (d1.bar_vol_rel >= 1.5) & (d1.bar_ret_bp < 0)), ("vol>=1.5 & bar up", (d1.bar_vol_rel >= 1.5) & (d1.bar_ret_bp >= 0)), ("vol<1.5 & bar down", (d1.bar_vol_rel < 1.5) & (d1.bar_ret_bp < 0)), ("vol<1.5 & bar up", (d1.bar_vol_rel < 1.5) & (d1.bar_ret_bp >= 0)),
                       ("bar down & close_loc<0.25", (d1.bar_ret_bp < 0) & (d1.bar_close_loc < .25)), ("bar up & close_loc>=0.75", (d1.bar_ret_bp >= 0) & (d1.bar_close_loc >= .75)),
                       ("vol>=1.5 & bar down & bsh==0", (d1.bar_vol_rel >= 1.5) & (d1.bar_ret_bp < 0) & (d1.bars_since_hi == 0)), ("vol>=1.5 & bar up & bsl==0", (d1.bar_vol_rel >= 1.5) & (d1.bar_ret_bp >= 0) & (d1.bars_since_lo == 0))]:
            r = rate_row(m, d1[lab_col], base, lab, d1.half); r.update(sym=sym, label=lab_col, note="k=1..7"); rows.append(r); ncomp += 1
B = pd.DataFrame(rows); B.to_csv(f"{OUT}/q7_break_and_volume_rules.csv", index=False)
print(B[["sym", "label", "cond", "n", "base", "rate", "ci90_lo", "ci90_hi", "p_binom", "rate_H1", "rate_H2"]].round(3).to_string())

# (c) 18:00 distance ladder -> timing of the extreme
print("\n=== (c) 18:00-knowable: distance ref_close -> RTH high/low and WHEN the extreme forms ===")
rows = []
for sym in ["NQ", "ES"]:
    x, p = load(sym); x = x[x.n_bars == 9].copy()
    x["ref_to_rth_high_bp"] = (x.lvl_rth_high / x.ref_close - 1) * 1e4
    x["ref_to_rth_low_bp"] = -(x.lvl_rth_low / x.ref_close - 1) * 1e4
    for side, dcol, kcol, firstcol, lastcol, bytk in [("high", "ref_to_rth_high_bp", "hi_k", "high_in_first_bar", "high_in_last_bar", "high_by_tokyo_open"), ("low", "ref_to_rth_low_bp", "lo_k", "low_in_first_bar", "low_in_last_bar", "low_by_tokyo_open")]:
        for lab, m in [("<10", x[dcol] < 10), ("10-25", (x[dcol] >= 10) & (x[dcol] < 25)), ("25-50", (x[dcol] >= 25) & (x[dcol] < 50)), ("50-100", (x[dcol] >= 50) & (x[dcol] < 100)), (">=100", x[dcol] >= 100)]:
            d = x[m]
            rec = dict(sym=sym, side=side, dist=lab, n=len(d), median_k=d[kcol].median(), mean_k=d[kcol].mean(), p_first=d[firstcol].mean(), p_last=d[lastcol].mean(), p_by_tokyo=d[bytk].mean(),
                       p_first_H1=d[d.half == "H1"][firstcol].mean(), p_first_H2=d[d.half == "H2"][firstcol].mean(), p_last_H1=d[d.half == "H1"][lastcol].mean(), p_last_H2=d[d.half == "H2"][lastcol].mean(),
                       base_first=x[firstcol].mean(), base_last=x[lastcol].mean(), p_binom_first=binom_p(int(d[firstcol].sum()), len(d), x[firstcol].mean()), p_binom_last=binom_p(int(d[lastcol].sum()), len(d), x[lastcol].mean()),
                       ext_bp_median=d["hi_bp" if side == "high" else "lo_bp"].median())
            rows.append(rec); ncomp += 2
    # also the RTH-day direction: is the 'near' side the continuation side?  P(high in last bar | is_down) etc.
C = pd.DataFrame(rows); C.to_csv(f"{OUT}/q7_distance_ladder_timing.csv", index=False)
print(C.round(3).to_string())

# (d) sunday_open and other calendar flags on first/last-bar outcomes, both symbols
print("\n=== (d) calendar flags (18:00) on first/last-bar outcomes, both symbols ===")
rows = []
for sym in ["NQ", "ES"]:
    x, p = load(sym); x = x[x.n_bars == 9]
    for f in ["sunday_open", "pre_holiday", "holiday_tomorrow", "month_end", "opex_today", "fomc_today", "tier1_data_today", "tier1_data_tomorrow", "megacap_earnings_tonight", "boj_tonight", "cn_data_tonight", "jp_data_tonight", "rba_tonight"]:
        for oc in ["high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar"]:
            r = rate_row(x[f] == 1, x[oc], x[oc].mean(), f"{f}==1", x.half); r.update(sym=sym, outcome=oc); rows.append(r); ncomp += 1
D = pd.DataFrame(rows); D.to_csv(f"{OUT}/q7_calendar_flags_firstlast.csv", index=False)
D["stable"] = np.sign(D.rate_H1 - D.base) == np.sign(D.rate_H2 - D.base)
print(D[(D.n >= 30) & (D.p_binom < .1)][["sym", "outcome", "cond", "n", "base", "rate", "ci90_lo", "ci90_hi", "p_binom", "rate_H1", "rate_H2", "stable"]].round(3).to_string())

# (e) simple detector table: P(high_done | k, pos_in_range<0.25) and P(low_done | k, pos_in_range>=0.75) with CI + halves, both symbols
print("\n=== (e) P(high_done | k, pos_in_range<0.25), P(low_done | k, pos_in_range>=0.75): CI and halves ===")
rows = []
for sym in ["NQ", "ES"]:
    x, p = load(sym); p = p[(p.n_bars == 9) & (p.k <= 7)]
    for k in range(8):
        d = p[p.k == k]
        for lab_col, m, lab in [("high_done", d.pos_in_range < .25, "pos<0.25"), ("high_done", d.pos_in_range >= .75, "pos>=0.75"), ("low_done", d.pos_in_range >= .75, "pos>=0.75"), ("low_done", d.pos_in_range < .25, "pos<0.25")]:
            r = rate_row(m, d[lab_col], d[lab_col].mean(), lab, d.half); r.update(sym=sym, k=k, label=lab_col); rows.append(r); ncomp += 1
E = pd.DataFrame(rows); E.to_csv(f"{OUT}/q7_pos_in_range_detector_table.csv", index=False)
print(E[["sym", "label", "k", "cond", "n", "base", "rate", "ci90_lo", "ci90_hi", "rate_H1", "rate_H2"]].round(2).to_string())
print("\ncomparisons run in q7:", ncomp)
