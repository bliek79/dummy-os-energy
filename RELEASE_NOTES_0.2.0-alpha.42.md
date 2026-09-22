## Dummy OS Energy 0.2.0-alpha.42

**Tag:** `0.2.0-alpha.42`

### Doel

Gerichte Home Assistant lifecycle-fix voor het opnieuw laden van de Dummy OS Energy config entry na een Options-wijziging, waaronder Solar-dakgeometrie.

### Aanleiding

Bij het opslaan van gewijzigde Solar-instellingen kon Home Assistant de config entry niet correct unloaden. Het log meldde:

`TypeError: a coroutine was expected, got <Task ... result=None>`

De oorzaak was dat een `async_on_unload` callback zelf al een Home Assistant Task aanmaakte. Nieuwere Home Assistant config-entry lifecycle-code plant een niet-lege callback-return zelf als taak in; een reeds aangemaakte `Task` is daar geen geldige coroutine voor.

Daarnaast was voor de achtergrond-cloudsetup ook een extra unload-callback geregistreerd, terwijl `async_unload_entry` die taak al expliciet annuleert en afwacht.

### Wijziging

- verwijder de unload-callback die `hass.async_create_task(ems_runtime.async_shutdown_shadow())` retourneerde;
- verwijder de redundante `entry.async_on_unload(source_setup_task.cancel)`;
- behoud de bestaande expliciete, awaitbare shutdown in `async_unload_entry`;
- voeg een regressietest toe die voorkomt dat deze Task-return constructie terugkomt.

### Niet gewijzigd

- Solar-model en Open-Meteo GTI-rekenlogica;
- performancefactor;
- noord/zuid DC- en AC-capaciteiten;
- 15 minuten / 72 uur / 288 slots;
- horizon-snapshots en Solar-evaluatie;
- Energy Forecast, Prices, Weather, planner-, EMS-, safety- of executionlogica;
- fysieke execution authority.

### Solar-validatie na installatie

De gebruiker heeft de dakhellingen handmatig aangepast op basis van geometrische fotometing. Deze release verandert die waarden niet zelf; hij zorgt dat een Options-wijziging betrouwbaar kan worden toegepast en herladen. Vanaf de eerstvolgende geldige forecastcaptures worden de nieuwe instellingen daarom in de normale Solar-validatieketen meegenomen. Bestaande historische snapshots blijven ongewijzigd.

### Live acceptatie

1. Installeer Alpha42 en herstart Home Assistant.
2. Controleer dat Dummy OS Energy zonder `Uitladen mislukt` geladen is.
3. Open de Solar-opties en bevestig de ingestelde noord-/zuidhellingen.
4. Sla eventueel één keer zonder inhoudelijke wijziging op om de reloadroute te testen.
5. Controleer het log op afwezigheid van `Error unloading entry Dummy OS Forecast for dummy_os_data` en de genoemde `TypeError`.
6. Controleer daarna dat Solar Forecast opnieuw data publiceert en de validatie-export nieuwe kwartieren/horizonrecords blijft opbouwen.
