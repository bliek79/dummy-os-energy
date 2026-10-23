## Dummy OS Energy 0.2.0-alpha.52 - Home Forecast & Prices retirement

**Tag:** `0.2.0-alpha.52`

### Doel

Op verzoek van de gebruiker wordt de afgekeurde Home Forecast met de bijbehorende learning- en evaluatielagen verwijderd, samen met de ongebruikte Prices-module. Zo kan de overblijvende integratie gecontroleerd opnieuw worden ingeschakeld.

### Verwijderd

- Home / Energy Forecast, 72h historical_baseline, kwartierhistorie en profielselectie.
- Observer-learning: Peak Learning, Time Windows, Recency Weighting, Fallback Hierarchy, Meaningful Confidence en Model Health.
- Prices: elektriciteits-/gasprijzen, tariefconfiguratie, prijsbuffer, polling en direct gepubliceerde do_prices_* states.
- Exclusieve codebestanden, configuratievelden en verouderde tests.
- Eenmalige cleanup van alleen de retired registry-ID's die Dummy OS Data zelf bezit en zijn oude directe Prices-statussen.

### Bewust behouden

- Alle zeven do_source_* canonieke bronentiteiten en hun bronopties.
- Open-Meteo Weather en Degree Days / Heat.
- Solar raw, F1, F3, F5, F6, Noord/Zuid modelvalidatie, opgeslagen F6-learningstate en snapshots.
- Native 15 min / 72 uur / 288 slots, integratiedomein dummy_os_data en projectidentiteit.
- Recorder- en Google Sheets-historie wordt niet gewist. DOEMS blijft ongewijzigd.

### Test na installatie

1. Zorg dat de Home Assistant-back-up is voltooid en bewaard.
2. Installeer deze release terwijl Dummy OS Data uitgeschakeld is.
3. Schakel Dummy OS Data één keer in; controleer Source, Weather, Solar en Degree Days.
4. Controleer de Solar-timeline op 288 punten en controleer F6-status en validatie.
5. Test systeemrespons, Historie, Statistieken en maak opnieuw een back-up.
6. Bij terugkeer van ernstige vertraging meteen uitschakelen; geen nieuwe functies activeren.

### Interpretatie

De eerder gemelde directe prestatieverbetering na uitschakelen van Dummy OS Data ondersteunt het probleem op integratieniveau. Deze release verwijdert verdachte onderdelen, maar de afzonderlijke interne oorzaak is nog niet door metingen bewezen. Eventueel overblijvende belasting uit Solar is buiten deze wijziging gelaten.
