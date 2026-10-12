# RobustPendling

RobustPendling ska stödja planering utifrån restidens variation och robusthet i Skåne.

- **Privatläge:** robust A–B-resa med T50/T90/T99 för vardag, kväll och helg. T50, T90 och T99 betecknar restidens 50:e, 90:e och 99:e percentil.
- **Arbetsplatsläge:** robust upptagningsområde för arbetspass med restidsgränser på 15/30/45/60 minuter och befolkningsantal inom respektive område.

Projektet innehåller en validerad tidtabellsmotor och en lokal interaktiv
[granskningsvy](docs/LOCAL_REVIEW.md) för Phase 2C-relationerna och egna A–B-punkter.

## Miljökontroll

Kör från projektroten i PowerShell:

```powershell
.\scripts\check_environment.ps1
```

Kontrollen rapporterar Python, Java, Git och GDAL utan att installera något. Versionskrav dokumenteras i `requirements/README.md`.
