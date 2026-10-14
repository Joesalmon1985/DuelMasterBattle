import sys, json
sys.path.insert(0,'.')
from wizard_rts.industry import registry as R
ex=R.extraction()
# start: Widelands wares the WL economy produces
have={"log","plank","granite","iron","coal","gold","iron_ore","gold_ore"}
liq=set(); built=set(); log=[]
kinds=[k for k in R.kinds() if not R.block(k).get("sandbox")]
tierof={}
for k in kinds:
    b=R.block(k)
    if b["role"] in("drill",): tierof[k]=int(b.get("tier") or 0)
def mdy(i): return i if i.startswith("mdy.") else "mdy."+i
ch=True; rnd=0
while ch:
    ch=False; rnd+=1
    for k in kinds:
        if k in built: continue
        b=R.block(k)
        if all(g in have for g in b["cost"]):
            built.add(k); ch=True; log.append((rnd,k))
    best=max([tierof[k] for k in built if k in tierof] or [0])
    for k in list(built):
        b=R.block(k)
        # drills: items from deposits/floors available at tier
        if b["role"]=="drill":
            t=tierof[k]
            for dep,rules in ex["deposit_rules"].items():
                for r in rules:
                    if r["min_tier"]<=t:
                        it=r["item"]; w=it if it in("granite","iron_ore","gold_ore","coal") else "mdy."+it
                        if w not in have: have.add(w); ch=True
            fr=ex["floor_rules"]["sand"]
            if fr["min_tier"]<=t and "mdy.sand" not in have: have.add("mdy.sand"); ch=True
        if b["role"]=="pump":
            for l in (b.get("output_liquid") or {}):
                if l=="water" and l not in liq: liq.add(l); ch=True
        ins=set(b.get("consume_items") or {}); cl=set(b.get("consume_liquids") or {})
        if b["role"] in("crafter","heater","generator") and ins<=have and cl<=liq:
            for o in list(b.get("output_item") or {})+list((b.get("results") or {})):
                if o not in have: have.add(o); ch=True
            for l in (b.get("output_liquid") or {}):
                if l not in liq: liq.add(l); ch=True
notbuilt=[k for k in kinds if k not in built]
print("rounds",rnd,"buildable",len(built),"of",len(kinds))
print("NOT bootstrap-buildable:",[(k[4:],[g for g in R.block(k)["cost"] if g not in have]) for k in notbuilt])
print("items",sorted(g for g in have if g.startswith("mdy.")))
print("liquids",sorted(liq))
json.dump({"built":sorted(built),"not":[(k,[g for g in R.block(k)["cost"] if g not in have]) for k in notbuilt]},open('/tmp/claude-0/audit/boot.json','w'))
