import sys, json
sys.path.insert(0,'.'); sys.path.insert(0,'tests')
from multiprocessing import Pool
LINE=("belt","conduit","payload_belt")
def job(kind):
    from test_mindustry_engine import world, run, C, F, R
    from wizard_rts import construction as con
    from wizard_rts.economy import produce
    w=world(); spec=R.block(kind); n=spec["size"]
    try:
        x,y=F.open_ground(w,"Red",n+3,n+3)
    except Exception as e:
        return kind,{"ok":False,"why":"no open ground "+repr(e)[:50]}
    if spec["role"] in LINE:
        tiles=[[x+i,y] for i in range(3)]
        res=C.place_belt(w,"Red",tiles,None,kind)
    else:
        res=con.place_building(w,"Red",kind,x+1,y+1)
    if res.get("status")!="ok": return kind,{"ok":False,"why":"place: "+str(res.get("reason"))}
    bid=res["id"]; b=w.buildings[bid]
    cost=dict(b["constructing"]["cost"])
    ask=dict(w.recipe_requests.get(bid,cost))
    for g,c in cost.items(): produce(w,bid,g,c)
    run(w,240)
    ok=bool(b.get("operational")) and not b.get("constructing")
    return kind,{"ok":ok,"why":"" if ok else "unfinished "+str(b.get("constructing"))[:70]}
if __name__=="__main__":
    from wizard_rts.industry import registry as R
    ks=[k for k in R.kinds() if not R.block(k).get("sandbox")]
    with Pool(2) as p: res=dict(p.map(job,ks,chunksize=4))
    json.dump(res,open('/tmp/claude-0/audit/mdy_build.json','w'),indent=1)
    bad=[(k,v["why"]) for k,v in res.items() if not v["ok"]]
    print("built",len(res)-len(bad),"of",len(res)); print(bad)
