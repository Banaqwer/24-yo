"""Independent recomputation of events-lens claims E1-E8, E10-E13 from the extremes tables + panels."""
import numpy as np
import pandas as pd
from scipy import stats

ROOT = "."
SPLIT = pd.Timestamp("2025-09-01")
EXCLUDE = {"NQ": [pd.Timestamp("2025-09-16")],
           "ES": [pd.Timestamp("2025-12-16"), pd.Timestamp("2025-12-17")]}
pd.set_option("display.width", 250)


def load(sym):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    x = x[~x.index.isin(EXCLUDE[sym])].copy()
    x["half"] = np.where(x.index < SPLIT, "H1", "H2")
    x["last_k"] = x["n_bars"] - 1
    x["hi_last"] = (x["hi_k"] == x["last_k"]).astype(int)
    x["lo_last"] = (x["lo_k"] == x["last_k"]).astype(int)
    x["either_first"] = ((x["hi_k"] == 0) | (x["lo_k"] == 0)).astype(int)
    x["both_first"] = ((x["hi_k"] == 0) & (x["lo_k"] == 0)).astype(int)
    x["either_last"] = ((x["hi_last"] == 1) | (x["lo_last"] == 1)).astype(int)
    x["abs_gap"] = x["gap_open_bp"].abs()
    x["abs_asia_ret"] = x["asia_ret_bp"].abs()
    x["close_loc_ext"] = ((x["close_loc"] > 0.8) | (x["close_loc"] < 0.2)).astype(int)
    x["asia_up"] = (x["asia_ret_bp"] > 0).astype(int)
    x["close_above_ref"] = (x["asia_close"] > x["ref_close"]).astype(int)
    x["both_inside"] = ((x["high_above_rth_high"] == 0) & (x["low_below_rth_low"] == 0)).astype(int)
    return x


def load_panel(sym):
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    p = p[~p["date"].isin(EXCLUDE[sym])].copy()
    p["half"] = np.where(p["date"] < SPLIT, "H1", "H2")
    return p


def wilson(k, n, z=1.645):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)


def prop(sub, base, col, label=""):
    n = int(sub[col].notna().sum()); k = int(sub[col].sum())
    r = k / n if n else np.nan
    p0 = base[col].mean()
    lo, hi = wilson(k, n)
    pv = stats.binomtest(k, n, p0).pvalue if n else np.nan
    # Fisher exact as a second check (two-by-two)
    k0 = int(base[col].sum()); n0 = int(base[col].notna().sum())
    fp = stats.fisher_exact([[k, n - k], [k0, n0 - k0]])[1] if n else np.nan
    h = {}
    for hh in ("H1", "H2"):
        s = sub[sub.half == hh]; b = base[base.half == hh]
        h[hh] = (f"{s[col].mean():.3f}" if len(s) else "nan", f"{b[col].mean():.3f}", len(s))
    print(f"  {label or col:34s} n={n:4d} k={k:3d} rate={r:.3f} base={p0:.3f} CI90=[{lo:.3f},{hi:.3f}] "
          f"binom_p={pv:.2e} fisher_p={fp:.2e} | H1 {h['H1'][0]} vs {h['H1'][1]} (n={h['H1'][2]}) | H2 {h['H2'][0]} vs {h['H2'][1]} (n={h['H2'][2]})")
    return dict(n=n, k=k, rate=r, base=p0, lo=lo, hi=hi, p=pv, fisher=fp)


def boot_med_ci(a, B=4000, seed=1):
    a = np.asarray(a, float); a = a[~np.isnan(a)]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(B, len(a)))
    s = np.median(a[idx], axis=1)
    return tuple(np.quantile(s, [0.05, 0.95]))


def boot_diff(a, b, B=4000, seed=1):
    a = np.asarray(a, float); a = a[~np.isnan(a)]
    b = np.asarray(b, float); b = b[~np.isnan(b)]
    rng = np.random.default_rng(seed)
    ia = rng.integers(0, len(a), size=(B, len(a))); ib = rng.integers(0, len(b), size=(B, len(b)))
    d = np.median(a[ia], axis=1) - np.median(b[ib], axis=1)
    return tuple(np.quantile(d, [0.05, 0.95]))


def med(sub, base, col, label=""):
    a = sub[col].dropna().values; b = base[col].dropna().values
    pv = stats.mannwhitneyu(a, b, alternative="two-sided").pvalue if len(a) > 1 else np.nan
    dlo, dhi = boot_diff(a, b) if len(a) > 1 else (np.nan, np.nan)
    h = {}
    for hh in ("H1", "H2"):
        s = sub[sub.half == hh][col].dropna(); bb = base[base.half == hh][col].dropna()
        h[hh] = (f"{s.median():.1f}" if len(s) else "nan", f"{bb.median():.1f}", len(s))
    print(f"  {label or col:34s} n={len(a):4d} med={np.median(a):7.2f} base={np.median(b):7.2f} diffCI90=[{dlo:.1f},{dhi:.1f}] MW_p={pv:.2e} "
          f"| H1 {h['H1'][0]} vs {h['H1'][1]} (n={h['H1'][2]}) | H2 {h['H2'][0]} vs {h['H2'][1]} (n={h['H2'][2]})")
    return dict(n=len(a), med=np.median(a), base=np.median(b), dlo=dlo, dhi=dhi, p=pv)


def done_rates(p, mask_dates, label, col="low_done", ks=range(0, 8)):
    """P(col | k) for sessions in mask vs not."""
    out = []
    for k in ks:
        d = p[p.k == k]
        s = d[d.date.isin(mask_dates)]; b = d[~d.date.isin(mask_dates)]
        kk = int(s[col].sum()); n = len(s)
        pv = stats.binomtest(kk, n, b[col].mean()).pvalue if n else np.nan
        out.append((k, n, s[col].mean(), b[col].mean(), pv))
    print(f"  {label} {col}: " + " ".join(f"k{k}:{r:.2f}/{b:.2f}(p={pv:.3f})" for k, n, r, b, pv in out) + f"  n={out[0][1]}")
    return out


for sym in ("NQ", "ES"):
    x = load(sym); p = load_panel(sym)
    print(f"\n==================== {sym}  n={len(x)}  H1={int((x.half=='H1').sum())} H2={int((x.half=='H2').sum())} ====================")
    sun = x[x.sunday_open == 1]; wk = x[x.sunday_open == 0]
    print(f"sunday n={len(sun)} weeknight n={len(wk)}; dow of sunday rows: {sun.dow.unique()}")

    # ---------------- E1 ----------------
    print("\n--- E1 Sunday reopen: low early ---")
    for c in ("low_by_tokyo_open", "low_in_first_bar", "high_by_tokyo_open", "high_in_first_bar", "either_first"):
        prop(sun, wk, c)
    print(f"  lo_k median sunday={sun.lo_k.median()} weeknight={wk.lo_k.median()}; hi_k median {sun.hi_k.median()} vs {wk.hi_k.median()}")
    for c in ("abs_gap", "first_bar_rng_bp", "first_bar_ret_bp", "rally_after_lo_bp"):
        med(sun, wk, c)
    for sgn, lab in ((sun.gap_open_bp < 0, "gap<0"), (sun.gap_open_bp > 0, "gap>0")):
        s = sun[sgn]; print(f"  P(low_in_first_bar | sunday, {lab}) = {s.low_in_first_bar.mean():.3f} (n={len(s)}); low_by_tokyo {s.low_by_tokyo_open.mean():.3f}")
    for sgn, lab in ((sun.is_down == 1, "Fri down"), (sun.is_down == 0, "Fri up")):
        s = sun[sgn]; print(f"  P(low_by_tokyo | sunday, {lab}) = {s.low_by_tokyo_open.mean():.3f} (n={len(s)}); low_in_first_bar {s.low_in_first_bar.mean():.3f}")
    big = wk[wk.first_bar_rng_bp >= 33]
    print(f"  weeknights first_bar_rng>=33: n={len(big)} low_in_first_bar={big.low_in_first_bar.mean():.3f} low_by_tokyo={big.low_by_tokyo_open.mean():.3f} high_in_first_bar={big.high_in_first_bar.mean():.3f}")
    # size-matched check: weeknights with first_bar_rng in same quantile band as sunday median
    # panel done rates
    done_rates(p, sun.index, "sunday", "low_done")
    done_rates(p, sun.index, "sunday", "high_done")
    # bar-1 rule: at close of bar 1, running low still the bar-0 low (bars_since_lo==1)
    d1 = p[(p.k == 1) & (p.bars_since_lo == 1)]
    s = d1[d1.date.isin(sun.index)]; b = d1[~d1.date.isin(sun.index)]
    print(f"  bar1 rule: P(low_done | k=1, bars_since_lo=1): sunday {s.low_done.mean():.3f} (n={len(s)}) vs weeknight {b.low_done.mean():.3f} (n={len(b)}) p={stats.binomtest(int(s.low_done.sum()), len(s), b.low_done.mean()).pvalue:.3f}")
    # also unconditional at k=1 for reference
    # how much of the Sunday low-early effect is first-bar gap/range? logistic-ish: stratify by first_bar_rng tercile
    x["fbr_q"] = pd.qcut(x.first_bar_rng_bp, 3, labels=["small", "mid", "large"])
    print("  low_in_first_bar by first-bar-range tercile, sunday vs weeknight:")
    for q in ["small", "mid", "large"]:
        s = x[(x.fbr_q == q) & (x.sunday_open == 1)]; b = x[(x.fbr_q == q) & (x.sunday_open == 0)]
        print(f"    {q}: sunday {s.low_in_first_bar.mean():.3f} (n={len(s)}) vs weeknight {b.low_in_first_bar.mean():.3f} (n={len(b)}); low_by_tokyo {s.low_by_tokyo_open.mean():.3f} vs {b.low_by_tokyo_open.mean():.3f}")

    # ---------------- E2 ----------------
    print("\n--- E2 Sunday: level placement / range ---")
    for c in ("high_above_rth_high", "low_below_rth_low", "both_inside", "asia_up", "close_loc_ext"):
        prop(sun, wk, c)
    for c in ("hi_vs_rth_high_bp", "lo_vs_rth_low_bp", "rng_bp", "hi_bp", "lo_bp", "asia_ret_bp"):
        med(sun, wk, c)

    # ---------------- E3 ----------------
    print("\n--- E3 Sunday after tier1 (NFP) ---")
    s3 = sun[sun.tier1_data_today == 1]; o3 = sun[sun.tier1_data_today == 0]
    print(f"  n sunday&tier1={len(s3)}, other sundays={len(o3)}")
    print("  events_today on those Sundays:", s3.events_today.value_counts().to_dict())
    for c in ("low_below_rth_low", "high_above_rth_high"):
        prop(s3, o3, c)
    for c in ("lo_vs_rth_low_bp", "rth_range_bp", "lo_bp", "rng_bp"):
        med(s3, o3, c)
    # is it just NFP? restrict to events_today containing NFP
    nfp = s3[s3.events_today.fillna("").str.contains("NFP|PAYROLL|payroll", case=False)]
    print(f"  NFP-only Sundays n={len(nfp)}: low_below_rth_low={nfp.low_below_rth_low.mean():.3f}")
    non = x[(x.tier1_data_today == 1) & (x.sunday_open == 0)]; nonb = x[(x.tier1_data_today == 0) & (x.sunday_open == 0)]
    print(f"  non-Sunday tier1 n={len(non)}: low_below={non.low_below_rth_low.mean():.3f} vs {nonb.low_below_rth_low.mean():.3f}")
    # Alternative: Friday RTH range relative to ATR
    med(s3, o3, "rth_range_atr")
    # is it the Friday RTH direction?  (NFP Fridays down?)
    print(f"  Fri is_down share: tier1 sundays {s3.is_down.mean():.2f} vs other sundays {o3.is_down.mean():.2f}; rth_ret med {s3.rth_ret.median():.4f} vs {o3.rth_ret.median():.4f}")
    for dd in (0, 1):
        a = s3[s3.is_down == dd]; b = o3[o3.is_down == dd]
        print(f"    is_down={dd}: tier1-sun low_below {a.low_below_rth_low.mean():.3f} (n={len(a)}) vs other-sun {b.low_below_rth_low.mean():.3f} (n={len(b)})")

    # ---------------- E4 ----------------
    print("\n--- E4 FOMC eve ---")
    f4 = x[x.fomc_tomorrow == 1]; o4 = x[x.fomc_tomorrow == 0]
    print(f"  n={len(f4)}; dates: {list(f4.index.strftime('%Y-%m-%d'))}")
    for c in ("hi_first", "hi_last", "lo_last", "low_in_first_bar", "close_above_ref", "asia_up"):
        prop(f4, o4, c)
    for c in ("hi_k", "close_loc", "asia_ret_bp", "drop_after_hi_bp", "rng_bp", "abs_gap"):
        med(f4, o4, c)
    done_rates(p, f4.index, "fomc_eve", "high_done")
    done_rates(p, f4.index, "fomc_eve", "low_done")

    # ---------------- E5 ----------------
    print("\n--- E5 FOMC night ---")
    f5 = x[x.fomc_today == 1]; o5 = x[x.fomc_today == 0]
    print(f"  n={len(f5)}")
    for c in ("low_in_first_bar", "either_last", "hi_first", "high_by_tokyo_open", "close_above_ref"):
        prop(f5, o5, c)
    for c in ("hi_bp", "rng_bp", "rally_after_lo_bp", "asia_ret_bp", "first_bar_rng_bp", "abs_gap"):
        med(f5, o5, c)
    done_rates(p, f5.index, "fomc_night", "low_done")
    done_rates(p, f5.index, "fomc_night", "high_done")

    # ---------------- E6 ----------------
    print("\n--- E6 megacap earnings ---")
    m6 = x[x.megacap_earnings_tonight == 1]; o6 = x[x.megacap_earnings_tonight == 0]
    print(f"  n={len(m6)}; sundays among them: {int(m6.sunday_open.sum())}")
    for c in ("high_in_first_bar", "low_in_first_bar", "either_last", "hi_last", "lo_last"):
        prop(m6, o6, c)
    for c in ("rng_bp", "first_bar_rng_bp", "abs_gap", "drop_after_hi_bp", "rally_after_lo_bp"):
        med(m6, o6, c)
    done_rates(p, m6.index, "megacap", "high_done", ks=[0, 1, 2])
    done_rates(p, m6.index, "megacap", "low_done", ks=[0, 1, 2])
    d0 = p[p.k == 0]
    print(f"  remaining_up at k=0 median: megacap {d0[d0.date.isin(m6.index)].remaining_up_bp.median():.1f} vs {d0[~d0.date.isin(m6.index)].remaining_up_bp.median():.1f}")

    # ---------------- E7 ----------------
    print("\n--- E7 megacap x sign(post_ret) ---")
    print(f"  post_ret units check: median |post_ret| all={x.post_ret.abs().median():.5f}; megacap={m6.post_ret.abs().median():.5f}")
    x["same_side_break"] = np.where(x.post_ret > 0, x.high_above_rth_high, np.where(x.post_ret < 0, x.low_below_rth_low, np.nan))
    x["opp_side_break"] = np.where(x.post_ret > 0, x.low_below_rth_low, np.where(x.post_ret < 0, x.high_above_rth_high, np.nan))
    m6 = x[x.megacap_earnings_tonight == 1]; o6 = x[x.megacap_earnings_tonight == 0]
    for c in ("same_side_break", "opp_side_break"):
        prop(m6, o6, c)
    for sg, lab in ((m6.post_ret > 0, "post>0"), (m6.post_ret < 0, "post<0")):
        s = m6[sg]
        if lab == "post>0":
            b = o6[o6.post_ret > 0]
            print(f"    {lab} n={len(s)}: P(high>RTH high)={s.high_above_rth_high.mean():.3f} vs non-earn post>0 {b.high_above_rth_high.mean():.3f}")
        else:
            b = o6[o6.post_ret < 0]
            print(f"    {lab} n={len(s)}: P(low<RTH low)={s.low_below_rth_low.mean():.3f} vs non-earn post<0 {b.low_below_rth_low.mean():.3f}")
    # |post_ret| size confound: non-earnings nights with |post_ret| >= 15bp
    ap = x.post_ret.abs() * (10000 if x.post_ret.abs().median() < 1 else 1)
    x["abs_post_bp"] = ap
    m6 = x[x.megacap_earnings_tonight == 1]; o6 = x[x.megacap_earnings_tonight == 0]
    big = x[(x.megacap_earnings_tonight == 0) & (x.abs_post_bp >= 15)]; small = x[(x.megacap_earnings_tonight == 0) & (x.abs_post_bp < 15)]
    print(f"  non-earn |post|>=15bp n={len(big)}: same_side {big.same_side_break.mean():.3f} vs <15bp {small.same_side_break.mean():.3f} (n={len(small)})")
    # matched on |post_ret|: earnings vs non-earnings in the same |post| band
    print(f"  megacap |post| median bp = {m6.abs_post_bp.median():.1f}; non-earn {o6.abs_post_bp.median():.1f}")
    for lo_, hi_ in ((15, 30), (30, 1e9)):
        a = m6[(m6.abs_post_bp >= lo_) & (m6.abs_post_bp < hi_)]; b = o6[(o6.abs_post_bp >= lo_) & (o6.abs_post_bp < hi_)]
        print(f"    |post| in [{lo_},{hi_}): earn same_side {a.same_side_break.mean():.3f} (n={len(a)}) vs non-earn {b.same_side_break.mean():.3f} (n={len(b)})")
    # logistic: same_side_break ~ megacap + abs_post_bp
    def logit_fit(X, y):
        X = np.asarray(X, float); y = np.asarray(y, float)
        X = np.column_stack([np.ones(len(X)), X])
        b = np.zeros(X.shape[1])
        for _ in range(50):
            pr = 1 / (1 + np.exp(-X @ b))
            W = pr * (1 - pr)
            H = X.T @ (X * W[:, None]); g = X.T @ (y - pr)
            step = np.linalg.solve(H + 1e-9 * np.eye(len(b)), g)
            b = b + step
            if np.abs(step).max() < 1e-8:
                break
        pr = 1 / (1 + np.exp(-X @ b)); W = pr * (1 - pr)
        cov = np.linalg.inv(X.T @ (X * W[:, None]))
        se = np.sqrt(np.diag(cov)); z = b / se
        pv = 2 * (1 - stats.norm.cdf(np.abs(z)))
        return b, se, pv
    dd = x.dropna(subset=["same_side_break", "abs_post_bp"])
    b, se, pv = logit_fit(dd[["megacap_earnings_tonight", "abs_post_bp"]], dd.same_side_break)
    print(f"  logit same_side ~ const + megacap + |post|bp: coef={np.round(b,4)} se={np.round(se,4)} p={np.round(pv,4)}")
    b, se, pv = logit_fit(dd[["megacap_earnings_tonight", "abs_post_bp", "sunday_open"]], dd.same_side_break)
    print(f"  logit same_side ~ const + megacap + |post|bp + sunday: coef={np.round(b,4)} p={np.round(pv,4)}")
    # log-|post| version (less leverage from extreme values)
    dd2 = dd.assign(lp=np.log1p(dd.abs_post_bp))
    b, se, pv = logit_fit(dd2[["megacap_earnings_tonight", "lp"]], dd2.same_side_break)
    print(f"  logit same_side ~ const + megacap + log1p(|post|bp): coef={np.round(b,4)} p={np.round(pv,4)}")
    # sunday-excluded base for fairness
    o6w = o6[o6.sunday_open == 0]
    print(f"  base same_side on weeknight non-earnings: {o6w.same_side_break.mean():.3f} (n={int(o6w.same_side_break.notna().sum())})")

    # ---------------- E8 ----------------
    print("\n--- E8 tier1 tomorrow ---")
    t8 = x[x.tier1_data_tomorrow == 1]; o8 = x[x.tier1_data_tomorrow == 0]
    print(f"  n={len(t8)}; sundays among: {int(t8.sunday_open.sum())}")
    for c in ("low_by_tokyo_open", "close_loc_ext", "either_last", "high_by_tokyo_open"):
        prop(t8, o8, c)
    for c in ("rng_bp", "abs_asia_ret", "hi_vs_rth_high_bp", "lo_vs_rth_low_bp"):
        med(t8, o8, c)
    done_rates(p, t8.index, "tier1_tmrw", "low_done", ks=[1, 2, 3, 4])
    # weeknight-only base (tier1 nights are never Sundays, so compare to weeknights)
    o8w = o8[o8.sunday_open == 0]
    print("  vs weeknight-only base:")
    for c in ("low_by_tokyo_open", "close_loc_ext", "either_last"):
        prop(t8, o8w, c, label=c + " (wk base)")
    pre_any = x[(x.tier1_data_tomorrow == 1) | (x.fomc_tomorrow == 1)]
    print(f"  pre_event_any close_loc_ext {pre_any.close_loc_ext.mean():.3f} (n={len(pre_any)}) vs {x[~x.index.isin(pre_any.index)].close_loc_ext.mean():.3f}")
    # close_loc distribution alternative thresholds
    for th in (0.1, 0.15, 0.2, 0.25, 0.3):
        a = ((t8.close_loc > 1 - th) | (t8.close_loc < th)).mean(); b = ((o8w.close_loc > 1 - th) | (o8w.close_loc < th)).mean()
        print(f"    close_loc_ext thr={th}: tier1 {a:.3f} vs wk {b:.3f}")

    # ---------------- E10 ----------------
    print("\n--- E10 China data weeknights ---")
    c10 = x[(x.cn_data_tonight == 1) & (x.sunday_open == 0)]; o10 = x[(x.cn_data_tonight == 0) & (x.sunday_open == 0)]
    print(f"  n={len(c10)} vs {len(o10)}; cn_data total {int(x.cn_data_tonight.sum())}, sundays {int(x[x.cn_data_tonight==1].sunday_open.sum())}")
    for c in ("either_last", "lo_last", "hi_last"):
        prop(c10, o10, c)
    for c in ("rng_bp", "abs_gap"):
        med(c10, o10, c)
    pw = p[p.date.isin(x[x.sunday_open == 0].index)]
    done_rates(pw, c10.index, "cn_weeknight", "high_done", ks=[5, 6, 7])
    done_rates(pw, c10.index, "cn_weeknight", "low_done", ks=[5, 6, 7])
    # n_bars check: are cn weeknights full sessions?
    print(f"  n_bars dist cn: {c10.n_bars.value_counts().to_dict()}; other: {o10.n_bars.value_counts().to_dict()}")
    full = x[x.n_bars == 9]
    c10f = full[(full.cn_data_tonight == 1) & (full.sunday_open == 0)]; o10f = full[(full.cn_data_tonight == 0) & (full.sunday_open == 0)]
    prop(c10f, o10f, "either_last", label="either_last (9-bar only)")

    # ---------------- E11 ----------------
    print("\n--- E11 short / holiday eve ---")
    sh = x[x.n_bars < 9]; fu = x[x.n_bars == 9]
    print(f"  short n={len(sh)} n_bars={sh.n_bars.value_counts().to_dict()}; holiday_tomorrow n={int(x.holiday_tomorrow.sum())}; pre_holiday n={int(x.pre_holiday.sum())}; overlap {int(((x.holiday_tomorrow==1)&(x.pre_holiday==1)).sum())}")
    print(f"  short dates: {list(sh.index.strftime('%Y-%m-%d'))}")
    for c in ("rng_bp", "rally_after_lo_bp", "drop_after_hi_bp", "first_bar_rng_bp", "abs_asia_ret"):
        med(sh, fu, c, label=c + " short")
    ht = x[x.holiday_tomorrow == 1]; oh = x[x.holiday_tomorrow == 0]
    for c in ("rng_bp", "rally_after_lo_bp", "drop_after_hi_bp", "first_bar_rng_bp", "abs_asia_ret"):
        med(ht, oh, c, label=c + " holiday_tmrw")
    for c in ("low_in_first_bar", "high_in_first_bar"):
        prop(sh, fu, c, label=c + " short")
    print(f"  short hi_frac med {(sh.hi_k/sh.last_k).median():.2f} lo_frac {(sh.lo_k/sh.last_k).median():.2f}; full {(fu.hi_k/fu.last_k).median():.2f} / {(fu.lo_k/fu.last_k).median():.2f}")
    ph = x[x.pre_holiday == 1]; oph = x[x.pre_holiday == 0]
    med(ph, oph, "hi_bp", label="hi_bp pre_holiday"); med(ph, oph, "rng_bp", label="rng pre_holiday")

    # ---------------- E12 ----------------
    print("\n--- E12 gap / month_end ---")
    me = x[x.month_end == 1]; ome = x[(x.month_end == 0) & (x.sunday_open == 0)]
    print(f"  month_end n={len(me)}, sundays among {int(me.sunday_open.sum())}")
    med(me, ome, "abs_gap", label="abs_gap month_end vs weeknights")
    me_w = me[me.sunday_open == 0]
    med(me_w, ome, "abs_gap", label="abs_gap month_end WEEKNIGHT only")
    for c in ("low_by_tokyo_open", "low_in_first_bar", "both_first"):
        prop(me, ome, c, label=c + " month_end vs wk")
        prop(me_w, ome, c, label=c + " month_end weeknight-only")
    for fl in ("sunday_open", "cn_policy_tonight", "opex_today", "megacap_earnings_tonight", "fomc_today", "tier1_data_today", "fomc_tomorrow"):
        s = x[x[fl] == 1]; print(f"    |gap| median {fl}: {s.abs_gap.median():.1f} (n={len(s)}) vs complement {x[x[fl]==0].abs_gap.median():.1f}")
    s = x[(x.cn_data_tonight == 1) & (x.sunday_open == 0)]; print(f"    |gap| cn_data non-sunday {s.abs_gap.median():.1f}")
    # gap size vs first-bar extremes (pooled)
    x["gap_q"] = pd.qcut(x.abs_gap, 4, labels=["q1", "q2", "q3", "q4"])
    print("  either_first by |gap| quartile:", x.groupby("gap_q", observed=True).either_first.mean().round(3).to_dict(),
          " low_in_first:", x.groupby("gap_q", observed=True).low_in_first_bar.mean().round(3).to_dict(),
          " high_in_first:", x.groupby("gap_q", observed=True).high_in_first_bar.mean().round(3).to_dict())
    wkx = x[x.sunday_open == 0]
    print("  WEEKNIGHT either_first by |gap| quartile:", wkx.groupby("gap_q", observed=True).either_first.mean().round(3).to_dict(),
          " low_in_first:", wkx.groupby("gap_q", observed=True).low_in_first_bar.mean().round(3).to_dict())

    # ---------------- E13 ----------------
    print("\n--- E13 opex Sundays ---")
    op = x[x.opex_today == 1]; osun = x[(x.opex_today == 0) & (x.sunday_open == 1)]
    print(f"  opex n={len(op)}, all sundays? {op.sunday_open.mean()}; witching n={int(x.witching_today.sum())} all sundays? {x[x.witching_today==1].sunday_open.mean()}")
    for c in ("lo_last", "hi_last", "either_last"):
        prop(op, osun, c)
    for c in ("first_bar_ret_bp", "abs_gap"):
        med(op, osun, c)
    w = x[x.witching_today == 1]
    print(f"  witching either_last {w.either_last.mean():.2f} (n={len(w)}); dates {list(w.index.strftime('%Y-%m-%d'))}; other-sunday either_last {osun.either_last.mean():.3f}")
