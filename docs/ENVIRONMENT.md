# Windows-miljö och indata: Phase 0–1

Python 3.12 i en separat projektmiljö är målplattformen. environment.yml
anger conda-forge, r5py 1.1.7 och geospatiala versionsserier samt miljöegen
OpenJDK 21 och rasterio 1.4. System-Python och system-Java ändras inte.
Phase 1 har löst miljön, verifierat binära importer och startat R5/JVM.
environment.win-64.lock.txt låser samtliga lösta paket och builds för Windows.
Conda, mamba och micromamba hittades inte vid Phase 0-kontrollen av PATH,
C:-roten, användarroten och AppData/Local. Ingen installation gjordes.

Version och metod kontrollerades 2026-10-11 mot
[conda-forge-paketet](https://anaconda.org/conda-forge/r5py) och
[r5py:s installationsguide](https://r5py.readthedocs.io/latest/user-guide/installation/installation.html).
Den senare rekommenderar separat conda-miljö på Windows och beskriver JDK
21 eller senare. Phase 1 installerade micromamba 2.9.0 lokalt i .venv/tools
och skapade robustpendling från environment.yml med root-prefix .venv/mamba.
Ingen shell-init, global PATH-, JAVA_HOME- eller aliasändring utfördes.
Verifieraren väljer JAVA_HOME och cache enbart i sin egen process.

Reproducerbara PowerShell-kommandon från projektroten (ingen admin krävs).
För exakt paketåterskapande, ersätt environment.yml med
environment.win-64.lock.txt i create-kommandot. Micromamba-bootstrapens
latest-adress kan förändras; den faktiskt använda versionen var 2.9.0.

```powershell
New-Item -ItemType Directory -Force .venv\tools, cache\runtime\r5py | Out-Null
Invoke-WebRequest https://micro.mamba.pm/api/micromamba/win-64/latest -OutFile .venv\tools\micromamba.tar.bz2
tar -xjf .venv\tools\micromamba.tar.bz2 -C .venv\tools Library/bin/micromamba.exe
$mambaExe = '.\.venv\tools\Library\bin\micromamba.exe'
& $mambaExe create -r .\.venv\mamba -n robustpendling -f environment.yml -y
# Windows-trust-validerad fallback om requests inte accepterar lokalt certifikat:
Invoke-WebRequest https://github.com/r5py/r5/releases/download/v7.5.1-r5py/r5-v7.5.1-r5py-all.jar -OutFile cache\runtime\r5py\r5-v7.5.1-r5py-all.jar
if ((Get-FileHash cache\runtime\r5py\r5-v7.5.1-r5py-all.jar).Hash.ToLower() -ne 'd50be106cadd7b636cfc0e209052767d7df570629f79fdf98ecd5cf5d2d89be7') { throw 'R5 checksum mismatch' }
& $mambaExe run -r .\.venv\mamba -n robustpendling python -B scripts\verify_runtime.py
& $mambaExe run -r .\.venv\mamba -n robustpendling python -B -m unittest discover -s tests -v
```

Kopiera exemplen. Redigera .env lokalt med en GTFS Regional-nyckel i
TRAFIKLAB_API_KEY; skriv inte nyckeln i terminalkommandon. En redan satt
miljövariabel med samma namn har företräde. .env-parsern accepterar en
enkel KEY=value-rad med valfria citattecken; inga substitutioner utförs.
Konfigurationen återger exakt de lokala Downloads-sökvägarna i
LOCAL_INVENTORY.md. Relativa sökvägar utgår från projektroten, inte cwd.
Lokala hemligheter, paths.toml, cache, miljö och rådata är Git-ignorerade.
Kör återstående python-kommandon i robustpendling via micromamba run som
ovan. Kopiera inte över en redan konfigurerad .env.

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

Före första A→B-testet återstår ett kompatibelt OSM-PBF med rätt
geografisk täckning, detaljerad trafik-/kalenderkontroll och routingkod.
Frys A/B-koordinater, Europe/Stockholm, datum, starttidsurval, gånghastighet,
bytesregler och percentilmetod. Börja med en handkontrollerad resa och
omöjlig resa, visa reskedjan och kontrollera T50/T90/T99, T90–T50 och ±15
minuter enligt MVP_SPEC. Historiska störningar ingår inte i Phase 0/R0.

## Faktisk Phase 1-verifiering, 2026-10-11

Python 3.12.15; r5py 1.1.7; geopandas 1.1.4; rasterio 1.4.4;
shapely 2.1.2; pyproj 3.7.2. Alla importer lyckades. JVM-property java.home
och JPypes jvm.dll-sökväg verifierades mot
`.venv/mamba/envs/robustpendling/Library/lib/jvm`.
Faktisk Java-version 21.0.10, vendor Azul Systems, Inc.
Verifieraren begränsar JVM-heapen till 2 GiB; uppmätt import/JVM-start
5,17 sekunder, RSS 315 224 064 byte (cirka 301 MiB). Detta är
runtime-start, inte nätverksbyggtid eller nätverkets minnesbehov.

Solve lyckades med ursprungliga versionskrav. Enda paketändringen var
tillägg av rasterio=1.4 för den begärda importkontrollen. Installationen
varnade om redan befintliga kinit.exe/klist.exe inom den nya miljön.
Första r5py-importen misslyckades med requests SSLCertVerificationError:
"certificate verify failed: unable to get local issuer certificate".
Windows Invoke-WebRequest hämtade därefter samma R5 7.5.1-r5py-jar med
TLS-validering, och SHA-256 kontrollerades mot r5py:s installerade kod.
Ingen verify=False eller ändring av globala certifikat gjordes.
Samtliga 14 tester passerade i den nya miljön.

OSM-underlaget `C:\Users\bengt\Downloads\export.osm` är XML, 52 845 570 byte,
415 402 noder, bbox (lat, lon) [55.5760295, 12.916027]–[55.8544178, 13.2315166].
Det är inte det [PBF-format som r5py kräver](https://r5py.readthedocs.io/latest/user-guide/user-manual/data-requirements.html).
Av 10 723 GTFS-hållplatsposter ligger 1 959 i nodernas bbox och 8 764 utanför.
Lomma station (cirka 55.6743, 13.0747) och Lund C (cirka 55.7064, 13.1870)
ligger inom bbox, men bbox bevisar inte ett komplett sammanhängande gångnät.
TransportNetwork och routingsmoke test kördes därför inte; byggtid,
nätverksminne och byggvarningar är ännu inte uppmätta. Inget nytt OSM
laddades ned.

För ett avgränsat Lomma–Lund-test rekommenderas komplett OSM-PBF med
noder, ways och relations över ungefär (lat, lon)
[55.60, 12.95]–[55.80, 13.30], inklusive gångvägar, anslutningar och marginal
för alternativa resvägar. Detta är ett planeringsförslag, inte en verifierad
minimigräns. GTFS bör då avgränsas med bibehållen referensintegritet eller
hanteras med uttryckligt redovisade hållplatser utanför området.
Hela feedens hållplatsomslutning är [55.339604, 11.971953]–[57.710295, 16.36119].
Om samtliga hållplatser ska omfattas behövs sydsvensk/dansk PBF-täckning
åtminstone över denna bbox med marginal, exempelvis
[55.29, 11.92]–[57.76, 16.42], samt kontroll av hela reskorridorer.
