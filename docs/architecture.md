# Dummy OS Data architecture — alpha.52

## Contract

Source / Weather / Solar / Degree Days remain. All native forecast arrays use 15 minutes / 72 hours / 288 slots. DOEMS is an independent system, responsible for planning, prices and execution. No second planner lives in Dummy OS Data.

## Runtime

Register the sensor platform first; initialize Weather and Solar concurrently in the background; initialize Degree Days after Weather. The Home Forecast coordinator and Prices runtime are removed.
Solar raw and F1, F3, F5 and F6 are observational; no automatic model promotion, no DOEMS data model modification.

## Migration

Preserve the technical domain dummy_os_data, existing source/solar/weather/degree_days entity IDs, config and Solar persisted training state. Drop only obsolete integration-owned Home Forecast / Prices states and config options. Recorder and Google Sheets history remain intact.

## Performance gate

Earlier user isolation test strongly implicated the full Dummy OS Data integration in slow Home Assistant operations and failed backups, which immediately improved when disabled. The internal root cause remains unmeasured.
Alpha.52 is a reduction of workload, not a claim of measured performance improvement. Re-enable only with a working backup; compare startup, UI, History/Statistics and backup against the disabled baseline. If it slows down again, disable the integration.
