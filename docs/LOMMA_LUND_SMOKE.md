# Reproducerbart Lomma–Lund-funktionstest, 2026-10-11

## Frysta källor och lokala sökvägar

`scripts/prepare_lomma_lund.ps1` kopierar den redan hämtade GTFS-filen,
hämtar endast daterad OSM och dess MD5-manifest, verifierar checksumma,
extraherar med osmium-tool 1.19.1 och kör fileinfo samt check-refs.
Nya filer skrivs via temporär fil och namnändring i samma katalog.
Befintliga filer återanvänds och kontrolleras. Original-XML raderas inte.
Ingen latest-OSM-adress används.

| Fil under C:\RobustPendling\data | Storlek, byte | Kontroll |
| --- | ---: | --- |
| gtfs\skane-20261011.zip | 38 123 482 | SHA-256 6a17c51b0924301eea8466e71d826bd7495199ce3a0de7f4f90d0293b4c13182 |
| osm\source\sweden-261008.osm.pbf | 874 874 207 | MD5 86e3acf4bb45dc4626d53e2abf368083 |
| osm\extracts\lomma_lund-20261008.osm.pbf | 9 687 479 | SHA-256 47942e06ea6c96c8893933f71f448f7e1deac9d906c216a16c60a414db521b9d |

OSM-källan är [Geofabriks daterade Sverige-fil](https://download.geofabrik.de/europe/sweden-261008.osm.pbf)
med [MD5-manifest](https://download.geofabrik.de/europe/sweden-261008.osm.pbf.md5).
OSM-data kommer från OpenStreetMap contributors, ODbL.
Utdragets urvalsbbox är lon 12.95–13.30, lat 55.60–55.80,
strategi complete_ways. Alla noder i utvalda ways följer med, varför
objektens faktiska bbox är större: lon 10.8598047–14.2820889,
lat 53.8929481–56.0182597. Detta garanterar inte komplett täckning över
hela den större bboxen. Lomma–Lund ligger inom urvalsrektangeln.

fileinfo: 936 385 noder, 148 171 ways, 2 747 relationer; sorterade objekt
utan flera versioner. Senaste objekttid 2026-10-08T12:36:06Z.
check-refs lyckades: **0 saknade nodreferenser i ways**.
Relationsmedlemmars fullständighet är inte verifierad och garanteras
inte av complete_ways. Det tidigare export.osm har motstridiga dubbletter
och är fortsatt ogiltigt för routing; se ENVIRONMENT.md.

Den Git-ignorerade config/paths.toml använder [paths] med följande värden
(TOML-strängar med enkla citattecken tillåter Windows-backslash):

- osm = 'C:\RobustPendling\data\osm\extracts\lomma_lund-20261008.osm.pbf'
- gtfs = 'C:\RobustPendling\data\gtfs\skane-20261011.zip'
- cache = 'cache'
- output = 'outputs'
- lomma_archive behåller inventeringens befintliga Downloads-sökväg.

Kör förberedelseskriptet och sedan miljöns Python med
`-B scripts/smoke_lomma_lund.py --rebuild` enligt ENVIRONMENT.md.
--rebuild skapar en ny ignorerad nätverkscache, utan att radera äldre cache.
Utelämna flaggan för återanvändning. Loggen innehåller alla Java-meddelanden;
outputs/lomma_lund_smoke.json innehåller parametrar, hashkontroller, delar,
byggtid, samplad RSS och kontroll mot originalfeedens kalender/stop_times.

## GTFS-kompatibilitet

R5 7.5.1-r5py avvisar 340 routes med route_type 1501:
`Number 1501.0 outside of acceptable range [0.0,1500.0]`.
allow_errors=True räcker inte: routern avvisar senare typen med
IllegalArgumentException. Produktionsoriginalet behålls därför orört.
smoke_helpers.routing_feed skapar den deterministiska, ignorerade
data/gtfs/skane-20261011-r0.zip och separat metadata med båda filhasharna.
Den tar bort 340 routes, 1 440 trips, 6 134 stop_times och 3 transfers
som refererar till denna förbeställningstrafik. Övriga tabeller bevaras.
Härledd SHA-256: 0a43ea916ed78a0d26a71e471483a0ee07bf1131fd0e7504be03ac7f6a1d6a9f.
R5:s GTFS-validering ger därefter 0 fel med allow_errors=False.
Testet verifierar därmed den frysta feedens vanliga kollektivtrafik efter
en uttrycklig kompatibilitetsfiltrering; originalfeeden kunde inte routas direkt.

## Nätverksbygge och samtliga varningskategorier

Slutlig körning med tom nätverkscache: **38,20 s** för TransportNetwork.
Största samplade RSS för Pythonprocessen inklusive inbäddad JVM:
**2 728 038 400 byte**, cirka **2,54 GiB**, samplat var 0,1 s under
bygge och routing. Detta är en ungefärlig topp, inte maskinens totala minne.
JVM-heapgräns 4 GiB. Tidigare laddning från cache tog 1,21 s och cirka
798 MiB RSS. Miljöversionerna finns i ENVIRONMENT.md.

Loggen outputs/lomma_lund_smoke_rebuild.log bevarar alla **8 616**
R5 WARN/ERROR-meddelanden, med varje okopplad hållplatsindex. Fördelning:

- 1 varning: maxspeed-värdet `walk` känns inte igen.
- 2 varningar: från/till-kanter saknas för restriktion 3545449 och 20079537; hoppas över.
- 1 varning: relation 12019798 refererar till way 884903509 som saknas; relationen tas bort.
- 4 ERROR: restriktion 17351617, 17351618, 17351619, 17351621 saknar giltigt from/to/via; hoppas över.
- 1 ERROR: restriktion 17351620 har flera from-medlemmar; hoppas över.
- 8 607 varningar: hållplatsen är inte kopplad till gatunätet och får ingen distanstabell.

8 607 av 10 723 hållplatsposter är okopplade. Detta är väntat för en hel
regional feed på ett litet gatunät, men varje fel har inte geografiskt
klassificerats. 2 116 poster kopplades. Antalet bevisar inte att samtliga
lokala hållplatser är korrekt kopplade. Den provade resans anslutningar fungerar.
Inga Python-byggvarningar noterades. JVM-avslutningen skriver dessutom
`org.jpype.PyExceptionProxy` från Thread-1 efter färdigt resultat;
processens exitkod är 0. Detta kvarstår som ett runtimeproblem att undersöka.

## En handkontrollerad resa

En enda OD-punktkombination: Lomma station till Lund C, måndag
2026-10-12, Europe/Stockholm, startfönster 07:00–07:05. Koordinaterna
väljs från GTFS efter exakt stationsnamn, station-area före plattform,
sedan lägsta stop_id. Kandidatantal redovisas i resultatet.

| Punkt | GTFS-ID | Latitud | Longitud |
| --- | --- | ---: | ---: |
| Lomma station | 9021012062000000 | 55.674346 | 13.074675 |
| Lund C | 9021012081216000 | 55.706384 | 13.187015 |

WALK + TRANSIT, gånghastighet 3,6 km/h, max restid 45 min,
max gångtid 15 min, max två kollektivtrafikdelar. Ett versionsbundet
adaptersteg använder en enda internt vald starttid i R5, reproducerbart
koordinatseedad: **07:01:55**. Ingen egen stokastik eller percentilanalys
har lagts till. R5:s interna väljare är inte en garanti för exakt 07:00.
Med många interna starttider upptäcktes återanvända, muterbara gångdelar
som gav inkonsekventa klocktider; därför begränsas funktionstestet till en.
Ett enminutsfönster med R5:s standard 60 draws gav dessutom OutOfMemoryError
på både 4 och 8 GiB: interna tidssteg kunde bli noll. Undvik den kombinationen.

| Del | Tid |
| --- | --- |
| Gång Lomma station → Lomma Strandvägen | 07:01:55–07:07:44, 5 min 49 s |
| Väntan | 07:07:44–07:12:08, 4 min 24 s |
| Buss 139, route_type 700 | 07:12:08–07:32:00, 19 min 52 s |
| R5:s marginal före avslutande gång | 07:32:00–07:33:00, 1 min |
| Gång till Lund C-punkten | 07:33:00–07:37:17, 4 min 17 s |

**Total 35 min 22 s**, gång **10 min 06 s**, väntan **4 min 24 s**,
separat marginal **1 min**, **0 byten**. Bussankomst 07:32:00,
ankomst till målpunkten 07:37:17. Enbart summering av r5py:s travel_time
och wait_time ger 34 min 22 s och missar marginalen; skriptet använder
klockspannet och redovisar skillnaden. Från exakt 07:00 till samma
ankomst är spannet 37 min 17 s, men detta är inte ett optimerat 07:00-resultat.

Original-GTFS matchar trip_id **121120000397070063**, aktiv kalender
2026-10-12, linje 139, båda hållplats-ID:n, stigande stop_sequence och
exakt avgång/ankomst. Gång till en närliggande busshållplats och cirka
20 min buss till Lund är rimligt. Gånggeometrin är modellberäknad och har
inte fältverifierats. En direkt gångalternativrad på 157 min 33 s saknar
giltig avgång och överskrider gränserna; den ignoreras i kollektivtrafikresultatet.

Flera felsökningskörningar behövdes för kompatibilitet och R5-adaptern;
slutresultatet omfattar en OD-kombination och en vald kollektivtrafikresa.
Detta är **inte T90**, störningsanalys eller verifiering av hela Skåne.
22 automatiska tester passerar, inklusive källbevarande, deterministisk
GTFS-härledning, referensfiltrering, stationsval, kalenderkontroll och tidsmarginal.
