import sys, json, os, time
sys.path.insert(0,'.'); sys.path.insert(0,'tests')
from multiprocessing import Pool
def one(kind):
    from test_widelands_completion import done, run, world
    from wizard_rts import wl_defs
    FACTION={"barbarians":"Red","empire":"Blue","frisians":"Green","atlanteans":"Yellow","amazons":"Purple"}
    tribe=kind[3:].split("_",1)[0]
    w=world(); spec=wl_defs.spec_for_kind(kind)
    stock={g:n*10 for g,n in spec["inputs"].items() if g not in("recruit","carrier")}
    try: b=done(w,kind,faction=FACTION[tribe],stock=stock)
    except AssertionError: return kind,{"placed":False}
    before=dict(w.stats)
    run(w,300,step=200)
    made={g:w.stats.get("made_"+g,0)-before.get("made_"+g,0) for g in spec["outputs"]}
    return kind,{"placed":True,"outputs":spec["outputs"],"made":made,"stall":(b.get("stall") or {}).get("reason"),"workers":len(b.get("worker_ids") or {})}
if __name__=="__main__":
    from test_widelands_sweep import sites
    ks=sites()
    t=time.time()
    with Pool(2) as p: res=dict(p.map(one,ks,chunksize=2))
    json.dump(res,open('/tmp/claude-0/audit/made.json','w'),indent=1)
    print("done",time.time()-t)
