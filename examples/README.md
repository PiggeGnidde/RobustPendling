# Små publicerbara resultat

`nminus-summary.json` är ett utdrag ur de redan validerade N−1-resultaten
för Lomma–Lund, Malmö C–Värnhem och Gunnesbo–Ideontorget. Det innehåller
basmått, tillämpliga scenariors kvantiler/täckning och ett exempel med
största extra restid per scenario. Extra tid jämförs med samma startminuts
basresa. Inputhashar, versioner, parametrar och originalresultatets checksumma
behålls; rådata, nätverk, cache och fullständiga minutvisa geometrier ingår inte.

Detta är ett dokumentationsexempel, inte ett fullständigt API-resultat.
Scenario enligt tidtabell – ingen sannolikhet för inställd tur uppskattas.
Se [valideringsrapporten](../docs/N_MINUS_ONE_VALIDATION.md).

Utdraget återskapas från lokala, ignorerade `outputs/nminus/*_1.json`:

```powershell
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/export_public_summary.py
```

Kommandot läser endast sparade resultat och gör ingen routing.
