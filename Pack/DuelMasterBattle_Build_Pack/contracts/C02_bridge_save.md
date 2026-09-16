# C02 — Desktop bridge, encounter ownership and saves

Source: GDD §§188–192. Python runs one bundled sidecar; Godot is the local client. Transport is replaceable behind `WorldClient` so mobile can be addressed later. The runtime has no internet dependency.

## Classes and boundaries

| Class / logical file | Contract |
|---|---|
| `SidecarServer` / `sim/dmb/bridge/server.py` | Bind 127.0.0.1, accept one authenticated client, decode frames, queue commands to the single writer, encode results. No game rules. |
| `FrameCodec` / `bridge/codec.py` and `client/bridge/frame_codec.gd` | Incremental bytes → complete envelopes; incomplete frames remain buffered. No assumption that one TCP read equals one message. |
| `SidecarLauncher` / `client/bridge/sidecar_launcher.gd` | Start bundled executable with per-launch token, read startup endpoint, handshake, own child PID, close cleanly. No shell interpolation. |
| `WorldClient` / `client/bridge/world_client.gd` | `send(command)`, `request_view(scope)`, `pause(reason)`, `resume(token)`; signals result, projection_updated, bridge_failed. |
| `EncounterRegistry` / `sim/dmb/encounters/registry.py` | `grant(kind, ids, snapshot)`, `checkpoint(delta)`, `prepare_transfer`, `commit_transfer`, `close(result)` |
| `EncounterHost` / `client/encounters/encounter_host.gd` | Execute a leased battle/puzzle/duel; submit ordered deltas and safe checkpoints. |
| `SaveCoordinator` / `sim/dmb/persistence/coordinator.py` | `request_save(slot)`, `prepare_load(slot)`, `commit_load()`; coordinates both owners. |
| `SaveRepository` / `persistence/repository.py` | Version/hash verification, atomic file replacement, previous-good backup and migrations. No partial load into live state. |

## Framing and handshake

Frame = 4-byte unsigned big-endian payload length, then exactly that many UTF-8 JSON bytes. Maximum frame size 8 MiB; reject zero/oversize/malformed envelopes and pause on protocol failure. Larger snapshots use numbered chunks with total hash, maximum aggregate 64 MiB for the initial build; tune with measured saves. Never apply an incomplete chunk set. Transport buffers must handle split headers, split multibyte characters and multiple frames in one read.

Handshake fields: protocol_version=1, session_id, launch token, game build ID, rule/content hashes, requested role=local_client. Reply: accepted protocol, authoritative world_version, pause state, save/lease versions and capabilities. Token is fresh per launch, not a save identity. Bind only loopback; do not log the token. Connection establishment uses a five-second timeout; transient retries are bounded at three attempts. A protocol/content mismatch reports the incompatible value and stays paused.

Mutation envelope fields: `protocol_version`, `session_id`, `world_id`, `command_id`, `expected_world_version`, `kind`, `payload`; encounter messages also carry `lease_id`, `lease_version`, `sequence`, `base_checkpoint_hash`. Client sends one mutation at a time at an accounting boundary. Passive reads can run separately. Replay stores semantic commands without requiring the old authentication token.

Reply: command ID, accepted/rejected/duplicate, code, committed world_version, ordered event batch, knowledge-filtered projection delta, interrupt and public feedback. The receipt lookup precedes stale-version rejection, so a retransmission after a lost acknowledgement returns its original result. Same ID/different payload fails. Distinct stale command fails without reinterpreting user intent.

## Command registry

| Kind | Required payload | Authority/check |
|---|---|---|
| `AdvanceGame` | delta_ms, clock_sequence, encounter checkpoint deltas | Single clock producer; no pause; aligned C03 boundary |
| `Travel` | from_node, to_node, departure checkpoint, observed exit token | Adjacency/current node; one strategic turn |
| `Wait` | current_node, press_id | Once per distinct press; no duel/modal pause |
| `Observe` | entity_id, observation token | Current visible representation; knowledge-filtered result |
| `Interact` | entity_id, action_id, view_version | Current range/local area and legal semantic verb |
| `ChooseDialogue` | conversation_id, choice_id, context_version | Re-evaluate predicates/effects; close choice pause once |
| `CastWorld` | effect_kind, target_id, observation token | C07 local target; route leased targets to owner |
| `StartDuel` | actor_or_cube_id, ruleset_id | Eligible local/adjacent encounter, visit allowance |
| `TransferItem` | item_id/quantity, source, destination, use_id | Ownership/range/recipe predicate; atomic effect |
| `EncounterCheckpoint/Result` | lease fields, ordered changes, outcome | Exclusive lease/version/sequence; legal transition |
| `Pause/Resume` | reason or pause token | Token ownership; no unrelated pause removal |
| `Save/Load` | validated slot ID | Coordinated barrier; never a caller-supplied path |

AI/internal construction/diplomacy actions use the same validator but a faction-authority context. Player commands cannot impersonate that role. Developer fixture setup is accepted only before a world begins or through explicitly enabled debug commands recorded in a non-release replay.

## Lease lifecycle

Python retains durable IDs and owns strategic node/affiliation, inventory, quest effects and era state. A battle lease transfers live position, tactical target, attack cooldown, health/shield/buff consumption and building damage for an enumerated participant set. A puzzle lease transfers mechanism and local trigger state. A duel lease transfers its private secrets, guesses, counters, local clock and RNG. The canonical snapshot in Python is a mirror of the last accepted checkpoint, not a competing simulator.

States: PREPARED → ACTIVE → FREEZING → CLOSED; failed preparation returns to unleased. Grant includes snapshot/hash/version; Godot acknowledges before any leased step. While active, Python does not damage or resolve those entities itself. Cross-system destruction requests become pending encounter commands; Godot applies them at the next 50 ms boundary, returns a checkpoint, then Python applies stock/ownership/quest consequences once. If no lease exists Python applies the shared destruction effect directly.

Every 100 ms boundary first drains two Godot steps, commits their ordered checkpoint, applies resulting destruction, then advances the corresponding Python industrial quantum. If an immediate interrupt occurs in the first 50 ms step, do not run the second step; preserve residual time and stop before additional world work. A unit produced afterward is created by Python with a unique ID, then added through a versioned reinforcement handshake. Godot may not manufacture units. Destruction at a boundary prevents subsequent production from that destroyed facility.

Travel freezes an outgoing battle, obtains its last checkpoint, closes its local lease and resolves the remainder in Python. Wait retains the lease. Incoming battle setup occurs after the travel destination commits. An era transition freezes every lease before conversion. No late delta from an earlier lease can overwrite a converted entity. A queued duplicate reinforcement or result returns the prior receipt.

## Save and recovery transaction

1. Acquire save pause token and finish the current accepted accounting boundary. Block new mutations.
2. Freeze active encounters and collect matching checkpoint hashes/versions, including a mid-duel secret/clock state.
3. Validate the composed snapshot, receipts, RNG and all references. Serialize to a temporary file in the save directory, flush and atomically replace the slot. Keep one previous-good backup. Never overwrite the backup with an invalid candidate.
4. Persist the matching replay offset/content manifest. Acknowledge save; release only the save token and restore other pause reasons.

Load builds a new candidate WorldState, validates schema/content and tombstones, and reconstructs encounters before swapping the live state. Clear the old session's pending input. No elapsed real-world time is applied. Reset authentication token on process relaunch but preserve command receipts/world IDs. Prototype versions remain on disk and receive an unsupported-version/new-game message; migrations are explicit, never guessed.

Maintain a coordinated recovery checkpoint every five unpaused seconds and after Travel/Wait, quest outcome, duel result and era conversion. On sidecar/client failure pause immediately. Bounded restart restores the checkpoint and matching encounter state; the UI reports the rollback time if progress since that checkpoint was lost. Never say an unsaved action survived. Recovery does not replay mouse input speculatively or grant catch-up production.

Verification includes lost acknowledgements, partial frames, stale deltas, client/sidecar termination at each save barrier, corrupt current save with good backup, mid-duel restore, a duplicated delivery and a mid-transition reconnect. Check continuation state, not merely that a save file exists.

## Technical references

Godot supplies a TCP stream client through [StreamPeerTCP](https://docs.godotengine.org/en/stable/classes/class_streampeertcp.html); Python supplies sockets in its [standard library](https://docs.python.org/3/library/socket.html). Length framing, leases and idempotency above are this project's contracts, not features supplied automatically by either API. Pin and verify calls against the checkout's actual versions.
