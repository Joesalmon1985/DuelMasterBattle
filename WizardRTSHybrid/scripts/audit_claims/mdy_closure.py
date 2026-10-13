import sys, json, collections
sys.path.insert(0,'.')
from wizard_rts.industry import registry as R, units as U, blocks as B
kinds=R.kinds()
ex=R.extraction()
# raw wares available from the world
have={"log","plank","granite","iron","coal","iron_ore","gold_ore","gold","stones"}   # Widelands economy wares
have|={"mdy.sand","mdy.copper","mdy.lead","mdy.scrap","mdy.titanium","mdy.thorium","mdy.beryllium","mdy.tungsten"}
for rules in ex["deposit_rules"].values():
    for r in rules: pass
liq={"water"}
def w(item): return item if item.startswith("mdy.") or item in have else item
produces=collections.defaultdict(list)
changed=True
rounds=0
made_by={}
while changed:
    changed=False; rounds+=1
    for k in kinds:
        b=R.block(k)
        if b["sandbox"] if "sandbox" in b else False: continue
        role=b["role"]
        cons=set(b.get("consume_items") or {})
        for grp in [b.get("consume_items") or {}]:
            pass
        cl=set(b.get("consume_liquids") or {})
        if not cons<=have or not cl<=liq: continue
        outs=set(b.get("output_item") or {})|set((b.get("results") or {}).keys())
        for o in outs:
            if o not in have: have.add(o); made_by[o]=k; changed=True
        for o in (b.get("output_liquid") or {}):
            if o not in liq: liq.add(o); made_by["liq:"+o]=k; changed=True
    # pumps/solid pumps yield liquids from floor
        if role=="pump":
            for o in (b.get("output_liquid") or {}):
                if o not in liq: liq.add(o); made_by["liq:"+o]=k; changed=True
print("closure rounds",rounds)
print("items obtainable:",sorted(have))
print("liquids obtainable:",sorted(liq))
# blocks whose COST wares are all obtainable
bad=[]
tot=0
for k in kinds:
    b=R.block(k)
    if b.get("sandbox"): continue
    tot+=1
    miss=[g for g in b["cost"] if g not in have]
    if miss: bad.append((k,miss))
print("blocks",tot,"with unobtainable cost ware:",len(bad)); print(bad[:40])
# all items declared vs obtainable
alli=[ "mdy."+i for i in R.defs().get("items",{})] if isinstance(R.defs().get("items"),dict) else []
print("items declared but not obtainable:", [i for i in alli if i not in have])
json.dump({"have":sorted(have),"liq":sorted(liq),"bad":bad,"made_by":made_by},open('/tmp/claude-0/audit/mdy_closure.json','w'),indent=1)
