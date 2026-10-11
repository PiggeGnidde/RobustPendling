# Phase 2C: nätstrukturer, hopp och JVM-livscykel

Kvantilerna mäter **tidtabellsvariation över startminuter**, inte faktisk
försening eller sannolikhet att komma fram i tid. Samtliga fall använder
2026-10-12, Europe/Stockholm, 07:00:00–07:59:59 och 60 exakta startminuter.
Oförändrade parametrar: 3,6 km/h gång, totalt högst 900 s gång/2700 s restid,
två fordonsdelar, strikt 60-s-boardingregel, 60 s före sista gången och
nearest-rank-percentiler. Ej nåbara minuter är +∞, aldrig borttagna.

## Data och testval

Koordinaterna kommer från original-GTFS:s hållplats-/stationsområden.
Tabellens koordinatordning är latitud, longitud.

| Fall | Startpunkt, stop_id och koordinater | Mål, stop_id och koordinater |
| --- | --- | --- |
| Regression | Lomma station, 9021012062000000; 55.674346, 13.074675 | Lund C, 9021012081216000; 55.706384, 13.187015 |
| Malmöalternativ | Malmö C, 9021012080000000; 55.608777, 13.000216 | Malmö Värnhem, 9021012080110000; 55.605188, 13.024123 |
| Obligatoriskt byte | Lund Gunnesbo station, 9021012081215000; 55.726523, 13.167866 | Lund Ideontorget, 9021012081125000; 55.715618, 13.214379 |

GTFS SHA-256: 6a17c51b0924301eea8466e71d826bd7495199ce3a0de7f4f90d0293b4c13182.
OSM SHA-256: 47942e06ea6c96c8893933f71f448f7e1deac9d906c216a16c60a414db521b9d.
Verifierat område [12.95,55.60,13.30,55.80] täcker endast norra Malmö.
1501-filtreringen är oförändrad. Python 3.12.15, r5py 1.1.7, R5
7.5.1-r5py, Java 21.0.10; inga nya paket eller data hämtades.

Den aktiva tidtabellen har flera linjer i Malmö C–Värnhem-korridoren.
En kandidatkontroll med hållplatser inom 900 m raklinje hittade bland annat
3, 4 och 9. Detta var kandidatselektion; faktisk gångbudget verifierades
sedan av nätverksanalysen. Malmö C–Segevång övervägdes också (4 och 13),
men Värnhem gav fler linjer och faktiskt varierande valda resvägar.

Lomma station–Ideontorget prövades först: 25/60 nåbara minuter, alla med
139→spårvagn 1. Från Strandvägen blev 48/60 nåbara. Strandvägen–Sparta
gav 5/60. Dessa bytesfall gav flera hopp till ej nåbarhet inom 45 minuter,
så båda sidor kunde inte granskas som resor. De behålls som diagnosfall,
utan ändrad budget. Gunnesbo–Ideontorget valdes i stället: kortare
tåg/buss→buss/spårvagn-resor, 60/60 nåbara och alltid ett byte.

## Mått, valda linjer och upptäckta alternativ

| Fall | T50 | T90 | T99 | buffer_90 | buffer_99 | full_range | Täckning / ej nåbara |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Lomma–Lund | 36:17 | 39:17 | 42:17 | 3:00 | 6:00 | 10:00 | 100 % / 0 |
| Malmö C–Värnhem | 16:26 | 19:26 | 20:26 | 3:00 | 4:00 | 7:00 | 100 % / 0 |
| Gunnesbo–Ideontorget | 32:56 | 37:56 | 41:52 | 5:00 | 8:56 | 19:56 | 100 % / 0 |

Lomma väljer buss 139 i 60/60 minuter, noll byten. Malmö väljer buss 9
52/60 (86,67 %), buss 4 5/60 (8,33 %), buss 3 2/60 (3,33 %) och
buss 39→3 1/60 (1,67 %): 59 minuter med noll byten och en med ett byte.
Fyra olika route families väljs under timmen.

Gunnesbos valda kombinationer, alla med ett byte:

| Kombination | Trafikslag | Minuter | Andel |
| --- | --- | ---: | ---: |
| 4→1 | buss→spårvagn | 23 | 38,33 % |
| 817→6 | tåg→buss | 21 | 35,00 % |
| 824→1 | tåg→spårvagn | 11 | 18,33 % |
| 4→6 | buss→buss | 3 | 5,00 % |
| 3→1 | buss→spårvagn | 2 | 3,33 % |

Detaljminuterna gav 9 alternativa family-observationer för Lomma,
34 för Malmö och 35 för Gunnesbo, deduplicerade per minut. Totalt upptäcktes
7/13/19 families inklusive valda. Malmö har exempelvis upptäckta
alternativ med 150, 5→6 och 7→130 som inte väljs under någon minut;
andra alternativ använder samma linje med andra på-/avstigningshållplatser.
Detta ska hållas skilt från timmens valandelar. Dominant share=100 %
bevisar inte att reservvägar saknas, vilket Lommaresultatet visar.
R5:s suboptimalMinutes=5 och dominansregler begränsar listan: den är inte
uttömmande och alternativsandelar över timmen skattas inte från detaljminuterna.

## De nio granskade hoppen

Tider nedan anges före→efter. Slutankomst är efter gång och sista marginal.
Alla resor och kartsegment för båda sidor finns i respektive JSON/GeoJSON.

| Fall, startminuter | Hopp | Total restid | Gång | Väntan | Slutankomst |
| --- | --- | --- | --- | --- | --- |
| Lomma 07:35→07:36 | +10:00 | 32:17→42:17 | 10:06→10:06 | 1:19→9:27 | 08:07:17→08:18:17 |
| Lomma 07:05→07:06 | +7:00 | 32:17→39:17 | 10:06→10:06 | 1:19→8:19 | 07:37:17→07:45:17 |
| Lomma 07:20→07:21 | +7:00 | 32:17→39:17 | 10:06→10:06 | 1:19→8:19 | 07:52:17→08:00:17 |
| Malmö 07:26→07:27 | +7:00 | 13:26→20:26 | 3:19→3:19 | 1:07→8:07 | 07:39:26→07:47:26 |
| Malmö 07:56→07:57 | +7:00 | 13:26→20:26 | 3:19→3:19 | 1:07→8:07 | 08:09:26→08:17:26 |
| Malmö 07:11→07:12 | +6:36 | 13:26→20:02 | 3:19→7:34 | 1:07→2:30 | 07:24:26→07:32:02 |
| Gunnesbo 07:26→07:27 | +16:33 | 25:19→41:52 | 9:47→7:36 | 3:01→6:14 | 07:51:19→08:08:52 |
| Gunnesbo 07:47→07:48 | +13:23 | 21:56→35:19 | 8:02→9:47 | 2:36→13:01 | 08:08:56→08:23:19 |
| Gunnesbo 07:58→07:59 | +7:00 | 32:56→39:56 | 7:09→7:09 | 2:27→9:27 | 08:30:56→08:38:56 |

**Lomma:** gång till Strandvägen 5:49, sista gång 4:17, inga byten.
07:05 hinner buss 139 07:12:08→07:32; 07:06 blir tillåten boardingtid
07:12:49 och nästa val är 07:20:08→07:40. Motsvarande 07:20/07:21
ersätter 07:27:08→07:47 med 07:35:08→07:55. Ökad väntan 420 s
förklarar båda hoppen. Vid 07:35 hinner man 07:42:08→08:02; 07:36
missar den och väljer 07:51:16→08:13. Väntan +488 s och fordonstid
+112 s förklarar hela hoppet 600 s; en minut senare start ger elva
minuter senare slutankomst.

**Malmö:** buss 9 kräver 53 s första och 146 s sista gång. 07:26 hinner
07:28→07:36; 07:27 missar avgången efter 60-s-regeln och väljer
07:36→07:44. 07:56/07:57 ger motsvarande 07:58→08:06 respektive
08:06→08:14. Väntan ökar 420 s, övriga komponenter är lika.
07:11 hinner buss 9 07:13→07:21. 07:12 missar den och går 5:32 till
Anna Lindhs plats, tar buss 3 07:20:02→07:29, går sedan 2:02.
Gång +255 s, väntan +83 s och fordonstid +58 s summerar till 396 s.
Ingen av dessa sex valda detaljresor har byte.

**Gunnesbo 07:26/07:27:** tåg 817 07:28→07:32, bytesgång 5:53 på Lund C
till 07:37:53, buss 6 07:39→07:46:31 till Scheeleparken. Boardingmarginal
67 s är strikt större än 60 s. Vid 07:27 missas tåget med sex sekunder
enligt boardingregeln. Bäst blir buss 4 07:33:58→07:56:12 till
Universitetssjukhuset, buss 6 07:59:16→08:04:04 från samma hållplats:
184 s väntan och ingen bytesgång. Gång −131 s, väntan +193 s och
fordonstid +931 s ger +993 s. Båda resorna har ett byte.

**Gunnesbo 07:47/07:48:** tåg 824 07:51→07:55, bytesgång 3:49 på Lund C
till 07:58:49, spårvagn 1 08:00→08:06:18 (71 s boardingmarginal).
07:48 missar tåget med 35 s. Valet blir tåg 817 07:58→08:02,
bytesgång 5:53 och buss 6 08:11→08:18:31 (187 s marginal).
Gång +105 s, väntan +625 s och fordonstid +73 s ger +803 s, ett byte.

**Gunnesbo 07:58/07:59:** buss 4 08:02:58→08:19, bytesgång 1:43 på Lund C,
spårvagn 1 08:22→08:28:18 med 77 s marginal. 07:59 når första hållplatsen
08:02:48 och missar avgången eftersom boarding kräver ytterligare 60 s.
Nästa val är buss 4 08:10:58→08:27, spårvagn 1 08:30→08:36:18.
Väntan +420 s ger hela hoppet; gång, fordonstid och ett byte är oförändrade.

## Avvikelse och rättning i R5-adaptern

Första Malmötestet avvek vid 07:20, 07:21, 07:50 och 07:51. R5 använde
SkåneExpressen 8, route_id 9011012040800000, från Malmö C
9022012080000008 till Värnhem 9022012080110007. Trip-ID
121120000393532661 avgår 07:26 och 121120000393532677 avgår 07:56.
GTFS har **drop_off_type=1** vid Värnhem för båda: förbjuden avstigning.
Service_id 6 är aktiv genom calendar_dates för 2026-10-12.

R5:s detaljrouter lät ogiltiga korta resor dominera giltiga alternativ;
efterfiltrering gav tomt detaljresultat vid 07:20. Sweepens regler var
korrekta och inga förväntade tider skrevs om. `r5_adapter.py` filtrerar nu
pickup/dropoff före SuboptimalDominatingList.add: endast SCHEDULED och
COORDINATE_WITH_DRIVER tillåts. Original-GTFS och installerad JAR ändras inte.
Alla 60 råa R5-restider matchar därefter sweepen i varje slutligt fall.

TravelTimeMatrix är en separat, oförändrad router och endast diagnostik.
Dess sekund-/modelljämförelser matchar 60/60 för Lomma, 5/60 för Malmö
och 38/60 för Gunnesbo. Behörigheter, gång-/bytesmodell och annan pruning
kan ge skillnader; fullständig orsaksfördelning för matrisens alla
avvikelser är inte utredd. Den får inte ersätta de verifierade sweepkvantilerna.

## Kartkontroll och JVM

47 tester passerar. Validatorn kontrollerar varje alternativs tidskomponenter,
monotona klockslag och boarding >60 s efter ankomst inklusive bytesgång.
Varje GeoJSON-feature matchar exakt segmentets geometri, hållplats-ID,
linje, tider och komponenter. Filhash och giltig EPSG:4326 kontrolleras.
Lomma/Malmö/Gunnesbo använder 7/9/8 detaljanalyser och 56/141/199 features;
överlappande percentil-/hopproller återanvänds.

R5:s gatungeometri utelämnar ibland anslutningen från GTFS-punkten till
snappad gata. Lund C:s järnvägsplattform hade cirka 315 m sådan anslutning.
WALK-exporten inkluderar nu en **approximativ rak anslutning**, märkt med
geometry_source och geometry_connectors_m. Detta är inte en verifierad
fysisk väg genom stationen. R5:s gångtid och kvantiler ändras inte av
ritningen; osäkerheten måste synas vid karttolkning.

JVM-felet sker efter RESULT_WRITTEN_ATOMICALLY: r5py:s Java shutdown-hook
anropar Python shutil.rmtree medan GeoTools/HSQL fortfarande håller
EPSG.data öppen. Full Python-traceback visar WinError 32. Enbart r5py-import
gav lyckad städning; routing gav felet. Ett försök att stänga GeoTools/HSQL
uttryckligen frigjorde inte låset och ingår inte i slutkoden.

Åtgärden skjuter upp just WinError 32 i den aktuella worker-TEMP-katalogen
tills supervisorn inväntat processavslut. Målet måste efter resolve vara
en direkt r5py*-underkatalog till worktreens cache/tmp. Sedan utförs samma
städning efter att JVM-filhandtagen stängts. Originaltraceback bevaras i
separat stderr och worker.shutdown_stderr, med cleanup_deferred=true och
cleanup_after_exit[].removed=true. cleanup_success avser själva hooken.
Andra fel blir inte tyst lyckade. Ingen installerad programvara ändras.

Alla sex slutliga workers gav exit 0, exited=true, ingen PyExceptionProxy
och lyckad städning efter avslut. Två analyser per fall gav identiska
analysresultat/GeoJSON; ingen resultatpåverkan av avslutsfelet observerades.
JVM är inbäddad i workerprocessen och joblib använder trådar, inte nya
routingprocesser. PID och avslut kontrolleras; inga av dessa workers kvarstår.
HSQL:s interna låsordning vid hooken är inte ändrad; den säkra städningen
sker nu i rätt processfas. Äldre diagnoskörningars ignorerade loggar kvarstår.

## Reproduktion

```powershell
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/validate_phase2c.py
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B -m unittest discover -s tests -v
```

`--case lomma_lund`, `malmo_varnhem` eller `gunnesbo_ideon` avgränsar
validatorn. JSON/GeoJSON och process-/valideringsloggar finns under
outputs/phase2c_CASE_1/2.* och är Git-ignorerade. Input-/kod-/JAR-hashar,
versioner och frysta parametrar ingår i varje resultats metadata.
Alla tre fall klarar två körningar med identiska metadata, minutobservationer,
mått, hopp, detaljresor, families, alternativ, verifieringar och GeoJSON-bytes.
Endast timing, worker (PID/logg/tid/temporärkatalog) och output-basnamnet i
geojson_path undantas. Nätverket byggs en gång per analysprocess.
