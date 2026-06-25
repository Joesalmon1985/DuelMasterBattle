# Game Rules — Duel Master Battle (Wizard Duel)

## Encounter-driven rules

Each duel uses an **encounter ruleset** (`DuelRuleset` / `DmbDuelRuleset`) defining:

- **Slot count** (1–4 points)
- **Secret magic pool** — types allowed when casting your hidden pattern
- **Attack magic pool** — types allowed when attacking (must include all secret types)
- **Max attacks per player** — base cap; modifiers may add `extra_attacks`

See [Encounter design](ENCOUNTER_DESIGN.md) for the four built-in encounters.

**Archmage Duel** (`archmage_duel`) matches classic Mastermind: 4 slots, 10 types, 12 attacks, Expert bot.

## Mechanical rules (Mastermind core)
- Each pattern has **1–4 slots** (encounter-dependent).
- Each slot uses a magic type from the relevant pool.
- **Repeated types** allowed unless the encounter sets `allow_repeats = false`.
- Illegal guesses are rejected and do not consume an attack.

## Wizard-duel terminology

| Mastermind | Wizard duel |
|------------|-------------|
| Secret code slot | Magical **point** (Shield, Body, Staff, Mind — or fewer per encounter) |
| Colour / peg | **Magic type** (Flame, Frost, Storm, …) |
| Exact match (black pin) | **Hit** — correct type, correct point |
| Colour-only (white pin) | **Weakness** — correct type, wrong point |
| No pin | **Unaffected** — no matching weakness revealed |

### Ten magic types (options 0–9)
0 Flame · 1 Frost · 2 Storm · 3 Stone · 4 Light · 5 Shadow · 6 Vine · 7 Metal · 8 Spirit · 9 Arcane

## Feedback scoring
Multiset Mastermind scoring (`exact`, `colour_only`). UI presents Hit / Weakness / Unaffected.

## Alternating Human vs Bot flow
1. Select encounter on main menu → **Start duel**.
2. Human sets pattern points and **Cast pattern** (secret pool).
3. Bot sets a hidden pattern from the same secret pool rules.
4. **Human attacks first** — one guess per turn; feedback in your attack history.
5. **Bot attacks** — one guess per turn; feedback in enemy history.
6. Turns alternate until someone solves or both exhaust configured max attacks.
7. Result screen; **New duel** or **Back to menu**.

## Win / draw
- Immediate win on full solve (Hits == slot count)
- Both exhaust max attacks without solving → draw
- Otherwise tie-break on best Hit/Weakness progress

## Bot difficulty (per encounter)
| Level | Behaviour |
|-------|-----------|
| Easy | Random legal guesses |
| Normal | Candidate elimination; random pick from survivors |
| Hard | Minimax partition strategy (capped pool) |
| Expert | Strongest deterministic solver (Archmage default) |

Opening guess pattern: first pool id twice, second pool id twice (truncated to slot count). Archmage → `[0,0,1,1]`.

## Accessibility
Magic types use labels, numbers, and symbols — not colour alone.
