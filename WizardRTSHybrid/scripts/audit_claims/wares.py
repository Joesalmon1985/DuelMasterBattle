import sys, json, collections
sys.path.insert(0,'.')
from wizard_rts import wl_defs, tribes, construction as con, ware_classes as WC
TRIBES=["barbarians","empire","frisians","atlanteans","amazons"]
d=wl_defs.defs()
# consumers outside Widelands production
ext=collections.defaultdict(set)
for u,r in con.RECIPES.items() if hasattr(con,'RECIPES') else []:
    pass
def rec_costs():
    out=collections.defaultdict(set)
    for prod,recs in con.RECIPES.items():
        for unit,r in recs.items():
            for g in r["cost"]: out[g].add("openra/unit:"+unit)
    return out
oc=rec_costs()
res={}
for t in TRIBES:
    tb=tribes.tribe_buildings(t)
    produced=collections.defaultdict(list); consumed=collections.defaultdict(list); raw=collections.defaultdict(list)
    for n,s in tb.items():
        for g in s["outputs"]:
            ins=tribes.inputs_for(t,n,g)
            produced[g].append(n)
            if not ins and not s["inputs"]: raw[g].append(n)
        for g in s["inputs"]: consumed[g].append(n)
        for g in s["cost"]: consumed[g].append("BUILD:"+n)
        for g in s["enhancement_cost"]: consumed[g].append("ENH:"+n)
    res[t]=dict(produced=produced,consumed=consumed,raw=raw,tb=tb)
json.dump({t:{"raw":{g:v for g,v in r["raw"].items()},"produced":sorted(r["produced"]),"never_used":sorted(g for g in r["produced"] if not r["consumed"].get(g))} for t,r in res.items()},open('/tmp/claude-0/audit/wares.json','w'),indent=1)
for t,r in res.items():
    print("==",t,"buildings",len(r["tb"]),"produced wares",len(r["produced"]))
    print(" raw:",{g:v[:2] for g,v in r["raw"].items()})
    nu=[g for g in r["produced"] if not r["consumed"].get(g)]
    print(" not consumed by any WL building/build cost:",nu)
print("\n=== after external consumers")
ext_all=set(oc)
from wizard_rts import trade
for t,r in res.items():
    cls=set(w for c in WC.CLASS_WARES[t].values() for w in c)
    sw=set(wl_defs.soldier_wares(t))
    nu=[g for g in r["produced"] if not r["consumed"].get(g) and g not in cls and g not in sw and g not in ext_all]
    print(t,"class wares:",sorted(cls&set(r["produced"])),"| soldier wares:",sorted(sw))
    print("   STILL NOT CONSUMED:",nu)
