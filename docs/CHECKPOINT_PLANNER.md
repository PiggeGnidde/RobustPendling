# Checkpoint: lokal A–B-planerare

2026-10-12, worktree `C:\Users\bengt\.codex\worktrees\a492\RobustPendling`,
branch `codex/mvp`. Implementering, kodgranskning och lokala kontroller klara.
Denna checkpoint ingår i planerarkommitten; ingen merge till main.

Klart: kartklick/redigerbara koordinater, datum-/områdeskontroll, 1–4 ben
genom både R5 och oberoende sökning, separata bortfall med bevarat prefix,
samlat N−1 inklusive +∞ och gångundantag, deadline som prövar varje minut,
cache och ett återanvänt nätverk per worker. Efter horisontkorrigeringen
passerar 84 tester. Exakt profilåteranvändning och konfigurerbar gång är nu
införda; se SCHEDULE_PROFILE.md och PLANNER_VALIDATION.md. Ett verkligt minutprov över 45 min matchar rå R5 och
oberoende sökning (54:06); nya analyser söker upp till 120 min. Alla 180
ursprungliga basminuter matchar, och sex N−1-arkiv är bevarade/verifierade.
Verklig fyrabensreserv och trebensfortsättning verifierade på ett litet prov.
Senaste kontroller: 240 profilminuter matchar sparade observationer, 180
originalminuter matchar separat sweep/rå R5, nytt 120-minutersfönster och
enminuts-N−1 med båda benens bortfall är verifierade. 60-minuterssökningen
med samma tidigare indata gick från 350,47 s till 29,86 s. Första nya
120-minutersanropet tog 131,3 s inklusive alla kontroller och nätverksstart.
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
Nya vyanalyser: basgräns 120 min, gång 4,5 km/h (3–6), högst 20 min totalt
(10–30), reservhorisont 120 min
efter besked. Sparade originalförval har fortfarande sina frysta 45 min.
Trafikdygns-/DST-övergång och frekvensbaserade turinstanser är begränsningar.

Framtida arbete: större täcknings-/prestandaprov och eventuellt optimala
tre-/fyrabensbasresor. Nu verifieras flerben i syntetiska tester och i verklig
reserv; inget sådant basfall har påvisats inom dessa små 45-minutersprov.
## N−1-prestanda, 2026-10-13

2026-10-14: rå R5-baskontroll rättad för falskt ROUTING_MISMATCH vid
tvåbensresor. Pareto-gallring bevarar gångbudget och kontrollhorisonten är
explicit. 60/60 minuter matchar i Bjärred–Malmö-fallet; basmåtten är
oförändrade. 91 tester passerar. Se `ROUTING_VALIDATION_FIX.md` för
lokala artefakter och reproduktion. Servern återstartas med rättad kod.

Interaktiv worker använder nu strukturell validering och återanvänder
basprofilen; full R5-dubbelkontroll finns kvar i `validate_nminus.py`.
Identiska reservproblem återanvänds med bibehållen gång-/trafikbensbudget.
De tre frysta 60-minutersfallen har körts två gånger i snabbt läge och
matchar arkiverade resor, mått och GeoJSON exakt. Lomma: 8,3–9,1 s;
Malmö: 11,5–12,7 s; Gunnesbo: 13,1–14,0 s. Initial nätverksladdning är
inte inkluderad. Ett nytt treminutersprov i båda lägena matchar också.
En Bjärred-startminut med fyrabensbudget och tre valda trafikben matchar
full R5-audit för alla tre bortfall: 121,3 s full audit mot 9,2 s snabbt.
89 enhetstester passerar. Lokala mätningar finns i
`outputs/nminus-performance/`; ursprungliga resultat har inte skrivits över.
Nya servern ska startas om vid routingkodändring enligt kommandot ovan.

Historiska förseningar, realtidsinsamling och sannolikheter ligger fortsatt
utanför detta steg. T90_schedule betyder inte verklig punktlighet.
