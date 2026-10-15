import sys,json
sys.path.insert(0,'.')
from wizard_rts import rules, construction as con
from wizard_rts.industry import units as U
def dps_of(wnames, weapon_lookup):
    best=0
    tot=0
    for n in wnames:
        w=weapon_lookup(n)
        if not w: continue
        dmg=sum(int(wh.get("damage",0)) for wh in w["warheads"])
        d=dmg*max(1,w.get("burst",1))*1000/max(1,rules.reload_ms(w))
        tot+=d
    return tot
rows=[]
# OpenRA units
for k,spec in con.BUILD_MENU.items(): pass
ra=[]
seen=set()
for prod,recs in con.RECIPES.items():
    for unit,r in recs.items():
        d=r.get("definition") or ""
        if not d.startswith("openra.") or d in seen: continue
        seen.add(d)
        a=rules.actor(d)
        if not a: continue
        dps=dps_of(a["armaments"],rules.weapon)
        rng=max([rules.weapon(n)["range"] for n in a["armaments"] if rules.weapon(n)] or [0])
        dom="air" if a.get("flying") or a.get("locomotor")=="fly" else ("naval" if a.get("naval") or a.get("locomotor") in("naval",) else "ground")
        ra.append(("OpenRA",unit,dom,a["hp"],round(dps),round(rng,1),a["speed"],r["cost"]))
actors,weapons=U.all_rules()
md=[]
for n in U.unit_list():
    if not U.is_producible(n): continue
    r=U.rules_for(n)
    if not r: continue
    a,ws=r
    dps=dps_of(a["armaments"],lambda x: ws.get(x))
    rng=max([ws[x]["range"] for x in a["armaments"]] or [0])
    dom="air" if a["flying"] else ("naval" if a["naval"] else "ground")
    md.append(("MDY",n,dom,a["hp"],round(dps),round(rng,1),a["speed"],a["tier"]))
json.dump({"ra":ra,"md":md},open('/tmp/claude-0/audit/power.json','w'))
for dom in("ground","air","naval"):
    print("\n==",dom)
    for lst,label in((ra,"OpenRA"),(md,"Mindustry")):
        rs=sorted([x for x in lst if x[2]==dom],key=lambda x:-(x[3]*max(x[4],1)))
        print(label,len(rs),"top by hp*dps:")
        for x in rs[:8]: print("   ",x[1],"hp",x[3],"dps",x[4],"rng",x[5],"spd",x[6],"| cost/tier",x[7])
        print("   weakest:", [(x[1],x[3],x[4]) for x in rs[-4:]])
