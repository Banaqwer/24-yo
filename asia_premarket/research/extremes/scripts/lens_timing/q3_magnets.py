"""Q3: magnets and stop-runs. Do extremes cluster at RTH high/low, RTH VWAP, prior Asia high/low, 17:00 close, round numbers?"""
import sys
sys.path.insert(0, "research/extremes/scripts/lens_timing")
import numpy as np, pandas as pd
from common import *

sym = sys.argv[1] if len(sys.argv) > 1 else "NQ"
x, p = load(sym)
print(sym, "sessions", len(x))
ncomp = 0
pd.set_option("display.width", 250)

# ---------- 1. spike test: share of extremes within +-5 bp of a level vs the neighbouring 5-bp shells ----------
# null: locally smooth density -> share in [-5,5] ~ average of shells [-15,-5] and [5,15]
def spike(v, label, w=5, span=50):
    global ncomp
    v = pd.Series(v).dropna().values
    n = len(v)
    inner = np.mean(np.abs(v) <= w)
    sh1 = np.mean((np.abs(v) > w) & (np.abs(v) <= 3 * w))        # 5..15, two shells (so halve)
    neigh = sh1 / 2
    # bootstrap the ratio
    idx = RNG.integers(0, n, size=(2000, n))
    b = []
    for i in idx:
        vv = v[i]; a = np.mean(np.abs(vv) <= w); c = np.mean((np.abs(vv) > w) & (np.abs(vv) <= 3 * w)) / 2
        b.append(a / c if c > 0 else np.nan)
    b = np.array(b); b = b[~np.isnan(b)]
    ncomp += 1
    # also the share within the band, and halves
    return dict(level=label, n=n, share_within_5bp=inner, share_neighbour_shell_avg=neigh, ratio=inner / neigh if neigh > 0 else np.nan,
                ratio_ci90=(float(np.quantile(b, .05)), float(np.quantile(b, .95))),
                share_within_2bp=np.mean(np.abs(v) <= 2), share_above_0=np.mean(v > 0), share_in_m50_p50=np.mean(np.abs(v) <= span),
                median=np.median(v))

def spike_halves(col, label):
    out = [dict(half="all", **spike(x[col], label))]
    for hh in ("H1", "H2"):
        out.append(dict(half=hh, **spike(x[x.half == hh][col], label)))
    return out

S = []
S += spike_halves("hi_vs_rth_high_bp", "high vs RTH high")
S += spike_halves("lo_vs_rth_low_bp", "low vs RTH low")
S += spike_halves("hi_vs_rth_vwap_bp", "high vs RTH vwap")
S += spike_halves("lo_vs_rth_vwap_bp", "low vs RTH vwap")
S += spike_halves("hi_vs_prior_asia_high_bp", "high vs prior Asia high")
S += spike_halves("lo_vs_prior_asia_low_bp", "low vs prior Asia low")
S += spike_halves("hi_bp", "high vs 17:00 close")
S += spike_halves("lo_bp", "low vs 17:00 close")
# controls: the high vs the RTH LOW and the low vs the RTH HIGH (should not spike), and vs RTH open / prev settle
x["hi_vs_rth_low_bp"] = (x.asia_high / x.lvl_rth_low - 1) * 1e4
x["lo_vs_rth_high_bp"] = (x.asia_low / x.lvl_rth_high - 1) * 1e4
x["hi_vs_rth_open_bp"] = (x.asia_high / x.lvl_rth_open - 1) * 1e4
x["lo_vs_rth_open_bp"] = (x.asia_low / x.lvl_rth_open - 1) * 1e4
x["hi_vs_prev_settle_bp"] = (x.asia_high / x.lvl_prev_settle - 1) * 1e4
x["lo_vs_prev_settle_bp"] = (x.asia_low / x.lvl_prev_settle - 1) * 1e4
x["hi_vs_prev_rth_high_bp"] = (x.asia_high / x.lvl_prev_rth_high - 1) * 1e4
x["lo_vs_prev_rth_low_bp"] = (x.asia_low / x.lvl_prev_rth_low - 1) * 1e4
S += spike_halves("hi_vs_rth_open_bp", "high vs RTH open")
S += spike_halves("lo_vs_rth_open_bp", "low vs RTH open")
S += spike_halves("hi_vs_prev_settle_bp", "high vs prev settle")
S += spike_halves("lo_vs_prev_settle_bp", "low vs prev settle")
S += spike_halves("hi_vs_prev_rth_high_bp", "high vs prev-day RTH high")
S += spike_halves("lo_vs_prev_rth_low_bp", "low vs prev-day RTH low")
S += spike_halves("hi_vs_rth_low_bp", "CONTROL high vs RTH low")
S += spike_halves("lo_vs_rth_high_bp", "CONTROL low vs RTH high")
SP = pd.DataFrame(S); SP.to_csv(f"{OUT}/q3_{sym}_level_spikes.csv", index=False)
print("\n=== spike test: share of extremes within +-5bp of level / avg share in 5-15bp shells ===")
print(SP[["level", "half", "n", "share_within_2bp", "share_within_5bp", "share_neighbour_shell_avg", "ratio", "ratio_ci90", "share_above_0", "median"]].round(3).to_string())

# ---------- 2. fine histogram around the RTH high / low (2-bp bins, -30..+30) ----------
H = []
for col, lab in [("hi_vs_rth_high_bp", "hi_vs_rth_high"), ("lo_vs_rth_low_bp", "lo_vs_rth_low"), ("hi_vs_rth_vwap_bp", "hi_vs_vwap"), ("lo_vs_rth_vwap_bp", "lo_vs_vwap"), ("hi_bp", "hi_vs_ref"), ("lo_bp", "lo_vs_ref")]:
    v = x[col].dropna()
    bins = np.arange(-30, 32, 2)
    c, _ = np.histogram(v, bins=bins)
    for b0, cnt in zip(bins[:-1], c):
        H.append(dict(level=lab, bin_lo=b0, bin_hi=b0 + 2, count=cnt, share=cnt / len(v)))
HH = pd.DataFrame(H); HH.to_csv(f"{OUT}/q3_{sym}_level_histograms_2bp.csv", index=False)
print("\n=== 2-bp histogram around RTH high (hi_vs_rth_high_bp) ===")
print(HH[HH.level == "hi_vs_rth_high"].pivot_table(index="bin_lo", values="count").T.to_string())
print("=== around RTH low (lo_vs_rth_low_bp) ===")
print(HH[HH.level == "lo_vs_rth_low"].pivot_table(index="bin_lo", values="count").T.to_string())

# ---------- 3. what follows a probe beyond the RTH extreme ----------
print("\n=== drop_after_hi_bp by relation of the Asia high to the RTH high ===")
def grp_stats(df, col, by, label):
    global ncomp
    out = []
    for lab, m in by:
        v = df.loc[m, col].dropna()
        lo, hi = boot_ci(v.values, np.median)
        out.append(dict(outcome=col, cond=lab, n=len(v), median=v.median(), ci90_lo=lo, ci90_hi=hi, mean=v.mean(), p25=v.quantile(.25), p75=v.quantile(.75),
                        med_H1=df.loc[m & (df.half == "H1"), col].median(), med_H2=df.loc[m & (df.half == "H2"), col].median(), n_H1=int((m & (df.half == "H1")).sum()), n_H2=int((m & (df.half == "H2")).sum())))
        ncomp += 1
    return pd.DataFrame(out)

hv = x.hi_vs_rth_high_bp
by_hi = [("high <= RTH high - 15", hv < -15), ("RTH high -15..-5 (approach)", (hv >= -15) & (hv < -5)), ("within +-5 (test)", hv.abs() <= 5), ("above +5..+15 (probe)", (hv > 5) & (hv <= 15)), ("above >+15 (break)", hv > 15),
         ("high_above_rth_high=0", x.high_above_rth_high == 0), ("high_above_rth_high=1", x.high_above_rth_high == 1)]
D1 = grp_stats(x, "drop_after_hi_bp", by_hi, "hi")
lv = x.lo_vs_rth_low_bp
by_lo = [("low >= RTH low + 15", lv > 15), ("RTH low +5..+15 (approach)", (lv > 5) & (lv <= 15)), ("within +-5 (test)", lv.abs() <= 5), ("below -5..-15 (probe)", (lv < -5) & (lv >= -15)), ("below <-15 (break)", lv < -15),
         ("low_below_rth_low=0", x.low_below_rth_low == 0), ("low_below_rth_low=1", x.low_below_rth_low == 1)]
D2 = grp_stats(x, "rally_after_lo_bp", by_lo, "lo")
# also: the drop after the high normalised by the ex-ante median range, and the close location
x["drop_after_hi_rel"] = x.drop_after_hi_bp / (x.asia_rng_med20 * 1e4)
x["rally_after_lo_rel"] = x.rally_after_lo_bp / (x.asia_rng_med20 * 1e4)
D3 = grp_stats(x, "drop_after_hi_rel", by_hi, "hi"); D4 = grp_stats(x, "rally_after_lo_rel", by_lo, "lo")
D5 = grp_stats(x, "close_loc", by_hi, "hi"); D6 = grp_stats(x, "close_loc", by_lo, "lo")
D7 = grp_stats(x, "hi_k", by_hi, "hi"); D8 = grp_stats(x, "lo_k", by_lo, "lo")
DD = pd.concat([D1, D2, D3, D4, D5, D6, D7, D8]); DD.to_csv(f"{OUT}/q3_{sym}_after_probe.csv", index=False)
print(DD[["outcome", "cond", "n", "median", "ci90_lo", "ci90_hi", "p25", "p75", "med_H1", "med_H2"]].round(2).to_string())

# P(high above RTH high) given 18:00 distance of the 17:00 close to the RTH high (knowable at 18:00)
print("\n=== P(Asia high > RTH high) by 18:00 distance ref_close -> RTH high (bp) ===")
x["ref_to_rth_high_bp"] = (x.lvl_rth_high / x.ref_close - 1) * 1e4
x["ref_to_rth_low_bp"] = (x.lvl_rth_low / x.ref_close - 1) * 1e4
rows = []
base = x.high_above_rth_high.mean()
for lab, m in [("<10", x.ref_to_rth_high_bp < 10), ("10-25", (x.ref_to_rth_high_bp >= 10) & (x.ref_to_rth_high_bp < 25)), ("25-50", (x.ref_to_rth_high_bp >= 25) & (x.ref_to_rth_high_bp < 50)), ("50-100", (x.ref_to_rth_high_bp >= 50) & (x.ref_to_rth_high_bp < 100)), (">=100", x.ref_to_rth_high_bp >= 100)]:
    r = rate_row(m, x.high_above_rth_high, base, f"ref->RTHhigh {lab}", x.half); r.update(label="high_above_rth_high"); rows.append(r); ncomp += 1
base = x.low_below_rth_low.mean()
for lab, m in [("<10", -x.ref_to_rth_low_bp < 10), ("10-25", (-x.ref_to_rth_low_bp >= 10) & (-x.ref_to_rth_low_bp < 25)), ("25-50", (-x.ref_to_rth_low_bp >= 25) & (-x.ref_to_rth_low_bp < 50)), ("50-100", (-x.ref_to_rth_low_bp >= 50) & (-x.ref_to_rth_low_bp < 100)), (">=100", -x.ref_to_rth_low_bp >= 100)]:
    r = rate_row(m, x.low_below_rth_low, base, f"ref->RTHlow {lab}", x.half); r.update(label="low_below_rth_low"); rows.append(r); ncomp += 1
PB = pd.DataFrame(rows); PB.to_csv(f"{OUT}/q3_{sym}_p_break_by_distance.csv", index=False)
print(PB[["label", "cond", "n", "base", "rate", "ci90_lo", "ci90_hi", "p_binom", "rate_H1", "rate_H2"]].round(3).to_string())

# ---------- 4. round numbers ----------
print("\n=== round numbers: distance of the extreme price to the nearest multiple ===")
mods = {"NQ": [100, 50, 25], "ES": [25, 10, 5]}[sym]
tick = {"NQ": 0.25, "ES": 0.25}[sym]
R = []
for M in mods:
    for col in ["asia_high", "asia_low", "asia_close"]:
        v = x[col].values
        dist = np.minimum(v % M, M - (v % M))           # points to nearest multiple
        # share within +-1 point (= 4 ticks) vs uniform expectation 2/M... use share within +-(M*0.05)
        w = max(tick * 4, M * 0.04)
        obs = np.mean(dist <= w); exp = (2 * w + tick) / M
        k = int((dist <= w).sum()); n = len(v)
        R.append(dict(mod=M, col=col, window_pts=w, n=n, share_within=obs, expected_uniform=exp, ratio=obs / exp, p_binom=binom_p(k, n, exp),
                      share_H1=np.mean(dist[(x.half == "H1").values] <= w), share_H2=np.mean(dist[(x.half == "H2").values] <= w)))
        ncomp += 1
RN = pd.DataFrame(R); RN.to_csv(f"{OUT}/q3_{sym}_round_numbers.csv", index=False); print(RN.round(3).to_string())

# ---------- 5. fraction of extremes that are 'at a level' at all (any of the 4 reference levels within 5bp) ----------
lv_hi = x[["hi_vs_rth_high_bp", "hi_vs_rth_vwap_bp", "hi_vs_prior_asia_high_bp", "hi_bp"]].abs()
lv_lo = x[["lo_vs_rth_low_bp", "lo_vs_rth_vwap_bp", "lo_vs_prior_asia_low_bp", "lo_bp"]].abs()
print("\nshare of highs within 5bp of ANY of {RTH high, RTH vwap, prior Asia high, 17:00 close}:", round((lv_hi <= 5).any(axis=1).mean(), 3))
print("share of lows  within 5bp of ANY of {RTH low, RTH vwap, prior Asia low, 17:00 close}:", round((lv_lo <= 5).any(axis=1).mean(), 3))
print("comparisons run in q3:", ncomp)
