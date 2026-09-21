# G05 known defects / notes — Village Foundation

**Status:** FIX_REQUIRED — Village Foundation human sanity check (quest paused)

## This checkpoint

| Item | Result |
|------|--------|
| Baseline fixture | `FX-VILLAGE` healthy; no demon / sluice / shortage quest |
| Quest preserved | `FX-VILLAGE-QUEST` |
| Primaries | Perimeter sectors; terrain props not houses |
| Occupations | Canonical `public_occupation` (not Carrier / attendant churn) |
| Dialogue | Baseline has no quest/cause/guide promises |
| Humanoid scale | `ActorVisual.normalize_humanoid_scale` → 96px height |
| Worker rhythm | Presentation-only load/unload pauses |

## Remaining oddities (non-blocking if true)

- Soft-contiguous countryside between nodes still discrete LocalArea loads
- Decorative housing scenery not yet densified
- Quest reintegration still required after foundation acceptance

Do not expose internal IDs in ordinary labels.
