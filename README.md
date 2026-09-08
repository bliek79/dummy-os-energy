# Dummy OS Energy

Dummy OS Energy is a custom Home Assistant integration for the complete Dummy OS energy architecture. It started as the Dummy OS Forecast / Data layer and is now the permanent integration in which forecasting, planning, safety and later execution are built step by step.

The fixed time architecture remains native **15-minute resolution**, a rolling **72-hour horizon** and **288 forecast slots**. Existing forecast functionality remains intact while new planner functionality is added in parallel and validated against the current Dummy OS EMS before any legacy EMS function is retired.

> **Project status:** early alpha / active development. Interfaces and behavior may still change until the project reaches a stable release.

## Purpose

Dummy OS Energy provides one controlled energy stack for Dummy OS:

- normalize canonical source data;
- retain historical observations;
- generate Energy, Weather and Solar forecast data;
- provide current and forecast price data;
- collect and validate Degree Days / heat-history data;
- evaluate forecast quality against actual measurements;
- expose source quality and freshness;
- provide the stable Forecast-to-Planner contract;
- build the new planner inside this integration under the `do_plan_*` namespace;
- add safety and execution only after the corresponding planner layers have been validated.

The current Dummy OS EMS remains separate during migration as a reference, comparison source and rollback path. It is not merged into Dummy OS Energy. Functionality is rebuilt and validated inside Dummy OS Energy and the old EMS can only be retired step by step after proven replacement.

## Core architecture

The permanent architecture is:

`Source / Data -> Forecast -> Contract -> Planner -> Safety -> Execution`

Core rules:

- **15-minute native resolution**;
- **rolling 72-hour horizon**;
- **288 forecast slots**;
- no second forecast architecture;
- missing, `unknown` or `unavailable` values are never silently converted to zero;
- stable entity IDs and unique IDs unless a controlled migration explicitly requires otherwise;
- strict separation between normal and away forecast profiles;
- source-quality and freshness monitoring;
- planner logic consumes normalized forecast contracts instead of duplicating source logic;
- physical execution authority never belongs to the forecast layer;
- planner, safety and execution are introduced independently and validated before activation.

The public entity namespaces are organized by function:

- `do_source_*`
- `do_energy_*`
- `do_weather_*`
- `do_solar_*`
- `do_prices_*`
- `do_degree_days_*`
- `do_plan_*` for all new planner entities

The visible integration name is **Dummy OS Energy**. The technical Home Assistant domain deliberately remains `dummy_os_data` to preserve the existing installation, config entry, entity registry and current `do_*` entities.

## Migration model

Dummy OS Energy is not created by merging repositories later. The existing Forecast integration is the permanent base and is extended in place.

Migration principles:

1. existing Forecast/Data functionality remains leading for source and forecast layers;
2. new planner capabilities are built in parallel under `do_plan_*`;
3. every new planner function is observer/shadow first;
4. results are compared with the current Dummy OS EMS where applicable;
5. safety is connected only after planner behavior is validated;
6. execution is connected only after safety and final revalidation are proven;
7. the old Dummy OS EMS remains available as reference and rollback until its replacement is live proven.

## Current functionality

### Source layer

Dummy OS Energy builds one canonical local energy-flow layer from configurable underlying power sources. Grid power uses one bidirectional source: positive means import and negative means export. Missing, `unknown` or `unavailable` source values are not silently converted to zero.

Registered Source entities include:

- `sensor.do_source_grid_net_power`
- `sensor.do_source_grid_import_power`
- `sensor.do_source_grid_export_power`
- `sensor.do_source_solar_power`
- `sensor.do_source_battery_charge_power`
- `sensor.do_source_battery_discharge_power`
- `sensor.do_source_home_power`

`do_source_home_power` uses the fixed balance:

`solar + grid_import + battery_discharge - grid_export - battery_charge`

### Energy Forecast

Energy Forecast consumes `sensor.do_source_home_power` as its canonical actual-power source.

It provides completed 15-minute energy observations, persistent history, separate `normal` and `away` profiles, a rolling 72-hour / 288-slot forecast, recency-weighted historical baseline modelling, fallback logic and forecast-versus-actual evaluation.

Important entities include:

- `sensor.do_energy_actual_quarter`
- `sensor.do_energy_history_status`
- `sensor.do_energy_history_days`
- `sensor.do_energy_forecast_model`
- `sensor.do_energy_forecast`
- `sensor.do_energy_forecast_timeline`
- `sensor.do_energy_forecast_next_quarter`
- `sensor.do_energy_forecast_coverage`
- `sensor.do_energy_forecast_confidence`
- `sensor.do_energy_forecast_model_health`
- `sensor.do_energy_forecast_accuracy`
- `sensor.do_energy_forecast_mae`
- `sensor.do_energy_forecast_bias`
- `sensor.do_energy_forecast_evaluation_samples`
- `sensor.do_energy_forecast_planner_contract`
- `select.do_energy_profile`

### Weather Forecast

The Weather module fetches forecast data from Open-Meteo and normalizes it into the common 15-minute / 72-hour architecture. It exposes current observations, normalized forecast timelines, source status, freshness and model information.

### Solar Forecast

The Solar module converts Open-Meteo radiation data into separate north/south and combined PV forecasts on the common 15-minute / 72-hour timeline. Actual production and forecast snapshots are evaluated independently; missing source data is never treated as zero.

### Prices

The Prices layer provides market, import and export price information while keeping market price and tariff composition separate. Known quarter-hour prices are preferred where available; hourly values can be projected to the common 15-minute axis while preserving source resolution metadata. Import and export tariffs remain independently configurable for 2027 compatibility.

### Degree Days

Degree Days collects and freezes completed daily weather-derived records and exposes current, weighted and reference degree-day information while retaining internal history.

### Planner

Planner development starts inside Dummy OS Energy under the dedicated `do_plan_*` namespace.

The planner must consume the validated Forecast contract and is initially observer/shadow only. The native Forecast architecture remains 15 minutes / 72 hours / 288 slots; planner projections may aggregate to hourly planning views where explicitly defined, but they do not create a second forecast architecture.

No `do_plan_*` entity may obtain physical execution authority merely by being planner-ready. Safety and execution remain later, separately guarded layers.

## Installation

Dummy OS Energy is intended for Home Assistant installations using custom integrations.

Typical alpha installation methods are:

1. install through HACS as a custom repository; or
2. copy `custom_components/dummy_os_data` into the Home Assistant `custom_components` directory.

After installation, restart Home Assistant and add **Dummy OS Energy** through **Settings > Devices & services**.

The repository is:

`bliek79/dummy-os-energy`

The technical integration directory and domain remain:

`custom_components/dummy_os_data`

`dummy_os_data`

## Configuration and Recorder behavior

The Source layer is built from configurable underlying power sources. Energy Forecast consumes the canonical source layer internally. The active Energy Forecast profile is selected through `select.do_energy_profile`.

Compact states and useful metadata can be recorded normally by Home Assistant. Large timeline attributes should remain excluded from Recorder where applicable. Persistent Energy and Degree Days histories remain managed by the integration.

## Forecast evaluation

Forecast quality remains a first-class part of the architecture. Forecast snapshots are compared with completed actual observations. Inter-source comparison between a legacy forecast and Dummy OS Energy is migration diagnostics and must not be confused with forecast error versus actual measurements.

## Sources and attribution

Dummy OS Energy uses external projects, documentation and data providers including Home Assistant, Open-Meteo, Stroomvoorspeller.nl and EnergyZero. External sources remain traceable in the repository and their applicable terms and attribution must be preserved.

Stroomvoorspeller data is used under **CC BY 4.0**; attribution to Stroomvoorspeller.nl must be retained.

Dummy OS Energy is an independent open-source community project and is not affiliated with, sponsored by or endorsed by Home Assistant, Nabu Casa, Open-Meteo, Stroomvoorspeller.nl, EnergyZero, Anker Innovations or other third-party providers mentioned in the project documentation.

## Roadmap

Current direction:

- maintain and validate the existing Source, Energy, Weather, Solar, Prices and Degree Days layers;
- keep the validated Forecast-to-Planner contract as the boundary between forecast and planning;
- build the new `do_plan_*` planner step by step inside Dummy OS Energy;
- compare planner behavior with the current Dummy OS EMS;
- add safety only after planner validation;
- add execution only after safety and final-revalidation validation;
- retire old EMS functionality only after the equivalent Dummy OS Energy path has been proven live.

## Releases and change history

Version-specific changes are documented in GitHub Releases and `RELEASE_NOTES.md`.

Alpha and beta versions should be treated as pre-releases until a stable release is explicitly published.
