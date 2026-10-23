# Dummy OS Energy / Dummy OS Data

Dummy OS Energy is a Home Assistant source/forecast observer integration with the technical domain **dummy_os_data**.
From **0.2.0-alpha.52**, Home Forecast / Energy learning and Prices have been retired; DOEMS owns its own planning and prices.

## Fixed forecast contract

- Native 15-minute resolution, rolling 72 hours, exactly 288 slots.
- Unknown / unavailable inputs must never be converted to zero.
- Raw Solar remains the main forecast. F1, F3, F5 and F6 remain parallel observer candidates, without planner/physical authority.

## Retained modules

- **Source:** seven existing canonical source power sensors including derived Home Power.
- **Weather:** Open-Meteo live state and forecast timeline.
- **Solar:** north/south raw forecast, F1/F3/F5/F6 candidates, exact-lock validation and persisted learning data.
- **Degree Days / Heat:** daily temperature/degree-day observations and reference validation.

## Retired in alpha.52

- Historical Home Forecast, Energy profiles, evaluation, learning, model health and associated sensor/select entities.
- Electricity/gas price polling, tariff configuration and the published do_prices_* runtime states.
- Historical Google Sheets rows and Home Assistant Recorder history are **not deleted**.

## Startup and rollback

Sensor platforms register before Weather and Solar are initialized in the background. Degree Days initializes afterwards.
Only retired integration-owned Home/Energy entity IDs and known direct Prices runtime states are removed. Other integrations are untouched.
Do not enable the new integration without a working Home Assistant backup. After installation, enable once, check retained entities, startup speed, History, Statistics and another backup. Disable the integration if system slowness returns.

Home Assistant version before installation and release version in manifest.json must be checked. Current live installation/version is not proven by code inspection alone.
