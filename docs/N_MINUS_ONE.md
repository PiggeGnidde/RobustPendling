# Deterministisk N−1 enligt tidtabell

**Utökning `nminus-1.1`:** [planerarkontraktet](PLANNER.md) generaliserar
bensbudgeten till 1–4 och lägger till `combined` samt deadline. Beskrivningen
nedan av två ben avser det bevarade ursprungliga regressionstestet/default.
Nya anrop bevarar den budget som valts för hela genomförd + återstående resa.

**Scenario enligt tidtabell – ingen sannolikhet för inställd tur uppskattas.**
Detta är en separat konsekvensanalys. Basfallet behåller exakt Phase 2C:s
60 startminuter, T50_schedule/T90_schedule/T99_schedule och gränsen 45 min.
Historiska förseningar, realtidsinsamling och en sannolikhetsmodell ingår inte.

## Informationsantagande, resurser och sökhorisont

För varje nåbar basresa finns ett separat scenario per trafikben. Gång
skapar inget scenario. Exakt en turinstans uteblir åt gången; inget annat
fordon försenas eller tas bort. Bortfall av ben 2 inkluderar aldrig också
bortfall av ben 1.

Beskedet kommer vid **det felande benets planerade avgång**, på dess
påstigningshållplats. Resenären har redan genomfört ursprunglig gång,
eventuella tidigare trafikben, bytesgång och väntan före beskedet.
Prefixets segment, geometri, klockslag och ursprunglig start bevaras.
Tid från prefixets slut till beskedet redovisas separat som förbrukad väntan.
Omplaneringen sker från exakt hållplats, med 0 s gång till samma hållplats;
den sker aldrig från anropspunkten och får inte välja passerade avgångar.

Sökhorisonten är **7200 s / 120 minuter efter beskedet**, inklusive
reservresans slutgång och eventuell 60-s-slutmarginal. Det sista giltiga
ankomstklockslaget lagras per scenario. Hela GTFS-fönstret laddas till sista
startminut + 45 min basresa + 120 min, alltså även trafik efter 07:59:59.
Detta är en uttrycklig analysgräns, inte en schablon för extra väntan.

Gånghastigheten är fortsatt 3,6 km/h. **900 s gång och högst två trafikben
gäller hela den genomförda + återstående resan**. Förbrukad gång/tid och
trafikben återställs inte vid beskedet. Ben-2-scenariot har därmed högst ett
återstående trafikben. Boarding från den nya beslutsögonblicket kräver
strikt avgång > besked + eventuell ny gång + 60 s. Redan förbrukad väntan
före beskedet krediteras inte som nytt boarding slack. Samma strikta regel
gäller fortsatta byten. Pickup/dropoff 0 och 3 tillåts, 1 och 2 avvisas.
60 s läggs före slutgång om resan har trafikben; helt ren gång har ingen
sådan marginal. N−1:s tidsgräns är alltså större än basfallets, medan gång-
och trafikbensbudget samt boardingregler bevaras.

## Exakt turidentitet och R5-stöd

Instansen identifieras med **feed-namespace, originalfeedens SHA-256,
GTFS trip_id och trafikdag**. R5:s verkliga namespace i det frysta
Skånetrafiken-underlaget är `SE-st`; det är inte operator-endpointens namn
`skane`. `r5_scoped_trip_id` bevaras också. Trip-ID:n ska vara entydiga i det
aktuella nätet. Frekvensbaserade turer avvisas; deras instansidentifiering
och R5:s frekvenssampling kräver en separat metod. Servicedag/DST-övergång
och tidsfönster som kräver nästa trafikdag avvisas i denna första version.

Pinned r5py 1.1.7/R5 7.5.1-r5py har ingen hög nivå för att utesluta ett
trip_id i DetailedItineraries. Källkodskontrollen visar att R5 söker första
**aktiva** TripSchedule i ett mönster före boarding och sedan avbryter
den sökningen. Ett rent efterfilter skulle därför kunna dölja nästa tur:
[McRaptorSuboptimalPathProfileRouter](https://github.com/r5py/r5/blob/v7.5.1-r5py/src/main/java/com/conveyal/r5/profile/McRaptorSuboptimalPathProfileRouter.java).
Den publika, ändringsbara `TripSchedule.serviceCode` kontrolleras mot
anropets aktiva trafikkalender:
[TripSchedule](https://github.com/r5py/r5/blob/v7.5.1-r5py/src/main/java/com/conveyal/r5/transit/TripSchedule.java).

Adaptern sätter **bara den exakta turens** serviceCode till en verifierat
inaktiv kod under det aktuella, serialiserade R5-anropet. Därmed hoppas
turen över före boarding vid samtliga hållplatser, medan nästa avgång på
samma linje kan väljas. `finally` återställer originalkoden även vid fel.
Alla turers kalenderkoder kontrolleras mot ursprungsvärdena efter varje
scenario. Ingen GTFS-fil, linje, global miljö eller serialiserad nätverkscache
ändras. Ingen annan request kan använda nätet under override-perioden.
Ett nytt anrop med annan trafikdag körs först efter återställning.

Den oberoende, uttömmande ett-/tvåbenssökningen tar bort samma trip_id
ur dagens aktiva GTFS-turer. Exaktsekundssvar från R5 jämförs med varje
vald reservrestid. En resursmedveten Pareto-lista skyddar gång-/bensbudget
och GTFS-permissioner **före dominanspruning**. R5:s target-time-pruning
vidgas för kontrollen så att ett tidigt men gångmässigt otillåtet tillstånd
inte döljer en senare giltig reserv. R5:s returnerade tillståndskedjor
kontrolleras också för att ingen innehåller den borttagna turen.

## Resultatkontrakt `nminus-1.0`

`/api/nminus` tar samma `analysis_id` som basresultatet och returnerar ett
jobb-ID. Efter beräkning/cache har resultatet `status=OK`, identitet,
basexperimenthash, input-/kodhashar, versioner, datum/zon, parametrar,
`horizon_seconds`, oförändrade `base_metrics` och `minute_observations`,
basresans segment för varje minut, `scenarios`, `summaries` och GeoJSON.
N−1-resultat/cache är Git-ignorerade under `outputs/review` och `outputs/nminus`.

Varje scenario har:

- `index`, oförändrad `start`, trafikbensnummer och status.
- `failed_leg`, `failed_instance`, `notification` med plats, koordinater och tid.
- `completed`: bevarade segment, förbrukad tid/gång/trafikben och väntan före besked.
- `remaining_parameters` och explicit `search_end`.
- `reserve`: trafikben, segment, gång/väntan/slack och restid från beskedet.
- `total_seconds` från ursprunglig start och `extra_seconds` mot samma minuts basfall.
- `raw_r5_seconds` och per-scenario GeoJSON med `phase=completed/reserve`.

Ej tillämplig minut har `NOT_APPLICABLE` (saknat ben eller ej nåbar basresa).
Den påverkar inte scenariots nämnare. `UNREACHABLE` betyder tillämpligt men
ingen giltig reserv inom horisont/resurser; tider är null och ingen reservgeometri
hittas på. Sammanfattningar anger tillämpliga, ej tillämpliga, nåbara,
ej nåbara samt täckning = nåbara / tillämpliga. **N−1-kvantilerna beräknas
över nåbara, tillämpliga scenarier**, lika vikt/minut, nearest rank.
Vid täckning <100 % sätts `conditional=true` och vyn märker kvantilerna
som villkorade på nåbarhet. Vid noll nåbara är kvantiler null. Vid noll
tillämpliga är täckning null och inget misslyckande påstås. Detta skiljer
sig avsiktligt från basfallets behandling av ej nåbara minuter som +∞.

## Reproduktion och livscykel

Använd befintlig `robustpendling`-miljö, lokala `config/paths.toml` och
de frysta Phase 2C-resultaten. Ingen installation krävs.

```powershell
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/validate_nminus.py
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/validate_nminus.py --check-existing
```

CLI:n kör tre relationer två gånger i **en enda** isolerad worker med ett
nätverk. Identiska fortsättningsproblem återanvänds med nyckel hållplats,
beskedstid, felande tur, förbrukad gång och antal genomförda trafikben.
Hela resultatet och exporterade GeoJSON-bytes jämförs mellan repetitionerna.
Körtid, PID och JVM-avslut ligger separat från deterministiskt analysresultat.
Ny oberoende kontraktvalidator kontrollerar prefix, originalstart, tider,
boarding, budget, uteslutning, nämnare och kartsegment innan publicering.

Vyn startas/stoppas med kommandona i [LOCAL_REVIEW.md](LOCAL_REVIEW.md),
på **http://127.0.0.1:8765/**. Basdetaljer och N−1 delar den kvarlevande
detaljworkerns nätverk och serialiseras. N−1 cachelagras per analys och
aktuell motorkod. Ändrade indata/minut/scenario rensar gammal resa direkt;
svar med gammal generation får aldrig renderas som nytt val.

## Kartbakgrund och begränsningar

Leaflet **1.9.4**, med versionsbundna CDN-filer och SRI, använder
`https://tile.openstreetmap.org/{z}/{x}/{y}.png`. Synlig attribution länkar
till OpenStreetMap contributors/copyright och kartvillkor. Vanlig browser-
User-Agent och origin-Referer används; providerstyrd HTTP-cache respekteras.
Ingen proxy, cacheförbigång, förhämtning, tile-arkivering eller offline-
nedladdning implementeras. Tilelagret ansluts först när kartan visas;
`keepBuffer=0`. Endast aktuell karta efter mänskligt minut-/scenarioval laddas.
Se [OSMF:s tilepolicy](https://operations.osmfoundation.org/policies/tiles/)
och [Leaflets stabila version](https://leafletjs.com/download.html).

Blå grundresa, grön genomförd del och lila reserv visas tillsammans.
Baslinjen är bredare vid överlapp för att inte försvinna under reserven.
Gång är streckad; tåg har tjockare linje. Start/mål, hållplatser, byte och
röd beskedsmarkör finns. Orange anslutningar är approximativa, inklusive
uppmätta interna gap när R5:s gånggeometri innehåller flera delar.
R5:s GTFS-hopgeometri kan vara schematisk (exempelvis buss 3 mellan
Frihamnen och Värnhem har två punkter); den är inte observerad körväg.
Gångtid följer samma förberäknade R5-länkar som basfallet även när kartan
kompletteras. Fysisk stationsframkomlighet verifieras inte av en rak linje.

Vid tilefel fungerar Leaflets lokala rutter/markörer och en tydlig varning
visas. Om även bibliotek/CSS saknas används lokal SVG-karta med markörer,
zoom och panorering. Diagnostik `?tile-error` använder lokala 404-plattor;
`?offline-map` simulerar otillgängligt bibliotek utan OSM-tilehämtning.
Inga privata ruttdata/API-nycklar skickas till karttjänsten; kartutsnittet
är däremot synligt för leverantören. Tjänsten är fortsatt endast lokal.

Analysen är begränsad till befintligt regionalt OSM-utdrag, max två trafikben,
15 min sammanlagd gång och två timmars reservhorisont. Utanför dessa gränser
kan verkliga reserver finnas. 1501-filtreringen och original-GTFS är oförändrade.
Ingen publikt deployad tjänst, störningssannolikhet, historik eller realtid byggs.
