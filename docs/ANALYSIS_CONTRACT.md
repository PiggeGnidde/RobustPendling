# A–B-analyskontrakt, schema 2.0 (Phase 2B/2C)

# Planerarutökning

Den lokala A–B-planeraren accepterar nu `max_rides` 1–4, kontrollerar
datumtäckning och erbjuder samlat N−1 samt ankomstdeadline enligt
[PLANNER.md](PLANNER.md). Default/regressionsexemplen behåller två ben.
Deadline prövas per startminut; schedule-kvantiler är variation över
startminuter och anger inte verklig punktlighet för en vald avgång.

CLI:n `scripts/analyze_t90.py` är anropsgränsen för ett framtida webbgränssnitt.
Det separata N−1-kontraktet och resultaten finns i
[N_MINUS_ONE.md](N_MINUS_ONE.md) och [N_MINUS_ONE_VALIDATION.md](N_MINUS_ONE_VALIDATION.md).
Basfallets definition och kod är oförändrade.
Phase 2D lägger till en lokal granskningsserver, beskriven i
[LOCAL_REVIEW.md](LOCAL_REVIEW.md). Metoden är **T90_schedule/R0**, variation i statisk
tidtabell, med definition och databegränsningar i [T90_DEFINITION.md](T90_DEFINITION.md).
Den beskriver inte observerad punktlighet, förseningar eller inställda turer.
**Schedule-kvantiler mäter variation över startminuter, varken faktisk
försening eller sannolikheten att komma fram i tid.** Phase 2C:s validering
och kvarstående databegränsningar finns i
[PHASE_2C_VALIDATION.md](PHASE_2C_VALIDATION.md).

## Anrop

```powershell
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/analyze_t90.py --from-lat 55.674346 --from-lon 13.074675 --to-lat 55.706384 --to-lon 13.187015 --from-name "Lomma station" --to-name "Lund C" --date 2026-10-12 --start 07:00:00 --window-minutes 60 --timezone Europe/Stockholm --output outputs/phase2b.json
```

Koordinater är WGS84: latitud −90…90 och longitud −180…180, ändliga tal.
Samtliga fyra koordinater krävs när någon anges. Underscore-alias, exempelvis
`--from_lat`, stöds. Namn är valfria visningsetiketter. Utan koordinater används
GTFS-namnen Lomma station och Lund C för bakåtkompatibilitet; valfria namn
väljer då station genom exakt namnmatch. `--window-length` är alias för
`--window-minutes`. Standarddatum/start/fönster/zon är 2026-10-12/07:00/60/
Europe/Stockholm. Äldre `--end` stöds, men får inte kombineras med fönsterlängd.

Starten måste ligga på hel minut. N minuter ger exakt start, start+1 minut,
…, start+(N−1) minuter; det sista fönstrets slut är sista startminut+59 s.
IANA-tidszoner stöds. UTC 05:00 motsvarar Stockholm 07:00 detta datum.
Tider konverteras till verifierad `agency_timezone` i GTFS för routing och
till begärd zon för exporterade klockslag. Fönster över lokal midnatt,
GTFS-servicedagens gräns eller sommartidsövergång stöds ännu inte.
Tvetydiga och obefintliga lokala tider avvisas, utan tyst korrigering.

## Nätverksgräns och parametrar

Det kända OSM-utdragets verifierade SHA-256 är
47942e06ea6c96c8893933f71f448f7e1deac9d906c216a16c60a414db521b9d.
Till dessa bytes binds den faktiska extraktionsrektangeln
**[12.95, 55.60, 13.30, 55.80]**, i ordningen väst/syd/öst/nord.
`complete_ways` inkluderar avlägsna way-noder: objektens totala bbox
är därför inte ett tillförlitligt mått på routingområdet.
För annat underlag krävs en verifierad lokal konfigurationssektion
`[network_area]` med `bbox`, `osm_sha256` och beskrivande `source`.
Ändrad filhash ogiltigförklarar områdesbeskrivningen. Ingen täckning gissas.

Utanför rektangeln returneras `OUTSIDE_NETWORK_AREA` med de berörda
ändpunkterna i `network_area.outside`, före nätverksbyggnad/JVM-import.
Okänd täckning ger `NETWORK_AREA_UNVERIFIED`. Felaktiga anropsvärden ger
`INVALID_REQUEST`; ej stödda kalenderfönster ger `UNSUPPORTED_WINDOW`.
Felstatus har samma toppnivåfält, tomma observations-/reselistor och null
för metrics/GeoJSON. En punkt inom rektangeln garanterar inte anslutning
till en gångväg; saknad användbar resa redovisas som UNREACHABLE.

Frysta routingparametrar är fortfarande 3,6 km/h, 900 s sammanlagd gång,
2700 s total restid, högst två fordonsdelar, 60 s boarding slack med strikt
avgångsregel och 60 s extra före sista gången. Pickup/dropoff 0 och 3
tillåts. **Rent gångalternativ tillåts nu**, inom samma gångbudget,
med noll byten och utan kollektivtrafikens slack. Detta påverkar inte
Lomma–Lund eftersom direkt gång överskrider budgeten. Ingen stokastik
eller nya percentilregler har lagts till.

Ovanstående 2700 s och två ben avser de historiska Phase 2B/2C-förvalen.
Den lokala planeraren använder nu **7200 s (120 minuter)** för nya
basanalyser och 1–4 valda trafikben. Gångstandard är 4,5 km/h, högst 20 min
totalt; valbara intervall är 3–6 km/h och 10–30 min. API-parametrarna
`walk_speed_kmh`, `max_walk_minutes` och `max_time_minutes`
och resultatets `metadata.parameters.max_time_seconds` anger horisonten;
den följer med genom routing, detaljresor, validering och cacheidentitet.
Ett resultat `UNREACHABLE` avser bara dessa dokumenterade analysgränser.

## JSON och strukturella mått

Alla tidsmått är **sekunder**; andelar är **0…1**. Tider är ISO 8601 med
UTC-offset. `schema_version` är `2.0`. `status=OK` betyder att representativa
R5-restider också matchar sweepen. Avvikelse ger `REPRESENTATIVE_MISMATCH`,
med båda värdena bevarade. Avvikelse i någon minuts råa R5-kontroll ger
`ROUTING_MISMATCH`. Konsumenten måste kontrollera status och
`worker.result_status`; processfel ger ett misslyckat CLI-anrop.

| Fält | Innehåll |
| --- | --- |
| `metrics` | T50/T90/T99, min/max/medel, täckning och strukturella mått |
| `minute_observations` | Samtliga minuter, duration/null, gång/väntan/slack/byten, reskedja och vald family |
| `representative_itineraries` | Representativa minuter, roller, bästa R5-resa, deduplicerade alternativ och kontrollresultat |
| `route_families` | Normaliserade sekvenser med ID, antal valda minuter och andelar |
| `alternatives` | Alternativens minut, roller, option, family, restid och extra sekunder |
| `geojson_path` | Sökväg relativt projektroten, exempelvis outputs/phase2b.HASH.geojson |
| `metadata` | Input-/kod-/JAR-hashar, versioner, datum/zon/startminuter, alla parametrar och experimenthash |
| `verification` | Exaktminutkontroller, matrixjämförelser, nätverksbyggnader och antal detaljanalyser |
| `derivation`, `worker`, `timing` | GTFS-filtrering, avslutsdiagnostik och uppmätta körtider |

Äldre `statistics`, `observations`, `components` och `combinations` behålls.
Gång- och väntestatistik finns i `components`; varje minut innehåller också
gång, väntan och byte. Saknade minuter droppas aldrig: null-restid motsvarar
+∞ i percentiler, max och medel. Ett icke ändligt mått kodas UNREACHABLE.

- `buffer_90 = T90−T50`, `buffer_99 = T99−T50`, `full_range = max−min`.
  Vid oändlig operand används UNREACHABLE, även vid ∞−∞.
- `route_coverage` är nåbara minuter / samtliga minuter.
- `dominant_route_share` avser andelen **nåbara** minuter som väljer dominant
  family; `dominant_route_share_all_minutes` använder alla minuter som nämnare.
- `distinct_selected_route_families` räknar endast minuternas valda optimum.
  Alternativ som bara hittas för representanter ökar inte detta antal.
- `transfer_count_distribution` är antal nåbara minuter per bytesantal;
  ej nåbara minuter rapporteras separat genom unreachable_count.
- `departure_sensitivity` är största **positiva** ökning av optimal restid
  mellan intilliggande startminuter, med båda klockslagen. Noll betyder att
  ingen ökning finns. Nåbar→ej nåbar ger UNREACHABLE. Alla övergångstyper
  som berör saknad resa räknas också i `unreachable_transitions`.

En family är den ordnade sekvensen trafikslag, route_id (linjenamn som
reserv om ID saknas), påstignings-ID och avstignings-ID. Linjenamn är även
visningsdata. WALK-delar och deras geometrier ingår inte i identiteten.
Olika på-/avstigningshållplatser eller ordning ger olika families; olika
trip_id på samma linje/hållplatssekvens gör det inte. ID är SHA-256 av den
kanoniska sekvensen. Ren gång har en tom sekvens och en gemensam family.

## Representativa resor och GeoJSON

Nearest-rank väljer observerade restider. För min/T50/T90/T99/max används
första startminuten med den aktuella restiden; flera roller för samma
observation samlas. Ej nåbara representanter behålls men routas inte.
Nätverket byggs **en gång**. DetailedItineraries körs endast för distinkta,
nåbara representanter, högst fem, inte för alla 60 minuter.
Med `--audit-jumps 3` tillkommer båda sidor om de tre största positiva
restidshoppen; överlappande minuter analyseras en gång. `departure_jumps`
lagrar rank, minutindex, klockslag och ökning. Detaljresor och features får
`audit_roles`, exempelvis jump_1_before, och tom percentile_role om minuten
endast är en hopprepresentant. Hopp till UNREACHABLE behålls och rankas
före ändliga hopp; saknad resa får ingen påhittad geometri.

Den versionsbundna adaptern ersätter DetailedItineraries OD-hook så att
R5 verkligen utvärderar exakt sekund och samtliga slutalternativ bevaras.
Stock-hooken kollapsar flera tillstånd per starttid och återanvänder
muterbara access/egress-ben. Adaptern kopierar varje segment separat.
R5:s slutalternativ filtreras med samma gång-/restidsbudget och
pickup/dropoff-regler, dedupliceras per family och behåller snabbaste
alternativet, sedan lägst gångtid och deterministisk segmentordning.
Phase 2C filtrerar GTFS-pickup/dropoff redan **före dominanspruning** via
en versionsbunden DominatingList-adapter. Otillåten avstigning får inte
slå ut giltiga alternativ. Varje alternativ har `timing_validation` för
klockspann, komponenter och strikt möjliga boardings inklusive bytesgång.
`slower_than_best_seconds` avser sweepens verifierade optimum; noll är
tillåtet för likvärdigt alternativ. R5:s suboptimalMinutes=5 begränsar
alternativsökningen: den är **inte** en uttömmande lista över alla resvägar,
och alternativa family-andelar över hela timmen uppskattas inte från fyra minuter.
Den historiska CLI-valideringen kontrollerar rå R5 för varje startminut.
Interaktiv analys använder nu exakt profilåteranvändning och kontrollerar
profilens sökminuter, gränserna före nästa sökning och sista minuten mot rå R5.
`verification.raw_r5_checked_indices` anger exakt vilka minuter som kontrollerats.
`--validate-every-minute` jämför dessutom profil mot separat sweep och rå R5
för varje minut. Se [SCHEDULE_PROFILE.md](SCHEDULE_PROFILE.md). Fullständiga
itinerary-/geometrianalyser görs fortsatt bara för representativa minuter.

GeoJSON är en FeatureCollection i EPSG:4326, med LineString eller
MultiLineString per segment. Transitgeometri kommer från R5:s
GTFS-hopgeometrier och gånggeometri från dess gatunät. Properties omfattar
mode, line/route_id, start/end_stop och namn, departure/arrival,
travel_seconds/walking_seconds/wait_seconds/fixed_slack_seconds, trip_id,
option, route_family, segment, representative_start och **percentile_role**
(lista, till exempel `["T99","max"]`). Option 0 är bästa returnerade resa;
option-numret är lokalt för representativ minut. Väntan tillhör följande
transitsegment och är inte en separat linjegeometri. Slutlig 60-s-marginal
redovisas separat. Punktnamn används vid gångresans yttre ändpunkter, utan
påhittade GTFS-ID:n. Geometrin valideras som ändliga lon/lat-koordinater.
WALK kompletteras vid behov med approximativa raka anslutningar från
GTFS-/anropspunkt till R5:s snappade gata. `geometry_source` och
`geometry_connectors_m` skiljer dessa från nätets gatungeometri.
Tid/kvantiler ändras inte av kartkompletteringen; fysisk tillgänglighet
genom exempelvis en station är inte verifierad av en rak anslutning.

GeoJSON skrivs atomiskt först till ett innehållsnamngivet filnamn, därefter
JSON-resultatet atomiskt. `geojson_sha256` verifierar faktiska filbytes;
`geojson_canonical_sha256` verifierar kanonisk JSON och styr filnamnet.
Inputhashar kontrolleras före och efter routing. Metadatahashen undantar
körtider, loggsökväg och processdiagnostik. Hela outputs är Git-ignorerad.
JVM-isoleringen behålls; PyExceptionProxy vid avslut loggas fortfarande
och redovisas som worker.jpype_shutdown_error=true även när exit_code=0.
Detta var Phase 2B:s avslutsläge. Phase 2C lokaliserar WinError 32 i
GeoTools EPSG-databasens temporärstädning och skjuter upp just denna
städning tills workerprocessen avslutats. Full traceback bevaras i
separat `worker.stderr_log` och `shutdown_stderr`. `cleanup_deferred` samt
`cleanup_after_exit[].removed` visar utfallet; `cleanup_success` avser
hookens ursprungliga försök. PID, exitkod, exited och elapsed_seconds
redovisas som körmetadata. Paketet ändras inte och andra fel undertrycks inte.

## Verifierat Lomma–Lund-resultat

Nedan är Phase 2B:s historiska artefakthashar, testantal och fyra
representanter. Aktuella Phase 2C-körningar med hoppgranskning redovisas i
PHASE_2C_VALIDATION.md; restidsfördelningen är oförändrad.

2026-10-12 kl. 07:00–07:59, 60 minuter:

| Mått | Resultat |
| --- | --- |
| T50 / T90 / T99 | **36:17 / 39:17 / 42:17** |
| Min / max / medel | 32:17 / 42:17 / 36:23 |
| buffer_90 / buffer_99 / full_range | 3:00 / 6:00 / 10:00 |
| Täckning / saknade minuter | **100 % / 0** |
| Dominant vald family | Buss 139, Lomma Strandvägen → Lund C, **100 %** |
| Valda families / byten | 1 / 0 byten i 60 minuter |
| Största minutvisa försämring | **10:00**, 07:35 → 07:36 |
| Representanter | T50 07:01; min 07:05; T90 07:06; T99/max 07:36 |
| Detaljanalyser / exporterade segment | **4 / 44** |
| Alternativa family-observationer | 8, efter deduplicering per representant |

Alla fyra bästa detaljresor matchar sweepen. Alla 60 exakta råa R5-restider
och alla 60 matrixkontroller matchar sina dokumenterade jämförelsevärden.
Två identiska körningar gav identiska metadata, observationer, mått,
representanter, families, alternativ, verifieringar och GeoJSON-bytes.
Experimenthash: bcd8b337d4388563d1425cece04da262a2e4018795ff23c877c66ea575a1537b.
GeoJSON-filens SHA-256:
4948e7a91904fd281347fce3d75ac07163a5787ce0d5d5ef5041530354749643.
Alla 40 tester passerade. En separat körning med godtyckliga närliggande
koordinater och UTC gav 308 s ren gång och en detaljanalys för två minuter.
Punkt utanför området avvisades utan JVM-start.
Gång är 606 s och inga byten väljs. Lika snabba alternativ med annan
avstigningshållplats är korrekt olika families. Geometri och
alternativ saknas avsiktligt för övriga 56 minuter.

Filtrering av 1501 är oförändrad: R5 stöder inte trafiktypen; separat
GTFS-kopia tar bort 340 routes, 1440 trips, 6134 stop_times och 3 transfers.
Originalets SHA-256 förblir
6a17c51b0924301eea8466e71d826bd7495199ce3a0de7f4f90d0293b4c13182.
Detta regionala test är inte full Skånetäckning, ±15-minutersstudie eller
arbetsplatsanalys. Inga miljöpaket eller nya data installerades/hämtades.
