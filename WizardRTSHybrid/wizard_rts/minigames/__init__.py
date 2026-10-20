"""The village minigames (`docs/PLAN_VILLAGE_MINIGAMES.md`): eighteen small games played at a conversation, each a pure engine over JSON dicts.

Nothing here touches the economy, the clock, the ledger or a relationship: a game is a thing two people do while the world goes on. The engines
are registered in `catalogue.ENGINES`; `table.py` runs one at a conversation; `data/narrative/minigames.json` says who plays what and what they say.
"""
