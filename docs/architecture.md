# Dummy OS Energy architecture

## Permanent integration model

Dummy OS Energy is the permanent Home Assistant energy integration. It started as the Dummy OS Forecast/Data layer and is now extended in place with planner, safety and later execution functionality.

The current Dummy OS EMS remains separate during migration as a reference, validation source and rollback path. It is not merged into Dummy OS Energy. Replacement functionality is rebuilt and validated inside Dummy OS Energy, after which the corresponding old EMS part can be retired step by step.

## Fixed time architecture

The forecast architecture remains fixed at:

- native resolution: **15 minutes**;
- rolling horizon: **72 hours**;
- exact forecast slots: **288**.

Planner projections may aggregate these data to hourly planning views where explicitly defined, but they do not create a second forecast architecture.

## Layer boundaries

The permanent functional chain is:

`Source / Data -> Forecast -> Contract -> Planner -> Safety -> Execution`

Responsibilities:

- **Source / Data** normalizes actual inputs and preserves missing-data semantics.
- **Forecast** creates and validates forward-looking Energy, Weather, Solar and price timelines.
- **Contract** exposes stable planner-consumable forecast data without physical authority.
- **Planner** is built under the `do_plan_*` namespace and initially remains observer/shadow only.
- **Safety** guards whether a validated plan may progress toward control.
- **Execution** may issue physical commands only after all preceding gates and final revalidation permit it.

Forecast never receives physical execution authority.

## Naming

The visible product and integration name is **Dummy OS Energy**.

The repository is:

`bliek79/dummy-os-energy`

For compatibility, the technical Home Assistant domain remains:

`dummy_os_data`

The integration directory also remains:

`custom_components/dummy_os_data`

Existing entity namespaces remain unchanged. All newly introduced planner entities use:

`do_plan_*`

## Migration rules

1. Existing Forecast/Data functionality remains operational while planner functionality is added.
2. New planner functions are observer/shadow first.
3. Every planner function is validated independently against expected behavior and, where applicable, against the current Dummy OS EMS.
4. No missing, `unknown` or `unavailable` input may be silently interpreted as zero.
5. No old EMS function is retired until the equivalent Dummy OS Energy function has been live proven.
6. Safety is connected only after planner behavior is validated.
7. Execution is connected only after safety and final revalidation are validated.
8. One problem should lead to one targeted change; migration work should not combine unrelated architectural changes.

## Forecast historical foundation

Every completed Energy quarter stores one profile:

- `normal`
- `away`

This prevents Away consumption from contaminating the normal household profile.

A completed quarter is valid only when sufficient real interval duration is covered by a valid W/kW source value. Zero power is valid. `unknown`, `unavailable`, invalid numeric values and unsupported units are not treated as zero.

## Solar shadow validation

The native Solar flow remains:

`Open-Meteo GTI north + GTI south -> timestamp normalization -> per-roof PV conversion -> AC cap -> 15-minute kWh -> combined 288-slot timeline`

Forecast snapshots and actual production are evaluated independently. This validation layer remains separate from planner promotion and physical execution.
