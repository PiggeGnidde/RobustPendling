# Lokal granskningsvy – Phase 2D

# Uppdaterad lokal planerare

Vyn stödjer nu egna kartpunkter/koordinater, 1–4 trafikben, samlat N−1 och
”framme senast”. Aktuellt kontrakt, startkommandon, begränsningar och
cache-/workerlivscykel finns i [PLANNER.md](PLANNER.md). Tidigare
granskningsbeskrivning längre ned avser den bevarade Phase 2D-vyn.

Aktuell vidareutveckling lägger till separat N−1-scenarioval och en
Leaflet/OpenStreetMap-bakgrund. Kontrakt, villkor och aktuella verifieringar
finns i [N_MINUS_ONE.md](N_MINUS_ONE.md) och
[N_MINUS_ONE_VALIDATION.md](N_MINUS_ONE_VALIDATION.md). Start-/stoppkommandon
nedan är fortfarande desamma. Beskrivningen av den helt lokala SVG-kartan
nedan avser Phase 2D; den finns nu som reserv när bakgrundsbiblioteket saknas.

Vyn använder den validerade Phase 2C-motorn utan ändrad routing eller
kvantildefinition. Varje startminut väger lika. **Enligt tidtabell –
förseningar ingår inte.** Schedule-kvantiler är inte en sannolikhet för
punktlig ankomst. Nästa analysläge är ”framme senast kl. …”; det är inte
implementerat här.

## Start och förutsättningar

Kör från denna worktree med den befintliga miljön `robustpendling` och
Git-ignorerad `config/paths.toml`. Inga nya paket behövs. Servern lyssnar
endast på **http://127.0.0.1:8765/**, utan externa skript, kartplattor eller
andra nätanrop. Den ska inte exponeras publikt.

```powershell
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/review_server.py
```

De tre förvalen läser `outputs/phase2c_{lomma_lund,malmo_varnhem,gunnesbo_ideon}_1.json`.
När resultaten finns lokalt måste de vara OK och ha samma OSM/GTFS-hashar,
frysta parametrar, r5py-version och routingkod som aktuell motor.
GeoJSON:s bytehash kontrolleras. Saknade resultat ger fortfarande tre
förval med koordinater lästa från GTFS; valet kör en ny analys. Äldre
resultat med fel hash avvisas. Återskapa saknade/äldre förvalsresultat:

```powershell
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/validate_phase2c.py
```

Starttid + fönsterlängd anger exakta hela startminuter, med samma gränser
och tidszonskontroller som CLI:n. Koordinater måste ligga inom den
hashbundna extraktionsrektangeln. Ej nåbara minuter behålls i kurvan och
kvantilerna och visar ingen påhittad resa.

## Worker, identitet och cache

HTTP-servern importerar inte JVM. Sparade detaljresor används bara för
exakt rätt minutindex, med godkänd sweepmatchning. Saknad detaljresa
hämtas av `review_detail_worker.py`, en separat Python/JVM-process som
byggs upp vid första cachemissen. Den behåller **ett TransportNetwork**
för samtliga detaljklick och relationer under serversessionen. För varje
begäran används den validerade exakta DetailedItineraries-adaptern,
inklusive avstigningskontroll före dominanspruning. Resultatet måste
matcha minutens optimala restid och godkända tidskedja.

Detaljanrop serialiseras. GTFS läses för aktuell servicedag/fönster per
cachemiss; det är enklare men långsammare än en separat kalendercache.
Worker-PID, byggtid och byggantal sparas i detaljresultaten. Nya kompletta
analyser använder befintlig engångsworker, en nätverksbyggnad per analys;
de delar inte detaljworkerns JVM. Det kan därför finnas två JVM samtidigt.

Analys-ID binds till metadata, inputhashar, mått och alla minutobservationer.
Detaljcache binds dessutom till minutindex och detaljmotorns kodhash.
Cache/resultat/loggar skrivs under ignorerade `outputs/review`. Atomisk
JSON skrivs före workersvaret. Webbläsaren kontrollerar analys-ID och
minutindex och använder generationsnummer för både indatasats och val.
Gamla svar får aldrig renderas efter ändrade indata eller nytt minutval;
reskedja och karta döljs omedelbart under laddning och vid fel.

Vid workerfel får användaren ett tydligt fel och nästa cachemiss kan
starta en ny process. Detaljanrop har 600 s timeout; full analys 1800 s.
Vid timeout stoppas fullanalysens eget supervisor-/JVM-processträd via
dess PID på Windows; andra Python-/Java-processer berörs inte.
Stdout/stderr sparas lokalt. WinError 32 vid JVM:s GeoTools-städning
loggas med traceback; samma avgränsade Phase 2C-städning utförs efter
workeravslut. Exitkod/PID/städresultat skrivs till
`outputs/review/detail-worker-exit.json`. Stoppa ordnat från en annan terminal:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/shutdown -ContentType application/json -Body '{}'
```

Servern väntar på pågående jobb, skickar stop till detaljworkern och väntar
på JVM-avslut. Efter 60 s avslutas workern tvingat. Tvångsstängning av
hela terminalens processträd kan kringgå denna ordnade städning; använd
shutdown-anropet för en reproducerbar avslutsdiagnos.

## Karta och omfattning

Leaflet-kartan visar WGS84-geometri från detaljsegmenten över OpenStreetMap,
med panorering/zoom, hållplatser och bytespunkter. SVG-reservkartan visar
samma lokala geometri utan bakgrund. Basresa, genomförd del och reserv har
olika färger. Gång är streckad i resans färg och approximativa raka anslutningar
är tjockt orange med en orange prick. Orange avser bara anslutningen mellan
gatunät och anrops-/hållplatspunkt, inte hela gångvägen. Segmenttexten visar
anslutningens längd; **Visa orange anslutningar** zoomar till dessa delar.
Markeringarna ritas ovanpå övriga rutter/markörer. Knappen fungerar också i
SVG-reservkartan, och **Återställ karta** återgår till hela resan.
Fokus och användarens zoom behålls när man skrollar bort från kartan och tillbaka.
Tunna orange/rosa streck i OpenStreetMaps bakgrund är kartleverantörens egna
symboler och ska inte förväxlas med analysens orange anslutningar.
Anslutningarna ändrar inte restiderna och verifierar inte fysisk
framkomlighet. Kartan markerar segmentändpunkter och visar vald basresa
och eventuell vald N−1-reserv. Antalet
upptäckta alternativ anges, men alternativa kartor väljs inte i denna fas.
Linjeandelar avser **valda** resor, inte en uttömmande reservvägsinventering.

## Verifiering i webbläsare

Alla tre förval öppnades och kurva, karta och reskedja granskades i
Codex in-app browser. Måtten är identiska med Phase 2C:

| Fall | T50 / T90 / T99 | buffer90 / buffer99 / full range | Täckning / saknade |
| --- | --- | --- | --- |
| Lomma–Lund | 36:17 / 39:17 / 42:17 | 3:00 / 6:00 / 10:00 | 100 % / 0 |
| Malmö C–Värnhem | 16:26 / 19:26 / 20:26 | 3:00 / 4:00 / 7:00 | 100 % / 0 |
| Gunnesbo–Ideontorget | 32:56 / 37:56 / 41:52 | 5:00 / 8:56 / 19:56 | 100 % / 0 |

Största hoppets båda sidor kontrollerades via knappar och kurvklick:

| Fall | Före → efter | Reskedja och ankomst |
| --- | --- | --- |
| Lomma | 07:35 32:17 → 07:36 42:17 | 139 07:42:08→08:02, mål 08:07:17; efter 139 07:51:16→08:13, mål 08:18:17 |
| Malmö | 07:26 13:26 → 07:27 20:26 | 9 07:28→07:36, mål 07:39:26; efter 9 07:36→07:44, mål 07:47:26 |
| Gunnesbo | 07:26 25:19 → 07:27 41:52 | 817→6, byte efter 5:53 gång med 1:07 kvar, mål 07:51:19; efter 4→6, bytesmarginal 3:04, mål 08:08:52 |

Tidigare ocachade minuter hämtades, bland annat Lomma 07:00 (37:17),
07:02 (35:17) och Gunnesbo 07:00 (38:56). Gunnesbo 07:00 och Lomma
07:02/07:03 använde samma PID och nätverksbyggnad (1,29 s).
Snabbt val 07:03→07:02 kontrollerade att endast senaste minut kan visas.
Latitud 91 gav indatafel; latitud 56 gav OUTSIDE_NETWORK_AREA och ingen
gammal karta. Ändrade koordinater/fönster kördes också genom motorn:
Lomma lat 55.67435, två minuter gav 37:17/36:17 med rätt separat resultat.
JavaScript-konsolen hade inga fel. Ej nåbara minuter och cacheidentitet
kontrolleras även med syntetiska tester; förvalen har inga saknade resor.

Regressionen `test_no_dropoff_state_cannot_prune_valid_alternative`
fanns redan och behålls. Nya tester kontrollerar indata/identitet,
exakta cacheindex, unreachable, workeråteranvändning samt HTTP:s
filvitlista och avvisning av externa origins. Ingen data, miljö eller
hemlighet ska committas.

Slutkontroll: **53 tester passerade**. Ordnat shutdown-anrop gav
workerexit **0** (PID 32812); GeoTools WinError 32 bevarades i stderr och
den uppskjutna temporärstädningen gav `removed=true`. Vyn startades igen
efter kontrollen för fortsatt lokal granskning.
