## Dummy OS Energy 0.2.0-alpha.25

**Tag:** `0.2.0-alpha.25`

### Operating Mode Policy Layer

Deze prerelease voegt de centrale Operating Mode-laag toe aan Dummy OS Energy.

Ondersteunde logische modi:

- `self_consumption`
- `manual`
- `automatic`
- `disabled`

### Nieuwe publieke entiteiten

- `select.do_plan_operating_mode`
- `sensor.do_plan_operating_mode_status`

### Scheduler

Operating Mode begrenst de Scheduler voordat een kandidaat wordt geselecteerd.

- `self_consumption`: geen operationele Scheduler-selectie;
- `disabled`: geen operationele Scheduler-selectie;
- `manual`: alleen plannen met origin `manual` zijn selecteerbaar;
- `automatic`: plannen met origin `manual` en `automatic_72h_planner` zijn toegestaan;
- bestaande manual-priority blijft behouden.

### Safety en Prestart

Safety valideert de actuele Operating Mode en de geselecteerde plan-origin onafhankelijk opnieuw. Prestart vergelijkt de actuele Operating Mode-signature met de signatures waarmee Scheduler en Safety hun beslissing namen. Een modewijziging vóór uitvoering faalt gesloten.

### Persistence

De ingestelde Operating Mode is restart-persistent. De runtime bewaart de actuele mode, vorige mode, wijzigingstijd, bron en Operating Mode-signature.

### Veiligheidsgrenzen

Deze release blijft volledig shadow-only:

- `shadow_only: true`
- `active_use_permitted: false`
- `physical_execution_authority: false`
- `operational_plan_store_write: false`
- `service_calls_performed: false`
- `mode_switch_performed: false`

`third_party_control` is geen Operating Mode-optie. De logische Operating Mode blijft gescheiden van de fysieke Anker-regelmodus en deze release voert geen Anker-servicecalls of fysieke mode-switches uit.

### Architectuur

De native architectuur blijft ongewijzigd op 15 minuten / 72 uur / 288 slots. Bestaande Profile-, Presence-, SOC-, Reserve SOC-, Scheduler-, Safety- en Prestart-contracten blijven behouden.

### Naamgeving

Bekende entity-ID/registry-naamgevingsschuld blijft bewust geparkeerd voor een latere integratiebrede opschoonstap en is geen onderdeel van deze release.

### Validatie vóór publicatie

Voor publicatie moeten de volledige testsuite, compile-gate, manifest-gate, Step 9 Profile Contract, bestaande runtime-gate en validation-ZIP opnieuw groen zijn. Na installatie blijft live Home Assistant-validatie van Operating Mode, restartpersistentie, Scheduler/Safety/Prestart-gating en het ontbreken van fysieke execution authority vereist.
