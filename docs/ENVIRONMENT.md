# Phase 0: Windows-miljö och indata

Python 3.12 i en separat projektmiljö är målplattformen. environment.yml
anger conda-forge, r5py 1.1.7 och geospatiala versionsserier samt miljöegen
OpenJDK 21. System-Python och system-Java ändras inte. Detta är ett
versionsstyrt kandidatunderlag, inte en fullständig transitiv låsfil:
Windows-solve, binära importer och R5-start måste verifieras innan routing.
Conda, mamba och micromamba hittades inte vid Phase 0-kontrollen av PATH,
C:-roten, användarroten och AppData/Local. Ingen installation gjordes.

Version och metod kontrollerades 2026-10-11 mot
[conda-forge-paketet](https://anaconda.org/conda-forge/r5py) och
[r5py:s installationsguide](https://r5py.readthedocs.io/latest/user-guide/installation/installation.html).
Den senare rekommenderar separat conda-miljö på Windows och beskriver JDK
21 eller senare. Följande installationsblock ska köras först när conda
finns tillgängligt; det kördes inte i denna uppgift. Prefixet ligger i
worktreen och ändrar inte globala miljöer. Exporten låser även beroenden
och builds för win-64; spara den granskade låsfilen innan benchmark.

```powershell
conda env create --prefix .\.venv\transit --file environment.yml
conda activate .\.venv\transit
conda list --explicit | Set-Content -Encoding utf8 environment.win-64.lock.txt
python -c "import r5py; print(r5py.__version__)"
java -version
```

Kopiera exemplen. Redigera .env lokalt med en GTFS Regional-nyckel i
TRAFIKLAB_API_KEY; skriv inte nyckeln i terminalkommandon. En redan satt
miljövariabel med samma namn har företräde. .env-parsern accepterar en
enkel KEY=value-rad med valfria citattecken; inga substitutioner utförs.
Konfigurationen återger exakt de lokala Downloads-sökvägarna i
LOCAL_INVENTORY.md. Relativa sökvägar utgår från projektroten, inte cwd.
Lokala hemligheter, paths.toml, cache, miljö och rådata är Git-ignorerade.

```powershell
Copy-Item .env.example .env
Copy-Item config\paths.example.toml config\paths.toml
python -B -m unittest discover -s tests -v
python -B scripts\inspect_inputs.py --config config\paths.toml
```

Hämtaren använder [Trafiklabs officiella GTFS Regional-adress](https://www.trafiklab.se/api/gtfs-datasets/gtfs-regional/)
med operator skane. Nyckeln finns endast i HTTPS-anropet, aldrig i
metadata eller utskrifter. Omdirigeringar blockeras och råa nätverksfel
skrivs aldrig ut. Ingen verklig feed hämtades under Phase 0.

Hämtaren skickar Accept-Encoding: gzip enligt Trafiklabs OpenAPI.
Content-Encoding: gzip avkodas strömmande innan ZIP-validering och lagring;
okomprimerade svar stöds också. Storlek och SHA-256 avser den lagrade ZIP-filen.
Vid HTTP-fel visas endast status och strikt tillåtna, säkra header-värden;
URL, reason och response body utelämnas eftersom de kan innehålla nyckeln.
GZIP-kravet finns i [GTFS Regional Static OpenAPI](https://github.com/trafiklab/openApi-docs/blob/master/gtfsRegionalStatic.yaml).

inspect_inputs rapporterar också feed_version, kalenderns datumomslutning,
antal stops/routes/trips/stop_times och route_type-koder. Trafikprover väljs
för måndag, lördag och söndag inom kalenderomslutningen, med calendar_dates
som tillägg/undantag. Referensdatum redovisas. Kvällsmåttet räknar turstarter
21:00–23:00; stop_times räknar tabellrader, inte unika fordonsavgångar.
Proverna indikerar trafikmängd men bevisar inte användbara A–B-förbindelser.

```powershell
python -B scripts\download_gtfs_skane.py --config config\paths.toml
python -B scripts\inspect_inputs.py --config config\paths.toml
# Endast vid avsiktlig uppdatering:
python -B scripts\download_gtfs_skane.py --config config\paths.toml --force
```

En befintlig giltig ZIP återanvänds utan nätverksanrop eller nyckelläsning.
Ogiltig ZIP ger fel; --force krävs för ersättning. Ny hämtning skrivs till
temporär fil i målkatalogen, ZIP-tabeller och CRC kontrolleras, sedan ersätts
målet atomiskt. Separat skane.zip.metadata.json innehåller UTC-hämtningstid,
storlek, SHA-256, operator och nyckelfri källa. Metadata ersätts också
atomiskt, men paret ZIP/metadata är inte en transaktion: efter avbrott måste
hashmatchning kontrolleras och saknad/felaktig proveniens markeras ASSUMED.
Befintlig provenance uppfinns aldrig vid återanvändning.

VERIFIED avser bara den kontroll som utskriften beskriver; ASSUMED betyder
att exempelvis proveniens eller formatets täckning inte verifierats;
MISSING betyder saknad eller oläsbar/ogiltig indata. Inspektionen är
skrivskyddad och hoppar över identifierade Windows-molnplatshållare.
OSM-XML läses strömmande för nodernas geografiska omslutning; det bevisar
inte gångnätets konnektivitet. PBF-täckning kräver en senare läsare.
Lomma-gräns och befolkningspunkter läses direkt i det inventerade arkivet,
utan extrahering; punkterna är inte verifierad befolkning 20–64 år.

Före första A→B-testet återstår miljöinstallation och win-64-låsning,
verifiering av R5/Java och eventuell R5-jar/cache, GTFS-hämtning med lokal
nyckel, kalender-/datum-/buss-/tågvalidering, ett kompatibelt OSM-PBF eller
verifierad konvertering med rätt geografisk täckning, samt routingkod.
Frys A/B-koordinater, Europe/Stockholm, datum, starttidsurval, gånghastighet,
bytesregler och percentilmetod. Börja med en handkontrollerad resa och
omöjlig resa, visa reskedjan och kontrollera T50/T90/T99, T90–T50 och ±15
minuter enligt MVP_SPEC. Historiska störningar ingår inte i Phase 0/R0.
