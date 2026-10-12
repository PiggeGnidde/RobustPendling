# Verifiering av lokal planerare, 2026-10-12

## Gångparametrar och exakt profil, senare uppdatering

Nya standardvärden 4,5 km/h och högst 20 minuter gång används genom hela
bas-/detalj-/N−1-kedjan. Intervall 3–6 km/h och 10–30 minuter valideras i
API och vy. Inställningarna ingår i metadata och cacheidentitet; cache för
bytesgång skiljer också hastighet och budget. R5:s byteslänkar längre än
1 km kompletteras till 3 km en gång, vilket täcker övre gånginställningen.
Originalens länkar/regler och parametrar behålls.

Profilen jämfördes mot **alla 240 sparade minutobservationer**: användarens
tidigare 60-minutersfall och de tre originalrelationerna (180 minuter).
Restid, gång, väntan, byten och exakt vald tur-/hållplatskedja är identiska.
Originalrelationernas 180 minuter jämfördes dessutom med aktuell separat
sweep och rå R5: samtliga passerar; regression-worker avslutade med exit 0.

| Samma frysta indata/parametrar | Minuter | Profilsökningar | Profilens söktid | Tidigare separat sweep |
| --- | ---: | ---: | ---: | ---: |
| Tidigare lokalt Bjärredfall, fyra ben | 60 | 8 | 29,86 s | 350,47 s |
| Lomma → Lund, original | 60 | 8 | 0,010 s | 0,079 s |
| Malmö C → Värnhem, original | 60 | 13 | 0,246 s | 1,243 s |
| Gunnesbo → Ideontorget, original | 60 | 10 | 0,028 s | 0,196 s |

Tider avser själva oberoende sökningen, inte import, nätverksladdning, rå
R5 och detaljer. Mätningarna gjordes vid olika körningar och är inte ett
kontrollerat laboratoriebenchmark. Bjärredfallet förbättrades cirka 11,7 gånger
för sökningen med oförändrade resultat; hela anropet har kvar andra kostnader.

Ett nytt 120-minutersfönster 06:30–08:29:59, 2026-10-14, till verifierad
OSM-entré med fyra ben och nya gångstandardvärden granskades i webbläsaren:
17 profilsökningar, 33 råa R5-kontrollminuter, alla kontrolltider identiska,
120/120 nåbara. T50 47:50, T90 51:44, T99 53:50; buffer_90 3:54;
minimum 38:07. Profilens söktid 38,68 s; första UI-anropet tog 131,3 s
inklusive nätverksstart, länkutökning, kontroller och geometri.
Vyn visar framsteg i dessa beräkningsfaser och återanvänder sedan cache.
Exakta privata koordinater och genererade användarresultat publiceras inte.

Ett separat enminuts-N−1-prov med nya parametrar passerade sweep/R5 och
kontraktsvalidering för båda trafikbenen. Bortfall av första benet gav
59:28 (extra 10:38), andra benet 55:09 (extra 6:19). Genomförd gång och
förbrukat trafikben bevarades; kvarvarande budget var 17:24 respektive
15:06. Nätverket återanvändes och efterföljande basfall var oförändrat.
N−1 är fortsatt betydligt dyrare än basprofilen och har inte benchmarkats
över 120 minuter i denna uppdatering.

84 tester passerar. Profiltester omfattar slumpade nät och direktgång som
först vinner, sedan slås av transit och åter vinner efter missad avgång.
Se [SCHEDULE_PROFILE.md](SCHEDULE_PROFILE.md) för exakt metod och fullvalidering.

## Korrigering av basresans sökhorisont

Nya vyanalyser använder 120 minuter i stället för 45. Parametern följer
med genom worker/supervisor, rå R5, oberoende sweep, detaljer, N−1-validering,
metadata, cacheidentitet och dygnsgränskontroll. Gånggränsen är fortsatt
15 minuter totalt. Originalförval och deras frysta 45-minutersresultat
bevaras och skiljs från nya analyser.

Ett exakt minutprov Bjärred → Lund, 2026-10-14 06:54, gav 54:06 och ankomst
07:48:06 med buss 137 → 6 → 171, gång 11:27 och väntan 14:44, samt 60 s
slutmarginal. Oberoende sökning och rå R5 överensstämmer. Den gamla gränsen
gav inget resultat eftersom resan tog mer än 45 minuter. Detaljresan och
kartan kontrollerades i vyn. Ett enda prov innebär inga slutsatser om
variation över ett större avreseintervall. Lokala koordinater/resultat
för detta användarprov publiceras inte.

79 tester passerar, inklusive en resa över 45 minuter för alla bensgränser
1–4, validering av horisonten, skilda cacheidentiteter och bibehållen
45-minutersidentitet för originalförvalen. Inga nya fullständiga sweeps.

## Regression och testsvit

77 tester passerade, inklusive 3-/4-benskedjor, strikta byten,
förbrukad gång-/bensbudget, senare snabbare trafik, en separat sökning utan
pruning, lexikografisk tie-break efter väntan, fjärde-ben-validator,
ej nåbara/ej tillämpliga fall, +∞ i samlat N−1, ren gång och icke-monotona
deadline-analyser. Befintlig förbjuden-avstigning-före-dominansregression
passerar fortfarande.
Bas- och reservhorisonter avvisar trafikdygns-/DST-övergång tydligt.
Rena gångfönster kräver ingen tvåtimmars turbortfallshorisont.

De tre frysta basrelationerna jämfördes en gång med aktuell oberoende sweep
och exakt rå R5 för **alla 180 startminuter**, default två ben. Inga avvikelser:

| Relation | Bas T50 / T90 / T99 | Samlat N−1 T50 / T90 / T99 | Alla bortfall har reserv |
| --- | --- | --- | --- |
| Lomma → Lund C | 36:17 / 39:17 / 42:17 | 44:17 / 47:17 / 49:17 | 100 % |
| Malmö C → Värnhem | 16:26 / 19:26 / 20:26 | 23:02 / 26:26 / 27:26 | 100 % |
| Gunnesbo → Ideontorget | 32:56 / 37:56 / 41:52 | 42:56 / 48:52 / 53:52 | 100 % |

Samlat mått härleddes från de bevarade N−1-resultaten, utan nya
60-minuters-scenariokörningar. Alla sex originalartefakter klarade återigen
kontrakt, checksumma och upprepningslikhet. Efter sista ändringarna i
3-/4-benspruning är 1-/2-benssökningen och råa regressionrutinen oförändrade;
de nya grenarna kontrolleras med tester och små R5-prov.

Deadline 08:00 med ursprungliga 07:00–07:59 ger:

| Relation | Senaste start bas | Senaste start vid alla enskilda bortfall |
| --- | --- | --- |
| Lomma → Lund C | 07:20 | 07:13 |
| Malmö C → Värnhem | 07:41 | 07:34 |
| Gunnesbo → Ideontorget | 07:26 | 07:14 |

JSON-exemplet [planner-summary.json](../examples/planner-summary.json)
innehåller värden i sekunder, ankomsttider och källresultatens checksumma.

## Verkligt tre-/fyrabensprov

Små manuellt valda prov gjordes före utökad regression. Värnhem–Ideontorget
07:00 var nåbart med två ben. Segevångsbadet–Brunnshögstorget 07:03 och
06:50, Kirsebergs kyrka 06:58 samt Kirsebergsskolan 06:56 till Brunnshög
gav ingen resa inom basgränsen 45 min. Kirsebergskedjan motiverades av
trafikdagens 14/15-anslutningar till Värnhem, men uppvisade inte önskad
struktur inom budgeten. Dessa var enminutsprov, ingen regional OD-sweep.
Ett fyrabensprov tog 138 s i oberoende sökning före den säkra
bakåtriktade pruningen; ingen resultatgräns eller gångbudget höjdes för
att göra provet nåbart.

Ett verifierat verkligt **fyrabensfall finns i reserven**:

- A: Malmö Ellstorp, GTFS-plattform `9022012080129001`,
  lat 55.604043, lon 13.027124.
- B: Lund Brunnshögstorget, GTFS-stationspunkt `9021012081260000`,
  lat 55.720660, lon 13.231109.
- Datum 2026-10-12, exakt start 06:54, ett minutprov, max fyra ben.
- Bas **38:24**: gång 0:09, buss 6 **06:55:29–06:57**, bytesgång
  **4:03**, buss 168 **07:05–07:24**, slutgång/marginal till **07:32:24**.
- Ben 1 uteblir: reserven går till 168 och når samma sluttid,
  **0:00 extra**. Genomförd gång och beskedstid bevaras.
- Ben 2 (168 kl. 07:05) uteblir: redan genomförd 6 och bytesgång
  bevaras. Reserven har **tre återstående trafikben**:
  131 **07:14–07:25:25**, 165 **07:28:34–07:39**, gång **1:43**,
  spårvagn 1 **07:45–07:55:49**, slutmarginal/gång till **08:01:40**.
  Total **67:40**, extra **29:16**; fyra trafikben totalt.
  Boardingmarginaler är **4:55**, **3:09** och **4:17**.
- Prefixets gång **4:12** lämnar **10:48**. Reservens gång är **10:39**;
  hela resan går **14:51**, inom 15-minutersbudgeten.
- Med max **tre** ben var basresan fortfarande 38:24, men senare bortfall
  får bara två återstående ben. Vald reserv blev nästa 168 och total
  **69:24**, extra **31:00**. Fyrabensbudgeten förbättrar alltså detta
  bortfall med **1:44**; det är en verklig motor-/validatorändring.

Den tredelade fortsättningen och fyrdelade hela resan matchar rå R5 och
oberoende sökning. Validatorn kontrollerar originalstart, prefix,
besked, exakt utesluten tur, återstående budget och ett kartfeature per segment.
Inget optimalt basfall med tre/fyra ben påvisades i dessa små 45-minutersprov;
verifieringen av verkliga flerben gäller reserven och påstår inte något annat.
En enda minut är ett funktionstest, inte statistisk stabilitet.

Små publicerbara detaljer finns i
[planner-four-leg-reserve.json](../examples/planner-four-leg-reserve.json).
Fulla resultat/geometrier ligger ignorerade under `outputs/planner`.

## Gränssnitt och livscykel

Kartklick för både A och B ändrade koordinater/namn och rensade föregående
resultat. Koordinater kunde därefter redigeras. Datum 2030-01-01 avvisades
med `OUTSIDE_FEED_DATES`; latitud 57 med `OUTSIDE_NETWORK_AREA`, före routing.
En egen 35-sekunders gångresa med två startminuter och max ett ben gav
100 % täckning, inga trafikben och samma senaste start 07:01 vid deadline
för basfall och samlat N−1. Syntetiska tester kontrollerar +∞ när reserv saknas.
Med slutlig kod provades också samma gångresa kl. 23:00–23:01, deadline
23:30: senaste start 23:01 och ankomst 23:01:35 i båda lägena. Den märktes
uttryckligen utan trafikben. Kartväljarens A/B-markörer är lokala SVG-cirklar
och kräver inga externa ikonbilder. Inga JavaScript-fel observerades.

Ellstorp-provet visar vid deadline 08:00 en godkänd basstart 06:54 och
ingen godkänd minut för alla bortfall: reserven anländer 08:01:40.
Klick öppnar vald minut och relevanta reserver; resultat från gamla indata
får inte blandas med nästa analys. Kartan visar bas, genomförd del och
reserv med hållplatser, orange anslutningar och OSM-attribution.

Routingnätet återanvänds i serverns worker; de små nya analyserna och N−1
använde samma instans tills servern startades om vid kodändringar. Källkod
kontrolleras även mot det som workern laddat så att en utvecklingsändring
kräver omstart i stället för felaktig reproduktionsmetadata.

Regressionworkern avslutades med exitkod 0 och uppskjuten städning lyckades.
Serveromstarter gav också exitkod 0. GeoTools `WinError 32` vid första
städningen är fortsatt känt och synligt i lokal stderr; det är inte generellt
löst. Inga fulla regionala sweeps, installationer eller nya rådatahämtningar
gjordes. Main-checkouten ändrades inte.
