# MVP-specifikation för RobustPendling

## Syfte och omfattning

MVP:n ska stödja planering av robust kollektivtrafikpendling i Skåne genom
privatläge för resor från A till B och arbetsplatsläge för arbetspass.
Första versionen, R0, baseras på tidtabell och gånganslutningar.
Historiska förseningar och inställda turer ingår i en senare version.

## Privatläge: robust resa från A till B

Användaren anger startpunkt A, målpunkt B, datum och önskad avgångstid eller
ankomsttid. Resan visas på karta med buss, tåg, gångsträckor, hållplatser,
stationer och bytesplatser. Reseförslaget visar avgång, ankomst, total restid,
gångtid och byten så att hela reskedjan går att följa.

Följande scenarier ska kunna jämföras med dokumenterade datum och tidsfönster:

- Vardagspendling: resa under vardagens pendlingsperioder.
- Kväll: resa under kvällstid, inklusive glesare förbindelser.
- Helg: resa enligt den valda helgdagens trafik.

## Restidsmått och robusthet i R0

| Mått | Definition |
| --- | --- |
| T50 | Restidens 50:e percentil, i minuter. |
| T90 | Restidens 90:e percentil, i minuter. |
| T99 | Restidens 99:e percentil, i minuter. |
| T90–T50 | Skillnaden mellan T90 och T50, i minuter; visar variationen. |

R0 beräknar måtten över ett uttryckligen dokumenterat urval av starttider i
scenariots tidsfönster, med tidtabellsenliga resor inklusive väntan, gång och
byten. Urvalets intervall, antal observationer, percentilmetod och hantering
av starttider utan möjlig resa ska redovisas. Om en starttid saknar möjlig
resa behandlas restiden som oändlig och andelen sådana starttider visas.
Percentiler som därmed inte är ändliga markeras som ej uppnåeliga.

Måtten beskriver tidtabellens variation mellan starttider. De är inte
empiriska sannolikheter för att anlända i tid och ska märkas som R0 i gränssnitt
och exporter. Historiska förseningar får inte antas ingå i beräkningen.

## Arbetsplatsläge: arbetspass och upptagningsområden

Användaren anger arbetsplats, datum samt arbetspassets start och slut.
Beräkningen ska pröva både en resa som når arbetsplatsen senast vid passets
start och en möjlig hemresa som avgår tidigast vid passets slut.
Pass som slutar nästa kalenderdag ska använda rätt datum och trafik.

Robusta upptagningsområden visas på karta för 15, 30, 45 och 60 minuter.
R0 använder T90 som robust restidsmått och redovisar också T50, T99 och
T90–T50. En bostadsplats ingår vid en gräns endast om både resan till arbetet
och hemresan klarar gränsen och passets tidsvillkor. Saknad möjlig hemresa
utesluter platsen. Gång, väntan och byten ingår i respektive restid.
Urvalet av starttider måste uppfylla passets villkor för respektive riktning;
beräkningsfönster och regler dokumenteras tillsammans med resultatet.

För varje upptagningsområde visas antal boende 20–64 år. Samma boende räknas
en gång inom respektive gräns, även när flera resvägar eller överlappande
områden når bostaden. Gränserna är kumulativa: en boende kan ingå i både
15- och 30-minutersresultatet, men resultaten får inte summeras.
Befolkningsunderlagets geografiska enhet, referensår och metod för enheter
som delvis täcks ska redovisas. Resultatet är antal boende, inte antal
anställda eller tillgängliga arbetstagare.

## Känslighetsanalys

För privatläge jämförs vald starttid med starttid −15 och +15 minuter.
För arbetsplatsläge jämförs passets start med start −15 och +15 minuter,
med oförändrat passlut. Varje variant räknas om i båda riktningarna.
Resultatet visar förändringar i restidsmått, möjliga förbindelser,
upptagningsområden och befolkningsantal samt när en variant saknar möjlig resa.

## Data och reproducerbarhet

- Tidtabellsdata, kalenderundantag, gångnät och befolkningsunderlag ska anges
  med källa, version eller hämtningstid och geografisk täckning.
- Varje körning ska dokumentera datum, tidszon Europe/Stockholm,
  scenariofönster, starttidsurval, gånghastighet, bytesmarginaler,
  percentilmetod och befolkningsmetod.
- Kommandon och programversioner för att återskapa resultat ska sparas.
  Hemligheter hålls i lokal, ignorerad `.env`; stora rådata i ignorerade
  datakataloger.

## Verifiering och acceptanskriterier

Börja med små, reproducerbara testfall innan en full Skånekörning:

1. Visa en A–B-resa med buss, tåg, gång och byte på karta, med en sammanhängande
   tidskedja och restidsmåtten T50, T90, T99 och T90–T50.
2. Verifiera percentiler med ett känt starttidsurval och kontrollera
   T50 ≤ T90 ≤ T99 samt korrekt hantering av en omöjlig resa.
3. Jämför vardagspendling, kväll och helg med rätt trafikkalender.
4. Verifiera ankomst före passstart, hemresa efter passlut och ett pass över
   midnatt; en plats utan hemresa ska uteslutas.
5. Verifiera områden för 15/30/45/60 minuter och unik räkning av boende
   20–64 år med ett litet befolkningsunderlag och överlappande resvägar.
6. Kör känslighetsanalysen för −15/0/+15 minuter och redovisa skillnaderna.
7. Återskapa samma resultat från dokumenterade data, parametrar och kommandon.

## Senare version

Historiska förseningar och inställda turer ska senare möjliggöra empiriska
restidsfördelningar och bedömning av missade byten. Datatäckning och metod
för dessa mått specificeras separat innan de införs.
