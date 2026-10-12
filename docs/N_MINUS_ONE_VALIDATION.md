# N−1: verifierade resultat

Frysta Phase 2C-inputs, måndag 2026-10-12, Europe/Stockholm, exakta
07:00…07:59. Kontrakt/horisont/antaganden i [N_MINUS_ONE.md](N_MINUS_ONE.md).
Alla tidstal nedan är **minuter:sekunder**. Basfallets ursprungliga mått,
reskedjor och turinstanser reproduceras; N−1 ändrar inte schedule-kvantilerna.

| Relation | Bas T50 / T90 / T99 |
| --- | --- |
| Lomma station → Lund C | 36:17 / 39:17 / 42:17 |
| Malmö C → Malmö Värnhem | 16:26 / 19:26 / 20:26 |
| Lund Gunnesbo station → Lund Ideontorget | 32:56 / 37:56 / 41:52 |

## Sammanfattningar

| Relation / fel | Tillämpliga / ej tillämpliga | Total T50 / T90 / T99 | Extra P50 / P90 / max | Täckning / ej nåbara |
| --- | --- | --- | --- | --- |
| Lomma, ben 1 | 60 / 0 | 44:17 / 47:17 / 49:17 | 7:00 / 11:00 / 11:00 | 100 % / 0 |
| Lomma, ben 2 | 0 / 60 | — | — | ej tillämpligt / 0 |
| Malmö, ben 1 | 60 / 0 | 22:33 / 26:26 / 27:26 | 7:00 / 8:00 / 8:00 | 100 % / 0 |
| Malmö, ben 2 | 1 / 59 | 27:02 / 27:02 / 27:02 | 8:00 / 8:00 / 8:00 | 100 % / 0 |
| Gunnesbo, ben 1 | 60 / 0 | 41:56 / 47:52 / 53:52 | 8:00 / 17:33 / 17:33 | 100 % / 0 |
| Gunnesbo, ben 2 | 60 / 0 | 37:56 / 44:56 / 48:52 | 6:56 / 7:23 / 8:00 | 100 % / 0 |

Alla **241 tillämpliga** scenarier är nåbara inom horisont och återstående
resurser. 119 av de 360 scenarioplatserna är ej tillämpliga, inget dolt
misslyckande. Malmö-ben-2 har bara en observation: identiska kvantiler är
ett litet urval, inte evidens för stabilitet. Regler för partiell täckning/
inga nåbara/inga tillämpliga verifieras med syntetiska tester.

## Reservexempel och största konsekvenser

**Lomma, start 07:29, ben 1.** Vald 139 kl. 07:42:08 uteblir. Resenären
har gått 5:49 till Lomma Strandvägen och förbrukat 13:08 från ursprunget
vid beskedet. Nästa 139, **07:51:16→08:13:00**, är fortsatt tillgänglig.
Slutgång/marginal ger mål **08:18:17**, total **49:17**, extra **11:00**.
Alla 60 reserver använder 139. Detta bevisar att linjen inte uteslutits;
olika trip_id finns bevarade även när line/route_id är samma.

**Malmö, start 07:00, ben 1.** Vald 9 kl. **07:06** uteblir efter gång
0:53 och väntan 5:07. Reserven går **0:24** till annan plattform vid Malmö C,
sedan **39 07:08→07:12**, byte med **3:14** marginal vid Frihamnen,
och **3 07:15:14→07:21** till Värnhem. Ankomst inklusive slutgång/marginal
**07:24:02**, total **24:02**, extra **6:36**. Boarding till 39 har 1:36
marginal efter den nya gången, större än 60 s. Originaltur 9 återanvänds inte.

Malmös ben-1-reserver fördelas på 9 (35 minuter), 4 (12), 3 (6), 39→3 (5)
och 5→9 (2). Det är valda reserver för specifika bortfall, inte en fullständig
inventering av alla möjliga alternativ. Största extra restiden **8:00**
förekommer exempelvis start 07:20: 9 kl. 07:28 uteblir, nästa 9 kl.
07:36→07:44 ger mål 07:47:26 och total 27:26.

**Malmö, start 07:05, ben 2.** Det enda tvåbensbasfallet har redan gått
1:05 och rest **39 07:08→07:12** till Frihamnen. Besked om 3 kommer
**07:15:14**, efter 3:14 väntan. Tid före besked **10:14** bevaras.
Nästa **3 07:23:14→07:29** ger mål **07:32:02**, total **27:02**, extra
**8:00**. Omplaneringen startar på Frihamnen med bara ett återstående
trafikben och 13:55 gångbudget; den startar inte på Malmö C.

**Gunnesbo, start 07:15, ben 1.** 817 kl. **07:28** uteblir efter 0:06
gång och 12:54 väntan. Reserven går **3:39** till busshållplatsen Gunnesbo,
tar **4 07:33:58→07:56:12**, därefter **6 07:59:16→08:04:04** från
Universitetssjukhuset med **3:04** bytesmarginal. Mål **08:08:52**, total
**53:52**, extra **17:33**, den största uppmätta extra restiden i fallen.
Reserverna växlar mellan 4→1 (22), 3→1 (2), 817→1 (6), 4→6 (12),
824→1 (7) och 817→6 (11); återanvändning av en annan 817-tur är tillåten.

**Gunnesbo, start 07:26, ben 2.** Tåg **817 07:28→07:32** och gång
**5:53** till bussplattformen på Lund C behålls. Resenären får besked
**07:39** om buss 6. Efter ny gång **1:27** till spårvagnsplattformen väljs
**1 07:45→07:51:18**, med **4:33** boardingmarginal efter gången.
Mål **07:53:56**, total **27:56**, extra **2:37**. Genomförd tid **13:00**,
gång 5:59 och ett trafikben bevaras. Resterande gångbudget är **9:01**.
Det finns ingen omplanering från Gunnesbo i denna reserv.

Gunnesbos ben-2-reserver är spårvagn 1 (36) eller buss 6 (24).
Största extra **8:00** förekommer exempelvis start 07:09 när spårvagn 1
kl. 07:37 ersätts av nästa 1 kl. **07:45→07:51:18**, mål **07:53:56**.

## Verifiering

- Två fullständiga körningar per relation i en gemensam worker/nätverk.
  Hela JSON-resultaten är identiska och exporterade GeoJSON matchar bytevis.
- 180 basminuter per repetition matchar fryst sweep och exakta råa R5-tider
  före/efter scenarier. Samtliga valda tur-ID:n i Phase 2C:s sparade
  representativa R5-resor matchar minutobservationernas tur-ID:n.
- 241 tillämpliga scenarier per repetition matchar oberoende uttömmande
  reservsökning och råa R5-restider. Ingen returnerad R5-tillståndskedja eller
  exporterad reserv innehåller den felande trip_id-instansen.
- Oberoende kontraktkontroll över alla sex resultat: bevarat prefix/start,
  exakt besked, strikta boardings, budget, horisont, status/nämnare och ett
  matchande GeoJSON-feature per genomfört/reservsegment.
- Nätverket byggs en gång för de sex analyserna. Identiska fortsättningar
  återanvänds; antal unika sökningar redovisas per resultat.
- JVM-workern PID 23920 avslutades med **exitkod 0**; GeoTools WinError 32
  loggades och den uppskjutna städningen gav `removed=true`. Totalt 348,90 s
  för sex analyser/JSON-/GeoJSON-exporter. Diagnostik ligger i ignorerade
  `outputs/nminus/validation.json` och workerloggar.
- RegionalTask varnar för det korta interna fönstret. Vår exakta adapter
  använder två sekunder, en draw och fast seed, med explicit kontroll av
  utvärderad sekund; inga native percentiler används som svart låda.

Artefakter och hash/checklistor finns i ignorerade `outputs/nminus`;
CLI-kommandon återskapar dem. Kartan och JSON ska inte tolkas som
förseningsmodell, verklig körväg eller inställd-tur-sannolikhet.

## Webbläsargranskning och slutkontroll 2026-10-12

Alla tre förval öppnades i den lokala granskningsvyn på
`http://127.0.0.1:8765/`. Basvärdena i tabellen ovan stämde. Lommas
ben-1-scenario 07:29, Malmös båda scenariotyper (inklusive ben 2 kl. 07:05)
och Gunnesbos ben 1 kl. 07:15 respektive ben 2 kl. 07:26 granskades med
tider, genomförd del, beskedshållplats och reservresa. Kartbakgrund och
attribution laddades; blå basresa, grön genomförd del, lila reserv och röd
beskedsmarkör kunde förstås tillsammans. Orange approximativa anslutningar
och gång-/trafikskillnader behölls. Lommas ben 2 visades som ej tillämpligt,
inte som ett misslyckande.

Lokalt simulerat tilefel gav tydligt felmeddelande medan Leaflets rutter
och markörer fungerade. Simulerat bibliotekfel visade den lokala SVG-kartan.
Både smal vy och desktopvy kontrollerades. En ny analys med två startminuter
och startlatitud 55.67435 gav ett tidigare ocachat N−1-resultat: 07:00-resan
blev 45:17 med 8:00 extra och ankomst 07:45:17. Återgång till basfallet
visade oförändrat 37:17 och ankomst 07:37:17. Detta provade den verkliga
API-/worker-vägen och återanvändning av nätverket. Granskningsbild finns
i ignorerade `outputs/review/nminus-lomma.jpg`.

Efter återupptagning från sleep passerade **65 tester**, inklusive
förbjuden avstigning före dominanspruning, exakt turuteslutning/återställning,
bevarad resursbudget, villkorade kvantiler, checksummefel och cache som hör
till fel analys. `validate_nminus.py --check-existing` verifierade alla sex
artefakter igen: kontrakt, checksumma, upprepningslikhet och GeoJSON-bytes.
Aktuella OSM-/original-GTFS-fingeravtryck och de sparade routingkodhasharna
matchade. Inga sex fullständiga routingkörningar upprepades; endast tester
och kontroll av redan sparade artefakter kördes efter återupptagningen.

Den senaste verkliga granskningsworkern (PID 28964) och servern stoppades
ordnat före sleep, båda med exitkod 0; uppskjuten R5-städning lyckades.
GeoTools-filhandtagets WinError 32 vid JVM-avslut är fortfarande ett känt
avslutningsproblem, inte dolt eller bevisat generellt löst. I de granskade
körningarna skrevs atomiska resultat före avslut, upprepningarna var identiska
och inga routingprocesser lämnades kvar. Ingen routingkod ändrades vid
slutkontrollen. Main-checkouten var ren och kvar på d2a5104.
