# RobustPendling

RobustPendling ska stödja planering utifrån restidens variation och robusthet i Skåne.

- **Privatläge:** robust A–B-resa med T50/T90/T99 för vardag, kväll och helg. T50, T90 och T99 betecknar restidens 50:e, 90:e och 99:e percentil.
- **Arbetsplatsläge:** robust upptagningsområde för arbetspass med restidsgränser på 15/30/45/60 minuter och befolkningsantal inom respektive område.

Projektet innehåller en validerad tidtabellsmotor och en lokal interaktiv
[granskningsvy](docs/LOCAL_REVIEW.md) för Phase 2C-relationerna och egna A–B-punkter.

Deterministisk N−1-analys av uteblivna turer beskrivs i
[kontraktet](docs/N_MINUS_ONE.md) och [valideringsrapporten](docs/N_MINUS_ONE_VALIDATION.md).
[Små JSON-exempel](examples/README.md) visar sparade resultat utan rådata eller cache.
Vyn är också en [lokal A–B-planerare](docs/PLANNER.md) med kartval, 1–4
trafikben, samlat N−1 och tidtabellsbaserad ankomstdeadline.
Nya analyser använder 4,5 km/h och högst 20 minuters sammanlagd gång,
valbart 3–6 km/h och 10–30 minuter. [Exakt profilåteranvändning](docs/SCHEDULE_PROFILE.md)
gör avresefönster på 60–120 minuter snabbare utan att ändra minutresultaten.

## Miljökontroll

Kör från projektroten i PowerShell:

```powershell
.\scripts\check_environment.ps1
```

Kontrollen rapporterar Python, Java, Git och GDAL utan att installera något. Versionskrav dokumenteras i `requirements/README.md`.
