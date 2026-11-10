"""Q4: (a) panel: P(high_done|k), P(low_done|k) under the strongest 18:00 encodings; share of the session move
accrued after the Tokyo-open bar; (b) 15m data (Aug 31 - Nov 9 2026): is the bar-0 / Tokyo-open-bar extreme the
opening print (first 15 min)?"""
import sys
sys.path.insert(0, "research/extremes/scripts/lens_narrative")
import numpy as np, pandas as pd
from common import *

x = pd.read_csv(f"{OUT}/NQ_extremes_enriched.csv", index_col="date", parse_dates=True)
fam = pd.read_csv(f"{OUT}/NQ_extremes_with_family.csv", index_col="date", parse_dates=True)
x["family"] = fam["family"]; x["big_asia_cash"] = fam["big_asia_cash"]
p = load_panel("NQ")
p = p.merge(x[["megacap_earnings_tonight", "abs_post", "sunday_open", "abs_kospi", "rth_ret_bp", "vix", "tier1_data_tomorrow",
               "fomc_today", "abs_sox", "family", "big_asia_cash", "asia_ret_bp", "close_bp", "abs_gap", "boj_tonight", "abs_rth"]],
            left_on="date", right_index=True, how="left")
p = p[p["n_bars"] == 9].copy()   # full sessions only for the k-indexed tables

CONDS = {
 "ALL": p["k"] >= 0,
 "megacap_tonight": p["megacap_earnings_tonight"] == 1,
 "|post|>=25bp": p["abs_post"] >= 25,
 "sunday_open": p["sunday_open"] == 1,
 "|kospi|>=3%": p["abs_kospi"] >= 3,
 "rth<=-150": p["rth_ret_bp"] <= -150,
 "vix>=25": p["vix"] >= 25,
 "tier1_tomorrow": p["tier1_data_tomorrow"] == 1,
 "fomc_today": p["fomc_today"] == 1,
 "[k0]|gap|>=20": p["abs_gap"] >= 20,
 "quiet(|rth|<50,|post|<8,|kospi|<1.5,no flags)": (p["abs_rth"] < 50) & (p["abs_post"] < 8) & (p["abs_kospi"] < 1.5) & (p["megacap_earnings_tonight"] == 0) & (p["sunday_open"] == 0) & (p["fomc_today"] == 0) & (p["boj_tonight"] == 0),
}
rows = []
for nm, c in CONDS.items():
    sub = p[c]
    for k in range(9):
        s = sub[sub.k == k]
        base = p[p.k == k]
        hd = s["high_done"].mean(); ld = s["low_done"].mean()
        lo_h, hi_h = boot_ci(s["high_done"].values); lo_l, hi_l = boot_ci(s["low_done"].values)
        # conditional on bars_since_hi >= 2
        s2 = s[s["bars_since_hi"] >= 2]; s3 = s[s["bars_since_lo"] >= 2]
        rows.append(dict(cond=nm, k=k, n=len(s), p_high_done=hd, ci_lo=lo_h, ci_hi=hi_h, base_high_done=base["high_done"].mean(),
                         p_low_done=ld, cil_lo=lo_l, cil_hi=hi_l, base_low_done=base["low_done"].mean(),
                         p_high_done_bsh2=s2["high_done"].mean() if len(s2) else np.nan, n_bsh2=len(s2),
                         base_high_done_bsh2=base[base["bars_since_hi"] >= 2]["high_done"].mean(),
                         p_low_done_bsl2=s3["low_done"].mean() if len(s3) else np.nan, n_bsl2=len(s3),
                         base_low_done_bsl2=base[base["bars_since_lo"] >= 2]["low_done"].mean(),
                         H1_high_done=s[s.half == "H1"]["high_done"].mean(), H2_high_done=s[s.half == "H2"]["high_done"].mean(),
                         H1_low_done=s[s.half == "H1"]["low_done"].mean(), H2_low_done=s[s.half == "H2"]["low_done"].mean(),
                         H1_n=(s.half == "H1").sum(), H2_n=(s.half == "H2").sum()))
pt = pd.DataFrame(rows)
pt.to_csv(f"{OUT}/q4_panel_conditional.csv", index=False)
pd.set_option("display.width", 300, "display.max_columns", 40, "display.max_rows", 500)
print("P(high_done | k) by condition (full sessions):")
print(pt.pivot(index="cond", columns="k", values="p_high_done").round(2).loc[list(CONDS.keys())].to_string())
print("\nP(low_done | k) by condition:")
print(pt.pivot(index="cond", columns="k", values="p_low_done").round(2).loc[list(CONDS.keys())].to_string())
print("\nn sessions:", pt[pt.k == 0].set_index("cond")["n"].to_dict())
print("\nP(high_done | k, bars_since_hi>=2):")
print(pt.pivot(index="cond", columns="k", values="p_high_done_bsh2").round(2).loc[list(CONDS.keys())].to_string())
print("\nP(low_done | k, bars_since_lo>=2):")
print(pt.pivot(index="cond", columns="k", values="p_low_done_bsl2").round(2).loc[list(CONDS.keys())].to_string())
print("\nhalves at k=0 and k=tko (H1/H2 high_done):")
print(pt[pt.k.isin([0, 1, 2])][["cond", "k", "n", "p_high_done", "H1_high_done", "H2_high_done", "p_low_done", "H1_low_done", "H2_low_done", "H1_n", "H2_n"]].round(2).to_string())

# ---- share of the session move accrued after the Tokyo-open bar closes ----
# cum_ret at close of bar (tko-1) = pre-cash-open move; after = close_bp - that
pre = p[p.k == p.tokyo_open_k - 1][["date", "cum_ret_bp"]].rename(columns={"cum_ret_bp": "pre_tko_ret"})
at = p[p.k == p.tokyo_open_k][["date", "cum_ret_bp"]].rename(columns={"cum_ret_bp": "at_tko_ret"})
xx = x.join(pre.set_index("date")).join(at.set_index("date"))
xx["post_tko_move"] = xx["close_bp"] - xx["at_tko_ret"]
xx["share_after_tko_bar"] = (xx["post_tko_move"].abs() / xx["close_bp"].abs().clip(lower=1)).clip(upper=3)
xx["sign_pre_eq_total"] = (np.sign(xx["pre_tko_ret"]) == np.sign(xx["close_bp"])).astype(int)
xx["sign_tkobar_eq_total"] = (np.sign(xx["at_tko_ret"] - xx["pre_tko_ret"]) == np.sign(xx["close_bp"])).astype(int)
xx["abs_pre"] = xx["pre_tko_ret"].abs(); xx["abs_post_tko"] = xx["post_tko_move"].abs()
out = []
for nm, c in [("ALL", xx["n_bars"] == 9), ("catalogue big_asia_cash (ex post)", xx["big_asia_cash"] == 1), ("catalogue other (ex post)", (xx["family"] != "none") & (xx["big_asia_cash"] == 0)),
              ("|kospi_ret|>=3% (18:00)", xx["abs_kospi"] >= 3), ("|sox_ret|>=3% (18:00)", xx["abs_sox"] >= 3), ("megacap_tonight", xx["megacap_earnings_tonight"] == 1),
              ("sunday_open", xx["sunday_open"] == 1), ("|post|>=25", xx["abs_post"] >= 25), ("rth<=-150", xx["rth_ret_bp"] <= -150), ("vix>=25", xx["vix"] >= 25)]:
    s = xx[c & (xx["n_bars"] == 9)]
    out.append(dict(cond=nm, n=len(s), med_abs_pre_tko_bp=s["abs_pre"].median(), med_abs_after_tko_bar_bp=s["abs_post_tko"].median(),
                    med_abs_total=s["close_bp"].abs().median(), share_after_tko_bar_median=s["share_after_tko_bar"].median(),
                    pre_sign_eq_total=s["sign_pre_eq_total"].mean(), tkobar_sign_eq_total=s["sign_tkobar_eq_total"].mean(),
                    H1_pre_sign_eq=s[s.half == "H1"]["sign_pre_eq_total"].mean(), H2_pre_sign_eq=s[s.half == "H2"]["sign_pre_eq_total"].mean(),
                    ci_pre_sign=boot_ci(s["sign_pre_eq_total"].values)))
st = pd.DataFrame(out); st.to_csv(f"{OUT}/q4_share_after_tokyo_open.csv", index=False)
print("\nshare of move after the Tokyo-open bar:")
print(st.round(2).to_string())

# ---- 15m timing ----
m15 = pd.read_csv(f"{ROOT}/data/NQ_15m.csv")
print("\n15m columns:", list(m15.columns)[:8], len(m15))
tcol = [c for c in m15.columns if "ate" in c or "time" in c.lower()][0]
m15[tcol] = pd.to_datetime(m15[tcol], utc=True).dt.tz_convert("America/New_York")
m15 = m15.set_index(tcol).sort_index()
m15["hour"] = m15.index.hour; m15["minute"] = m15.index.minute
m15["gdate"] = m15.index.date
sh = m15.index.hour >= 18
m15.loc[sh, "gdate"] = (m15.index[sh] + pd.Timedelta(days=1)).date
asia = m15[m15["hour"].isin([18, 19, 20, 21, 22, 23, 0, 1, 2])]
recs = []
for gd, g in asia.groupby("gdate"):
    if len(g) < 24:
        continue
    g = g.sort_index()
    ih = g["High"].values.argmax(); il = g["Low"].values.argmin()
    th = g.index[ih]; tl = g.index[il]
    # map to date D in extremes: asia_gdate == gd
    d = x.index[x["asia_gdate"] == str(gd)]
    if len(d) == 0:
        continue
    r = x.loc[d[0]]
    recs.append(dict(date=d[0], gdate=gd, hi_time=th.strftime("%H:%M"), lo_time=tl.strftime("%H:%M"), hi_hour=th.hour, hi_min=th.minute,
                     lo_hour=tl.hour, lo_min=tl.minute, hi_k=r["hi_k"], lo_k=r["lo_k"], tko=r["tokyo_open_k"], is_dst=r["is_dst"],
                     hi_first15=int(th.hour == 18 and th.minute == 0), lo_first15=int(tl.hour == 18 and tl.minute == 0),
                     hi_in_bar0=int(th.hour == 18), lo_in_bar0=int(tl.hour == 18)))
t15 = pd.DataFrame(recs); t15.to_csv(f"{OUT}/q4_15m_timing.csv", index=False)
print("\n15m sessions:", len(t15))
print("hi in 18:00 hourly bar:", t15.hi_in_bar0.sum(), " of which the 18:00-18:15 sub-bar:", t15.hi_first15.sum())
print("lo in 18:00 hourly bar:", t15.lo_in_bar0.sum(), " of which the 18:00-18:15 sub-bar:", t15.lo_first15.sum())
# Tokyo-open hourly bar: which 15m sub-bar?
tk_h = np.where(t15.is_dst == 1, 20, 19)
th_mask = (t15.hi_hour == tk_h); tl_mask = (t15.lo_hour == tk_h)
print("hi in Tokyo-open hourly bar:", th_mask.sum(), "sub-bar minutes:", t15[th_mask].hi_min.value_counts().to_dict())
print("lo in Tokyo-open hourly bar:", tl_mask.sum(), "sub-bar minutes:", t15[tl_mask].lo_min.value_counts().to_dict())
# last hourly bar (02:00): which sub-bar?
print("hi in 02:00 bar:", (t15.hi_hour == 2).sum(), "sub-bar:", t15[t15.hi_hour == 2].hi_min.value_counts().to_dict())
print("lo in 02:00 bar:", (t15.lo_hour == 2).sum(), "sub-bar:", t15[t15.lo_hour == 2].lo_min.value_counts().to_dict())
print("all hi minutes-of-hour:", t15.hi_min.value_counts().to_dict(), " lo:", t15.lo_min.value_counts().to_dict())
# 15m: distribution of hi/lo time (ET) across the session, 15m resolution
t15["hi_slot"] = ((t15.hi_hour - 18) % 24) * 4 + t15.hi_min // 15
t15["lo_slot"] = ((t15.lo_hour - 18) % 24) * 4 + t15.lo_min // 15
print("hi_slot hist (0=18:00..35=02:45):", np.bincount(t15.hi_slot, minlength=36).tolist())
print("lo_slot hist:", np.bincount(t15.lo_slot, minlength=36).tolist())
