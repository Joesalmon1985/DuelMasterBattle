import sys; sys.path.insert(0,'.'); sys.path.insert(0,'tests')
from test_openra_content import world, home, run, unlock
from wizard_rts import rules
def duel(a,b,secs=90,n=1):
    w=world("test_showcase")
    h=home(w,"Red"); x,y=h["tx"]+14,h["ty"]+14
    def mk(defn,fac,tile):
        r=rules.actor(defn)
        uid=w._unit(w.faction_info[fac]["id"],fac,defn.split(".")[-1],r["name"],defn,tile)
        return w.units[uid]
    A=[mk(a,"Red",(x-3,y+i)) for i in range(n)]
    B=[mk(b,"Blue",(x+3,y+i)) for i in range(n)]
    for u in A+B:
        pass
    run(w,secs)
    ha=sum(max(0,u["hp"]) for u in A if u.get("alive",True)); hb=sum(max(0,u["hp"]) for u in B if u.get("alive",True))
    ma=sum(u["max_hp"] for u in A); mb=sum(u["max_hp"] for u in B)
    return round(ha/ma*100),round(hb/mb*100)
pairs=[("openra.4tnk","mindustry.dagger"),("openra.4tnk","mindustry.mace"),("openra.4tnk","mindustry.fortress"),("openra.4tnk","mindustry.scepter"),
       ("openra.3tnk","mindustry.mace"),("openra.3tnk","mindustry.fortress"),
       ("openra.mig","mindustry.horizon"),("openra.mig","mindustry.zenith"),("openra.mig","mindustry.antumbra"),
       ("openra.dd","mindustry.minke"),("openra.dd","mindustry.bryde"),("openra.ca","mindustry.sei")]
for a,b in pairs:
    try: print(a,"vs",b,"-> survivors hp% (openra, mindustry):",duel(a,b))
    except Exception as e: print(a,b,"ERR",repr(e)[:120])
