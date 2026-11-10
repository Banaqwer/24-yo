import os, numpy as np, pandas as pd
EX="./research/extremes"; S=os.path.dirname(os.path.abspath(__file__))
def brier(p,y): return float(np.mean((p-y)**2))
def pinball(pred,y,q):
    d=y-pred; return float(np.mean(np.maximum(q*d,(q-1)*d)))
for sym in ["NQ","ES"]:
    x=pd.read_csv(f"{EX}/{sym}_extremes.csv",index_col="date",parse_dates=True).sort_index()
    o=pd.read_csv(f"{S}/orig/oos_preasia_{sym}.csv",index_col="date",parse_dates=True)
    dup=x["asia_gdate"].duplicated(keep=False)
    print(f"\n{sym}: rows sharing an asia_gdate (same night mapped to two RTH dates):")
    print(x.loc[dup,["asia_gdate","n_bars","asia_rng_prev","rng_bp","hi_bp","lo_bp"]].to_string())
    this=(x.asia_high-x.asia_low)/x.asia_open
    leak=x.index[(x.asia_rng_prev-this).abs()<1e-12]
    mis=x.index[dup & ~x.index.isin(leak)]
    print("  leaked asia_rng_prev rows:", [str(d.date()) for d in leak], "| mislabelled (night belongs to next RTH date):", [str(d.date()) for d in mis])
    print("  in OOS:", [str(d.date()) for d in leak if d in o.index], [str(d.date()) for d in mis if d in o.index])
    keep=~o.index.isin(list(leak)+list(mis))
    for t in ["high_above_rth_high","low_below_rth_low"]:
        y=o[f"{t}__y"].values; pc=o[f"{t}__full__p_cal"].values; b=o[f"{t}__full__base"].values
        print(f"  {t}: skill all {1-brier(pc,y)/brier(b,y):+.4f} | excl {int((~keep).sum())} rows {1-brier(pc[keep],y[keep])/brier(b[keep],y[keep]):+.4f}")
    for t in ["rng_bp","hi_bp","lo_bp"]:
        for q in (0.2,0.5,0.8):
            c=f"q{int(q*100)}"; y=o[f"{t}__y"].values; m=o[f"{t}__{c}"].values; b=o[f"{t}__base_{c}"].values
            print(f"  {t} {c}: skill all {1-pinball(m,y,q)/pinball(b,y,q):+.4f} | excl {1-pinball(m[keep],y[keep],q)/pinball(b[keep],y[keep],q):+.4f}")
