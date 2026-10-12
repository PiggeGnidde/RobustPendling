# Pendling utan att passa en viss avgång

Avresefönstret beskriver när personen kan lämna startpunkten, exempelvis
06:30–07:59:59. Varje exakt startminut ges lika vikt. T50 och T90 beskriver
hur lång resan blir över dessa startminuter enligt tidtabell. T90−T50 visar
variation med starttid, men en liten skillnad räcker inte ensam: även total
restid, täckning och hela kurvan behöver granskas. Måttet är ingen uppskattning
av verklig försening eller sannolikheten att en viss resa kommer fram i tid.

## Exakt återanvändning av reskedjor

Den första startminuten söks med den befintliga oberoende tidtabellsmotorn.
För den valda kollektivtrafikresan är fordonsavgångar, byten, gång och
ankomsttid fasta. För senare startminuter återanvänds kedjan så länge
`första avgång > start + gång till påstigning + boardingmarginal`.
Total restid och väntan minskar med skillnaden i starttid. När första
avgången inte längre kan nås görs nästa fulla sökning.

Detta är exakt, inte en interpolation: senare start gör mängden möjliga
avgångar mindre. En nytillkommen resa inom den förskjutna restidshorisonten
ankommer senare än föregående optimum och kan därför inte slå det så länge
det fortfarande går att nå. Tie-break för gång och tur-/hållplats-ID påverkas
inte av att samma starttidsskillnad dras från alla fasta ankomsttider.

Ren gång jämförs separat eftersom dess ankomsttid förskjuts med starttiden.
Transit behöver då bara sökas inom gångalternativets restid. Minuter utan
kollektivtrafikresultat måste sökas på nytt: en senare minut kan bli nåbar
när restidshorisonten flyttas. Ej nåbara minuter behålls alltid som +∞.

## Kontroll och reproduktion

Alla minutobservationer finns fortfarande i JSON. Profilen testas mot den
gamla separata sökningen per minut, även med slumpade små nät, 1–4 ben,
gångalternativ, förbjuden avstigning, tie-break och ändlig horisont.
I den interaktiva körningen kontrollerar rå R5 profilens sökminuter, minuten
före varje ny sökning och sista minuten. Dessa index anges uttryckligen i
`verification.raw_r5_checked_indices`; ingen okontrollerad minut utges för
att ha fått en separat rå R5-körning. Detaljer hämtas som tidigare endast
för representativa minuter och senare vid klick.

Full kontroll av både profil och separat sökning, samt rå R5 för varje
minut, kan göras genom `scripts/analyze_t90.py --planner
--validate-every-minute` tillsammans med övriga indata. Det är avsiktligt
dyrare och används för validering, inte varje interaktiv fråga.

## Gånginställningar

Nya vyanalyser: 4,5 km/h, valbart 3–6; högst 20 minuter sammanlagd gång,
valbart 10–30. Budgeten omfattar startgång, bytesgång och slutgång. Samma
inställningar gäller basfall, detaljer, N−1 och dess återstående gångbudget.
API-fält är `walk_speed_kmh` och `max_walk_minutes`; de ingår i cacheidentitet
och fryst metadata. Originalförvalen behåller 3,6 km/h och 15 minuter.

R5 har ursprungligen gatubaserade byteslänkar upp till 1 km. När större
gångbudget behövs kompletteras nätverket en gång per process med WALK-länkar
över 1 km och upp till 3 km (6 km/h × 30 minuter). Befintliga länkar/regler
behålls; längre länkar filtreras efter aktuell hastighet och budget. Därmed
behöver nätverket inte byggas om vid inställningsändringar och gamla
15-minutersfall vid 3,6 km/h kan inte använda de tillagda länkarna.

Initial nätverksladdning, komplettering av byteslänkar och detaljgeometri
kostar fortfarande tid. Resultat utan användbar resa kan kräva en sökning
för varje minut. N−1 gör separata reservsökningar med befintlig cache; denna
optimering av basprofilen innebär inte att alla reservsökningar försvinner.
