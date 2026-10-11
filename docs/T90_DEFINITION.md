# Phase 2A: T90_schedule

Detta dokument bevarar Phase 2A:s metod och första verifiering. Aktuellt
Phase 2B-anropskontrakt, koordinater, nätverksgräns, strukturella mått,
representativa resor och GeoJSON beskrivs i
[ANALYSIS_CONTRACT.md](ANALYSIS_CONTRACT.md). Phase 2B tillåter även rent
gångalternativ inom samma gångbudget och andra anropstidszoner; det ändrar
inte Lomma–Lund-resultatet. Nedanstående Phase 2A-experimenthash och
testantal är historiska, inte den nuvarande kodens identitet.

## Vad måtten betyder

**T90_schedule** är 90:e percentilen av optimala, tidtabellsenliga
dörr-till-dörr-restider över ett explicit urval av startminuter. Det
beskriver publicerad statisk GTFS tillsammans med ett bestämt gångnät
och frysta routingregler. Variation kommer bland annat från väntetid,
turtäthet och olika tidtabellsenliga reskedjor. Måttet är inte en
sannolikhet för att komma fram i tid i verklig drift.

**T90_operational** är ett framtida separat mått där observerade
förseningar, inställda turer och missade byten påverkar restidsfördelningen.
Det kräver historiska observationer och en definierad metod för dessa
händelser och datatäckning. Ingen sådan information används i Phase 2A.

**route_coverage** = startminuter med en användbar resa / samtliga
startminuter. En användbar resa måste klara de angivna gång-, restids-
och bytesgränserna i det tillgängliga nätet. Täckningen avser detta
A–B-fönster; den mäter inte driftstabilitet eller geografisk GTFS-täckning.
100 % täckning kan samexistera med lång T90_schedule.

Metoden konkretiserar R0:s urval av starttider i MVP_SPEC.md. Alla
resultat måste märkas schedule/R0 och behålla täckning och begränsningar.

## Observationer, optimering och percentiler

Första testet använder måndag **2026-10-12**, **Europe/Stockholm**,
inklusive fönstret **07:00:00–07:59:59**. Observationerna startar exakt
07:00:00, 07:01:00, …, 07:59:00: **60 lika viktade observationer**.
08:00 ingår inte. Start och ankomst lagras med UTC-offset +02:00.
Sommar-/vintertidsambiguiteter och obefintliga lokala starttider avvisas.

En observation är minsta möjliga ankomsttid minus den begärda
startminutens tid. Att vänta innan man börjar gå ingår också i restiden.
Optimeringen avser gång + minst en kollektivtrafikdel, inom den frysta
modellens begränsningar; ett rent gångalternativ används inte här.
Station-area-koordinater väljs ur original-GTFS genom exakt namnmatch,
location_type 1 före plattform, sedan lägsta stop_id:

| Punkt | stop_id | Latitud | Longitud |
| --- | --- | ---: | ---: |
| Lomma station | 9021012062000000 | 55.674346 | 13.074675 |
| Lund C | 9021012081216000 | 55.706384 | 13.187015 |

Frysta värden från smoke-testet:

- Gånghastighet **3,6 km/h**; maximalt **15 min sammanlagd gång**.
- Maximalt **45 min dörr-till-dörr-restid**, inklusive sista gångmarginalen.
- Maximalt **två kollektivtrafikdelar**, alltså högst ett byte.
- R5:s boarding slack **60 s**, med dess strikta regel: avgång måste
  ligga **senare än** ankomst till hållplatsen + 60 s.
- r5py:s extra **60 s före sista gången** behålls separat, liksom i
  smoke-testets korrigerade klockspann. Marginalen är en modellregel,
  inte en uppmätt försening. Boarding slack ingår redan i väntetiden.
- Tillgång/avslutande gång är R5:s kortaste gatunätsvägar; bytesgång
  använder nätverkets förberäknade streetTransfers och samma stop med 0 s.
- GTFS pickup/dropoff 0 och 3 tillåts; 1 och 2 tillåts inte.
  Typ 3 innebär koordinering med föraren, typ 2 telefonbokning hos operatören,
  enligt [GTFS-referensen](https://gtfs.org/documentation/schedule/reference/#stop_timestxt).
- Vid lika restid väljs lägst gångtid, sedan lexikografiska
  trip-/påstignings-/avstignings-ID:n. Inga kostnads- eller fare-mått optimeras.
- Frekvensbaserade GTFS-turer avvisas om frequencies.txt har datarader;
  deras tidsmodell behöver definieras separat. Saknade/icke-monotona
  stopptider ger fel, inte påhittad interpolering eller borttappade minuter.

schedule_sweep.py prövar alla tillåtna på-/avstigningspositioner på
aktiva tidtabellsturer, även senare fordon som kommer fram tidigare,
och alla tillåtna kombinationer med en eller två fordonsdelar. Gång,
tid, pickup/dropoff och slack kontrolleras för varje komplett kandidat.
Detta ger optimum inom det givna gång-/bytesnätet och gränserna. Det
garanterar inte ett globalt optimum över vägar utanför OSM-utdraget.
Tidtabellsturer kan fortsätta utanför gatunätet; gånganslutningar måste
finnas i nätet. Kalendern och calendar_dates avgör datumets aktiva turer.

Percentiler använder **nearest rank**, utan interpolering:
sortera N observationer och välj enbaserad position ceil(p × N / 100).
För N=60 används position **30, 54, 60** för T50, T90, T99.
T50 är därmed en observationsbaserad percentil, inte medelvärdet av de
två mittersta värdena. Beräkningen behåller sekundprecision.

En startminut utan användbar resa får värdet +∞ för statistiken. I JSON
är dess duration_seconds null och status UNREACHABLE. Antalet behålls i
N och route_coverage. En percentil som väljer +∞ returnerar strängen
**UNREACHABLE**. Maximum och medel över hela urvalet blir också
UNREACHABLE om någon observation saknas; reachable_mean redovisas
separat och ersätter aldrig robusthetsmåttet. Exempel: med 54/60 nåbara
minuter kan T90 vara ändlig men T99 är UNREACHABLE; med 53/60 nåbara
är även T90 UNREACHABLE. Alla observationer finns kvar i resultatet.

## Experimentell kontroll av R5

Miljö: Python 3.12.15, r5py **1.1.7**, R5 **7.5.1-r5py**, Java **21.0.10**,
JVM-heapgräns **4 GiB**. Detaljrouterns suboptimalMinutes är **5**.
JAR-hashen kontrolleras innan den privata adaptern används. Adaptern
är bunden till dessa versioner och avbryter vid avvikelse.

Tre experiment skiljer beräkningsvägarna åt:

1. **Explicit sweep:** de 60 ovan angivna startminuterna skickas till
   den uttömmande tidtabellssökningen. Resultatets 60 rader används för
   de publicerade percentilerna, inte R5:s färdiga percentilsvar.
2. **Råa detaljroutertillstånd:** R5:s privata starttidsväljare körs med
   ett tvåsekundersintervall kring varje begärd minut, monteCarloDraws=1
   och verifierad intern seed 0. Den väljer då exakt önskad sekund.
   Både väljaren och finalStatesByDepartureTime kontrolleras experimentellt
   för varje minut. Samtliga slutalternativ granskas; r5py:s sammanslagna
   detaljtabell används inte. **60/60** minsta godkända restider överensstämmer
   exakt med den explicita sökningen. Detta är en teknisk adapter för
   exakta tider, inte en simulerad störningsfördelning.
3. **Normala R5-vägar:** detaljrouterns vanliga timfönster med 60 interna
   draws gav 60 startsekunder, men endast **en** matchade minutgriden.
   Första startsekunderna efter midnatt var 25255, 25322, 25406, 25442,
   motsvarande 07:00:55, 07:02:02, 07:03:26, 07:04:02. Ett normalt
   DetailedItineraries-fönster är alltså inte denna minutvisa sweep.
   TravelTimeMatrix använder en annan router; dess logg verifierar
   **60 iterationer, en per minut, frequencies=false**. En timmatris ger
   T50/T90/T99 = **35/38/41 hela minuter**. Dessutom kördes 60 separata
   enminutsmatriser. **60/60** matchar floor((explicit restid − 60 s)/60).

De två skillnaderna ska inte blandas ihop. Matrisens nearest-rank-definition
överensstämmer med vår, enligt den versionsbundna
[TravelTimeReducer-koden](https://github.com/r5py/r5/blob/v7.5.1-r5py/src/main/java/com/conveyal/r5/analyst/TravelTimeReducer.java).
Matrisens heltalsminuter och avsaknad av r5py:s sista 60-s-marginal förklarar
det observerade resultatgapet i detta test. Detaljrouterns vanliga
[starttidsurval](https://github.com/r5py/r5/blob/v7.5.1-r5py/src/main/java/com/conveyal/r5/profile/McRaptorSuboptimalPathProfileRouter.java)
ger dessutom andra starttider. Vi använder därför inte dess timfönster
som ersättning för explicit sweep.

Enminutsmatriserna ger r5py:s varning om fönster kortare än fem minuter,
vilken sparas i JSON. FastRaptorWorker slutförde dem korrekt. Denna
kontroll använder inte den detaljrouterkombination med nollsteg som
tidigare gav OutOfMemoryError. Matriskörningen loggar också **81
overtaking-varningar**, inklusive linje 139. Alla meddelanden finns i
den ignorerade workerloggen. Den explicita sökningen prövar samtliga
turer och förutsätter inte att första fordonet är snabbast.

## Data, reproduktion och processgräns

Gemensamma OSM-/GTFS-sökvägar och kontroller finns i LOMMA_LUND_SMOKE.md.
Original-GTFS SHA-256 är
6a17c51b0924301eea8466e71d826bd7495199ce3a0de7f4f90d0293b4c13182.
OSM-utdragets SHA-256 är
47942e06ea6c96c8893933f71f448f7e1deac9d906c216a16c60a414db521b9d.
Filhasharna kontrolleras både före och efter analysen för oförändrad indata.

R5 stöder inte route_type **1501**: den statiska valideraren ger
RangeError för värden över 1500, och detaljroutern avvisar senare typen
även med allow_errors=True. En separat deterministisk härledning
tar därför bort **340 routes, 1 440 trips, 6 134 stop_times och 3 transfers**
som refererar till dem. Original-GTFS skrivs aldrig till. Härledd SHA-256:
0a43ea916ed78a0d26a71e471483a0ee07bf1131fd0e7504be03ac7f6a1d6a9f.
Täckningen och percentilerna gäller den återstående trafiken, inte
förbeställningstrafiken. Inga nya data eller paket behövs för analysen.

Kör från worktreens projektrot med befintlig miljö och lokal paths.toml:

```powershell
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts\analyze_t90.py --date 2026-10-12 --start 07:00:00 --end 07:59:59 --timezone Europe/Stockholm
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B -m unittest discover -s tests -v
```

CLI-supervisorn importerar inte r5py. En separat Pythonprocess äger
JVM:n och skriver resultat atomiskt innan normalt processavslut.
Supervisorn väntar, kontrollerar exitkod, sparar shutdown-diagnostik
och publicerar slutresultatet atomiskt. Ett misslyckat jobb kan inte
återanvända ett gammalt workerresultat. Ett tidigare slutresultat behålls
om det nya jobbet inte lyckas; ett resultat med icke-noll exit är DIAGNOSTIC.

Det kvarvarande **org.jpype.PyExceptionProxy** vid JVM-avslut finns
fortfarande i workerloggen. Felet döljs inte: slutresultatet anger
jpype_shutdown_error=true och exit_code=0. Processisoleringen hindrar
att felet påverkar CLI-supervisorn, men rotorsaken är inte löst.

Genererade, Git-ignorerade artefakter:

- outputs/t90_schedule_lomma_lund.json: samtliga observationer,
  indata-/kodhashar, versioner, datum/tidszon, frysta parametrar,
  percentiler, täckning, komponenter, kombinationer och jämförelser.
- outputs/t90_schedule_lomma_lund.worker.json: atomiskt workerresultat.
- outputs/t90_schedule_lomma_lund.worker.log: kompletta R5-/Python-meddelanden.

experiment_sha256 beräknas från kanoniskt sorterad metadata. Körtider,
processdiagnostik och lokala loggsökvägar påverkar inte dess värde.
Två körningar med oförändrad kod gav identiska metadata, samtliga
60 observationer, statistik, komponenter, kombinationer och verifieringar.
Experimenthash: f99e71155d77452b2f6eb12533bfdcef5d94917dadc5bc23e3a6973d2d25eff2.
**31 tester passerade**, inklusive percentilpositioner, ej nåbara minuter,
tidszon/fönstergränser, deterministisk metadata, snabbare senare tur,
bytesgång, gånggräns, strikt boarding slack och pickup/dropoff 3.

## Första resultatet

| Mått | Tid |
| --- | --- |
| T50_schedule | **36 min 17 s** (2177 s) |
| T90_schedule | **39 min 17 s** (2357 s) |
| T99_schedule | **42 min 17 s** (2537 s) |
| Minimum | **32 min 17 s** |
| Maximum | **42 min 17 s** |
| Medel | **36 min 23 s** |
| T90–T50 | **3 min** |

route_coverage **60/60 = 100 %**; **0** minuter utan användbar resa.
Gång **10 min 06 s** i samtliga valda resor. Väntan **1 min 19 s–9 min 27 s**,
medel **4 min 40,2 s**; sista gångmarginalen **1 min** redovisas separat.
Alla **60/60 (100 %)** använder en bussdel med **linje 139**, route_type
**700**, **0 byten**. Andelar finns både över alla och över nåbara minuter.

Handkontroll: exakt start 07:00 ger buss 139 från Lomma Strandvägen
07:12:08 till Lund C 07:32:00 och målpunktsankomst **07:37:17**, total
**37 min 17 s**. Start 07:59 ger målpunktsankomst **08:33:17**, total
**34 min 17 s**. Resorna är förenliga med det tidigare smoke-testet.
Detta bevisar inte observerad punktlighet, framtida tidtabeller eller
full geografisk täckning. Kväll, helg, omvänd resa och ±15 min återstår.
