# Public entities — alpha.52

| Prefix | Description |
|---|---|
| do_source_* | Normalized grid, solar, battery and derived home power |
| do_weather_* | Open-Meteo weather and 288-slot timeline |
| do_solar_* | Raw/F1/F3/F5/F6 north/south 288-slot forecasts and evaluations |
| do_degree_days_* | Weather/heat degree-days and daily reference observations |

Retired: do_energy_*, do_home_* and do_prices_* runtime entities and select.do_energy_profile. Existing Solar states and History/Recorder are not cleared.
F6's persistent learner state and exact-lock history are preserved; old F6 validation may be rechecked when re-enabled.
DOEMS is not modified and no price/planner authority lives here.
