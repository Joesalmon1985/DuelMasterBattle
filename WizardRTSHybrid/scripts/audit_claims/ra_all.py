import sys, json
sys.path.insert(0,'.'); sys.path.insert(0,'tests')
from multiprocessing import Pool
def unit_job(args):
    prod,unit=args
    from test_openra_content import world, unlock, building, run
    from wizard_rts import construction as con, openra_content as OC
    from wizard_rts.economy import produce
    w=world("developer"); unlock(w,"Red")
    try:
        from test_openra_content import home
        b=home(w,"Red") if prod=="warehouse" else building(w,prod,"Red")
    except Exception as e:
        return args,{"ok":False,"why":"producer not buildable: "+repr(e)[:80]}
    try:
        for pre in OC.UNIT_PREREQ_OVERRIDE.get(unit,[]): building(w,pre)
    except Exception: pass
    rec=con.recipe_for(w,b,unit)
    for g,n in rec["cost"].items(): produce(w,b["id"],g,n)
    r=con.queue_unit(w,b["id"],unit)
    if r["status"]!="ok": return args,{"ok":False,"why":"queue refused: "+str(r.get("reason"))}
    before=len([u for u in w.units.values() if u["faction_name"]=="Red"])
    run(w,rec["ms"]/1000+30)
    after=len([u for u in w.units.values() if u["faction_name"]=="Red"])
    return args,{"ok":after>before,"why":"" if after>before else "not produced; queue="+str(b.get("queue"))[:80]}
def bld_job(kind):
    from test_openra_content import world, unlock, building, home, run
    from wizard_rts import construction as con, openra_content as OC, ai
    from wizard_rts.economy import produce
    w=world("developer"); unlock(w,"Red")
    for pre in con.build_spec(kind).get("requires",[]):
        try: building(w,pre)
        except Exception: pass
    wh=home(w)
    spec=con.build_spec(kind)
    for g,n in spec["cost"].items(): produce(w,wh["id"],g,n+2)
    bid=ai._place_near(w,"Red",kind,wh)
    if not bid: return kind,{"ok":False,"why":"no placement"}
    run(w,400)
    b=w.buildings[bid]
    return kind,{"ok":bool(b.get("operational") and not b.get("constructing")),"why":str(b.get("constructing"))[:60]}
if __name__=="__main__":
    from wizard_rts import construction as con
    jobs=[(p,u) for p,recs in con.RECIPES.items() for u in recs]
    kinds=[k for k,s in con.BUILD_MENU.items() if s.get("game") in("openra",) ]
    print(len(jobs),"units",len(kinds),"openra buildings")
    with Pool(2) as p:
        ur=p.map(unit_job,jobs,chunksize=2); br=p.map(bld_job,kinds,chunksize=2)
    json.dump({"units":[[list(a),r] for a,r in ur],"buildings":dict(br)},open('/tmp/claude-0/audit/ra_all.json','w'),indent=1)
    print("units ok",sum(r["ok"] for a,r in ur),"/",len(ur)); print([ (a,r["why"]) for a,r in ur if not r["ok"]])
    print("bld ok",sum(r["ok"] for k,r in br),"/",len(br)); print([(k,r["why"]) for k,r in br if not r["ok"]])
