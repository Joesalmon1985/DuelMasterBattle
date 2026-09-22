# Canonical game ontology

**Status:** CANONICAL — Joe decisions 2026-09-21 (consolidation on `refactor/canonical-ontology-g05`).  
**Required reading** for any cross-system people / military / industry / village / quest work.  
Supersedes conflicting DEFINED defaults in older contracts where noted; does not silently override LOCKED GDD rules.

Companion: [`docs/INTEGRATED_RUNTIME_ARCHITECTURE.md`](INTEGRATED_RUNTIME_ARCHITECTURE.md), [`docs/review/`](review/README.md).

---

## Diagram

```text
WORLD
│
├── PLACE
│   ├── Hex
│   ├── Node
│   ├── Settlement
│   ├── LocalArea
│   └── Dungeon
│
├── PERSON
│   ├── Identity/Profile
│   ├── Location
│   ├── Knowledge
│   ├── Relationships
│   ├── Goals
│   ├── Dialogue
│   ├── Employment?
│   ├── CombatantState?     → Unit record (person_id)
│   ├── LeadershipRole?
│   └── QuestBindings?
│
├── BUILDING
│   └── capabilities / attached processes
│
├── CART
├── ITEM
├── HAZARD
├── FACTION
│
└── PROCESSES
    ├── Construction / Catan economy
    ├── Logistics
    ├── Industry
    ├── Military / battle
    ├── Catastrophe
    ├── Quest
    ├── Dialogue
    └── Era / history
```

The wizard / player remains a distinct `player` record (not a Person) unless a later decision says otherwise.

---

## Hard invariants

1. **ONE Person ID = ONE human identity.** Workers, villagers, leaders, quest participants, and soldiers are all Persons.
2. **Employment does not define identity.** Job/occupation can change; ID stays.
3. **CombatantState does not define identity.** `state.units[unit:*]` holds combat fields and **must** reference `person_id`.
4. **ONE persistent entity ID = at most ONE local actor** (for Persons: one Person actor).
5. **Activity presenters update actors; they do not invent entities.** Never create a Person solely for a moving sprite.
6. **Occupation ≠ activity.** e.g. occupation=woodcutter, activity=carrying.
7. **Buildings are things; industry is a process** involving buildings (channels, processor bindings, factory meters are not separate player-facing entities).
8. **Carts are `cart:*` vehicles**, never `person:cart`.
9. **Fixtures arrange production state;** they do not own gameplay semantics.
10. **Python owns durable truth.** Godot presents that truth and owns local input / movement / leased encounters.
11. **NPC** is presentation shorthand only — not a Python entity kind.
12. **Every visible living Person supports Observe and Talk** (depth may be fallback dialogue).
13. **Unit death ⇒ linked Person death** (one tombstone/history). Demobilisation may end CombatantState while Person lives.
14. **Processed industrial outputs remain typed goods** in fiction (goat broth, pottery, …). MVP may abstract their downstream use into military supply — that is gameplay abstraction, not ontology collapse.

---

## Person ↔ Combatant

```text
state.people[person:…]     identity, social, dialogue, jobs, leadership, quests
        ↑
        │ person_id
        │
state.units[unit:…]        archetype, HP, buffs, formation, lease, battle pose
```

- `MilitaryService.spawn` creates/associates a Person and sets `unit["person_id"]`.
- A living Person has at most one **active** UnitState unless an explicit later rule says otherwise.
- Formations remain ordered **unit** IDs (combat groups), not a second human identity.

---

## Places and exploration

- Strategic truth: 19 hexes, 54 nodes, 72 edges.
- Play: soft-contiguous feel over **discrete node Travel** (one adjacent Travel = one World Turn).
- `LocalArea` is generated on first visit and **persisted**; never a second board of all 54 nodes at once.
- Settlement presentation follows [`docs/LOCAL_SETTLEMENT_PRESENTATION.md`](LOCAL_SETTLEMENT_PRESENTATION.md):
  perimeter resource sites from touching-hex orientation + built core + exits.
  Primaries are not houses.

---

## Building knowledge layers

| Layer | Meaning | Example |
|---|---|---|
| VISIBLY APPARENT | Immediate label | Village Factory |
| OBSERVED / INVESTIGATED | Operating evidence | Yard quiet; workers waiting |
| LEARNED / KNOWN | Cause via evidence/testimony/Aspects | Ridge supply stopped after the manifestation |

Never show processor/route IDs, solver coefficients, hidden stocks, or privileged intentions in ordinary UI.

---

## Population boundary

Persistent Person: any human who materially participates in simulation or can be meaningfully interacted with.

Allowed non-Persons: purely decorative anonymous crowds — **no Person ID, not targetable, no quests/history**.

---

## Roadmap gate

```text
Canonical ontology consolidation → G05 coherent Prehistoric slice → Joe PASS
  → T097 era → G06 same game becomes Historic → G07+ cycles
```

**Do not start T097 until Joe PASSes the revised G05.**

---

## Locked vs superseded

| Topic | Ruling |
|---|---|
| Soldiers are Persons + UnitState(`person_id`) | **USER decision 2026-09-21** — supersedes prior DEFINED split-without-link |
| No ECS / one-subclass-per-def | C01 LOCKED — retained |
| Worker motion illustrative | GDD LOCKED — retained |
| Carts persistent entities | GDD LOCKED — retained |
| Python durable ownership | LOCKED — retained |
