#!/usr/bin/env python3
import json, urllib.request, datetime as dt
from collections import defaultdict
from pathlib import Path
UA={"User-Agent":"Mozilla/5.0 OptionsSwingDesk/1.1","Accept":"application/json"}
CBOE="https://cdn.cboe.com/api/global/delayed_quotes/options/{}.json"
DEFAULT=["NVDA","TSLA","SPY","QQQ","PLTR","AAPL","AMD","AVGO"]
OUT=Path("data/reports.json")
def fetch(sym):
    req=urllib.request.Request(CBOE.format(sym),headers=UA)
    with urllib.request.urlopen(req,timeout=25) as r: return json.load(r)
def parse_occ(occ):
    i=0
    while i<len(occ) and occ[i].isalpha(): i+=1
    rest=occ[i:]
    if len(rest)<15: return None
    yymmdd,cp,k=rest[:6],rest[6],rest[7:]
    if cp not in "CP" or not yymmdd.isdigit() or not k.isdigit(): return None
    expiry=dt.date(2000+int(yymmdd[:2]),int(yymmdd[2:4]),int(yymmdd[4:6]))
    return expiry,("call" if cp=="C" else "put"),int(k)/1000,yymmdd
def mid(c):
    b,a=float(c.get("bid") or 0),float(c.get("ask") or 0)
    if b>0 and a>0: return (b+a)/2
    return float(c.get("last_trade_price") or c.get("theo") or 0)
def analyze(sym,payload):
    d=payload.get("data") or payload
    spot=float(d.get("current_price") or d.get("close") or 0)
    iv30=d.get("iv30"); asof=d.get("last_trade_time") or payload.get("timestamp")
    today=dt.date.today(); rows=[]
    for c in d.get("options") or []:
        p=parse_occ(c.get("option",""))
        if not p: continue
        expiry,typ,strike,yymmdd=p
        dte=(expiry-today).days
        if dte<0: continue
        vol=float(c.get("volume") or 0); oi=float(c.get("open_interest") or 0); m=mid(c)
        b,a=float(c.get("bid") or 0),float(c.get("ask") or 0)
        spr=99 if m<=0 or a<=0 else (a-b)/m
        rows.append(dict(typ=typ,strike=strike,yymmdd=yymmdd,dte=dte,vol=vol,oi=oi,mid=m,prem=m*vol*100,spr=spr))
    liquid=[r for r in rows if r["spr"]<=0.10 and (r["oi"]>=50 or r["vol"]>=20) and r["mid"]>0.05]
    near=[r for r in liquid if 3<=r["dte"]<=45]
    hot2=[r for r in near if r["oi"]>0 and r["vol"]/r["oi"]>=2]
    hot3=[r for r in near if r["oi"]>0 and r["vol"]/r["oi"]>=3]
    call_p=sum(r["prem"] for r in near if r["typ"]=="call")
    put_p=sum(r["prem"] for r in near if r["typ"]=="put")
    by=defaultdict(list)
    for r in near: by[r["yymmdd"]].append(r)
    em=None
    for y in sorted(by):
        calls=[r for r in by[y] if r["typ"]=="call"]; puts=[r for r in by[y] if r["typ"]=="put"]
        if not calls or not puts: continue
        c=min(calls,key=lambda r:abs(r["strike"]-spot))
        p=next((x for x in puts if x["strike"]==c["strike"]), min(puts,key=lambda r:abs(r["strike"]-spot)))
        cand=dict(y=y,dte=c["dte"],k=c["strike"],em=round(c["mid"]+p["mid"],2))
        if 7<=c["dte"]<=21:
            em=cand; break
        if em is None: em=cand
    cwall=max((r for r in near if r["typ"]=="call" and r["strike"]>=spot), key=lambda r:r["oi"], default=None)
    pwall=max((r for r in near if r["typ"]=="put" and r["strike"]<=spot), key=lambda r:r["oi"], default=None)
    rel=[r for r in near if abs(r["strike"]-spot)/max(spot,1)<=0.08 and 7<=r["dte"]<=45 and r["vol"]>=50]
    rel.sort(key=lambda r:-r["prem"])
    star=rel[0] if rel else (max(hot3,key=lambda r:r["prem"]) if hot3 else None)
    call_side=call_p>put_p*1.25; put_side=put_p>call_p*1.25; mixed=not call_side and not put_side
    lean="偏多覆盖" if call_side and any(r["typ"]=="call" for r in hot3) else ("偏空或保护" if put_side and any(r["typ"]=="put" for r in hot3) else "中性 / 对冲")
    score=1 + (1 if hot3 else 0) + (1 if (call_side or put_side) and not mixed else 0)
    if em and star and abs(star["strike"]-spot)<=em["em"]*1.15: score+=1
    verdict="WAIT"
    if score<5 or mixed or not star: verdict="AVOID"
    if put_side and not call_side: verdict="SHORT / HEDGE ONLY"
    if call_side and hot3 and star: verdict="WAIT"
    if verdict=="WAIT" and not hot3: verdict="AVOID"
    seen=set(); table=[]
    for r in sorted(hot3+hot2, key=lambda x:-x["prem"]):
        key=(r["yymmdd"],r["typ"],r["strike"])
        if key in seen: continue
        seen.add(key)
        table.append({"yymmdd":r["yymmdd"],"dte":r["dte"],"typ":r["typ"],"strike":r["strike"],"dist":round(r["strike"]-spot,2),"pct":round((r["strike"]-spot)/spot*100,2),"vol":int(r["vol"]),"oi":int(r["oi"]),"voi":round(r["vol"]/r["oi"],1) if r["oi"] else None,"prem":round(r["prem"],0),"star":bool(star and r["typ"]==star["typ"] and r["strike"]==star["strike"] and r["yymmdd"]==star["yymmdd"])})
        if len(table)>=10: break
    def wall(w):
        return None if not w else {"strike":w["strike"],"oi":int(w["oi"]),"dte":w["dte"]}
    return {"symbol":sym,"spot":spot,"iv30":iv30,"asof":asof,"lean":lean,"verdict":verdict,"score":score,"callPrem":round(call_p,0),"putPrem":round(put_p,0),"em":em,"star":None if not star else {"typ":star["typ"],"strike":star["strike"],"yymmdd":star["yymmdd"],"dte":star["dte"]},"callWall":wall(cwall),"putWall":wall(pwall),"rows":table}
def load_syms():
    extra=[]
    p=Path("data/watchlist.json")
    if p.exists():
        raw=json.loads(p.read_text())
        extra=raw if isinstance(raw,list) else (raw.get("symbols") or raw.get("watch") or [])
    out=[]
    for s in list(DEFAULT)+list(extra):
        s=str(s).upper().strip()
        if s and s not in out: out.append(s)
    return out
def main():
    reports={}
    for s in load_syms():
        try: reports[s]=analyze(s,fetch(s))
        except Exception as e: reports[s]={"symbol":s,"error":str(e)}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    bundle={"updated":dt.datetime.now(dt.timezone.utc).isoformat(),"source":"CBOE delayed via GitHub Actions","reports":reports}
    OUT.write_text(json.dumps(bundle,ensure_ascii=False),encoding="utf-8")
    print("wrote",OUT,OUT.stat().st_size, list(reports))
if __name__=="__main__":
    main()
