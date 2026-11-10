"""Follow-ups: Monday ex-2025Q4, Sunday in 2026, C12 mean asymmetry, C13 mag top-decile vs VIX, C11 dow mixture."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "research/extremes/scripts/refute_context_regime")
from common import *

for sym in ("NQ", "ES"):
    f = load(sym)
    raw = pd.read_csv(f"./research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    f = f.join(raw[["close_bp"]])
    print(f"\n==================== {sym} ====================")
    mon = f.monday == 1; sun = f.sunday == 1; tt = f.dow.isin([1, 2, 3])
    # ---- C6 Monday without 2025Q4 ----
    print("C6 Monday effects excluding 2025Q4 (the 13-Monday quarter with hi_first 13/13):")
    ex = f.quarter != "2025Q4"
    for t in ("low_in_first_bar", "low_by_tokyo_open", "hi_first", "high_in_first_bar", "low_in_last_bar"):
        r_all = rate_diff(f, mon, ~mon, t); r_ex = rate_diff(f, mon & ex, ~mon & ex, t); r_q = rate_diff(f, mon & ~ex, ~mon & ~ex, t)
        print(f"  {t}: all {r_all['p_a']:.3f} vs {r_all['p_b']:.3f} (p={r_all['p']:.3g}) | ex-2025Q4 {r_ex['p_a']:.3f} vs {r_ex['p_b']:.3f} (n={r_ex['n_a']}, p={r_ex['p']:.3g}) | 2025Q4 only {r_q['p_a']:.3f} vs {r_q['p_b']:.3f} (n={r_q['n_a']})")
    # Monday by year
    f["year"] = f.index.year
    print("  Monday by year:", f[mon].groupby("year")[["low_in_first_bar", "low_by_tokyo_open", "hi_first", "low_in_last_bar"]].mean().round(3).to_dict("index"))
    print("  Rest by year:", f[~mon].groupby("year")[["low_in_first_bar", "low_by_tokyo_open", "hi_first", "low_in_last_bar"]].mean().round(3).to_dict("index"))
    # ---- C5 Sunday by year ----
    print("C5 Sunday by year:", f[sun].groupby("year")[["low_by_tokyo_open", "low_in_first_bar", "close_bp"]].agg(["mean", "count"]).round(3).to_dict("index"))
    print("   rest by year:", f[~sun].groupby("year")[["low_by_tokyo_open", "low_in_first_bar"]].mean().round(3).to_dict("index"))
    y26 = f.year == 2026
    r = rate_diff(f, sun & y26, ~sun & y26, "low_by_tokyo_open"); print(f"   2026 only: sunday {r['p_a']:.3f} (n={r['n_a']}) rest {r['p_b']:.3f} (n={r['n_b']}) p={r['p']:.3g}")
    r = rate_diff(f, sun & ~y26, ~sun & ~y26, "low_by_tokyo_open"); print(f"   2024-25: sunday {r['p_a']:.3f} (n={r['n_a']}) rest {r['p_b']:.3f} (n={r['n_b']}) p={r['p']:.3g}")
    r = rate_diff(f, sun & y26, ~sun & y26, "low_in_first_bar"); print(f"   2026 only low_in_first_bar: sunday {r['p_a']:.3f} rest {r['p_b']:.3f} p={r['p']:.3g}")
    # ---- C12 mean asymmetry ----
    d = (f["with_ext_bp"] - f["against_ext_bp"]).dropna()
    print(f"C12 mean(with-against) {d.mean():.2f} bp CI {np.round(boot_ci(d.values), 2)}; median {d.median():.2f}; Wilcoxon p {stats.wilcoxon(d).pvalue:.3g}; mean with {f.with_ext_bp.mean():.1f} against {f.against_ext_bp.mean():.1f}; P90 with {f.with_ext_bp.quantile(.9):.1f} against {f.against_ext_bp.quantile(.9):.1f}")
    for lab, m in (("up", f.is_down == 0), ("down", f.is_down == 1)):
        dd = d[m[d.index]]
        print(f"   {lab}: mean {dd.mean():.2f} CI {np.round(boot_ci(dd.values), 2)} median {dd.median():.2f} P(with>against) {(dd > 0).mean():.3f}")
    # ---- C13: mag top decile controlling for vol ----
    f["rng_rel"] = f["rng_bp"] / (f["asia_rng_med20"] * 1e4)
    big = f["mag"] >= f["mag"].quantile(0.9)
    print(f"C13 mag top decile: median rng_rel {f.loc[big,'rng_rel'].median():.2f} vs rest {f.loc[~big,'rng_rel'].median():.2f}, MWU p {stats.mannwhitneyu(f.loc[big,'rng_rel'].dropna(), f.loc[~big,'rng_rel'].dropna()).pvalue:.3g}; median vix top-decile {f.loc[big,'vix'].median():.1f} vs {f.loc[~big,'vix'].median():.1f}")
    f["_vt"] = pd.qcut(f["vix"], 3, labels=["T1", "T2", "T3"])
    for v in ("T1", "T2", "T3"):
        m = f._vt == v
        a = f.loc[m & big, "rng_bp"]; b = f.loc[m & ~big, "rng_bp"]
        print(f"   VIX {v}: top-decile-mag median rng {a.median():.1f} (n={len(a)}) vs rest {b.median():.1f} (n={len(b)}) MWU p {stats.mannwhitneyu(a.dropna(), b.dropna()).pvalue if len(a)>2 else np.nan:.3g}")
    print("   Spearman(mag, rng_rel):", spearman(f.mag.values.astype(float), f.rng_rel.values.astype(float)))
    print("   Spearman(mag, rng_bp) by year:", {yr: round(spearman(g.mag.values.astype(float), g.rng_bp.values.astype(float))[0], 3) for yr, g in f.groupby("year")})
    # ---- C11 dow mixture ----
    print("C11 d0 (low0-high0) by dow:", f.groupby("dow").apply(lambda g: round((g.low_in_first_bar - g.high_in_first_bar).mean(), 3)).to_dict(),
          " d8 (high8-low8) by dow:", f.groupby("dow").apply(lambda g: round((g.high_in_last_bar - g.low_in_last_bar).mean(), 3)).to_dict())
    d8 = (f.high_in_last_bar - f.low_in_last_bar)
    print(f"   d8 overall {d8.mean():.3f} CI {np.round(boot_ci(d8.values), 3)}; by half:", d8.groupby(f.half).mean().round(3).to_dict(), "; by year:", d8.groupby(f.year).mean().round(3).to_dict())
    d0 = (f.low_in_first_bar - f.high_in_first_bar)
    print(f"   d0 overall {d0.mean():.3f} CI {np.round(boot_ci(d0.values), 3)}; by year:", d0.groupby(f.year).mean().round(3).to_dict())
    # ---- C8 close_top20 by year, close_with_dir by year ----
    for t in ("close_top20", "close_with_dir"):
        print(f"C8 {t} down vs up by year:", {yr: (round(g.loc[g.is_down == 1, t].mean(), 3), round(g.loc[g.is_down == 0, t].mean(), 3)) for yr, g in f.groupby("year")})
    # ---- C9 hi_first direction by year ----
    print("C9 hi_first up vs down by year:", {yr: (round(g.loc[g.is_down == 0, 'hi_first'].mean(), 3), round(g.loc[g.is_down == 1, 'hi_first'].mean(), 3), len(g)) for yr, g in f.groupby("year")})
    # ---- C4: VIX tercile median range ex-tariff, by year ----
    print("C4 Spearman(vix, rng_bp) by year:", {yr: round(spearman(g.vix.values.astype(float), g.rng_bp.values.astype(float))[0], 3) for yr, g in f.groupby("year")})
