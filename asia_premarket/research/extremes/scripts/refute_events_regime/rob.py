"""Regime / robustness recomputation helpers for the events-lens claims E1..E13.

For every (subgroup vs base, statistic) pair we report:
  full      : the lens number (splice sessions already removed as in lens common.py)
  quarters  : subgroup rate/median vs base rate/median inside each calendar quarter 2024Q3..2026Q4
  halves    : 2024H2, 2025H1, 2025H2, 2026H1, 2026H2 (larger n than quarters)
  ex-regime : the same statistic with (a) the Apr-2025 tariff shock, (b) the Mar/Apr-2026 Iran war,
              (c) the Nov-2026 election/crash week removed, and (d) all three removed
  top5      : remove the 5 subgroup nights that contribute most to the effect and recompute
  sunday    : subgroup split into Sunday reopens vs weeknights (base split the same way)
"""
import sys
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "research/extremes/scripts/lens_events")
from common import load_extremes, load_panel, load_calendar, boot_ci, boot_diff_ci, binom_p, mw_p, SPLIT

OUT = "research/extremes/scripts/refute_events_regime"

REGIMES = {
    "tariff_apr25": (pd.Timestamp("2025-03-31"), pd.Timestamp("2025-04-30")),
    "iran_war_26": (pd.Timestamp("2026-02-27"), pd.Timestamp("2026-04-17")),
    "nov26_crash": (pd.Timestamp("2026-11-02"), pd.Timestamp("2026-11-06")),
}


def regime_mask(idx, names):
    m = pd.Series(False, index=idx)
    for nm in names:
        a, b = REGIMES[nm]
        m |= (idx >= a) & (idx <= b)
    return m.values


def load(sym):
    x = load_extremes(sym)
    x["q"] = x.index.to_period("Q").astype(str)
    x.loc[x["q"] == "2024Q2", "q"] = "2024Q3"      # 7 sessions of late June 2024 folded into 2024Q3
    yr = x.index.year; hf = np.where(x.index.month <= 6, "H1", "H2")
    x["hy"] = [f"{y}{h}" for y, h in zip(yr, hf)]
    x["abs_close_bp"] = x.close_bp.abs()
    x["asia_up"] = (x.asia_ret_bp > 0).astype(int)
    x["close_above_ref"] = (x.close_bp > 0).astype(int)
    x["post_side_break"] = np.where(x.post_ret > 0, x.high_above_rth_high, np.where(x.post_ret < 0, x.low_below_rth_low, np.nan))
    x["opp_side_break"] = np.where(x.post_ret > 0, x.low_below_rth_low, np.where(x.post_ret < 0, x.high_above_rth_high, np.nan))
    x["both_inside"] = ((x.high_above_rth_high == 0) & (x.low_below_rth_low == 0)).astype(int)
    for nm in REGIMES:
        x[nm] = regime_mask(x.index, [nm]).astype(int)
    x["any_regime"] = regime_mask(x.index, list(REGIMES)).astype(int)
    return x


def _stat(v, kind):
    v = np.asarray(v, float); v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan
    return v.mean() if kind == "prop" else np.median(v)


def compare(sub, base, col, kind):
    """returns dict(n, val, base, p, ci)"""
    a = sub[col].dropna().values.astype(float); b = base[col].dropna().values.astype(float)
    if kind == "prop":
        n = len(a); k = int(a.sum()); p0 = b.mean() if len(b) else np.nan
        p = binom_p(k, n, p0) if n and not np.isnan(p0) else np.nan
        ci = boot_ci(a) if n else (np.nan, np.nan)
        return dict(n=n, k=k, val=k / n if n else np.nan, base=p0, nb=len(b), p=p, ci_lo=ci[0], ci_hi=ci[1])
    else:
        n = len(a)
        p = mw_p(a, b) if n >= 2 and len(b) >= 2 else np.nan
        dci = boot_diff_ci(a, b) if n > 1 and len(b) > 1 else (np.nan, np.nan)
        return dict(n=n, k=np.nan, val=np.median(a) if n else np.nan, base=np.median(b) if len(b) else np.nan,
                    nb=len(b), p=p, ci_lo=dci[0], ci_hi=dci[1])


def top5_removed(sub, base, col, kind, direction):
    """remove the 5 subgroup nights that push the statistic most in the claimed direction."""
    s = sub.dropna(subset=[col])
    if len(s) <= 5:
        return None, []
    if kind == "prop":
        # claimed direction +1: subgroup rate > base -> remove 5 hits ; -1: remove 5 non-hits
        tgt = 1 if direction > 0 else 0
        cand = s[s[col] == tgt]
        drop = cand.index[:5] if len(cand) >= 5 else cand.index
    else:
        order = s[col].sort_values(ascending=(direction < 0))
        drop = order.index[:5]
    s2 = s.drop(drop)
    return compare(s2, base, col, kind), list(pd.to_datetime(drop).strftime("%Y-%m-%d"))


def run(sym, x, claim, label, sub_mask, base_mask, col, kind, direction, rows, min_q=5, verbose=True):
    """sub_mask/base_mask: boolean Series over x.index"""
    sub = x[sub_mask]; base = x[base_mask]
    full = compare(sub, base, col, kind)
    rec = dict(claim=claim, sym=sym, label=label, col=col, kind=kind, dir=direction,
               n=full["n"], val=full["val"], base=full["base"], p=full["p"], ci_lo=full["ci_lo"], ci_hi=full["ci_hi"])
    # halves
    for h in ("H1", "H2"):
        r = compare(sub[sub.half == h], base[base.half == h], col, kind)
        rec[f"{h}_n"] = r["n"]; rec[f"{h}_val"] = r["val"]; rec[f"{h}_base"] = r["base"]; rec[f"{h}_p"] = r["p"]
    # quarters
    qs = sorted(x["q"].unique())
    flips = []; qtxt = []
    for q in qs:
        r = compare(sub[sub.q == q], base[base.q == q], col, kind)
        rec[f"{q}_n"] = r["n"]; rec[f"{q}_val"] = r["val"]; rec[f"{q}_base"] = r["base"]
        if r["n"] >= min_q and not np.isnan(r["val"]) and not np.isnan(r["base"]):
            sgn = np.sign(r["val"] - r["base"])
            if sgn != 0 and sgn != np.sign(direction):
                flips.append((q, r["n"]))
            qtxt.append(f"{q}:{r['val']:.2f}/{r['base']:.2f}(n={r['n']})")
    rec["q_flips"] = ";".join(f"{q}(n={n})" for q, n in flips)
    rec["n_q_tested"] = sum(1 for q in qs if rec[f"{q}_n"] >= min_q)
    rec["n_q_flip"] = len(flips)
    rec["n_q_flip_ge25"] = sum(1 for q, n in flips if n >= 25)
    # half-years
    hys = sorted(x["hy"].unique()); hflips = []; htxt = []
    for hy in hys:
        r = compare(sub[sub.hy == hy], base[base.hy == hy], col, kind)
        if r["n"] >= min_q and not np.isnan(r["val"]) and not np.isnan(r["base"]):
            sgn = np.sign(r["val"] - r["base"])
            if sgn != 0 and sgn != np.sign(direction):
                hflips.append((hy, r["n"]))
            htxt.append(f"{hy}:{r['val']:.2f}/{r['base']:.2f}(n={r['n']})")
    rec["hy_flips"] = ";".join(f"{h}(n={n})" for h, n in hflips)
    rec["n_hy_flip"] = len(hflips)
    # ex-regime
    for nm in list(REGIMES) + ["any_regime"]:
        r = compare(sub[sub[nm] == 0], base[base[nm] == 0], col, kind)
        rec[f"ex_{nm}_n"] = r["n"]; rec[f"ex_{nm}_val"] = r["val"]; rec[f"ex_{nm}_base"] = r["base"]; rec[f"ex_{nm}_p"] = r["p"]
        rin = compare(sub[sub[nm] == 1], base[base[nm] == 1], col, kind)
        rec[f"in_{nm}_n"] = rin["n"]; rec[f"in_{nm}_val"] = rin["val"]; rec[f"in_{nm}_base"] = rin["base"]
    # top-5 removal
    t5, dropped = top5_removed(sub, base, col, kind, direction)
    if t5 is not None:
        rec["top5_n"] = t5["n"]; rec["top5_val"] = t5["val"]; rec["top5_base"] = t5["base"]; rec["top5_p"] = t5["p"]
        rec["top5_dropped"] = ",".join(dropped)
        rec["top5_sign_kept"] = int(np.sign(t5["val"] - t5["base"]) == np.sign(direction))
    # sunday split (only meaningful if subgroup contains both)
    for lab, m in (("sun", 1), ("wk", 0)):
        r = compare(sub[sub.sunday_open == m], base[base.sunday_open == m], col, kind)
        rec[f"{lab}_n"] = r["n"]; rec[f"{lab}_val"] = r["val"]; rec[f"{lab}_base"] = r["base"]; rec[f"{lab}_p"] = r["p"]
    rows.append(rec)
    if verbose:
        fmt = (lambda v: f"{v:.3f}") if kind == "prop" else (lambda v: f"{v:.1f}")
        print(f"\n[{claim} {sym}] {label}: {col} ({kind}) n={full['n']} val={fmt(full['val'])} base={fmt(full['base'])} p={full['p']:.3g} "
              f"| H1 {fmt(rec['H1_val'])}/{fmt(rec['H1_base'])} (n={rec['H1_n']}) H2 {fmt(rec['H2_val'])}/{fmt(rec['H2_base'])} (n={rec['H2_n']})")
        print("   quarters: " + " ".join(qtxt))
        print(f"   quarter sign flips (n>={min_q}): {rec['q_flips'] or 'none'}  [{rec['n_q_flip']}/{rec['n_q_tested']}]; half-year flips: {rec['hy_flips'] or 'none'}")
        print("   half-years: " + " ".join(htxt))
        for nm in list(REGIMES) + ["any_regime"]:
            print(f"   ex {nm:13s}: n={rec[f'ex_{nm}_n']} val={fmt(rec[f'ex_{nm}_val'])} base={fmt(rec[f'ex_{nm}_base'])} p={rec[f'ex_{nm}_p']:.3g}"
                  f"   | inside: n={rec[f'in_{nm}_n']} val={fmt(rec[f'in_{nm}_val']) if not np.isnan(rec[f'in_{nm}_val']) else 'nan'} base={fmt(rec[f'in_{nm}_base']) if not np.isnan(rec[f'in_{nm}_base']) else 'nan'}")
        if t5 is not None:
            print(f"   top-5 removed ({rec['top5_dropped']}): n={t5['n']} val={fmt(t5['val'])} base={fmt(t5['base'])} p={t5['p']:.3g} sign kept={rec['top5_sign_kept']}")
        print(f"   Sunday part: n={rec['sun_n']} val={fmt(rec['sun_val']) if not np.isnan(rec['sun_val']) else 'nan'} base={fmt(rec['sun_base']) if not np.isnan(rec['sun_base']) else 'nan'} p={rec['sun_p']:.3g} | weeknight part: n={rec['wk_n']} val={fmt(rec['wk_val']) if not np.isnan(rec['wk_val']) else 'nan'} base={fmt(rec['wk_base']) if not np.isnan(rec['wk_base']) else 'nan'} p={rec['wk_p']:.3g}")
    return rec
