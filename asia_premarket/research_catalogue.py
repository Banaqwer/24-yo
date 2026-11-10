"""Loads the agent-built research catalogue (why each Asia session moved) for the report."""
from __future__ import annotations

import glob
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "research")


def load_catalogue() -> pd.DataFrame:
    frames = []
    for p in sorted(glob.glob(os.path.join(RES, "catalogue_*.csv"))):
        try:
            d = pd.read_csv(p, dtype=str).fillna("")
            d["date"] = pd.to_datetime(d["date"], errors="coerce")
            d = d.dropna(subset=["date"])
            d["source_file"] = os.path.basename(p)
            frames.append(d)
        except Exception as e:
            print("catalogue: skipping", p, e)
    if not frames:
        return pd.DataFrame(columns=["date", "rth_driver", "asia_driver", "tags", "sources", "source_file"])
    cat = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["date"], keep="last")
    return cat.set_index("date").sort_index()


def narrative_for(cat: pd.DataFrame, date: pd.Timestamp, max_len: int = 220) -> str:
    if cat is None or len(cat) == 0 or date not in cat.index:
        return ""
    r = cat.loc[date]
    txt = f"RTH: {r.get('rth_driver','')} | Asia: {r.get('asia_driver','')}"
    txt = " ".join(str(txt).split())
    return txt if len(txt) <= max_len else txt[: max_len - 1] + "…"


def current_context() -> str:
    """The 'CURRENT CONTEXT' section of the most recent narrative file, if the agent wrote one."""
    files = sorted(glob.glob(os.path.join(RES, "narrative_*.md")))
    for p in reversed(files):
        try:
            txt = open(p, encoding="utf-8").read()
        except Exception:
            continue
        i = txt.upper().find("CURRENT CONTEXT")
        if i >= 0:
            # take from that heading to the next top-level heading of the same level
            seg = txt[i:]
            nxt = seg.find("\n## ", 10)
            return seg if nxt < 0 else seg[:nxt]
    return ""


def repeating_patterns() -> list[str]:
    """Collect the 'repeating patterns' bullet points from every narrative file."""
    out = []
    for p in sorted(glob.glob(os.path.join(RES, "narrative_*.md"))):
        try:
            txt = open(p, encoding="utf-8").read()
        except Exception:
            continue
        low = txt.lower()
        i = low.find("repeating pattern")
        if i < 0:
            continue
        seg = txt[i:]
        nxt = seg.find("\n## ", 10)
        seg = seg if nxt < 0 else seg[:nxt]
        for line in seg.splitlines():
            ls = line.strip()
            if ls.startswith("---") or len(ls) < 12:
                continue
            if ls.startswith(("-", "*", "•")) or (ls[:2].rstrip(".").isdigit()):
                out.append(f"{ls}  _(source: {os.path.basename(p)})_")
    return out
