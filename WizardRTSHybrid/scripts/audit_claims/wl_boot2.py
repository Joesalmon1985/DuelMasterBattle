import sys; sys.path.insert(0,'.')
from wizard_rts import wl_defs, tribes, construction as con
from wizard_rts.content import graph
TR=["barbarians","empire","frisians","atlanteans","amazons"]
for t in TR:
    tb=tribes.tribe_buildings(t)
    seeds=set(tribes.starter_stock(t))
    have=set(seeds); built=set(); produced=set()
    ch=True
    while ch:
        ch=False
        for n,s in tb.items():
            if n in built: continue
            if s.get("enhanced_from") and s["enhanced_from"][3:] not in built: continue
            if all(g in have for g in s["cost"]): built.add(n); ch=True
        for n in list(built):
            s=tb[n]
            for g in s["outputs"]:
                ins=tribes.inputs_for(t,n,g)
                if all(i in have for i in ins) and g not in produced:
                    produced.add(g); have.add(g); ch=True
    # sustained: every cost ware of every building is produced (or is log)
    unsust={n:[g for g in s["cost"] if g not in produced and g!="log"] for n,s in tb.items()}
    unsust={n:v for n,v in unsust.items() if v}
    print(t,len(tb),"seed-buildable",len(built),"| buildings with a cost ware nothing in the tribe makes:",unsust)
    # plank: hybrid sawmill?
