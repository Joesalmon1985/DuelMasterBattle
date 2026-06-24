# Game Rules — Duel Master Battle (Wizard Duel)

## Mechanical rules (unchanged Mastermind)
- Each pattern has exactly **4 slots**.
- Each slot uses one of **10 magic types** (ids `0`–`9`).
- **Repeated types are allowed**.
- Up to **12 guesses** per side.
- Illegal guesses are rejected and do not consume a guess.

## Wizard-duel terminology

| Mastermind | Wizard duel |
|------------|-------------|
| Secret code slot | Magical **point** (Shield, Body, Staff, Mind) |
| Colour / peg | **Magic type** (Flame, Frost, Storm, …) |
| Exact match (black pin) | **Hit** — correct type, correct point |
| Colour-only (white pin) | **Weakness** — correct type, wrong point |
| No pin | **Unaffected** — no matching weakness revealed |

### Four points (positions)
1. **Shield**
2. **Body**
3. **Staff**
4. **Mind**

### Ten magic types (options 0–9)
0 Flame · 1 Frost · 2 Storm · 3 Stone · 4 Light · 5 Shadow · 6 Vine · 7 Metal · 8 Spirit · 9 Arcane

Each type has a distinct colour, text label, and short symbol (not colour alone).

## Feedback scoring
Multiset Mastermind scoring is unchanged internally (`exact`, `colour_only`). UI presents Hit / Weakness / Unaffected.

Example: secret `[0,0,1,2]`, guess `[0,1,0,3]` → Hit=1, Weakness=1.

## Sequential Human vs Bot flow
1. Human sets four magical points and **Cast pattern**.
2. Enemy bot attacks with up to 12 visible guesses + Hit/Weakness feedback.
3. Bot sets a hidden pattern.
4. Human attacks with up to 12 guesses via the same click-slot picker.
5. Result screen compares outcomes; **New duel** restarts.

## Win / draw
Same as Mastermind duel rules (see previous table in release notes).

## Bot difficulty
| Level | Behaviour |
|-------|-----------|
| Easy | Random legal guesses |
| Normal | Candidate elimination; picks from remaining possible patterns |
| Hard | Candidate elimination + minimax partition strategy (capped for responsiveness) |
| Expert | Strongest deterministic solver implemented (default) |

The solver uses candidate elimination with fixed opener `[0,0,1,1]`. It is **not claimed mathematically optimal**.

## Accessibility
Magic types use labels, numbers, and symbols — not colour alone.
