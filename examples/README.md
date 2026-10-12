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

`planner-summary.json` härleder samlat N−1 (inklusive reglerna för +∞) och
deadline 08:00 ur samma tre frysta regressioner. Originalexemplet ovan
behålls oförändrat. Återskapa med `python -B scripts/export_planner_examples.py`
i projektmiljön; ingen ny routing görs.

`planner-four-leg-reserve.json` visar ett verkligt verifierat fyrabensfall
(genomförd buss 6 plus tre reservben 131→165→1). Det är ett enminutsprov,
inte en större kvantilpopulation. Återskapa utdraget från lokala resultat:

```powershell
python -B scripts/export_planner_examples.py --baseline outputs/planner/ellstorp-max4-base.json --nminus outputs/planner/ellstorp-max4-nminus.json
```
