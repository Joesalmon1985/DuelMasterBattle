# Game Rules — Duel Master Battle

## Setup
- Each player has a **secret code** of exactly **4 pegs**.
- Each peg colour is chosen from **10 colours** (ids `0`–`9`).
- **Repeated colours are allowed** in a code.

## Guessing
- Each player has up to **12 guesses** against the opponent's code.
- Each guess is exactly 4 pegs, each from colours 0–9.
- Illegal guesses (wrong length, out-of-range colour) are **rejected** and do **not** consume a guess.

## Feedback (Mastermind scoring)
After each legal guess, the game reports:
- **exact**: pegs with correct colour **and** correct position
- **colour_only**: pegs with correct colour in the **wrong** position

Scoring uses multiset matching: each secret peg and each guess peg is counted at most once. Duplicate-colour edge cases follow standard Mastermind rules.

Example: secret `[0,0,1,2]`, guess `[0,1,0,3]` → exact=1, colour_only=1.

## Sequential Human vs Bot flow (vertical slice)
1. Human sets and locks a 4-peg secret code.
2. Bot makes up to 12 guesses against human's code (visible on board with feedback).
3. Bot sets its own hidden 4-peg code.
4. Human makes up to 12 guesses against bot's code.
5. Result screen compares outcomes.

## Win / draw (end of sequential duel)
| Situation | Outcome |
|-----------|---------|
| Only human solves bot's code | Human wins |
| Only bot solves human's code | Bot wins |
| Both solve | Fewer total guesses wins; equal → draw |
| Neither solves in 12 | Tie-break: most exact pegs in best single guess, then most colour_only; still equal → draw |

## Bot requirements (minimum)
- Generate a legal 4-peg code (colours 0–9).
- Make legal 4-peg guesses only.
- Stop after 12 guesses or on solve.
- Random legal bot is acceptable for the vertical slice.

## Accessibility (later milestone)
Colours should be distinguishable by label/number/shape, not colour alone.
