## Dummy OS Energy 0.2.0-alpha.28

**Tag:** `0.2.0-alpha.28`

### Grid Support Contract Alignment

Alpha 28 aligns the Reserve SOC -> Grid Support -> Preview -> Plan72 chain after live validation of Alpha 27 exposed downstream contract mismatches.

#### Fixed
- Grid Support now consumes the published Reserve SOC grid-support handoff when `grid_support_required` is true.
- `grid_support_deficit_kwh` is treated as the authoritative battery-energy shortfall for safety grid support.
- Structurally complete 72-hour input remains usable for shadow planning when the public Input72h state is `runtime_blocked` but all 72 planner hours are valid.
- Grid-support feasibility is evaluated across dynamic pre-solar 15-minute charge windows instead of being capped by only the battery headroom available at the current instant.
- Plan72 can consume Grid Support selected charge slots.
- A 100% reserve target created by the grid-support handoff is treated as a target rather than as a permanent 100% discharge floor during dynamic support.
- Published-contract wiring now includes Input72h, Energy Need and Reserve SOC without rebuilding those contracts inside the Grid Support sensor path.

#### Validation
- Full regression suite passes.
- Live regression case covered: 10.002 kWh battery-energy deficit, equivalent to approximately 10.872 kWh AC grid input at 92% charge efficiency.
- Native architecture remains 15 minutes / 72 hours / 288 slots.
- Shadow-only safety boundary remains unchanged: no physical execution authority, no battery service calls, no operational plan-store writes from this planner layer.

#### Release intent
This release is intended for live Home Assistant validation of the corrected planner chain. Physical battery execution remains outside this release boundary.
