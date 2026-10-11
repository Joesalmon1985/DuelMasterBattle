Kept on purpose: the first version of the guard-post / squad code, rejected. 1040 s wall for 40 game minutes, 0-2 attacks per faction,
armies of 24-33 standing at their posts, and the stuck report listing units stalled for 1200-1800 s ("another unit stands on the next tile",
"route search budget for this quantum was spent"). Causes: every soldier was sent to the same tile (a shared tile jams the rest), a goal tile
occupied by a friendly unit could never be reached, and the per-quantum route budget was always spent by the same units. Fixed by distinct
post slots, "within two tiles of an occupied goal is there", and rotating who gets the route budget (see DECISIONS D8).
