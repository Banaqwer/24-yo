"""Detail tables for the findings: direction asymmetry, level-distance deciles, Sunday/Monday,
FOMC-tomorrow, volatility-scale terciles, with/against extension asymmetry."""
import sys, warnings
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
OUT = "research/extremes/scripts/lens_context"
rng = np.random.default_rng(3)
pd.set_option("display.width", 250)


def ci(x, B=2000, stat=np.mean):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 5:
        return (np.nan, np.nan)
    idx = rng.integers(0, len(x), (B, len(x)))
    return tuple(np.quantile(stat(x[idx], axis=1), [0.05, 0.95]))


def rate_row(df, mask, t, label):
    x = df.loc[mask, t].dropna()
    lo, hi = ci(x)
    h1 = df.loc[mask & (df.half == "H1"), t].dropna(); h2 = df.loc[mask & (df.half == "H2"), t].dropna()
    return dict(group=label, target=t, n=len(x), rate=x.mean(), ci_lo=lo, ci_hi=hi, n_h1=len(h1), rate_h1=h1.mean(),
                n_h2=len(h2), rate_h2=h2.mean())


def fisher(df, mask, t):
    ct = pd.crosstab(mask, df[t]).values
    return stats.fisher_exact(ct)[1] if ct.shape == (2, 2) else np.nan


def run(sym):
    df = pd.read_csv(f"{OUT}/frame_{sym}.csv", index_col=0, parse_dates=True).sort_index()
    raw = pd.read_csv(f"./research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    df = df.join(raw[["close_bp", "asia_ret_bp", "open_bp", "first_bar_ret_bp"]])
    out = {}
    # ---- A. direction asymmetry: is_down x targets ----
    rows = []
    for t in ["hi_first", "high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar",
              "high_by_tokyo_open", "low_by_tokyo_open", "high_above_rth_high", "low_below_rth_low",
              "with_in_first_bar", "against_in_first_bar", "with_in_last_bar", "against_in_last_bar",
              "with_beyond_rth", "against_beyond_rth", "close_top20", "close_bot20", "close_with_dir", "with_first"]:
        for v, lab in [(0, "up_day"), (1, "down_day")]:
            r = rate_row(df, df.is_down == v, t, lab); r["p_fisher"] = fisher(df.dropna(subset=[t]), df.dropna(subset=[t]).is_down == 1, t)
            rows.append(r)
    A = pd.DataFrame(rows); A.to_csv(f"{OUT}/tab_direction_{sym}.csv", index=False)
    print("== A. is_down x targets ==\n", A.round(3).to_string(index=False))

    # ---- B. level-distance deciles ----
    for f, t in [("dist_rth_high0", "high_above_rth_high"), ("dist_rth_low0", "low_below_rth_low")]:
        x = df[f].abs() if f == "dist_rth_low0" else df[f]
        # also scaled by the ex-ante expected range
        scaled = x / (df["asia_rng_med20"] * 1e4)
        for name, v in [(f, x), (f + "/asia_rng_med20", scaled)]:
            sub = df.assign(v=v).dropna(subset=["v", t])
            sub["dec"] = pd.qcut(sub["v"], 10, labels=False, duplicates="drop")
            g = sub.groupby("dec").agg(n=(t, "size"), v_min=("v", "min"), v_med=("v", "median"), v_max=("v", "max"), rate=(t, "mean"),
                                       rate_h1=(t, lambda s: s[sub.loc[s.index, "half"] == "H1"].mean()),
                                       rate_h2=(t, lambda s: s[sub.loc[s.index, "half"] == "H2"].mean()))
            g["ci_lo"], g["ci_hi"] = zip(*[ci(sub.loc[sub.dec == d, t]) for d in g.index])
            g.to_csv(f"{OUT}/tab_decile_{name.replace('/', '_over_')}_{sym}.csv")
            print(f"== B. deciles of {name} -> {t} (base {sub[t].mean():.3f}) ==\n", g.round(3).to_string())
        # fixed cut-offs useful for a rule
        for cut in [5, 10, 15, 20, 30, 50]:
            m = x <= cut
            r = rate_row(df, m, t, f"{f}<= {cut}bp"); r["p_fisher"] = fisher(df, m, t)
            print(f"   {f} <= {cut} bp: n={r['n']} rate={r['rate']:.3f} [{r['ci_lo']:.3f},{r['ci_hi']:.3f}] H1 {r['rate_h1']:.3f} H2 {r['rate_h2']:.3f}")
        for cut in [50, 80, 120]:
            m = x > cut
            r = rate_row(df, m, t, f"{f} > {cut}bp")
            print(f"   {f} >  {cut} bp: n={r['n']} rate={r['rate']:.3f} [{r['ci_lo']:.3f},{r['ci_hi']:.3f}] H1 {r['rate_h1']:.3f} H2 {r['rate_h2']:.3f}")

    # ---- C. Sunday / Monday ----
    rows = []
    for lab, m in [("sunday_reopen(dow=4)", df.dow == 4), ("monday(dow=0)", df.dow == 0), ("tue-thu", df.dow.isin([1, 2, 3]))]:
        for t in ["low_in_first_bar", "high_in_first_bar", "low_by_tokyo_open", "high_by_tokyo_open", "low_in_last_bar",
                  "high_in_last_bar", "hi_first", "high_above_rth_high", "low_below_rth_low", "close_top20", "close_bot20"]:
            r = rate_row(df, m, t, lab); r["p_fisher_vs_rest"] = fisher(df, m, t); rows.append(r)
    C = pd.DataFrame(rows); C.to_csv(f"{OUT}/tab_dow_{sym}.csv", index=False)
    print("== C. Sunday / Monday ==\n", C.round(3).to_string(index=False))
    sun = df[df.dow == 4]
    print("   Sunday: median hi_bp %.1f lo_bp %.1f rng %.1f | rest: %.1f %.1f %.1f" % (
        sun.hi_bp.median(), sun.lo_bp.median(), sun.rng_bp.median(),
        df[df.dow != 4].hi_bp.median(), df[df.dow != 4].lo_bp.median(), df[df.dow != 4].rng_bp.median()))
    print("   Sunday lo_k dist:", sun.lo_k.value_counts().sort_index().to_dict(), " hi_k dist:", sun.hi_k.value_counts().sort_index().to_dict())
    print("   Monday lo_k dist:", df[df.dow == 0].lo_k.value_counts().sort_index().to_dict())

    # ---- D. FOMC tomorrow / today / megacap earnings ----
    rows = []
    for lab, m in [("fomc_tomorrow", df.fomc_tomorrow == 1), ("fomc_today", df.fomc_today == 1),
                   ("megacap_earnings_tonight", df.megacap_earnings_tonight == 1), ("tier1_data_tomorrow", df.tier1_data_tomorrow == 1),
                   ("boj_tonight", df.boj_tonight == 1), ("cn_data_tonight", df.cn_data_tonight == 1), ("pre_holiday", df.pre_holiday == 1),
                   ("month_end", df.month_end == 1), ("opex_today", df.opex_today == 1)]:
        for t in ["hi_first", "high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar", "close_top20", "close_bot20",
                  "high_above_rth_high", "low_below_rth_low"]:
            r = rate_row(df, m, t, lab); r["p_fisher"] = fisher(df, m, t); rows.append(r)
        s = df[m]
        print(f"   {lab}: n={m.sum()} median hi_bp {s.hi_bp.median():.1f} lo_bp {s.lo_bp.median():.1f} rng {s.rng_bp.median():.1f} close_loc mean {s.close_loc.mean():.2f} asia_ret_bp median {s.asia_ret_bp.median() if 'asia_ret_bp' in s else float('nan'):.1f} hi_k mean {s.hi_k.mean():.2f} lo_k mean {s.lo_k.mean():.2f}")
    D = pd.DataFrame(rows); D.to_csv(f"{OUT}/tab_calendar_{sym}.csv", index=False)
    print("== D. calendar flags (p<0.05 only) ==\n", D[D.p_fisher < 0.05].round(3).to_string(index=False))

    # ---- E. volatility scale terciles -> magnitudes ----
    rows = []
    for f in ["vix", "asia_rng_med20", "asia_rng_prev", "rth_range_atr", "dist_20d_high", "mag", "rv_ratio", "vix_z20"]:
        sub = df.dropna(subset=[f])
        g = pd.qcut(sub[f], 3, labels=["T1", "T2", "T3"])
        for lab in ["T1", "T2", "T3"]:
            s = sub[g == lab]
            r = dict(feature=f, tercile=lab, n=len(s), f_min=s[f].min(), f_max=s[f].max())
            for t in ["rng_bp", "hi_bp", "lo_bp", "with_ext_bp", "against_ext_bp"]:
                lo, hi = ci(s[t], stat=np.median)
                r[f"{t}_med"] = s[t].median(); r[f"{t}_ci"] = f"[{lo:.0f},{hi:.0f}]"
                r[f"{t}_med_h1"] = s[s.half == "H1"][t].median(); r[f"{t}_med_h2"] = s[s.half == "H2"][t].median()
            r["rng_p90"] = s.rng_bp.quantile(0.9)
            rows.append(r)
    E = pd.DataFrame(rows); E.to_csv(f"{OUT}/tab_volscale_{sym}.csv", index=False)
    print("== E. vol-scale terciles ==\n", E[["feature", "tercile", "n", "f_min", "f_max", "rng_bp_med", "rng_bp_ci", "rng_bp_med_h1", "rng_bp_med_h2", "hi_bp_med", "lo_bp_med", "rng_p90"]].round(2).to_string(index=False))

    # ---- F. with / against extension asymmetry ----
    rows = []
    for lab, m in [("all", df.index == df.index), ("up_day", df.is_down == 0), ("down_day", df.is_down == 1)]:
        for f in ["mag", "ext_in_dir", "vwap_in_dir", "stretch20_in_dir", "post_in_dir", "abs_streak"]:
            sub = df[m].dropna(subset=[f])
            g = pd.qcut(sub[f].rank(method="first"), 3, labels=["T1", "T2", "T3"]) if f != "abs_streak" else sub[f].clip(upper=3).astype(int).astype(str)
            for lab2 in sorted(g.unique()):
                s = sub[g == lab2]
                dlo, dhi = ci(s.with_ext_bp - s.against_ext_bp, stat=np.median)
                plo, phi = ci((s.with_ext_bp > s.against_ext_bp).astype(float))
                rows.append(dict(day=lab, feature=f, tercile=lab2, n=len(s), with_med=s.with_ext_bp.median(), against_med=s.against_ext_bp.median(),
                                 diff_med=(s.with_ext_bp - s.against_ext_bp).median(), diff_ci_lo=dlo, diff_ci_hi=dhi,
                                 p_with_gt=(s.with_ext_bp > s.against_ext_bp).mean(), p_ci_lo=plo, p_ci_hi=phi,
                                 p_with_gt_h1=(s[s.half == "H1"].with_ext_bp > s[s.half == "H1"].against_ext_bp).mean(),
                                 p_with_gt_h2=(s[s.half == "H2"].with_ext_bp > s[s.half == "H2"].against_ext_bp).mean(),
                                 close_loc_in_dir_mean=s.close_loc_in_dir.mean()))
    F = pd.DataFrame(rows); F.to_csv(f"{OUT}/tab_with_against_{sym}.csv", index=False)
    print("== F. with/against extension ==\n", F.round(3).to_string(index=False))
    # overall asymmetry
    for lab, m in [("all", df.index == df.index), ("up_day", df.is_down == 0), ("down_day", df.is_down == 1)]:
        s = df[m]
        print(f"   {lab}: n={len(s)} median with_ext {s.with_ext_bp.median():.1f} against_ext {s.against_ext_bp.median():.1f} P(with>against) {(s.with_ext_bp > s.against_ext_bp).mean():.3f} "
              f"H1 {(s[s.half=='H1'].with_ext_bp > s[s.half=='H1'].against_ext_bp).mean():.3f} H2 {(s[s.half=='H2'].with_ext_bp > s[s.half=='H2'].against_ext_bp).mean():.3f} "
              f"close_loc_in_dir mean {s.close_loc_in_dir.mean():.3f} top20 {s.close_top20.mean():.3f} bot20 {s.close_bot20.mean():.3f}")

    # ---- G. first-bar extreme vs post-close bar / mag ----
    rows = []
    for f in ["abs_post", "mag", "rth_range_atr", "rth_vol_rel", "vix_z20"]:
        sub = df.dropna(subset=[f]); g = pd.qcut(sub[f], 5, labels=False)
        for q in range(5):
            s = sub[g == q]
            r = dict(feature=f, quint=q, n=len(s), f_med=s[f].median())
            for t in ["high_in_first_bar", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar", "same_bar_extremes"]:
                r[t] = s[t].mean()
            r["first_bar_rng_share"] = np.nan
            rows.append(r)
    G = pd.DataFrame(rows); G.to_csv(f"{OUT}/tab_firstbar_quint_{sym}.csv", index=False)
    print("== G. first/last bar by quintile ==\n", G.round(3).to_string(index=False))

    # ---- H. base rates by half and the Asia drift ----
    for lab, s in [("all", df), ("H1", df[df.half == "H1"]), ("H2", df[df.half == "H2"])]:
        print(f"   {lab}: n={len(s)} low_in_first {s.low_in_first_bar.mean():.3f} high_in_first {s.high_in_first_bar.mean():.3f} "
              f"low_in_last {s.low_in_last_bar.mean():.3f} high_in_last {s.high_in_last_bar.mean():.3f} hi_first {s.hi_first.mean():.3f} "
              f"median close_bp {s.close_bp.median() if 'close_bp' in s else float('nan'):.1f} median hi_bp {s.hi_bp.median():.1f} lo_bp {s.lo_bp.median():.1f} "
              f"P(hi_bp>-lo_bp) {(s.hi_bp > -s.lo_bp).mean():.3f} close_loc mean {s.close_loc.mean():.3f}")


if __name__ == "__main__":
    for sym in sys.argv[1:] or ["NQ"]:
        run(sym)
