# N−1-optimering, 2026-10-13

Normala vyanalyser återanvänder minutprofilen, gör en reservsökning per
unik beskedspunkt/tid/tur/gångbudget/trafikbensbudget, och använder den
oberoende kontraktvalidatorn på varje scenario. Full R5-audit är ett separat
läge. Ingen routingregel, horisont, kvantil eller turidentitet har ändrats.
Den befintliga reservcachen behålls; den stora ändringen är att bassökningar
och hela turkalenderns JVM-läsning inte upprepas per minut/scenario i vyn.

## Uppmätt tid

Samma Windowsmiljö: Python 3.12.15, r5py 1.1.7, R5 7.5.1-r5py och Java 21.
Tiderna omfattar N−1-analys, kontraktkontroll och atomisk resultatskrivning,
inklusive GTFS-inläsning. Initial nätverksladdning är exkluderad. Nätverket
byggs en gång i varje benchmarkprocess och återanvänds mellan repetitionerna.

| Fall | Startminuter | Unika reserver | Körning 1 | Körning 2 |
|---|---:|---:|---:|---:|
| Lomma → Lund | 60 | 8 | 9,08 s | 8,31 s |
| Malmö C → Värnhem | 60 | 14 | 12,66 s | 11,51 s |
| Gunnesbo → Ideontorget | 60 | 20 | 13,98 s | 13,05 s |

Resor, scenariomått, samlat mått och GeoJSON matchar sparad full audit för
samtliga tre fall. Två nya snabba resultat är helt identiska, inklusive
verifieringsmetadata. Tid ligger i separat benchmarkmetadata. Ursprungliga
bas-/N−1-resultat har inte skrivits över, och inga nya bassweeps gjordes.

Ett nytt Lomma-prov med tre startminuter tog 7,06 s med full audit respektive
5,24 och 5,11 s i snabbt läge; resor/GeoJSON matchade exakt mellan lägena.
Detta är den direkt jämförbara tidsmätningen: den historiska sexkörnings-
rapportens 348,9 s inkluderar annat arbete och ger ingen exakt speedup-faktor.

Bjärred–Lund, 2026-10-14 kl. 06:30, provades med fyra tillåtna trafikben,
4,5 km/h, 20 min gång och 120 min basgräns. Basresan hade tre trafikben.
En minut med tre bortfall tog **121,34 s** i full audit och **9,16/9,20 s**
i snabbt läge: cirka **13,2 gånger snabbare** i detta jämförbara prov.
Samtliga tre reserver matchade råa R5-restider; resor, mått och GeoJSON
matchade mellan lägena och två snabba resultat var helt identiska.
Ett separat treminutersprov tog 22,70/9,07 s, också med identiska resultat.
Första fyrabensprovet betalade bland annat komplettering av längre
gatubaserade byteslänkar; uppvärmd tid ska inte förväxlas med kallstart.
Ingen full 60-/120-minuterskörning med fyrabensbudget gjordes här.

89 tester passerar, inklusive cacheidentitet för olika förbrukade budgetar,
oförändrad basprofil, tydlig skillnad mellan saknad audit och ej nåbar resa,
och jämförelse som upptäcker ändrade reservturer men tillåter olika auditbevis.

## Reproduktion och begränsningar

Använd `scripts/benchmark_nminus.py` enligt `docs/SCHEDULE_PROFILE.md`.
För hela Malmö-/Gunnesbofönstret, ersätt case i `--report` och `--expected`.
Output går till `outputs/nminus-performance/` och är ignorerad. SHA-256 för
OSM är `47942e06ea6c96c8893933f71f448f7e1deac9d906c216a16c60a414db521b9d`;
original-GTFS är `6a17c51b0924301eea8466e71d826bd7495199ce3a0de7f4f90d0293b4c13182`.

Gatunätsladdning, GTFS-parsning, geometri och unika reservsökningar kostar
fortfarande tid. Fyra tillåtna trafikben kan ge fler söktillstånd; dessa
60-minutersmätningar gäller originalens tvåbensbudget och får inte användas
som garanti för alla 120-minutersfall. R5:s EPSG-fil kan fortfarande vara
låst vid JVM-avslut; loggen redovisar detta och benchmarksupervisorn använder
projektets befintliga säkra städning efter att workern avslutats.
Samtliga benchmarkworkers avslutades med exitkod 0. Uppskjuten städning
lyckades efter exit; tidigare provloggars temporära kataloger städades med
samma avgränsade hjälpfunktion. Processkontroll görs före återstart av vyn.
