# Dummy OS Energy 0.2.0-alpha.26 - Manual Plan Controls Recovery

**Tag:** `0.2.0-alpha.26`

Alpha.26 is a corrective release that restores complete native Home Assistant manual planning controls while preserving the new Dummy OS Energy planner architecture.

## Restored manual controls

Each of the three persistent plan slots now exposes six native controls:

- action (`charge` / `discharge`)
- start time
- power (100-3200 W)
- target SOC (5-100%)
- maximum start delay (0-60 minutes)
- maximum runtime (15-1440 minutes, 15-minute steps)

The controls feed the existing Manual Plan Lifecycle. Finalization still uses validation, overlap protection, manual priority and the persistent three-slot shadow Plan Store.

## Persistence

Manual input controls and in-progress per-slot drafts are stored through Home Assistant storage and restored after integration/Home Assistant restart. Finalized plans continue to use the existing persistent Plan Store.

## Safety boundary

This release restores planning functionality only. It does not grant physical battery execution authority:

- operational Plan Store write: false
- scheduler invoked: false
- safety chain invoked: false
- external service calls performed: false
- physical execution authority: false

The existing EMS remains responsible for physical battery control until that migration is separately validated and approved.

## Architecture invariants

Unchanged:

- native 15-minute resolution
- rolling 72-hour horizon
- 288 forecast slots
- three persistent plan slots
- manual priority over automatic candidates

## Validation gate

Publication requires compile validation, the complete pytest suite, manifest validation and the alpha.26 manual-control regression contract to pass on the release commit.
