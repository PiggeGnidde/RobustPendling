# Checkpoint: lokal A–B-planerare

2026-10-12, worktree `C:\Users\bengt\.codex\worktrees\a492\RobustPendling`,
branch `codex/mvp`. Implementering, kodgranskning och lokala kontroller klara.
Denna checkpoint ingår i planerarkommitten; ingen merge till main.

Klart: kartklick/redigerbara koordinater, datum-/områdeskontroll, 1–4 ben
genom både R5 och oberoende sökning, separata bortfall med bevarat prefix,
samlat N−1 inklusive +∞ och gångundantag, deadline som prövar varje minut,
cache och ett återanvänt nätverk per worker. 77 tester passerar. Alla 180
ursprungliga basminuter matchar, och sex N−1-arkiv är bevarade/verifierade.
Verklig fyrabensreserv och trebensfortsättning verifierade på ett litet prov.
Se [PLANNER_VALIDATION.md](PLANNER_VALIDATION.md) för resultat/begränsningar.

Vyn lämnas igång på **http://127.0.0.1:8765/** för Bengts prov. Inga stora
automatiska körningar pågår. Miljö, konfiguration, rådata och genererade
resultat förblir lokala och ignorerade. Geometribilder finns under
`outputs/review`; nya små funktionstestresultat under `outputs/planner`.
Inga paket installerades och inga nya rådata hämtades.

För senare start, i PowerShell:

```powershell
Set-Location C:\Users\bengt\.codex\worktrees\a492\RobustPendling
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/review_server.py
```

Stoppa ordnat före sleep eller omstart:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/shutdown -ContentType application/json -Body '{}'
```

GeoTools-filen kan vara låst vid första JVM-städningen; uppskjuten städning
efter exit har fungerat. Felet döljs inte. Vid fortsatt utveckling, stoppa
servern innan routingkod ändras och starta om så kodhashar och laddad JVM
stämmer. Börja med 1–5 startminuter. Högst 120 minuter per nytt anrop.
Basgräns 45 min, gång 15 min totalt, reservhorisont 120 min efter besked.
Trafikdygns-/DST-övergång och frekvensbaserade turinstanser är begränsningar.

Framtida arbete: större täcknings-/prestandaprov och eventuellt optimala
tre-/fyrabensbasresor. Nu verifieras flerben i syntetiska tester och i verklig
reserv; inget sådant basfall har påvisats inom dessa små 45-minutersprov.
Historiska förseningar, realtidsinsamling och sannolikheter ligger fortsatt
utanför detta steg. T90_schedule betyder inte verklig punktlighet.
