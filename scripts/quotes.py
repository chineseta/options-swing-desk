#!/usr/bin/env python3
import json, urllib.request, datetime as dt
from pathlib import Path

UA={"User-Agent":"Mozilla/5.0 OptionsSwingDesk/1.1","Accept":"application/json"}
DEFAULT=["NVDA","TSLA","SPY","QQQ","PLTR","AAPL","AMD","AVGO"]
OUT=Path("data/quotes.json")
CHART="https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&range=1d"

def load_syms():
    extra=[]
    p=Path("data/watchlist.json")
    if p.exists():
        raw=json.loads(p.read_text())
        extra=raw if isinstance(raw,list) else (raw.get("symbols") or [])
    out=[]
    for s in list(DEFAULT)+list(extra):
        s=str(s).upper().strip()
        if s and s not in out: out.append(s)
    return out

def quote(sym):
    req=urllib.request.Request(CHART.format(sym=sym), headers=UA)
    with urllib.request.urlopen(req, timeout=12) as r:
        d=json.load(r)
    m=d["chart"]["result"][0]["meta"]
    px=m.get("regularMarketPrice")
    prev=m.get("chartPreviousClose") or m.get("previousClose")
    ch=None if px is None or prev in (None,0) else px-prev
    pct=None if ch is None or not prev else ch/prev*100
    return {
        "price": px,
        "prev": prev,
        "change": None if ch is None else round(ch,4),
        "pct": None if pct is None else round(pct,3),
        "ts": m.get("regularMarketTime"),
        "tz": m.get("exchangeTimezoneName"),
    }

def main():
    q={}
    for s in load_syms():
        try: q[s]=quote(s)
        except Exception as e: q[s]={"error": str(e)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bundle={"updated": dt.datetime.now(dt.timezone.utc).isoformat(), "source": "Yahoo Finance chart (not OPRA)", "quotes": q}
    OUT.write_text(json.dumps(bundle), encoding="utf-8")
    print("wrote", OUT, len(q))

if __name__=="__main__":
    main()
