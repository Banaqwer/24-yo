"""Independent recompute of the descriptive 'context' claims from the raw extremes CSVs."""
import sys
import numpy as np
import pandas as pd
from scipy import stats
import warnings
warnings.filterwarnings("ignore")

ROOT = "."
rng = np.random.default_rng(123)
ARTEFACTS = {"NQ": ["2025-09-16", "2024-06-21", "2024-12-20", "2025-03-21"], "ES": ["2025-12-16", "2025-12-17"]}


def load(sym):
    df = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True).sort_index()
    drop = [pd.Timestamp(d) for d in ARTEFACTS[sym] if pd.Timestamp(d) in df.index]
    df = df.drop(index=drop)
    ref = df["ref_close"]
    df["dist_rth_high0"] = (df["lvl_rth_high"] / ref - 1) * 1e4
    df["dist_rth_low0"] = (df["lvl_rth_low"] / ref - 1) * 1e4
    df["sd_high"] = df["dist_rth_high0"] / (df["asia_rng_med20"] * 1e4)
    df["sd_low"] = -df["dist_rth_low0"] / (df["asia_rng_med20"] * 1e4)
    d = np.where(df["is_down"] == 1, -1.0, 1.0)
    df["dir"] = d
    df["with_ext_bp"] = np.where(d > 0, df["hi_bp"], -df["lo_bp"])
    df["against_ext_bp"] = np.where(d > 0, -df["lo_bp"], df["hi_bp"])
    df["close_loc_in_dir"] = np.where(d > 0, df["close_loc"], 1 - df["close_loc"])
    df["close_top20"] = (df["close_loc"] >= 0.8).astype(int)
    df["close_bot20"] = (df["close_loc"] <= 0.2).astype(int)
    df["close_with_dir"] = (df["close_loc_in_dir"] >= 0.5).astype(int)
    df["abs_post"] = df["post_ret"].abs()
    df["half"] = np.where(df.index < pd.Timestamp("2025-09-01"), "H1", "H2")
    return df


def boot_rate_ci(y, B=4000):
    y = np.asarray(y, float); y = y[~np.isnan(y)]
    n = len(y)
    if n == 0:
        return (np.nan, np.nan)
    idx = rng.integers(0, n, (B, n))
    m = y[idx].mean(1)
    return tuple(np.round(np.quantile(m, [0.05, 0.95]), 3))


def rate_line(name, y, base=None):
    y = np.asarray(y, float); y = y[~np.isnan(y)]
    n = len(y); r = y.mean() if n else np.nan
    ci = boot_rate_ci(y)
    s = f"{name}: n={n} rate={r:.3f} CI90={ci}"
    if base is not None:
        k = int(y.sum())
        p = stats.binomtest(k, n, base).pvalue if n else np.nan
        s += f" base={base:.3f} binom_p={p:.2e}"
    return s


def fisher(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    t = [[int(a.sum()), int(len(a) - a.sum())], [int(b.sum()), int(len(b) - b.sum())]]
    return stats.fisher_exact(t)[1]


def by_half(df, mask, col):
    out = []
    for h in ("H1", "H2"):
        m = mask & (df["half"] == h)
        y = df.loc[m, col].dropna()
        out.append(f"{h}: n={len(y)} rate={y.mean():.3f}")
    return " | ".join(out)


def main(sym):
    df = load(sym)
    print(f"\n######## {sym}: n={len(df)}  H1={int((df.half=='H1').sum())} H2={int((df.half=='H2').sum())}")

    # ---------------- C1 / C2: level distance buckets ----------------
    for side, dcol, scol, tcol in [("HIGH", "dist_rth_high0", "sd_high", "high_above_rth_high"),
                                   ("LOW", "dist_rth_low0", "sd_low", "low_below_rth_low")]:
        print(f"\n== C1/C2 {side}: base {tcol} = {df[tcol].mean():.3f} (n={len(df)})")
        dist = df[dcol] if side == "HIGH" else df[dcol].abs()
        print(f"  sessions with 17:00 close already beyond the RTH {side}: {(df[dcol] < 0).sum() if side=='HIGH' else (df[dcol] > 0).sum()} ; target rate among them {df.loc[(df[dcol] < 0) if side=='HIGH' else (df[dcol] > 0), tcol].mean():.3f}")
        for lab, m in [("<=10bp", dist <= 10), ("<=20bp", dist <= 20), ("<=30bp", dist <= 30), ("<=50bp", dist <= 50),
                       (">50bp", dist > 50), (">80bp", dist > 80), (">120bp", dist > 120)]:
            y = df.loc[m, tcol]
            print(f"  {lab:8s} n={len(y):3d} rate={y.mean():.3f} CI90={boot_rate_ci(y)}  {by_half(df, m, tcol)}")
        sd = df[scol]
        print(f"  scaled (n with asia_rng_med20 = {sd.notna().sum()})")
        edges = [(-np.inf, 0.10), (0.10, 0.25), (0.25, 0.50), (0.50, 0.75), (0.75, 1.0), (1.0, 1.5), (1.5, np.inf)]
        for lo, hi in edges:
            m = (sd > lo) & (sd <= hi)
            y = df.loc[m, tcol]
            print(f"  ({lo:>5},{hi:>5}] n={len(y):3d} rate={y.mean():.3f} CI90={boot_rate_ci(y)}  {by_half(df, m, tcol)}")
        # MWU of distance between target groups
        a = dist[df[tcol] == 1].dropna(); b = dist[df[tcol] == 0].dropna()
        print(f"  MWU p(dist | target) = {stats.mannwhitneyu(a, b).pvalue:.2e}; AUC(dist) = {stats.mannwhitneyu(b, a).statistic/(len(a)*len(b)):.3f}")
        # sanity: dist sign
        print(f"  sign check: {dcol} min={df[dcol].min():.1f} max={df[dcol].max():.1f}; frac<0 (close above RTH high / below low)={(df[dcol] < 0).mean() if side=='HIGH' else (df[dcol] > 0).mean():.3f}")

    # ---------------- C3: direction ----------------
    print("\n== C3 direction")
    up = df["is_down"] == 0; dn = df["is_down"] == 1
    for t in ["high_above_rth_high", "low_below_rth_low"]:
        print(f"  {t}: up n={up.sum()} {df.loc[up,t].mean():.3f} CI{boot_rate_ci(df.loc[up,t])} | down n={dn.sum()} {df.loc[dn,t].mean():.3f} CI{boot_rate_ci(df.loc[dn,t])} | fisher p={fisher(df.loc[up,t], df.loc[dn,t]):.2e}")
        print(f"     up: {by_half(df, up, t)} || down: {by_half(df, dn, t)}")
    # does is_down add on top of scaled distance? logistic in-sample LR test
    from sklearn.linear_model import LogisticRegression
    def llf(X, y):
        m = LogisticRegression(C=1e6, max_iter=5000).fit(X, y)
        p = m.predict_proba(X)[:, 1]
        return np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)), m
    for t, scol in [("high_above_rth_high", "sd_high"), ("low_below_rth_low", "sd_low")]:
        sub = df[[t, scol, "is_down"]].dropna()
        x = np.log1p(sub[[scol]].clip(lower=0).values)
        l0, _ = llf(x, sub[t].values); l1, m1 = llf(np.hstack([x, sub[["is_down"]].values]), sub[t].values)
        lr = 2 * (l1 - l0)
        print(f"  {t}: LR test adding is_down to log1p({scol}): LR={lr:.2f} p={stats.chi2.sf(lr,1):.3g}; coef is_down={m1.coef_[0][1]:.3f}")

    # ---------------- C5 / C6: Sunday / Monday ----------------
    print("\n== C5 Sunday (dow=4) / C6 Monday (dow=0)")
    for lab, m in [("SUN", df["dow"] == 4), ("MON", df["dow"] == 0)]:
        rest = ~m
        print(f" {lab}: n={m.sum()} rest n={rest.sum()}")
        for t in ["low_by_tokyo_open", "low_in_first_bar", "high_by_tokyo_open", "high_in_first_bar", "hi_first", "low_in_last_bar", "high_in_last_bar"]:
            a = df.loc[m, t]; b = df.loc[rest, t]
            print(f"   {t:20s} {a.mean():.3f} CI{boot_rate_ci(a)} vs rest {b.mean():.3f} CI{boot_rate_ci(b)} fisher p={fisher(a,b):.2e} | {by_half(df, m, t)}")
        print(f"   lo_k==0: {(df.loc[m,'lo_k']==0).sum()}/{m.sum()}  lo_k==8: {(df.loc[m,'lo_k']==8).sum()}/{m.sum()}  n_bars==9 frac: {(df.loc[m,'n_bars']==9).mean():.3f}")
        print(f"   median close_bp {df.loc[m,'close_bp'].median():.1f} vs rest {df.loc[rest,'close_bp'].median():.1f}; P(close_bp>0) {(df.loc[m,'close_bp']>0).mean():.3f} vs {(df.loc[rest,'close_bp']>0).mean():.3f}; median hi_bp {df.loc[m,'hi_bp'].median():.1f} vs {df.loc[rest,'hi_bp'].median():.1f}; lo_bp {df.loc[m,'lo_bp'].median():.1f} vs {df.loc[rest,'lo_bp'].median():.1f}")
        for dst in (0, 1):
            mm = m & (df["is_dst"] == dst)
            print(f"   is_dst={dst} tokyo_open_k={df.loc[mm,'tokyo_open_k'].unique()} n={mm.sum()} low_by_tokyo {df.loc[mm,'low_by_tokyo_open'].mean():.3f} low_in_first {df.loc[mm,'low_in_first_bar'].mean():.3f} hi_first {df.loc[mm,'hi_first'].mean():.3f} | rest same dst: low_by_tokyo {df.loc[(~m)&(df.is_dst==dst),'low_by_tokyo_open'].mean():.3f} (n={((~m)&(df.is_dst==dst)).sum()})")
        if lab == "SUN":
            gdn = m & (df["open_bp"] < 0); gup = m & (df["open_bp"] >= 0)
            print(f"   gap-down low_in_first {df.loc[gdn,'low_in_first_bar'].mean():.3f} (n={gdn.sum()}) | gap-up {df.loc[gup,'low_in_first_bar'].mean():.3f} (n={gup.sum()})")
            # Does the sunday effect survive after controlling for the drift? P(low_in_first | close_bp>0) sunday vs rest
            for cond, cm in [("close>0", df["close_bp"] > 0), ("close<=0", df["close_bp"] <= 0)]:
                print(f"   [{cond}] low_by_tokyo SUN {df.loc[m&cm,'low_by_tokyo_open'].mean():.3f} (n={(m&cm).sum()}) vs rest {df.loc[rest&cm,'low_by_tokyo_open'].mean():.3f} (n={(rest&cm).sum()})")
    # weekday table
    print("  weekday table:")
    for d in range(5):
        m = df["dow"] == d
        print(f"   dow={d} n={m.sum()} low_in_first {df.loc[m,'low_in_first_bar'].mean():.3f} low_by_tokyo {df.loc[m,'low_by_tokyo_open'].mean():.3f} high_in_first {df.loc[m,'high_in_first_bar'].mean():.3f} hi_first {df.loc[m,'hi_first'].mean():.3f} median close_bp {df.loc[m,'close_bp'].median():.1f}")
    # chi2 for dow x targets
    for t in ["low_in_first_bar", "low_by_tokyo_open", "hi_first", "high_in_first_bar"]:
        ct = pd.crosstab(df["dow"], df[t])
        print(f"   chi2 dow x {t}: p={stats.chi2_contingency(ct)[1]:.2e}")

    # ---------------- C7: FOMC eve ----------------
    print("\n== C7 FOMC-eve")
    m = df["fomc_tomorrow"] == 1
    print(f"  n={m.sum()} dates={[str(x.date()) for x in df.index[m]]}")
    for t, base in [("hi_first", df["hi_first"].mean()), ("close_top20", df["close_top20"].mean()), ("close_bot20", df["close_bot20"].mean()),
                    ("low_in_first_bar", df["low_in_first_bar"].mean()), ("high_in_last_bar", df["high_in_last_bar"].mean()), ("low_in_last_bar", df["low_in_last_bar"].mean())]:
        y = df.loc[m, t]
        print(f"   {rate_line(t, y, base)} | {by_half(df, m, t)}")
    print(f"   mean close_loc {df.loc[m,'close_loc'].mean():.3f}; median close_bp {df.loc[m,'close_bp'].median():.1f}; P(close_bp>0) {(df.loc[m,'close_bp']>0).mean():.3f} ({(df.loc[m,'close_bp']>0).sum()}/{m.sum()}); median hi_bp {df.loc[m,'hi_bp'].median():.1f} lo_bp {df.loc[m,'lo_bp'].median():.1f}; mean hi_k {df.loc[m,'hi_k'].mean():.2f} lo_k {df.loc[m,'lo_k'].mean():.2f}; same_bar {df.loc[m,'same_bar_extremes'].sum()}")
    print(f"   hi_first values: {df.loc[m,'hi_first'].tolist()}  hi_k: {df.loc[m,'hi_k'].tolist()} lo_k: {df.loc[m,'lo_k'].tolist()}")
    print(f"   close_bp list: {np.round(df.loc[m,'close_bp'].values,1).tolist()}")
    # Multiple-testing context: how many calendar flags x targets?
    flags = ["fomc_today", "fed_minutes_today", "tier1_data_today", "tier2_data_today", "opex_today", "witching_today", "roll_today",
             "megacap_earnings_tonight", "election_today", "politics_today", "boj_tonight", "jp_data_tonight", "cn_data_tonight",
             "cn_policy_tonight", "rba_tonight", "fomc_tomorrow", "tier1_data_tomorrow", "tier2_data_tomorrow", "ecb_tomorrow",
             "boe_tomorrow", "opex_tomorrow", "holiday_tomorrow", "sunday_open", "month_end", "quarter_end", "pre_holiday"]
    tg = ["hi_first", "close_top20", "close_bot20", "low_in_first_bar", "high_in_last_bar", "low_in_last_bar", "high_in_first_bar",
          "high_by_tokyo_open", "low_by_tokyo_open", "high_above_rth_high", "low_below_rth_low", "close_with_dir"]
    res = []
    for f in flags:
        if f not in df.columns:
            continue
        mm = df[f] == 1
        if mm.sum() < 5:
            continue
        for t in tg:
            p = fisher(df.loc[mm, t], df.loc[~mm, t])
            res.append((f, t, int(mm.sum()), df.loc[mm, t].mean(), df.loc[~mm, t].mean(), p))
    res = pd.DataFrame(res, columns=["flag", "target", "n", "rate", "rest", "p"]).sort_values("p")
    from scipy.stats import false_discovery_control
    res["q"] = false_discovery_control(res["p"].values, method="bh")
    print(f"   calendar flag x target Fisher tests: {len(res)}; top 12:")
    print(res.head(12).to_string(index=False))

    # ---------------- C8: close location by direction ----------------
    print("\n== C8 close location by direction")
    for t in ["close_top20", "close_bot20", "close_with_dir"]:
        a = df.loc[dn, t]; b = df.loc[up, t]
        print(f"  {t}: down {a.mean():.3f} CI{boot_rate_ci(a)} (n={len(a)}) vs up {b.mean():.3f} CI{boot_rate_ci(b)} (n={len(b)}) fisher p={fisher(a,b):.2e} | down: {by_half(df, dn, t)} || up: {by_half(df, up, t)}")
    print(f"  mean close_loc down {df.loc[dn,'close_loc'].mean():.3f} up {df.loc[up,'close_loc'].mean():.3f}; close_loc_in_dir down {df.loc[dn,'close_loc_in_dir'].mean():.3f} up {df.loc[up,'close_loc_in_dir'].mean():.3f}")
    r, p = stats.spearmanr(df["is_down"], df["close_loc_in_dir"], nan_policy="omit")
    print(f"  spearman(is_down, close_loc_in_dir) = {r:.3f} p={p:.2e}")
    for h in ("H1", "H2"):
        s = df[df.half == h]; r, p = stats.spearmanr(s["is_down"], s["close_loc_in_dir"], nan_policy="omit"); print(f"   {h}: rho={r:.3f} p={p:.2e}")
    z = df["rth_ret_z"]
    terc = pd.qcut(z, 3, labels=["T1 big down", "T2", "T3 big up"])
    for lv in terc.cat.categories:
        mm = terc == lv
        print(f"  rth_ret_z {lv}: n={mm.sum()} close_with_dir {df.loc[mm,'close_with_dir'].mean():.3f} close_loc_in_dir {df.loc[mm,'close_loc_in_dir'].mean():.3f} close_top20 {df.loc[mm,'close_top20'].mean():.3f}")
    # a cleaner reading: is 'close_with_dir' lower after down days simply because the Asia drift is positive?
    print(f"  P(close_bp>0): down {(df.loc[dn,'close_bp']>0).mean():.3f} up {(df.loc[up,'close_bp']>0).mean():.3f}; median close_bp down {df.loc[dn,'close_bp'].median():.1f} up {df.loc[up,'close_bp'].median():.1f}")
    print(f"  close_loc >= 0.5: down {(df.loc[dn,'close_loc']>=0.5).mean():.3f} up {(df.loc[up,'close_loc']>=0.5).mean():.3f}")

    # ---------------- C9: hi_first ----------------
    print("\n== C9 hi_first")
    print(f"  base hi_first {df['hi_first'].mean():.3f}; same_bar {df['same_bar_extremes'].mean():.3f}")
    a = df.loc[up, "hi_first"]; b = df.loc[dn, "hi_first"]
    print(f"  up {a.mean():.3f} CI{boot_rate_ci(a)} vs down {b.mean():.3f} CI{boot_rate_ci(b)} fisher p={fisher(a,b):.3f} | up: {by_half(df, up, 'hi_first')} || down: {by_half(df, dn, 'hi_first')}")
    # excluding same-bar
    ns = df["same_bar_extremes"] == 0
    a = df.loc[up & ns, "hi_first"]; b = df.loc[dn & ns, "hi_first"]
    print(f"  excl same-bar: up {a.mean():.3f} (n={len(a)}) vs down {b.mean():.3f} (n={len(b)}) fisher p={fisher(a,b):.3f}")
    wf = np.where(df["dir"] > 0, df["hi_first"], 1 - df["hi_first"]).astype(float); wf[~ns.values] = np.nan
    print(f"  with_first (excl same-bar): {np.nanmean(wf):.3f} CI{boot_rate_ci(wf)} n={ns.sum()}")

    # ---------------- C11: bar0 / bar8 asymmetry ----------------
    print("\n== C11 bar-0 / bar-8 asymmetry")
    full = df["n_bars"] == 9
    print(f"  n_bars==9: {full.sum()}/{len(df)}")
    for t in ["low_in_first_bar", "high_in_first_bar", "high_in_last_bar", "low_in_last_bar"]:
        print(f"  {t}: all {df[t].mean():.3f} CI{boot_rate_ci(df[t])} | {by_half(df, df[t].notna(), t)} | up {df.loc[up,t].mean():.3f} down {df.loc[dn,t].mean():.3f} fisher p={fisher(df.loc[up,t], df.loc[dn,t]):.3f}")
    # paired test low-in-first vs high-in-first (McNemar)
    a = df["low_in_first_bar"]; b = df["high_in_first_bar"]
    n01 = int(((a == 1) & (b == 0)).sum()); n10 = int(((a == 0) & (b == 1)).sum())
    print(f"  McNemar low_in_first vs high_in_first: discordant {n01} vs {n10}, exact binom p={stats.binomtest(n01, n01+n10, 0.5).pvalue:.2e}")
    a = df["high_in_last_bar"]; b = df["low_in_last_bar"]
    n01 = int(((a == 1) & (b == 0)).sum()); n10 = int(((a == 0) & (b == 1)).sum())
    print(f"  McNemar high_in_last vs low_in_last: discordant {n01} vs {n10}, exact binom p={stats.binomtest(n01, n01+n10, 0.5).pvalue:.2e}")
    # half drift significance
    for t in ["low_in_first_bar", "high_in_first_bar", "high_in_last_bar", "low_in_last_bar"]:
        h1 = df.loc[df.half == "H1", t]; h2 = df.loc[df.half == "H2", t]
        print(f"  {t} H1 {h1.mean():.3f} H2 {h2.mean():.3f} fisher p={fisher(h1,h2):.3f}")
    for t in ["hi_bp", "lo_bp", "close_bp"]:
        print(f"  median {t}: H1 {df.loc[df.half=='H1',t].median():.1f} H2 {df.loc[df.half=='H2',t].median():.1f} MWU p={stats.mannwhitneyu(df.loc[df.half=='H1',t], df.loc[df.half=='H2',t]).pvalue:.3f}")
    # with_in_first_bar by direction
    wif = np.where(df["dir"] > 0, df["high_in_first_bar"], df["low_in_first_bar"])
    print(f"  with_in_first_bar: down {wif[dn.values].mean():.3f} up {wif[up.values].mean():.3f}")

    # ---------------- C12: with/against symmetry ----------------
    print("\n== C12 with vs against extension")
    w = df["with_ext_bp"]; ag = df["against_ext_bp"]
    pw = (w > ag).astype(float); pw[w == ag] = np.nan
    print(f"  median with {w.median():.1f} against {ag.median():.1f}; P(with>against) {np.nanmean(pw):.3f} CI{boot_rate_ci(pw)} (ties {(w==ag).sum()}) | up {np.nanmean(pw[up]):.3f} down {np.nanmean(pw[dn]):.3f} | H1 {np.nanmean(pw[df.half=='H1']):.3f} H2 {np.nanmean(pw[df.half=='H2']):.3f}")
    print(f"  Wilcoxon signed-rank with-against p={stats.wilcoxon(w, ag).pvalue:.3f}; mean diff {(w-ag).mean():.2f} bp")
    r, p = stats.spearmanr(df["is_down"], w, nan_policy="omit"); print(f"  rho(is_down, with_ext) {r:.3f} p={p:.3f}")
    r, p = stats.spearmanr(df["mag"], df["rng_bp"], nan_policy="omit"); print(f"  rho(mag, rng) {r:.3f} p={p:.3f}")
    cells = 0; sig = 0
    for f in ["mag", "ext_in_dir", "vwap_in_dir", "stretch20_in_dir", "post_in_dir", "abs_streak"]:
        if f not in df.columns:
            continue
        try:
            terc = pd.qcut(df[f].rank(method="first"), 3, labels=["T1", "T2", "T3"])
        except Exception as e:
            print("  skip", f, e); continue
        line = f"  {f}:"
        for dlab, dm in [("up", up), ("down", dn), ("all", pd.Series(True, index=df.index))]:
            for lv in ["T1", "T2", "T3"]:
                mm = (terc == lv) & dm
                v = pw[mm]; ci = boot_rate_ci(v)
                cells += 1
                flag = "*" if (ci[0] > 0.5 or ci[1] < 0.5) else ""
                sig += bool(flag)
                line += f" {dlab}/{lv} {np.nanmean(v):.2f}[{ci[0]:.2f},{ci[1]:.2f}]n{int(np.sum(~np.isnan(v)))}{flag}"
        print(line)
    print(f"  cells {cells}, CI excluding 0.5: {sig}")

    # ---------------- C13: mag vs scale ----------------
    print("\n== C13 mag / ext_in_dir vs range")
    for f in ["mag", "ext_in_dir", "vwap_in_dir", "post_in_dir", "abs_post", "is_down", "vix", "rth_range_bp", "asia_rng_med20", "rth_ret_z"]:
        if f not in df.columns:
            continue
        line = f"  {f:14s}"
        for t in ["rng_bp", "hi_bp", "lo_bp"]:
            s = df[[f, t]].dropna(); r, p = stats.spearmanr(s[f], s[t])
            line += f" {t}: rho={r:+.3f} p={p:.1e} (n={len(s)})"
        for h in ("H1", "H2"):
            s = df.loc[df.half == h, [f, "rng_bp"]].dropna(); r, p = stats.spearmanr(s[f], s["rng_bp"]); line += f" | {h} rho(rng)={r:+.3f}"
        print(line)
    terc = pd.qcut(df["mag"].rank(method="first"), 3, labels=["T1", "T2", "T3"])
    for lv in ["T1", "T2", "T3"]:
        mm = terc == lv
        print(f"  mag {lv}: n={mm.sum()} median rng {df.loc[mm,'rng_bp'].median():.1f} hi_bp {df.loc[mm,'hi_bp'].median():.1f} lo_bp {df.loc[mm,'lo_bp'].median():.1f}")
    terc = pd.qcut(df["abs_post"].rank(method="first"), 3, labels=["T1", "T2", "T3"])
    for lv in ["T1", "T2", "T3"]:
        mm = terc == lv
        print(f"  abs_post {lv}: n={mm.sum()} median rng {df.loc[mm,'rng_bp'].median():.1f}")
    print(f"  down-day median rng {df.loc[dn,'rng_bp'].median():.1f} vs up {df.loc[up,'rng_bp'].median():.1f}")
    # partial: does mag add to vix + asia_rng_med20 for rng? OLS on log rng
    def ols(X, y):
        X = np.column_stack([np.ones(len(y)), X]); b, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ b; n, k = X.shape; s2 = r @ r / (n - k)
        se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X))); r2 = 1 - r @ r / np.sum((y - y.mean()) ** 2)
        return r2, b / se
    sub = df[["rng_bp", "mag", "vix", "asia_rng_med20", "abs_post", "rth_range_bp"]].dropna().copy()
    y = np.log(sub["rng_bp"].values); base = np.column_stack([np.log(sub["vix"]), np.log(sub["asia_rng_med20"])])
    r0, _ = ols(base, y)
    r1, t1 = ols(np.column_stack([base, sub["mag"]]), y); r2, t2 = ols(np.column_stack([base, sub["abs_post"]]), y); r3, t3 = ols(np.column_stack([base, np.log(sub["rth_range_bp"])]), y)
    print(f"  OLS log rng: R2 base {r0:.3f}; +mag {r1:.3f} (t={t1[-1]:.2f}); +abs_post {r2:.3f} (t={t2[-1]:.2f}); +log rth_range {r3:.3f} (t={t3[-1]:.2f})")

    # ---------------- C4 descriptive: VIX terciles ----------------
    print("\n== C4 VIX terciles")
    terc = pd.qcut(df["vix"], 3)
    for lv in terc.cat.categories:
        mm = terc == lv
        r = df.loc[mm, "rng_bp"]
        idx = rng.integers(0, len(r), (2000, len(r))); med = np.median(r.values[idx], axis=1)
        print(f"  vix {lv}: n={mm.sum()} median rng {r.median():.1f} CI90 med [{np.quantile(med,0.05):.1f},{np.quantile(med,0.95):.1f}] P90 {r.quantile(0.9):.0f} hi_bp med {df.loc[mm,'hi_bp'].median():.1f} lo_bp med {df.loc[mm,'lo_bp'].median():.1f} | H1 med {df.loc[mm&(df.half=='H1'),'rng_bp'].median():.1f} H2 {df.loc[mm&(df.half=='H2'),'rng_bp'].median():.1f}")
    for f in ["vix", "dist_20d_high", "asia_rng_prev", "rth_range_bp", "asia_rng_med20", "abs_post"]:
        s = df[[f, "rng_bp"]].dropna(); r, p = stats.spearmanr(s[f], s["rng_bp"])
        s1 = df.loc[df.half == "H1", [f, "rng_bp"]].dropna(); s2 = df.loc[df.half == "H2", [f, "rng_bp"]].dropna()
        print(f"  rho({f}, rng) = {r:+.3f} p={p:.1e} | H1 {stats.spearmanr(s1[f], s1['rng_bp'])[0]:+.3f} H2 {stats.spearmanr(s2[f], s2['rng_bp'])[0]:+.3f}")
    terc = pd.qcut(df["dist_20d_high"], 3)
    for lv in terc.cat.categories:
        mm = terc == lv
        print(f"  dist_20d_high {lv}: n={mm.sum()} median rng {df.loc[mm,'rng_bp'].median():.1f}")


if __name__ == "__main__":
    for sym in sys.argv[1:] or ["NQ", "ES"]:
        main(sym)
