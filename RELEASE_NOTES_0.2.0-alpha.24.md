## Dummy OS Energy 0.2.0-alpha.24

**Tag:** `0.2.0-alpha.24`

### Presence / Afwezigheid

Deze prerelease voegt de eerste centrale Presence/Away-laag toe bovenop het bestaande Energy Profile Contract v1.

- persistent Away-schema met start- en eindtijd;
- half-open intervalsemantiek: `start <= now < end`;
- profielwijzigingen lopen uitsluitend via het bestaande `async_set_profile()`-contract;
- actief Away-schema schakelt naar `away` en bewaart het profiel van voor de periode;
- na afloop wordt dat profiel hersteld zolang geen handmatige override binnen dezelfde periode is gedaan;
- handmatige override is gekoppeld aan de exacte schedule-window identity en wordt niet stilzwijgend overschreven;
- ongeldige of onvolledige planning faalt gesloten en forceert nooit `normal`;
- Presence-configuratie en actieve window-state zijn restart-persistent.

### Nieuwe publieke entiteiten

- `sensor.do_presence_context`
- `binary_sensor.do_presence_away_active`
- `binary_sensor.do_presence_away_schedule_valid`
- `switch.do_presence_away_schedule_enabled`
- `datetime.do_presence_away_start`
- `datetime.do_presence_away_end`

### Veiligheidsgrenzen

Deze release wijzigt geen fysieke batterijuitvoering en geeft Presence geen fysieke execution authority. Plan72, SOC Contract, Reserve SOC, Safety, Prestart en Execution Preview blijven binnen hun bestaande veiligheidsgrenzen. De kernarchitectuur blijft 15 minuten / 72 uur / 288 slots.

### Validatie vóór publicatie

- volledige testsuite groen;
- compile-gate groen;
- manifest-gate groen;
- bestaand Profile Contract v1 behouden;
- bestaande alpha.23 Safety Reserve SOC wiring ongewijzigd;
- geen fysieke execution authority toegevoegd.

Na installatie is live Home Assistant-validatie van de zes Presence-entiteiten, schedule-overgangen, restartpersistentie en profielpropagatie vereist voordat Presence als volledig live gevalideerd wordt gemarkeerd.
