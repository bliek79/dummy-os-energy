# GitHub Release

**Tag:** `0.2.0-alpha.19`  
**Release title:** Dummy OS Energy 0.2.0-alpha.19 - Manual Plan Lifecycle

## Dummy OS Energy 0.2.0-alpha.19

Deze prerelease bouwt de volledige handmatige planning lifecycle voor de bestaande drie-slot shadow Plan Store.

### Nieuw
- `draft`: maakt een in-memory concept zonder de Plan Store te wijzigen.
- `validate`: controleert actuele store-state, 15-minutenalignment, vermogen, SOC, runtime, startvertraging en overlap.
- `finalize`: valideert opnieuw en schrijft atomisch/persistent naar de shadow Plan Store.
- `edit`: maakt een guarded edit-draft van een bestaand niet-running handmatig plan; `plan_id` en `created_at` blijven behouden en `manual_revision` loopt op.
- `clear`: wist uitsluitend niet-running handmatige slots met optimistic-concurrency bescherming.
- Home Assistant-services: `dummy_os_data.manual_plan_draft`, `manual_plan_edit`, `manual_plan_validate`, `manual_plan_finalize`, `manual_plan_clear`.

### Overlap en Plan Store-veiligheid
- Manual-manual en manual-automatic overlap wordt geblokkeerd.
- Het gereserveerde venster omvat ook `max_start_delay_minutes`.
- Aansluitende vensters zonder feitelijke overlap blijven toegestaan.
- Automatic-owned slots en running manual slots kunnen niet handmatig worden gewijzigd of gewist.
- Stale edits worden geblokkeerd via `base_plan_id` en `base_updated_at`.
- Automatische bridge-refresh en handmatige writes delen een transaction lock.
- Bij persistence failure blijft de vorige in-memory snapshot behouden.

### Grenzen
- Maximaal laad-/ontlaadvermogen: 3200 W.
- Target SOC: 5-100%.
- Runtime: 15-1440 minuten in stappen van 15 minuten.
- Max startvertraging: 0-60 minuten.
- Native architectuur blijft 15 minuten / 72 uur / 288 slots.

### Veiligheidsgrens ongewijzigd
- Alleen de geisoleerde shadow Plan Store mag door de manual lifecycle worden geschreven.
- `operational_plan_store_write=false`.
- `physical_execution_authority=false`.
- Geen externe batterijservicecalls, mode-switch of command dispatch.

### Validatie
PR #203: definitieve CI-run #170 heeft 370 tests geslaagd in 1,29 s. Compile sources, manifestvalidatie, Step 9 profile contract, alpha.12.18 runtime gate, validation ZIP en artifact-upload zijn geslaagd.

### Live validatie na installatie
Valideer na installatie draft -> validate -> finalize, persistence na Home Assistant-herstart, overlapblokkades, edit en clear. Controleer tevens dat automatic/running slots beschermd blijven en dat de fysieke uitvoeringsgrens gesloten blijft.
