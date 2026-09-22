# G05 starting village dialogue audit — node:35 / seed 507

Authoritative Person roster with ordinary and Rockfall talk behaviour.

## person:16

- display_name: Worker-attendant:building:25
- role: worker
- occupation: Factory worker
- workplace_id: building:25
- workplace: Skirmisher Yard (factory)
- activity: working / Working
- resource: None
- eligible Rockfall helper: True
- occupation answer: I work at Skirmisher Yard. Processed material comes here for the muster.

## person:17

- display_name: Worker-attendant:building:26
- role: worker
- occupation: Factory worker
- workplace_id: building:26
- workplace: Line Yard (factory)
- activity: working / Working
- resource: None
- eligible Rockfall helper: True
- occupation answer: I work at Line Yard. Processed material comes here for the muster.

## person:18

- display_name: Worker-attendant:building:27
- role: worker
- occupation: Factory worker
- workplace_id: building:27
- workplace: Heavy Yard (factory)
- activity: working / Working
- resource: None
- eligible Rockfall helper: True
- occupation answer: I work at Heavy Yard. Processed material comes here for the muster.

## person:19

- display_name: Worker-site_worker:building:21
- role: worker
- occupation: Clay worker
- workplace_id: building:21
- workplace: Clay Pits (primary)
- activity: carrying / Carrying spring water
- resource: Spring water
- eligible Rockfall helper: True
- occupation answer: I work the clay ground beyond the houses.

## person:20

- display_name: Worker-site_worker:building:22
- role: worker
- occupation: Miner
- workplace_id: building:22
- workplace: Ore Ridge (primary)
- activity: working / Working
- resource: None
- eligible Rockfall helper: True
- occupation answer: I work the ridge. Material from here goes down to the works.

## person:21

- display_name: Worker-site_worker:building:23
- role: worker
- occupation: Woodcutter
- workplace_id: building:23
- workplace: Woodland Cuttings (primary)
- activity: carrying / Carrying foraged berries and nuts
- resource: Foraged berries and nuts
- eligible Rockfall helper: True
- occupation answer: I work the woodland edge. We bring foraged berries and nuts back into the settlement.

## person:22

- display_name: Worker-site_worker:building:24
- role: worker
- occupation: Works worker
- workplace_id: building:24
- workplace: Berry infusion Cooking Hearth (processor)
- activity: carrying / Carrying berry infusion
- resource: Berry infusion
- eligible Rockfall helper: True
- occupation answer: I work at Berry infusion Cooking Hearth. We combine what comes in from the surrounding land.

### Talk samples — person:16
- normal Talk: `dialogue.person.ordinary` — The works are running steadily.
- post-inspect Talk: `dialogue.boulder.offer` — Need something?
  - choices: ask_clear_rockfall, ask_occupation, not_now
- Rockfall-active Talk: `dialogue.boulder.moving` — Give me a moment. I'll get these shifted.
- Rockfall-completed Talk: `dialogue.person.ordinary` — The works are running steadily.

### Talk samples — person:17
- normal Talk: `dialogue.person.ordinary` — The works are running steadily.
- post-inspect Talk: `dialogue.boulder.offer` — Need something?
  - choices: ask_clear_rockfall, ask_occupation, not_now
- Rockfall-active Talk: `dialogue.boulder.other_watching` — Looks like someone's dealing with those rocks.
- Rockfall-completed Talk: `dialogue.person.ordinary` — The works are running steadily.

### Talk samples — person:18
- normal Talk: `dialogue.person.ordinary` — The works are running steadily.
- post-inspect Talk: `dialogue.boulder.offer` — Need something?
  - choices: ask_clear_rockfall, ask_occupation, not_now
- Rockfall-active Talk: `dialogue.boulder.other_watching` — Looks like someone's dealing with those rocks.
- Rockfall-completed Talk: `dialogue.person.ordinary` — The works are running steadily.

### Talk samples — person:19
- normal Talk: `dialogue.person.ordinary` — I'm taking spring water down to the works.
- post-inspect Talk: `dialogue.boulder.offer` — Need something?
  - choices: ask_clear_rockfall, ask_occupation, not_now
- Rockfall-active Talk: `dialogue.boulder.other_watching` — Looks like someone's dealing with those rocks.
- Rockfall-completed Talk: `dialogue.person.ordinary` — I'm taking spring water down to the works.

### Talk samples — person:20
- normal Talk: `dialogue.person.ordinary` — Steady work at Ore Ridge.
- post-inspect Talk: `dialogue.boulder.offer` — Need something?
  - choices: ask_clear_rockfall, ask_occupation, not_now
- Rockfall-active Talk: `dialogue.boulder.other_watching` — Looks like someone's dealing with those rocks.
- Rockfall-completed Talk: `dialogue.person.ordinary` — Steady work at Ore Ridge.

### Talk samples — person:21
- normal Talk: `dialogue.person.ordinary` — I'm taking foraged berries and nuts down to the works.
- post-inspect Talk: `dialogue.boulder.offer` — Need something?
  - choices: ask_clear_rockfall, ask_occupation, not_now
- Rockfall-active Talk: `dialogue.boulder.other_watching` — Looks like someone's dealing with those rocks.
- Rockfall-completed Talk: `dialogue.person.ordinary` — I'm taking foraged berries and nuts down to the works.

### Talk samples — person:22
- normal Talk: `dialogue.person.ordinary` — I'm taking berry infusion down to the works.
- post-inspect Talk: `dialogue.boulder.offer` — Need something?
  - choices: ask_clear_rockfall, ask_occupation, not_now
- Rockfall-active Talk: `dialogue.boulder.other_watching` — Looks like someone's dealing with those rocks.
- Rockfall-completed Talk: `dialogue.person.ordinary` — I'm taking berry infusion down to the works.

