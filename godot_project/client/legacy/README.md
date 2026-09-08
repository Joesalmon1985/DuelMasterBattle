# Legacy client components (dormant)

These components belonged to the pre-MVP board (picker-above-locus, drag tray,
FTUE overlays, ward barrier art, cast timer ring, Last Stand visuals). They are
not referenced by the current game but still parse, and several are worth
reviving for the wider game (encounters, bosses, tutorial):

- `ward_barrier.gd` – layered ward art with STABLE/IMPACTED/FRACTURED/UNSTABLE states
- `ftue_overlay.gd` – highlight + arrow tutorial steps
- `essence_tray.gd`, `essence_token.gd`, `magic_picker.gd` – drag/drop + popup spell picker
- `locus_socket.gd`, `peg_slot.gd` – rune-decorated loci with long-press peek
- `duel_animation_controller.gd` – event-driven projectile/impact choreography
- `cast_timer.gd`, `rival_cast_indicator.gd` – ring timers
- `feedback_display.gd`, `history_row.gd` – older history rows

The MVP equivalents live in `client/components/` (`spell_slot.gd`,
`feedback_pips.gd`, `cast_button.gd`) and `client/scripts/game_board.gd`.
