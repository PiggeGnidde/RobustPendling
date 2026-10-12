# Lokal A–B-planerare

Välj A/B med kartklick eller redigerbara WGS84-koordinater, datum, starttid
och ett explicit antal startminuter. Varje minut på minutgräns analyseras
med lika vikt. Förvalen från Phase 2C och deras originalresultat finns kvar.
Börja med 1–5 minuter; servern tillåter högst 120 minuter per nytt anrop.

Fryst GTFS täcker 2026-10-08–2027-06-13 enligt kalender/feed-info. Enskilda
datum kontrolleras även mot trafikdagar och kalenderundantag. Datum utanför
feeden ger `OUTSIDE_FEED_DATES`, trafiklös dag `NO_SERVICE_DATE` och punkter
utanför verifierat OSM-område `OUTSIDE_NETWORK_AREA`. Aktuell OSM-täckning:
lon 12.95–13.30, lat 55.60–55.80. Datatäckning garanterar inte en nåbar resa.

## Parametrar och flerbensrouting

Gång 3,6 km/h, högst 900 s sammanlagd gång, basresa högst 2700 s.
`max_rides` är ett heltal 1–4 (default 2). Boarding kräver strikt avgång
efter aktuell ankomst + gång + 60 s; slutmarginal efter trafik är 60 s.
Pickup/dropoff 0 och 3 tillåts; 1 och 2 avvisas före R5-dominanspruning.

R5-request, detaljer, cacheidentitet, metadata och den oberoende sökningen
använder samma valda bensgräns. Sökningen för 1–2 ben behåller den gamla
algoritmen. För 3–4 används rundbaserade tidtabellsetiketter med resurs- och
turhistorikmedveten dominans. Bakåtriktade optimistiska avgångsgränser tar
bort prefix som inte kan avslutas inom tidsgränsen; de bortser från förbrukad
gång och redan använda turer och kan därför inte avvisa en giltig fortsättning.
Sista rundan söker bara trafik till möjliga slutgångshållplatser. Tester
jämför även med en separat sökning utan pruning.
Detaljkartan visar alltid den exakt valda basresans turinstanser med R5:s
geometri, även när R5:s dominanslista behåller en annan lika snabb kedja.

Ett separat N−1-scenario skapas för varje trafikben i vald basresa. Beskedet
kommer utan fördröjning vid planerad avgång. Genomförda segment, tid, gång
och antal ben bevaras. Reserven får bara använda återstående del av den
valda 1–4-bensbudgeten och gångbudgeten. Exakt felande turinstans utesluts
före boarding och återställs efter scenariot. Reservhorisonten är fortsatt
7200 s efter beskedet. Ingen omplanering från ursprunget vid senare bortfall.
Se även [N−1-kontraktet](N_MINUS_ONE.md).

## Samlat N−1 och deadline

För varje startminut är samlat N−1 den största totalrestiden bland separata
bortfall av **den valda optimala basresans** trafikben, med bästa tillåtna
reserv för varje bortfall. Basresan optimeras inte för robusthet.
Om något tillämpligt bortfall saknar reserv blir minutens värde +∞.
T50/T90/T99 beräknas över alla startminuter inklusive +∞ (JSON använder
`UNREACHABLE` för oändliga kvantiler och null för ej nåbara minutvärden).
Andelen startminuter där alla bortfall har reserv visas separat. En ren
gångresa har inga trafikben och använder basrestiden i det samlade måttet.
Ej nåbar basresa är även ej nåbar i det samlade måttet. Separata villkorade
sammanfattningar per ben behåller sitt tidigare kontrakt.

I läget **Framme senast** väljs datum, deadline i angiven tidszon och ett
explicit avreseintervall. Motorn prövar varje minut och visar den senaste
som klarar deadline dels i basfallet, dels vid varje enskilt bortfall. En
senare start kan ge tidigare ankomst: ingen monotonitet antas. Deadline
inkluderar gång och slutmarginal. Knappen öppnar basresan eller det värsta
bortfallet; scenarioväljaren visar också övriga reserver för samma minut.
Ingen godkänd minut visas tydligt som ett misslyckat villkor inom intervallet.

Detta är **tidtabellsbaserade villkor**, inte sannolikhet att komma fram i
verklig trafik. T90_schedule mäter variation över startminuter och får inte
tolkas som 90 % punktlighet för en exakt vald resa.

## Livscykel och frysta regressioner

Den lokala servern behåller en isolerad worker/JVM. Nätverket byggs vid
första uncachade uppdraget och återanvänds för nya basanalyser, detaljer och
N−1. Anrop serialiseras kring nätet och turuteslutningen. Resultat skrivs
atomiskt; kod-/datafingeravtryck kontrolleras och cacheidentiteten innehåller
parametrar och motorkod. Ändrade formulärvärden eller kartpunkter rensar gamla
resor och deadline-resultat direkt; äldre asynkrona svar får inte renderas.

`legacy_regressions.json` låser identitet och checksumma för de tre tidigare
validerade originalen från commit 7b80071. Endast dessa exakta arkivresultat
accepteras med äldre kodhashar. Inputhashar och kontrakt kontrolleras fortfarande.
Det samlade måttet/deadline kan härledas från dessa utan ny routing och utan
att ändra originalfilerna. Andra gamla resultat med ändrad kod avvisas.

## Start, kontroll och begränsningar

Kör i projektroten med befintlig lokal miljö och `config/paths.toml`:

```powershell
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/review_server.py
```

Öppna **http://127.0.0.1:8765/**. Förvalen använder frysta 60-minutersresultat.
För egna punkter rekommenderas först ett litet avreseintervall.

```powershell
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B -m unittest discover -s tests -v
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/validate_planner.py
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/validate_nminus.py --check-existing
```

Regressionkontrollen bygger ett nätverk och jämför de 180 frysta basminuterna
en gång med aktuell sweep och rå R5. Den gör inga nya N−1-fönstersweeps.
Resultat, miljö och cache är fortsatt ignorerade. Nätverksschematisk geometri
och orange approximativa gånganslutningar verifierar inte fysisk framkomlighet.
OSM-bakgrund använder samma attribution och policy som tidigare; koordinater
och rutter skickas inte till en publik routingserver.

Service-dags-/DST-övergång och frekvensbaserade turinstanser är fortsatt
begränsningar; valda tidsfönster som kräver sådana avvisas. 1501-filtreringen
och originalfeed är oförändrade. GeoTools-filhandtagsfelet vid JVM-städning
är känt: efter processavslut görs uppskjuten städning. Fel döljs inte i loggen.
