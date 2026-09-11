# GitHub Release

**Tag:** `0.2.0-alpha.20`  
**Release title:** Dummy OS Energy 0.2.0-alpha.20 - Manual Lifecycle Diagnostic

## Dummy OS Energy 0.2.0-alpha.20

Deze prerelease voegt een veilige diagnostische eendrukstest toe voor de in alpha.19 gebouwde handmatige Plan Store lifecycle.

### Nieuw
- `dummy_os_data.manual_plan_lifecycle_test`: doorloopt gecontroleerd `draft -> validate -> finalize -> edit/patch -> validate -> finalize -> clear`.
- De test kiest standaard een toekomstig kwartier en gebruikt uitsluitend de bestaande alpha.19 lifecyclelogica.
- Na de eerste finalize wordt `origin=manual`, `manual_priority=true`, `status=pending` en `manual_revision=1` gecontroleerd.
- Na edit blijft dezelfde `plan_id` behouden, wordt het vermogen aantoonbaar gewijzigd en moet `manual_revision=2` zijn.
- Na clear moet het gekozen slot weer `empty` zijn.
- Het volledige resultaat wordt machineleesbaar gepubliceerd via `last_manual_diagnostic` op DO Plan Manual Interface.

### Fail-closed
- Alleen een leeg slot kan worden gebruikt.
- Automatic-owned, running, overlappende, stale of anderszins geblokkeerde situaties stoppen de test direct.
- Bij een fout wordt geen gedeeltelijke diagnostische snapshot opgeslagen; de bestaande Plan Store blijft leidend.
- Persistence wordt pas uitgevoerd nadat de volledige lifecycle inclusief clear succesvol is doorlopen.

### Geen dubbele lifecycle
- Er is geen aparte `manual_plan_update` toegevoegd.
- Alpha.20 gebruikt de reeds aanwezige `patch_manual_draft()`-route uit alpha.19.

### Veiligheidsgrens ongewijzigd
- Alleen de geisoleerde shadow Plan Store wordt gebruikt.
- `operational_plan_store_write=false`.
- `physical_execution_authority=false`.
- Geen Scheduler-, Safety-, execution-handoff-, mode-switch- of batterijservicecalls.
- Native architectuur blijft 15 minuten / 72 uur / 288 slots.

### Validatie
De implementatie-PR #205 was groen: 374 tests geslaagd in 1.13 s. Compile, manifestvalidatie, Step 9 profile contract, alpha.12.18 runtime gate, validation ZIP en artifact-upload zijn geslaagd.

### Live validatie na installatie
Voer `dummy_os_data.manual_plan_lifecycle_test` uit op een leeg slot en controleer dat `last_manual_diagnostic.status=passed`, alle tien stappen slagen en het slot na afloop opnieuw `empty` is. Controleer daarnaast dat alle fysieke uitvoeringsflags gesloten blijven.
