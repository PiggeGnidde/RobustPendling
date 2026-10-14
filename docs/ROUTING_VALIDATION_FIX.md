# Rå R5-kontroll: falskt ROUTING_MISMATCH, 2026-10-14

Ett Bjärred–Malmö-fall för 2026-10-15 kl. 07:00–07:59, två tillåtna
trafikben, 4,5 km/h, 20 min total gång och 120 min restidsgräns gav
ROUTING_MISMATCH. Minutprofilen hittade resor som detaljanalysen bekräftade,
men råa R5-kontrollen returnerade ingen användbar resa för flera minuter.
Start 07:04 hade exempelvis 134 → 3, total 64:25.

Råkontrollen använde en femminuters suboptimalitetströskel och, vid högst
två trafikben, R5:s vanliga dominanslista. Den bevarade inte gångbudget som
separat resurs. Destinationstidsheuristik och dominans kunde därmed gallra
bort ett senare men budgetgiltigt alternativ. Att enbart öka tröskeln gav
rätt 64:25 men tog 225 s i själva R5-sökningen och är inte en lämplig fix.

Råkontrollen använder nu Pareto-dominans över ankomsttid, förbrukad gång
och trafikben även för ett/två ben, med permissions- och resurskontroll före
dominans. Tröskeln sätts över hela den explicita restidshorisonten, så
destinationstidsheuristiken inte undergräver gångbudgetkontrollen. Den
ursprungliga detaljadapter som redovisar alternativ behåller sitt läge;
ändringen gäller råvalideringens bästa restid. Ingen avvikelse ignoreras.

## Verifiering

- 91 tester passerar, inklusive senare/lägre-gång-label som måste behållas
  trots en tidigare/högre-gång-label, samt horisont för 45/120 min.
- Alla 60 minuter matchar mellan profil, explicit minutvis sweep och rå R5.
  Fyra representativa detaljresor matchar också.
- Minutobservationer och samtliga mått är identiska med den felmarkerade
  originalrapporten: täckning 100 %, T50 60:54, T90 64:25, T99 66:54,
  minimum 54:43 och maximum 66:54.
- CLI-resultatets GeoJSON har samma segmentantal (40); dess hash skiljer sig
  eftersom CLI:s standardnamn Origin/Destination ersatte vyns A/B.
- De tre sparade N−1-originalens båda repetitioners kontrakt, turuteslutning,
  tider och GeoJSON har kontrollerats utan ny N−1-routing.
- Routingworker avslutades med exitkod 0. Känd EPSG-låsning vid JVM-avslut
  loggades och temporärkatalogen städades efter exit.

Indata och ursprunglig felrapport förvaras lokalt i den ignorerade filen
`outputs/review/analysis-7f337633f4f47b03e18a9de8ccc56c819d28222838414e3dbb6b512e7223ee0b.json`.
Kommandot nedan återanvänder dessa indata, inklusive visningsnamnen:

```powershell
$case = Get-Content outputs/review/analysis-7f337633f4f47b03e18a9de8ccc56c819d28222838414e3dbb6b512e7223ee0b.json -Raw | ConvertFrom-Json
$p = $case.metadata.parameters
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/analyze_t90.py --planner --from-lat $p.origin.lat --from-lon $p.origin.lon --from-name $p.origin.name --to-lat $p.destination.lat --to-lon $p.destination.lon --to-name $p.destination.name --date $case.metadata.date --start 07:00 --window-minutes 60 --validate-every-minute --max-rides 2 --max-time-minutes 120 --walk-speed-kmh 4.5 --max-walk-minutes 20 --output outputs/routing-mismatch-verified-hour.json
```

Råkontrollens faktiska tröskel och dominansmetod fryses nu separat i metadata
(`r5_raw_suboptimal_minutes`, `r5_raw_dominance`); native-requestens äldre
`r5_suboptimal_minutes` beskriver inte längre råkontrollen. Data och lokala
resultat förblir ignorerade, och gamla regressionsartefakter skrivs inte över.
