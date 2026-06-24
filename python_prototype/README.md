# Python Prototype

Minimal tkinter proof of rules + sequential Human vs Bot flow.

## Run tests
```bash
cd python_prototype
python3 -m pytest -q
```

## Run prototype
```bash
cd python_prototype
python3 run_prototype.py
```

## Flow
1. Click secret peg slots, pick colours 0-9, lock when all 4 set.
2. Bot auto-guesses (up to 12).
3. Make your guesses against bot's hidden code.
4. Result dialog on finish; New game to restart.
