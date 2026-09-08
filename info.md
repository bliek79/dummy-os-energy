# Dummy OS Energy

Centrale energie-integratie voor Dummy OS. De integratie werkt native op 15 minuten met een rollende horizon van 72 uur / 288 slots en bevat Source, Energy Forecast, Weather, Solar, Prices en Degree Days. De nieuwe planner wordt stapsgewijs binnen deze integratie opgebouwd onder de `do_plan_*`-namespace, terwijl de bestaande Dummy OS EMS voorlopig als referentie en rollback naast de nieuwe keten blijft bestaan.
