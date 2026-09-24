# Dummy OS Energy

Dummy OS Energy is the Home Assistant forecast/data integration for Dummy OS. Its technical domain remains `dummy_os_data` for installation and registry compatibility.

The integration is deliberately forecast-only. Planning, EMS, safety and shadow execution live in DOEMS; Dummy OS Energy does not keep a second EMS stack. Physical battery authority remains outside this integration.

## Core architecture

The native forecast contract is fixed:

- 15-minute resolution;
- rolling 72-hour horizon;
- 288 forecast slots;
- missing, unknown or unavailable values are never silently converted to zero;
- Normal, Away and Unclassified are explicit forecast profile states;
- Normal and Away learning are kept strictly separate.

## Responsibilities

Dummy OS Energy provides:

- canonical source normalization and Source Home Power;
- Energy Forecast history and 72-hour forecast;
- Energy forecast learning and validation;
- accuracy, MAE, bias, coverage and confidence;
- Peak Learning, Time Windows and Recency Weighting;
- Fallback Hierarchy, Meaningful Confidence, Horizon Quality and Model Health;
- Weather Forecast;
- Solar Forecast;
- electricity and gas price data;
- Degree Days and weather-derived support data;
- persistent forecast/learning stores required for restart continuity.

## Explicit boundary

Dummy OS Energy does **not** provide an EMS/planner runtime.

The internal `do_plan_*`, Plan Store, Scheduler, Safety, manual-plan controls, Presence/Away scheduling and Operating Mode stack that existed in the 0.2.0 alpha development line was removed in `0.2.0-alpha.43`.

The simple Energy Forecast profile selector remains:

- `normal`
- `away`
- `unclassified`

This profile contract is part of forecasting and prevents away periods from polluting the normal learning profile. It is not an EMS Presence scheduler.

## Startup model

Local Energy history/state and Home Assistant platforms register first. Weather, Prices and Solar initialize as a background source wave; Degree Days initializes after Weather is available. Expensive forecast/quality calculations remain executor-backed and cached so they do not run on Home Assistant's main thread.

## Public namespaces

Forecast/data entities use:

- `do_source_*`
- `do_energy_*`
- `do_weather_*`
- `do_solar_*`
- `do_prices_*`
- `do_degree_days_*`

No active `do_plan_*` namespace is part of Dummy OS Energy from alpha.43 onward; planner ownership is singular in DOEMS.

## Project status

Active alpha development. The leading architecture and progress record is maintained in the project routebaseline before code changes are made.
