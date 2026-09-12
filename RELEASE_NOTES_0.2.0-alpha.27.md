## Dummy OS Energy 0.2.0-alpha.27

**Tag:** `0.2.0-alpha.27`

## Grid-support capacity handoff fix

Alpha.27 corrects the planner behavior for reserve requirements that exceed what the battery can hold above the minimum SOC.

Previously, such a case was marked `infeasible` by Reserve SOC and blocked Preview, Safety and the 72-hour planner before grid charging could be evaluated.

Alpha.27 keeps the reserve target capped at 100% and exposes the remaining battery-energy deficit as grid-support demand. Feasibility is then decided downstream from actual safe charge-window capacity and price-aware 15-minute grid-charge allocation.

### Live regression case

The fix covers the observed live Alpha.26 case:

- battery capacity: 7.2 kWh
- SOC: 95%
- minimum SOC: 5%
- safety reserve: 7%
- energy need until usable solar: 8.688 kWh
- required including reserve: 9.192 kWh
- available battery energy above minimum SOC: 6.48 kWh
- remaining deficit: 2.712 kWh

This deficit is now routed to grid-support planning instead of being treated as a fatal static-capacity blocker.

## Safety boundary

Unchanged:

- shadow-only planning
- no physical execution authority
- no direct battery service calls
- native 15-minute resolution
- rolling 72-hour horizon / 288 slots
- physical battery execution remains with the existing EMS until separately validated

## Validation gate

Publication requires compile validation, the complete pytest suite, manifest validation, version consistency and the Alpha.27 reserve-to-grid-support regression contract to pass on the release commit.
