"""Independent recomputation + leakage / mechanical checks for F1..F14 (narrative lens)."""
import sys, os
import numpy as np, pandas as pd
from scipy import stats

ROOT = "."
LENS = "research/extremes/scripts/lens_narrative"
OUT = "research/extremes/scripts/refute_narrative_leak"
ART_NQ = pd.to_datetime(["2024-06-21", "2024-12-20", "2025-03-21", "2025-09-16"])
ART_ES = pd.to_datetime(["2025-12-16", "2025-12-17"])
SPLIT = pd.Timestamp("2025-09-01")
rng = np.random.default_rng(11)

def bci(a, f=np.mean, n=2000):
    a = np.asarray(a, float); a = a[~np.isnan(a)]
    if len(a) == 0: return (np.nan, np.nan)
    idx = rng.integers(0, len(a), size=(n, len(a)))
    s = np.array([f(a[i]) for i in idx]); return (round(float(np.quantile(s, .05)), 3), round(float(np.quantile(s, .95)), 3))

def bp(k, n, p0):
    return float(stats.binomtest(int(k), int(n), p0).pvalue) if n > 0 else np.nan

def load(sym):
    x = pd.read_csv(f"{ROOT}/research/extremes/{sym}_extremes.csv", index_col="date", parse_dates=True)
    x = x[~x.index.isin(ART_NQ if sym == "NQ" else ART_ES)].copy()
    x["half"] = np.where(x.index < SPLIT, "H1", "H2")
    x["lo_after_tko"] = (x.lo_k >= x.tokyo_open_k).astype(int)
    x["lo_post_tko"] = (x.lo_k > x.tokyo_open_k).astype(int)
    x["any_first_bar"] = ((x.hi_k == 0) | (x.lo_k == 0)).astype(int)
    x["any_last_bar"] = ((x.hi_k == x.n_bars - 1) | (x.lo_k == x.n_bars - 1)).astype(int)
    x["any_at_tko"] = ((x.hi_k == x.tokyo_open_k) | (x.lo_k == x.tokyo_open_k)).astype(int)
    x["trend_close"] = ((x.close_loc >= .8) | (x.close_loc <= .2)).astype(int)
    x["mid_close"] = ((x.close_loc > .35) & (x.close_loc < .65)).astype(int)
    x["cont"] = (np.sign(x.asia_ret_bp) == np.sign(x.rth_ret_bp)).astype(int)
    x["asia_up"] = (x.asia_ret_bp > 0).astype(int)
    x["abs_post"] = x.post_ret.abs() * 1e4; x["abs_kospi"] = x.kospi_ret.abs() * 100; x["abs_sox"] = x.sox_ret.abs() * 100
    x["lo_by_tko_and_close_hi"] = ((x.lo_k <= x.tokyo_open_k) & (x.close_loc >= .6)).astype(int)
    x["hi_ge7"] = (x.hi_k >= 7).astype(int)
    # 18:00-knowable distances from the 17:00 close to the RTH levels (bp)
    x["dist_rth_low_bp"] = (x.lvl_rth_low / x.ref_close - 1) * 1e4
    x["dist_rth_high_bp"] = (x.lvl_rth_high / x.ref_close - 1) * 1e4
    return x

def lp(sym):
    p = pd.read_csv(f"{ROOT}/research/extremes/{sym}_hourly_panel.csv", parse_dates=["date"])
    p = p[~p.date.isin(ART_NQ if sym == "NQ" else ART_ES)].copy()
    p["half"] = np.where(p.date < SPLIT, "H1", "H2")
    return p

def rate_row(name, sub, base, lab):
    r = sub[lab].mean(); k = int(sub[lab].sum()); n = len(sub); b = base[lab].mean()
    h1 = sub[sub.half == "H1"][lab].mean(); h2 = sub[sub.half == "H2"][lab].mean()
    b1 = base[base.half == "H1"][lab].mean(); b2 = base[base.half == "H2"][lab].mean()
    return dict(claim=name, label=lab, n=n, rate=round(r, 3), base=round(b, 3), ci=bci(sub[lab].values), p=round(bp(k, n, b), 4),
                H1=f"{h1:.2f}/{b1:.2f} (n={int((sub.half=='H1').sum())})", H2=f"{h2:.2f}/{b2:.2f} (n={int((sub.half=='H2').sum())})")

def med_row(name, sub, base, col):
    s = sub[col].dropna(); b = base[col].dropna(); other = base.loc[~base.index.isin(sub.index), col].dropna()
    p = stats.mannwhitneyu(s, other).pvalue if len(s) and len(other) else np.nan
    return dict(claim=name, label=col + "(median)", n=len(s), rate=round(float(s.median()), 1), base=round(float(b.median()), 1), ci=bci(s.values, np.median),
                p=round(float(p), 4), H1=f"{sub[sub.half=='H1'][col].median():.0f}/{base[base.half=='H1'][col].median():.0f}",
                H2=f"{sub[sub.half=='H2'][col].median():.0f}/{base[base.half=='H2'][col].median():.0f}")

x = load("NQ"); e = load("ES"); p = lp("NQ"); pe = lp("ES")
rows = []
print("NQ sessions", len(x), "ES", len(e))

# ---------- F2 Sunday ----------
s = x[x.sunday_open == 1]
for lab in ["low_in_first_bar", "lo_after_tko", "lo_by_tko_and_close_hi", "high_in_first_bar", "trend_close", "asia_up"]:
    rows.append(rate_row("F2", s, x, lab))
rows.append(med_row("F2", s, x, "rng_bp"))
p9 = p[p.n_bars == 9].merge(x[["sunday_open", "abs_post", "megacap_earnings_tonight", "abs_kospi", "rth_ret_bp", "fomc_today", "tier1_data_tomorrow"]], left_on="date", right_index=True)
for k in [0, 1, 2]:
    a = p9[(p9.k == k)]; b = a[a.sunday_open == 1]
    print(f"F2 panel P(low_done|k={k}) sunday {b.low_done.mean():.3f} (n={len(b)}) vs all {a.low_done.mean():.3f}")
at = p9[p9.k == p9.tokyo_open_k]
sb = at[(at.sunday_open == 1) & (at.pos_in_range >= .8)]
print(f"F2/F10 Sunday & pos>=0.8 at tko close: P(low_done)={sb.low_done.mean():.3f} n={len(sb)}")

# ---------- F3 AH print ----------
for nm, c in [("F3 megacap", x.megacap_earnings_tonight == 1), ("F3 |post|>=25", x.abs_post >= 25)]:
    sub = x[c]
    rows.append(med_row(nm, sub, x, "first_bar_rng_bp")); rows.append(med_row(nm, sub, x, "rng_bp"))
    for lab in ["any_last_bar", "high_in_first_bar", "high_in_last_bar", "mid_close"]:
        rows.append(rate_row(nm, sub, x, lab))
    up = x[x.asia_ret_bp > 0]; su = up[c.reindex(up.index)]
    rows.append(rate_row(nm + " up-nights", su, up, "high_in_last_bar"))
for k in range(2, 8):
    a = p9[(p9.k == k) & (p9.bars_since_hi >= 2)]; b = a[a.abs_post >= 25]
    print(f"F3 P(high_done|k={k},bsh>=2) |post|>=25: {b.high_done.mean():.2f} (n={len(b)}) vs {a.high_done.mean():.2f}")
# sign of post
for nm, c in [("post>=+15", x.post_ret >= .0015), ("post<=-15", x.post_ret <= -.0015)]:
    sub = x[c]; print(f"F3 {nm}: n={len(sub)} asia_up={sub.asia_up.mean():.2f} low_first={sub.low_in_first_bar.mean():.2f} high_first={sub.high_in_first_bar.mean():.2f}")

# ---------- F4 Kospi ----------
kb = x[x.abs_kospi >= 3]
for lab in ["any_at_tko", "low_at_tokyo_open", "high_at_tokyo_open", "low_in_last_bar", "cont"]:
    rows.append(rate_row("F4", kb, x, lab))
rows.append(med_row("F4", kb, x, "rng_bp"))
# Is the Kospi effect just the 2026 regime? compare with same-window non-kospi nights
w = x[x.index >= "2025-09-01"]
print(f"F4 H2 window: |kospi|>=3 any_at_tko {w[w.abs_kospi>=3].any_at_tko.mean():.3f} (n={(w.abs_kospi>=3).sum()}) vs H2 others {w[w.abs_kospi<3].any_at_tko.mean():.3f}; "
      f"H2 base incl {w.any_at_tko.mean():.3f}; p vs H2-others={bp(w[w.abs_kospi>=3].any_at_tko.sum(), (w.abs_kospi>=3).sum(), w[w.abs_kospi<3].any_at_tko.mean()):.4f}")
# encoding test: at k>tko, if the running low was set in the tko bar -> P(low_done)?
pk = p9[(p9.k > p9.tokyo_open_k)].copy()
pk["lo_set_at_tko"] = ((pk.k - pk.bars_since_lo) == pk.tokyo_open_k).astype(int)
for nm, c in [("all", pk.k >= 0), ("|kospi|>=3", pk.abs_kospi >= 3)]:
    a = pk[c]
    for k in [3, 4, 5]:
        s1 = a[(a.k == k) & (a.lo_set_at_tko == 1)]; s0 = a[(a.k == k) & (a.lo_set_at_tko == 0) & (a.bars_since_lo >= 1)]
        print(f"F4 enc {nm} k={k}: P(low_done | low set in tko bar)={s1.low_done.mean():.2f} (n={len(s1)}) vs low set elsewhere, bsl>=1: {s0.low_done.mean():.2f} (n={len(s0)})")

# ---------- F5 rth<=-150 ----------
d15 = x[x.rth_ret_bp <= -150]
for lab in ["low_below_rth_low", "high_above_rth_high", "asia_up", "low_by_tokyo_open"]:
    rows.append(rate_row("F5", d15, x, lab))
rows.append(med_row("F5", d15, x, "rally_after_lo_bp")); rows.append(med_row("F5", d15, x, "rng_bp"))
# mechanical: where is the 17:00 close relative to the RTH low / high at 18:00?
print(f"F5 rth<=-150: median dist to RTH low at 18:00 = {d15.dist_rth_low_bp.median():.1f} bp (all: {x.dist_rth_low_bp.median():.1f}); "
      f"median dist to RTH high = {d15.dist_rth_high_bp.median():.1f} bp (all {x.dist_rth_high_bp.median():.1f}); "
      f"share with 17:00 close already below RTH low = {(d15.ref_close < d15.lvl_rth_low).mean():.3f} (n={(d15.ref_close < d15.lvl_rth_low).sum()}); "
      f"share with 18:00 open below RTH low = {(d15.asia_open < d15.lvl_rth_low).mean():.3f}")
nt = d15[d15.ref_close >= d15.lvl_rth_low]
print(f"F5 among rth<=-150 with 17:00 close >= RTH low: low_below_rth_low = {nt.low_below_rth_low.mean():.3f} (n={len(nt)})")
# distance-matched: all sessions with dist_rth_low in the same range as the -150 nights
lo_q, hi_q = d15.dist_rth_low_bp.quantile([.25, .75])
m = x[(x.dist_rth_low_bp >= lo_q) & (x.dist_rth_low_bp <= hi_q)]
mm = m[m.rth_ret_bp > -150]
print(f"F5 distance-matched (dist_rth_low in [{lo_q:.0f},{hi_q:.0f}] bp): all n={len(m)} low_below={m.low_below_rth_low.mean():.3f}; "
      f"non-(-150) nights n={len(mm)} low_below={mm.low_below_rth_low.mean():.3f}; -150 nights in band n={len(m)-len(mm)} {m[m.rth_ret_bp<=-150].low_below_rth_low.mean():.3f}")
# logistic-ish: low_below_rth_low vs dist only
for lo_, hi_ in [(-1000, -60), (-60, -30), (-30, -15), (-15, 0), (0, 1000)]:
    b = x[(x.dist_rth_low_bp > lo_) & (x.dist_rth_low_bp <= hi_)]
    print(f"   dist_rth_low in ({lo_},{hi_}]: n={len(b)} P(low<RTH low)={b.low_below_rth_low.mean():.2f}  (of which rth<=-150: n={(b.rth_ret_bp<=-150).sum()} rate={b[b.rth_ret_bp<=-150].low_below_rth_low.mean() if (b.rth_ret_bp<=-150).sum() else np.nan:.2f})")
print(f"F5 median hi_bp={x.hi_bp.median():.0f}; -150 nights need +{d15.dist_rth_high_bp.median():.0f} bp to clear RTH high; max hi_bp on those nights={d15.hi_bp.max():.0f}; P(hi_bp>=150) all={ (x.hi_bp>=150).mean():.3f}")
# encoding test: first bar where run_lo breaks the RTH low -> is low done?
pm = p9.merge(x[["lvl_rth_low"]], left_on="date", right_index=True)
pm = pm.sort_values(["date", "k"])
pm["prev_break"] = pm.groupby("date").run_lo_below_rth_low.shift(1).fillna(0)
first_break = pm[(pm.run_lo_below_rth_low == 1) & (pm.prev_break == 0)]
for nm, c in [("all", first_break.k >= 0), ("rth<=-150", first_break.rth_ret_bp <= -150)]:
    f = first_break[c]
    base_same_k = p9[p9.k.isin(f.k.unique())]
    print(f"F5 enc {nm}: at the first bar whose low breaks the RTH low: P(low_done)={f.low_done.mean():.3f} (n={len(f)}); median k={f.k.median():.0f}; "
          f"P(low_done) unconditional at those k's (weighted)={np.mean([p9[p9.k==kk].low_done.mean() for kk in f.k]):.3f}; "
          f"P(low_done|bars_since_lo==0) at those k's={np.mean([p9[(p9.k==kk)&(p9.bars_since_lo==0)].low_done.mean() for kk in f.k]):.3f}")

# ---------- F6 moderate ----------
md = x[(x.rth_ret_bp <= -30) & (x.rth_ret_bp >= -130)]; mu = x[(x.rth_ret_bp >= 30) & (x.rth_ret_bp <= 130)]
for lab in ["low_below_rth_low", "high_above_rth_high", "cont", "asia_up"]:
    rows.append(rate_row("F6 mod-down", md, x, lab)); rows.append(rate_row("F6 mod-up", mu, x, lab))
x["close_hi70"] = (x.close_loc >= .7).astype(int); x["close_lo30"] = (x.close_loc <= .3).astype(int)
md = x.loc[md.index]; mu = x.loc[mu.index]
rows.append(rate_row("F6 mod-down", md, x, "close_hi70")); rows.append(rate_row("F6 mod-up", mu, x, "close_lo30"))
print(f"F6 mod-down: median dist to RTH low {md.dist_rth_low_bp.median():.0f} bp, to RTH high {md.dist_rth_high_bp.median():.0f} bp; "
      f"17:00 close already below RTH low {(md.ref_close<md.lvl_rth_low).mean():.3f}; mod-up: dist high {mu.dist_rth_high_bp.median():.0f}, low {mu.dist_rth_low_bp.median():.0f}; close already above RTH high {(mu.ref_close>mu.lvl_rth_high).mean():.3f}")
# distance-matched for mod-down
for lo_, hi_ in [(-1000, -60), (-60, -30), (-30, -15), (-15, 0), (0, 1000)]:
    b = x[(x.dist_rth_low_bp > lo_) & (x.dist_rth_low_bp <= hi_)]; c = b[(b.rth_ret_bp <= -30) & (b.rth_ret_bp >= -130)]
    print(f"   F6 dist_rth_low in ({lo_},{hi_}]: all n={len(b)} P={b.low_below_rth_low.mean():.2f}; mod-down n={len(c)} P={c.low_below_rth_low.mean() if len(c) else np.nan:.2f}")

# ---------- F7 FOMC ----------
f = x[x.fomc_today == 1]
for lab in ["any_first_bar", "any_last_bar", "low_in_first_bar", "cont", "asia_up"]:
    rows.append(rate_row("F7", f, x, lab))
rows.append(med_row("F7", f, x, "rng_bp"))
print("F7 fomc dates:", [d.strftime("%Y-%m-%d") for d in f.index], "megacap overlap:", int(f.megacap_earnings_tonight.sum()), "|post|>=25 overlap:", int((f.abs_post >= 25).sum()))

# ---------- F8 holiday ----------
h = x[(x.holiday_tomorrow == 1) | (x.pre_holiday == 1)]
rows.append(med_row("F8", h, x, "rng_bp")); rows.append(med_row("F8", h, x, "asia_ret_bp"))
print("F8 holiday rows:"); print(h[["holiday_tomorrow", "pre_holiday", "n_bars", "rng_bp", "events_tonight_tomorrow"]].to_string())
h9 = h[h.n_bars == 9]
print(f"F8 holiday full-9-bar only: n={len(h9)} median rng={h9.rng_bp.median():.0f} vs all 9-bar {x[x.n_bars==9].rng_bp.median():.0f}; short sessions n={(h.n_bars<9).sum()} med rng {h[h.n_bars<9].rng_bp.median():.0f}")
print(f"   all short sessions (n_bars<9): n={(x.n_bars<9).sum()} median rng={x[x.n_bars<9].rng_bp.median():.0f}; of which holiday-flagged {((x.n_bars<9)&((x.holiday_tomorrow==1)|(x.pre_holiday==1))).sum()}")

# ---------- F9 tier1 tomorrow ----------
t1 = x[x.tier1_data_tomorrow == 1]
rows.append(med_row("F9", t1, x, "rng_bp")); rows.append(rate_row("F9", t1, x, "lo_post_tko")); rows.append(rate_row("F9", t1, x, "cont"))
t0 = x[x.tier1_data_today == 1]; rows.append(med_row("F9 tier1_today", t0, x, "rng_bp"))
for k in [2, 3, 4]:
    a = p9[p9.k == k]; b = a[a.tier1_data_tomorrow == 1]
    print(f"F9 P(low_done|k={k}) tier1_tomorrow {b.low_done.mean():.2f} (n={len(b)}) vs {a.low_done.mean():.2f}")

# ---------- F10 Tokyo-open position ----------
def f10(pp, xx, nm):
    pp = pp[pp.n_bars == 9]
    a = pp[pp.k == pp.tokyo_open_k].merge(xx[["sunday_open"]], left_on="date", right_index=True)
    out = {}
    base_h = a.high_done.mean(); base_l = a.low_done.mean()
    for cn, c, lab in [("pos<0.2", a.pos_in_range < .2, "high_done"), ("pos>=0.8", a.pos_in_range >= .8, "low_done"),
                       ("pos<0.2&rr>=0.7", (a.pos_in_range < .2) & (a.run_rng_vs_med20 >= .7), "high_done"),
                       ("pos>=0.8&rr>=0.7", (a.pos_in_range >= .8) & (a.run_rng_vs_med20 >= .7), "low_done"),
                       ("pos<0.2&rr<0.4", (a.pos_in_range < .2) & (a.run_rng_vs_med20 < .4), "high_done"),
                       ("pos>=0.8&rr<0.4", (a.pos_in_range >= .8) & (a.run_rng_vs_med20 < .4), "low_done"),
                       ("sun&pos>=0.8", (a.sunday_open == 1) & (a.pos_in_range >= .8), "low_done"),
                       ("sun&pos<0.2", (a.sunday_open == 1) & (a.pos_in_range < .2), "high_done")]:
        s = a[c]; b = base_h if lab == "high_done" else base_l
        out[cn] = f"{s[lab].mean():.3f} n={len(s)} H1={s[s.half=='H1'][lab].mean():.2f}({(s.half=='H1').sum()}) H2={s[s.half=='H2'][lab].mean():.2f}({(s.half=='H2').sum()}) base={b:.3f} p={bp(s[lab].sum(), len(s), b):.1e}"
    print(f"F10 {nm}: base P(high_done|k=tko)={base_h:.3f} P(low_done)={base_l:.3f} n={len(a)}")
    for k_, v in out.items(): print("   ", k_, v)
    # check label identity: high_done at k=tko == (hi_k<=tko)
    print("    label identity high_done==(hi_k<=tko):", bool((a.high_done == (a.hi_k <= a.tokyo_open_k).astype(int)).all()))
    # DST check: does the pos<0.2 effect hold in both DST regimes?
    for dst in [0, 1]:
        s = a[(a.is_dst == dst) & (a.pos_in_range < .2)]; t = a[(a.is_dst == dst) & (a.pos_in_range >= .8)]
        print(f"    is_dst={dst}: pos<0.2 P(high_done)={s.high_done.mean():.2f} (n={len(s)}); pos>=0.8 P(low_done)={t.low_done.mean():.2f} (n={len(t)})")
    # is the effect specific to the Tokyo-open bar, or does it hold at every k? (pos<0.2 at k -> P(high_done))
    for k in range(0, 8):
        s = pp[(pp.k == k) & (pp.pos_in_range < .2)]; t = pp[(pp.k == k) & (pp.pos_in_range >= .8)]
        print(f"    k={k}: pos<0.2 -> P(high_done)={s.high_done.mean():.2f} (n={len(s)}, base {pp[pp.k==k].high_done.mean():.2f}); pos>=0.8 -> P(low_done)={t.low_done.mean():.2f} (n={len(t)}, base {pp[pp.k==k].low_done.mean():.2f})")
f10(p, x, "NQ"); f10(pe, e, "ES")

# ---------- F11 momentum ----------
for pp, xx, nm in [(p, x, "NQ"), (pe, e, "ES")]:
    pp9 = pp[pp.n_bars == 9]
    a = pp9[pp9.k == pp9.tokyo_open_k].merge(xx[["close_bp", "sunday_open", "half"]].rename(columns={"half": "hh"}), left_on="date", right_index=True)
    a["rest"] = a.close_bp - a.cum_ret_bp; a["rc"] = (np.sign(a.rest) == np.sign(a.cum_ret_bp)).astype(int)
    for cn, c in [("all", a.k >= 0), ("|move|>=20", a.cum_ret_bp.abs() >= 20), ("|move|>=40", a.cum_ret_bp.abs() >= 40), ("sunday", a.sunday_open == 1)]:
        s = a[c]; print(f"F11 {nm} {cn}: rest_cont={s.rc.mean():.3f} n={len(s)} ci={bci(s.rc.values)} p={bp(s.rc.sum(), len(s), .5):.3f} H1={s[s.hh=='H1'].rc.mean():.2f} H2={s[s.hh=='H2'].rc.mean():.2f}")
x["rest_fb"] = x.asia_ret_bp - x.first_bar_ret_bp; x["fb_agree"] = (np.sign(x.first_bar_ret_bp) == np.sign(x.rest_fb)).astype(int)
bfb = x[x.first_bar_ret_bp.abs() >= 20]
hd = (bfb.megacap_earnings_tonight == 1) | (bfb.sunday_open == 1) | (bfb.fomc_today == 1) | (bfb.abs_post >= 15)
print(f"F11 first-bar |ret|>=20: n={len(bfb)} rest agrees {bfb.fb_agree.mean():.3f}; headline proxy {bfb[hd].fb_agree.mean():.3f} (n={hd.sum()}); no proxy {bfb[~hd].fb_agree.mean():.3f} (n={(~hd).sum()})")

# ---------- F12 15m ----------
t15 = pd.read_csv(f"{LENS}/q4_15m_timing.csv")
print(f"F12 n={len(t15)}: hi in bar0 {t15.hi_in_bar0.sum()} first15 {t15.hi_first15.sum()}; lo in bar0 {t15.lo_in_bar0.sum()} first15 {t15.lo_first15.sum()}")
print(f"   knowable-at-18:15 quantity: P(session HIGH is the 18:00-18:15 sub-bar)={t15.hi_first15.mean():.3f}, LOW={t15.lo_first15.mean():.3f}; uniform over 36 sub-bars = {1/36:.3f}; "
      f"P(session high in bar 0)={t15.hi_in_bar0.mean():.3f} (hourly base .235)")
l2 = t15[t15.lo_hour == 2]; print(f"   02:00-bar lows n={len(l2)} minute dist {l2.lo_min.value_counts().sort_index().to_dict()}; hi 02:00 n={(t15.hi_hour==2).sum()} {t15[t15.hi_hour==2].hi_min.value_counts().sort_index().to_dict()}")
# compare the 15m extremes with the hourly table's hi_k/lo_k
m15 = pd.read_csv(f"{ROOT}/data/NQ_15m.csv"); print("   15m rows", len(m15), m15.columns.tolist()[:3])
t15["hi_k_15"] = ((t15.hi_hour - 18) % 24); t15["lo_k_15"] = ((t15.lo_hour - 18) % 24)
print(f"   agreement of 15m-derived hi bar with hourly hi_k: {(t15.hi_k_15==t15.hi_k).mean():.2f}; lo: {(t15.lo_k_15==t15.lo_k).mean():.2f}")

# ---------- F13 TSMC ----------
ts = ["2024-07-17", "2024-10-16", "2025-01-15", "2025-04-16", "2025-07-16", "2025-10-15", "2026-01-14", "2026-04-15", "2026-07-15", "2026-10-14"]
tsd = x.reindex(pd.to_datetime(ts))
print("F13 TSMC rows:"); print(tsd[["is_dst", "hi_k", "lo_k", "n_bars", "rng_bp", "megacap_earnings_tonight", "abs_post", "tier1_data_tomorrow", "opex_tomorrow", "events_today", "events_tonight_tomorrow"]].to_string())
print(f"   P(hi_k>=7) all={x.hi_ge7.mean():.3f}; Wednesdays={x[x.index.dayofweek==2].hi_ge7.mean():.3f} (n={(x.index.dayofweek==2).sum()}); "
      f"H1={x[x.half=='H1'].hi_ge7.mean():.3f} H2={x[x.half=='H2'].hi_ge7.mean():.3f}; EDT={x[x.is_dst==1].hi_ge7.mean():.3f} EST={x[x.is_dst==0].hi_ge7.mean():.3f}")
# control: Wednesday nights in the week of the 3rd Friday of Jan/Apr/Jul/Oct that are NOT TSMC
wk = x[(x.index.dayofweek == 2) & (x.index.month.isin([1, 4, 7, 10])) & (x.index.day >= 12) & (x.index.day <= 21)]
print(f"   mid-month Wed nights in earnings months (12th-21st): n={len(wk)} P(hi_k>=7)={wk.hi_ge7.mean():.3f}; non-TSMC among them n={len(wk.drop(tsd.index, errors='ignore'))} {wk.drop(tsd.index, errors='ignore').hi_ge7.mean():.3f}")
print(f"   other Wed nights with tier1 tomorrow etc irrelevant; same-season Thursday nights (12-21) P(hi_k>=7)={x[(x.index.dayofweek==3)&(x.index.month.isin([1,4,7,10]))&(x.index.day>=12)&(x.index.day<=21)].hi_ge7.mean():.3f}")
# ES on those nights
tse = e.reindex(pd.to_datetime(ts)); print("   ES hi_k on TSMC nights:", tse.hi_k.tolist(), "P(hi_k>=7) ES all", round(e.hi_ge7.mean(), 3))

# ---------- F14 direction ----------
for nm, c in [("megacap", x.megacap_earnings_tonight == 1), ("sunday", x.sunday_open == 1), ("fomc", x.fomc_today == 1), ("mod-down", (x.rth_ret_bp <= -30) & (x.rth_ret_bp >= -130)),
              ("|kospi|>=3", x.abs_kospi >= 3), ("chip-led down", (x.sox_ret <= -.03) & (x.rth_ret_bp < 0)), ("up days", x.rth_ret_bp > 0), ("boj", x.boj_tonight == 1)]:
    rows.append(rate_row("F14 " + nm, x[c], x, "cont"))

# ---------- F1 catalogue ----------
fam = pd.read_csv(f"{LENS}/NQ_extremes_with_family.csv", index_col="date", parse_dates=True)
w = fam[(fam.index >= "2025-11-01") & (fam.index <= "2026-11-06")].copy()
w["any_first_bar"] = ((w.hi_k == 0) | (w.lo_k == 0)).astype(int); w["any_at_tko"] = ((w.hi_k == w.tokyo_open_k) | (w.lo_k == w.tokyo_open_k)).astype(int)
w["trend_close"] = ((w.close_loc >= .8) | (w.close_loc <= .2)).astype(int)
c = w[w.family != "none"]; o = w[w.family == "none"]
print(f"F1 window: catalogue n={len(c)} other n={len(o)}; any_first_bar {c.any_first_bar.mean():.3f} vs {o.any_first_bar.mean():.3f} p={bp(c.any_first_bar.sum(), len(c), o.any_first_bar.mean()):.1e}; "
      f"any_at_tko {c.any_at_tko.mean():.3f} vs {o.any_at_tko.mean():.3f} p={bp(c.any_at_tko.sum(), len(c), o.any_at_tko.mean()):.1e}; trend_close {c.trend_close.mean():.3f} vs {o.trend_close.mean():.3f}; rng {c.rng_bp.median():.0f} vs {o.rng_bp.median():.0f}")
print("   family sizes:", c.family.value_counts().to_dict())
for fm, g in c.groupby("family"):
    print(f"   {fm:10s} n={len(g)} first_bar={g.any_first_bar.mean():.2f} at_tko={g.any_at_tko.mean():.2f} trend={g.trend_close.mean():.2f} cont={(np.sign(g.asia_ret_bp)==np.sign(g.rth_ret_bp)).mean():.2f} low_last={(g.lo_k==g.n_bars-1).mean():.2f}")
# how many catalogue nights are flagged by the 18:00 proxies?
prox = (c.megacap_earnings_tonight == 1) | (c.sunday_open == 1) | (c.fomc_today == 1) | (c.post_ret.abs() * 1e4 >= 25) | (c.kospi_ret.abs() >= .03)
proxo = (o.megacap_earnings_tonight == 1) | (o.sunday_open == 1) | (o.fomc_today == 1) | (o.post_ret.abs() * 1e4 >= 25) | (o.kospi_ret.abs() >= .03)
print(f"   share of catalogue nights carrying any 18:00 proxy (megacap|sunday|fomc|post>=25|kospi>=3): {prox.mean():.2f}; other nights {proxo.mean():.2f}")

tab = pd.DataFrame(rows); pd.set_option("display.width", 250, "display.max_columns", 20, "display.max_rows", 200)
print(tab.to_string())
tab.to_csv(f"{OUT}/recomputed_rates.csv", index=False)
