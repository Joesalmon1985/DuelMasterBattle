The AI of the playtested checkpoint 6096997 (git worktree of that commit), seed 507, six factions at war, 40 game minutes.
Per ten minutes and faction: units, navy, warehouses, kills (units + buildings). Findings: no kill and no army movement before minute 20
(12-29 idle units each), then at minutes 20-30 a collapse (Red, Blue, Purple, Orange lose their only warehouse, Green and Yellow
survive), no ship until minute 30, worst simulation step 15.7 s. The same script ran against the new tree for the comparison in
docs/PLAYTEST_FIXES.md: python3 run_on_any_checkout.py <checkout root> 507 40
