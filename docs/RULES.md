# Game Rules — Duel Master Battle (Wizard Ward Duel)

**Source of truth:** [PRD.md](PRD.md)

## Rules Canon

Duel Master Battle is a real-time wizard ward duel built on hidden-pattern deduction. Each duelist secretly sets a **ward pattern** by placing **essences** into named **loci**. Attacks compare patterns using aggregate feedback only.

### Terminology

| Concept | Term |
|---------|------|
| Colour / magic type | **Essence** |
| Slot / point | **Locus** (Roach, Uzag, Lieana, Gyse, …) |
| Secret code | **Ward pattern** |
| Guess | **Attack pattern** |
| Exact match | **Fracture** |
| Colour-only match | **Echo** |
| Miss | **Fade** |
| Bot | **Rival wizard** |
| Draw (no solve) | **Stalemate** |
| Simultaneous solve | **Clash** |

### Feedback rule (hard)

Attacks may travel positionally in animation, but feedback resolves **non-positionally**. The UI receives only aggregate counts: fractures, echoes, fades.

## Encounter-driven rules

Each duel uses a `DuelRuleset` / `DmbDuelRuleset` defining:

- **Locus count** (1–8)
- **Secret essence pool** and **attack essence pool**
- **Max attacks per duelist**
- **Cast window** base min/max seconds
- **Last Stand** optional comeback fields
- **allow_repeats**

See [Encounter design](ENCOUNTER_DESIGN.md).

**Core Duel** (the MVP, default) is the balance anchor: 4 loci, 6 essences, 10 casts each,
5 s minimum / 60 s maximum cast window. See [CORE_MVP.md](CORE_MVP.md). Archmage Duel
(4 loci, 10 essences, 12 casts) and the other encounters remain defined but dormant.

## Mechanical rules

- Multiset Mastermind scoring (`exact` / `colour_only` internally; Fracture / Echo / Fade in UI).
- Illegal attacks rejected.
- Repeats per encounter config.

## Real-time duel flow

1. Select difficulty and encounter.
2. Set hidden ward pattern → **Lock ward**.
3. Both duelists act in real time with independent **cast windows**.
4. Cast when min time elapsed; auto-cast at max time.
5. Aggregate feedback after each attack.
6. Result: Victory, Defeat, Clash, or Stalemate.

## Win conditions

- **Victory:** player breaks rival ward (rival Last Stand exhausted).
- **Defeat:** rival breaks player ward.
- **Clash:** simultaneous ward breaks or comeback clash during Last Stand.
- **Defeat (exhaustion):** you use all your casts without breaking the rival's ward.
- **Victory (exhaustion):** the rival uses all its casts first.
- **Stalemate:** both exhaust attack limits in the same instant without a broken ward.

No progress tie-break in v1.

## Difficulty (global)

| Level | Bot behaviour | Casts at |
|-------|---------------|----------|
| Apprentice (easy) | Consistent guesses, 40% "forgetful" casts | 26–48 s into its window |
| Adept (medium) | Consistent guesses | 16–30 s |
| Archmage (hard) | Capped minimax | 10–20 s |

## Accessibility

Essences use labels, symbols, and icons — not colour alone.
