# Lokal inventering inför RobustPendling MVP

Inventerad 2026-10-11, Europe/Stockholm. Rapporten avser lokalt åtkomliga
resurser och är inte en fullständig inventering av alla filer på datorn.
Ingen installation, nedladdning, routingkörning eller extrahering genomfördes.
Endast denna rapport skapades i worktreen.

## Slutsats

Det finns användbara Python-/Java-installationer, ett verifierat lokalt
OSM-XML-utdrag och ett äldre designunderlag för en Lomma R0-pilot. En
Skånetrafiken-GTFS, exekverbar Pendlingindex-kod, R5-jar och installerat
r5py/JPype har däremot inte hittats i sökområdena. Datorn är därför inte
verifierat redo för ett minimalt gång + buss/tåg-test med tidtabellsbaserad
T90. Detta betyder inte att resurserna saknas överallt på datorn.

## Arbetsplats, diskar och sökomfattning

- Arbetskatalog: `C:\Users\bengt\.codex\worktrees\a492\RobustPendling`.
  Branch vid inventering: `codex/mvp`; HEAD före rapporten: `c5d03f0`.
  Git-status var ren före arbetet.
- `C:\`: tillgänglig filsystemsvolym; cirka 584 GB använt och 438 GB ledigt
  enligt Get-PSDrive (decimala GB; ögonblicksvärden).
- `D:\`: rapporterad enhet men roten kunde inte listas eftersom sökvägen
  inte fanns. Inget innehåll verifierat.
- `G:\`: Google Drive-monterad katalog med `G:\My Drive` och
  `G:\Shared drives`. Sandboxens åtkomstfel löstes med godkänd skrivskyddad
  listning. Endast katalogmetadata lästes; inga filer öppnades.
  `G:\My Drive\ChatGPT` och `G:\My Drive\test` saknade underkataloger.
  Inget tydligt transitprojekt identifierades på de listade nivåerna.
- PowerShell-enheten Temp är en katalog på C:, inte en ytterligare disk.

Först listades C:-roten och användarkatalogen. Namnsökning med `rg --files
--hidden` gjordes därefter i följande sannolika områden:

- `C:\Users\bengt\Documents`
- `C:\Users\bengt\Downloads`
- `C:\Users\bengt\OneDrive`
- `C:\Users\bengt\OLD COMPUTER FILES`
- `C:\files Old Computer`
- `C:\Users\bengt\phy-files`
- `C:\Users\bengt\spectral`

Dessa gav 104 895 filnamn efter avgränsningar. Sökningen utvidgades till
projekten direkt under C: med namn som börjar på Aker, ValAtlas och Robust,
samt riktat till `C:\Users\bengt\.codex\worktrees`, Python-installationer,
`C:\Users\bengt\.cache` och `C:\Users\bengt\AppData\Local\pip`.
Innehållssökning gjordes i lokala `.py`, `.ps1`, `.java` och `.ipynb`-filer
efter T90, GTFS, r5py, Conveyal, TravelTimeMatrix och routingrelaterade ord.
En för lång kommandorad ersattes med sökning per rot.

Windows genomsöktes inte. Program Files och AppData listades på relevanta
nivåer; endast identifierade Python-/Java-kataloger undersöktes vidare.
Git-metadata, node_modules, bilder, MATLAB-installationsmaterial och
Hugging Face-modellcache undantogs från relevanta sökningar. Virtuella
miljöer söktes separat på projektrötternas första nivå och den funna miljön
undersöktes vidare. Det är inte ett bevis för att inga djupare miljöer finns.
OneDrive-filer lästes inte: namn, storlek och attribut inventerades utan
hydrering. Stora orelaterade Google Drive-områden genomsöktes inte rekursivt.

## Relevanta dokument och data

Storlekar anges i byte. Ändringstider anges i lokal tid; de visar inte
nödvändigtvis datakällans versionsdatum. Arkiv lästes direkt utan extrahering.

| Fullständig sökväg | Typ, storlek, ändrad | Innehåll och verifieringsnivå | Rekommendation |
| --- | --- | --- | --- |
| `C:\Users\bengt\Downloads\Steg A – bygg ut befintligt Pendlingindex-projekt till verifierad Lomma R0-pilot.md` | Markdown, 12 601, 2026-08-09 09:41:44 | Texten verifierad. Beskriver fetch_data.py, clean_gtfs.py, compute_matrix.py, r5py, Trafiklab Regional Skåne, Geofabrik och R0-profiler. Själva projektets existens och funktion är endast påståenden i dokumentet. | Återanvänd som designreferens; undersök projektets verkliga plats vidare. |
| `C:\Users\bengt\Downloads\Lomma R0-pilot.docx` | Word, 17 909, 2026-08-09 09:41:56 | Metadata verifierad; innehåll inte läst. Sannolikt relaterat pilotunderlag. | Undersök vidare vid behov; Markdown-underlaget är redan läst. |
| `C:\Users\bengt\Downloads\export.osm` | OSM XML, 52 845 570, 2026-08-13 10:09:56 | XML verifierad: Overpass-generator, ODbL-notis, osm_base 2026-08-13T08:03:00Z; 415 402 noder och 77 158 ways. Nodernas lat/lon-omslutning: 55.5760295–55.8544178, 12.916027–13.2315166. Innehåller bland annat 5 033 footway- och 3 568 path-ways. Detta är ett lokalt utdrag, inte hela Skåne. | Återanvänd som kandidat för ett litet gångtest; kontrollera topologi, A/B-täckning och motorns XML-/PBF-krav före routing. |
| `C:\Users\bengt\Downloads\Lomma_V5_1_resultat_och_validering.zip` | ZIP, 1 883 601, 2026-08-13 20:16:32 | Arkivlista och fyra JSON/GeoJSON-strukturer verifierade. Skyddsrumspilot med kommungräns, befolkningspunkter, manifest och resultat; inte GTFS. | Undersök vidare för geografiska hjälpresurser. |
| `C:\Users\bengt\Downloads\lomma_skyddsrum_V4_V5_hela_kitet.zip` | ZIP, 1 661 449, 2026-08-13 16:28:00 | Arkivlista verifierad: README, skyddsrumsresultat, CSV och kartor; ingen transitmotor identifierad. | Ignorera för första transitkörningen; möjlig senare kartreferens. |
| `C:\Users\bengt\Downloads\Lomma_skyddskapacitet_demo_V5_1.zip` | ZIP, 1 781 781, 2026-08-13 20:16:27 | Arkivlista verifierad: rapport, två HTML-kartor och läs-mig-fil. | Ignorera för transitmotorn. |
| `C:\Users\bengt\OneDrive\BL innovation AB\MSB skyddsrum\MVP\LOMMA.osm` | OSM, 52 845 570, 2026-08-13 10:09:56 | Endast metadata. Samma storlek/tid som export.osm; byteidentitet inte verifierad. RecallOnDataAccess-attribut: innehåll lästes inte. | Använd den verifierade lokala Downloads-kandidaten först. |
| `C:\Users\bengt\OneDrive\BL innovation AB\MSB skyddsrum\MVP\ESLÖV.osm` | OSM, 14 363 648, 2026-08-13 20:57:18 | Endast metadata; geografiskt innehåll antaget från namnet, inte verifierat. RecallOnDataAccess. | Undersök vidare när lokalt tillgänglig; inte läst i detta uppdrag. |
| `C:\Users\bengt\OneDrive\BL innovation AB\Diskussioner Jacob S\lomma_platsindex_R0_2026-08-07.csv` | CSV, 14 377, 2026-08-07 18:38:34 | Endast metadata, RecallOnDataAccess. Namnet antyder R0-resultat; inga värden eller proveniens verifierade. | Undersök vidare som möjlig baseline. |
| `C:\Users\bengt\OneDrive\BL innovation AB\Diskussioner Jacob S\lomma_platsindex_R0_2026-08-07_ChatGPT.xlsx` | XLSX, 30 074, 2026-08-07 19:25:04 | Endast metadata, RecallOnDataAccess. Möjlig motsvarande resultattabell; inte verifierad. | Undersök vidare som möjlig baseline. |
| `C:\Users\bengt\OneDrive\BL innovation AB\MSB skyddsrum\MVP\requirements.txt` | Paketlista, 106, 2026-08-13 09:33:33 | Endast metadata; innehållet inte läst. | Undersök vidare för skyddsrumspiloten, inte anta transitberoenden. |
| `C:\AkerSyncRepo\requirements.txt` | Paketlista, 104, 2026-08-24 09:16:09 | Innehåll verifierat: numpy, pandas >=2.3,<3, pyarrow, scipy, geopandas, pyogrio, rasterio, shapely, pyproj, Pillow och whitebox. Inga r5py-/JPype-beroenden. | Återanvänd som GIS-referens, inte som färdig routingmiljö. |

I det verifierade resultatarkivet är
`C:\Users\bengt\Downloads\Lomma_V5_1_resultat_och_validering.zip` värdfil för:

- `V4/lomma_boundary.geojson`: 15 568 byte, en Polygon med name och scb_code.
  Strukturen är verifierad; gränsens precision, licens och aktualitet behöver
  kontrolleras innan återanvändning.
- `V4/lomma_population_origins.geojson`: 3 231 075 byte, 7 378 Point-features
  med bland annat origin_id, population, rutid_scb och building_type.
  Ingen verifierad åldersuppdelning 20–64 finns bland egenskapsnamnen.
  Återanvänd inte population direkt som MVP:ns åldersmått.
- `V4/cache_manifest.json`: 1 159 byte, nycklar för osm_snapshot,
  source_sha256, walk_kmh och hash. Struktur verifierad; hashvärdenas
  koppling till nu tillgängliga filer är inte kontrollerad.
- `V4/summary.json`: 1 720 byte, nycklar för SCB-referenstid,
  befolkningskalibrering och gångnät. Detta är skyddsrumsanalysens metadata,
  inte verifierade transitresultat.

## Kod, arkiv, beroenden och cache

351 ZIP-arkiv under Downloads (MATLAB-material undantaget) öppnades endast
för att läsa arkivlistor. Sökning efter GTFS, r5py, Conveyal, PBF,
fetch_data.py, clean_gtfs.py, compute_matrix.py, stop_times.txt och trips.txt
gav inga träffar och inga arkivläsfel. Ingen GTFS-ZIP eller Skåne-/södra
Sverige-PBF hittades i övriga namnsökta områden. ZIP-innehåll utanför
Downloads inventerades inte generellt.

Ingen faktisk transitkod eller R5-/Conveyal-jar identifierades. Generiska
T90-träffar i ÅkerSync-kod var bland annat RT90-koordinatsystem och en
variabel som slutar på strict90, inte kollektivtrafikpercentiler. Gamla
Robust-dokument avsåg radioteknik/värmepumpar; de ignoreras. Java-filen
`C:\Users\bengt\AppData\Local\Programs\Eclipse Adoptium\jdk-25.0.2.10-hotspot\lib\jrt-fs.jar`
är JDK-material, inte R5.

Flera ÅkerSync-projekt har requirements.txt; stickprovet ovan visar ett
GIS-spår. Ingen transitrelaterad pyproject.toml eller environment.yml
identifierades. Paketens egna test-/metadatafiler är inte projektmiljöer.
Ingen R5-cache identifierades i `.cache`, pip-katalogen eller undersökta
Python-/projektkataloger. Namnsökning kan missa anonymt namngiven cache.

## Programvara och virtuella miljöer

Versionerna kontrollerades genom lokala versionskommandon och
importlib.metadata, utan paketinstallation eller import av routingmotorn.
Python kördes med `-B` för att undvika bytekodsskrivning. Paketmetadata visar
installation, inte att alla binära importer eller routing fungerar.

| Fullständig sökväg | Verifierat fynd | Rekommendation |
| --- | --- | --- |
| `C:\Users\bengt\AppData\Local\Python\pythoncore-3.14-64\python.exe` | Python 3.14.4; 106 328 byte, ändrad 2026-04-18 14:47:54. geopandas 1.1.4, shapely 2.1.2, pyproj 3.8.0, pyogrio 0.13.0, pandas 3.0.2, numpy 2.4.4. | Återanvänd för lokala data-/metadataförtester; fastställ routingkompatibilitet separat. |
| `C:\Users\bengt\AppData\Local\Programs\Python\Python314\python.exe` | Python 3.14.8; 106 208 byte, ändrad 2026-09-30 19:16:36. geopandas 1.1.4, shapely 2.1.2, pyproj 3.7.2, pyogrio 0.13.0, rasterio 1.5.1, pandas 2.3.3, numpy 2.5.2. | GIS-kandidat; undersök kompatibilitet innan en ny isolerad projektmiljö byggs. |
| `C:\Users\bengt\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` | Python 3.12.14; 107 312 byte, ändrad 2026-10-10 07:18:05. pandas 3.0.1 och numpy 2.3.5; inget geopandas. | Återanvänd för enkla verifieringar; apphanterad runtime bör inte behandlas som låst projektmiljö. |
| `C:\AkerSync-AkerAccess\.venv\akerpass_u5` | Virtuell miljö, katalog ändrad 2026-10-04 18:46:49. pyvenv.cfg anger 3.14.7 och Python314 som bas; Scripts/python.exe kör faktiskt 3.14.8. Ingen av de kontrollerade GIS-/routingpaketen finns i miljön. | Ignorera som färdig transitmiljö. |
| `C:\Program Files\Eclipse Adoptium\jdk-25.0.4.101-hotspot\bin\java.exe` | Fungerande Temurin/OpenJDK 25.0.4.1; installationskatalog ändrad 2026-09-28. | Återanvänd kandidat; R5-versionens Java-krav måste först verifieras. |
| `C:\Program Files\Eclipse Adoptium\jdk-25.0.4.7-hotspot\bin\java.exe` | Fungerande OpenJDK 25.0.4; installationskatalog ändrad 2026-08-05. | Alternativ Java-kandidat. |
| `C:\Users\bengt\AppData\Local\Programs\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin\java.exe` | Fungerande OpenJDK 25.0.2. | Alternativ Java-kandidat. |
| `C:\Program Files\Git\cmd\git.exe` | Git 2.56.0.windows.1 verifierad. | Återanvänd för versionshantering. |

r5py, JPype1, Python-paketet gdal och folium saknades i samtliga fyra
kontrollerade Python-miljöer. osmnx saknades i de tre basinstallationerna.
Python314-installationerna gav varningen "Failed to find real location"
men slutförde metadata-/XML-kontroller. WindowsApps-aliasen för Python
misslyckades i miljöskriptet; använd explicit verifierad exekverbarsökväg.

`scripts/check_environment.ps1` kördes och slutfördes med exitkod 0:
Python, Java och Git tillgängliga; GDAL saknas i PATH. Ingen fristående
GDAL-, OSGeo4W-, QGIS- eller Conda-installation identifierades via riktade
katalognamn och uninstall-registernycklar. Det utesluter inte bibliotek
bundlade med pyogrio/rasterio eller en installation på annan plats.
Registerfrågan gav inga matchande poster i den tillgängliga vyn och är
därför inte en uttömmande installationslista.

## Vad som saknas för ett minimalt A→B-test

1. **Verifierad Skånetrafiken-tidtabell:** lokal GTFS med agency, stops,
   routes, trips, stop_times och calendar/calendar_dates. Kontrollera
   buss/tåg, datumtäckning, kalenderundantag, källa/version och SHA-256.
2. **Verifierad routingmotor och körbar kod:** lokalisera Pendlingindex
   eller bygg en liten reproducerbar implementation. Lås r5py, JPype,
   R5-jar, Python och Java till en kombination som faktiskt har testats.
   Ingen sådan kombination har verifierats här.
3. **Gångnät i motorns format:** export.osm är en verklig kandidat men
   XML-stöd/konvertering, topologi och täckning måste kontrolleras. För
   exempelvis en resa till Lund får detta utdrags täckning inte antas räcka.
   Ingen verifierad Skåne-PBF hittades; konvertering utfördes inte.
4. **Ett explicit litet test:** ange koordinater för A/B inom verifierad
   täckning, ett GTFS-täckt datum, Europe/Stockholm, starttidsfönster,
   samplingsintervall, gånghastighet, bytesregler och maximala restider.
   Dokumentera buss-/tågval och anropsstyrd trafik. Visa en full reskedja
   inklusive gång, väntan och byten för representativa starttider.
5. **T90-kontrakt och verifiering:** beräkna total restid från varje
   efterfrågad starttid; dokumentera percentilmetod och observationer.
   Följ MVP_SPEC:s regel för omöjliga resor (oändlig restid i fördelningen,
   ej uppnåelig percentil och redovisad andel). Kontrollera T50 ≤ T90 ≤ T99,
   T90–T50 och starttid ±15 minuter mot ett handkontrollerat litet fall.
6. **Reproducerbar körning:** inputhashar, källor/licenser, datum, versioner,
   parametrar, starttidsobservationer och ett exakt lokalt körkommando.
   Det finns ännu inget verifierat routingkommando att ange.

Fristående GDAL är inte visat som nödvändigt för själva A→B-testet; avgör
behovet utifrån vald datakonvertering. Befolkningsdata behövs inte för A→B,
men arbetsplatsläget kräver senare ett verifierat 20–64-årsunderlag,
unik räkning, passstart/passlut, möjlig hemresa och områden 15/30/45/60.

## Kontroll mot MVP_SPEC.md och AGENTS.md

Rapporten skiljer tidtabellsbaserad R0 från historiska förseningar och
inställda turer. Det äldre pilotdokumentet är en referens, inte nya
projektinstruktioner. Dess NA/unreachable-formulering måste förenas med
MVP_SPEC:s uttryckliga percentilregel före kodåteranvändning; omöjliga
starttider får inte tyst tas bort. Dess profiler med sammanvägda riktningar
ersätter inte arbetsplatslägets separata prövning av till- och hemresa.

Ingen full Skånekörning gjordes. Rekommenderad ordning är dataverifiering,
ett litet A→B-fall och först därefter fler scenarier och geografisk skala.
Inga hemligheter eller rådata läggs i Git. Befintlig .gitignore skyddar
`.env`, virtuella miljöer, data/, outputs/ och logs/.

Inventeringen använde Get-PSDrive, Get-ChildItem/Get-Item, Get-Command,
rg-filnamns-/innehållssökning, Python zipfile/XML-iterparse och
importlib.metadata samt projektets miljöskript. Endast installerade
lokala verktyg användes. Läsningar av main-checkoutens struktur och
projektfiler var skrivskyddade; inga filer där ändrades. Rapporten är
avsiktligt en ögonblicksbild och ger inga löften om nuvarande externa
datakällor eller om paketkompatibilitet som inte testats.
