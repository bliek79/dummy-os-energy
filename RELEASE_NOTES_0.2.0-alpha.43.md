## Dummy OS Energy 0.2.0-alpha.43

**Tag:** `0.2.0-alpha.43`

### Forecast-only scope reset

This prerelease removes the unused internal EMS/planner and Presence/Away scheduling stack from Dummy OS Data while preserving the proven forecast, learning, validation and source layers.

#### Removed
- Forecast-to-Planner transport entities and DO Plan input/results.
- Energy Need, Reserve SOC, Preview, Plan72, Grid Support, Plan Store, Scheduler, Safety and related shadow planner modules.
- Manual plan controls and services.
- Presence/Away schedule runtime, switch and start/end datetime entities.
- Operating Mode and planner-specific control platforms.
- Binary sensor, switch, datetime and number platforms that existed only for the retired EMS/planner layer.

#### Preserved
- Native Energy Forecast: 15 minutes / 72 hours / 288 slots.
- Source Home Power and source normalization.
- Normal / Away / Unclassified forecast profile contract; normal and away learning remain strictly separated.
- Forecast accuracy, MAE, bias, coverage, confidence, Peak Learning, Time Windows, Recency Weighting, Fallback Hierarchy, Meaningful Confidence, Horizon Quality and Model Health.
- Weather, Solar, Prices and Degree Days.
- Later forecast-only executor/cache improvements and the Alpha30 non-blocking cloud-source startup path.
- Price-buffer and exact 15-minute timing helpers needed by forecast sources.
- No physical battery control is added.

### Startup objective

The reset follows a Home Assistant A/B test in which ZHA started cleanly when Dummy OS Data was disabled, while the preceding failing startup showed long-running Dummy OS Data planner/forecast tasks around the global bootstrap timeout. Alpha43 removes the unused planner/EMS runtime so the integration can remain enabled for its valuable forecast data without carrying a second EMS stack.

### Architecture boundary

- Dummy OS Data = data, forecast, learning, validation and quality.
- DOEMS = planner, EMS, safety and shadow execution.
- anker_ems remains the physical battery authority.
- This release does not open DOEMS G6 or physical cutover.

### Version note

The cleanup was first prepared as alpha36, but that tag already existed historically in the repository. No existing tag was overwritten or moved. The release was therefore retargeted to the first free prerelease number: alpha43.

### Validation

Publication requires:
- full remaining repository test suite;
- compile and manifest/version gates;
- Alpha29 Prices buffer regression;
- Alpha30 non-blocking startup regression;
- Energy Profile, Model Health, Horizon Quality and forecast executor regressions;
- Alpha43 scope-reset regression proving no active `do_plan_*`, Presence schedule or Operating Mode runtime remains.
