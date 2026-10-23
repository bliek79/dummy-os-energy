## Dummy OS Energy 0.2.0-alpha.53 - Entity migration startup hotfix

**Tag:** `0.2.0-alpha.53`

### Directe aanleiding
Na installatie van alpha.52 toont een echte Home Assistant-opstartlog een NameError bij de migratie van bestaande Dummy OS Data entiteiten:

```
NameError: name 'ENERGY_GENERATED_ENTITY_ID_ALIASES' is not defined
```

De Energy alias-map is in alpha.52 verwijderd, maar de generieke migratiefunctie verwees er nog naar. Daardoor brak de setup al voordat Source, Weather, Solar en Degree Days geregistreerd werden.

### Gerichte hotfix
- Verwijder de laatste verwijzing naar de verdwenen Energy alias-map uit `entity_migrations.py`.
- Behoud Solar-, Degree Days-, Source- en obsolete Home Input-aliasdetectie, zodat bestaande geldige entity IDs hun identiteit kunnen behouden.
- Voeg regressietests toe die `is_known_generated_entity_id()` uitvoerend aanroepen voor alle overgebleven bekende migraties, ongeldige gebruikershernoemingen en verwijderde Energy-aliases.
- Corrigeer versie-, manifest- en releasegates naar alpha.53.

### Bewust niet veranderd
- Inhoudelijke alpha.52-scope: Home Forecast en Prices blijven verwijderd.
- Solar Raw/F1/F3/F5/F6, Weather, Degree Days en Source blijven ongewijzigd.
- Native 15 minuten / 72 uur / 288 slots en opgeslagen Solar F6-learningstatus blijven intact.
- Geen DOEMS-wijzigingen, Google Sheets- of Recorder-historieverwijderingen.

### Live controle
1. Maak/controleer de werkende backup terwijl Dummy OS Data uitgeschakeld is.
2. Installeer de **complete** alpha.53-integratie en laat geen oude .py-bestanden staan.
3. Herstart Home Assistant en schakel Dummy OS Data in; herstart nogmaals indien vereist door de lokale HA-situatie.
4. Bevestig dat de NameError niet meer voorkomt en dat `do_solar_*`, `do_weather_*`, `do_degree_days_*` en `do_source_*` weer beschikbaar zijn.
5. Vergelijk Dashboard/Statistieken/Geschiedenis, opstartduur en de mogelijkheid tot een backup.
6. Schakel Dummy OS Data weer uit als ernstige vertraging terugkomt.

### Afzonderlijke melding
De aangeleverde log bevat ook een losse `homeassistant.components.command_line` IndentationError op regel 113 van een extern command_line Python-script. Die fout hoort niet bij `dummy_os_data` en wordt **niet** in deze integratie-release gewijzigd.
