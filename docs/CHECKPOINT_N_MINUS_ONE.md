# Checkpoint inför sleep

**Återupptaget och slutkontrollerat 2026-10-12.** Checkpointen nedan är
historisk. 65 tester och kontroll av alla sex sparade artefakter passerade;
routingkod och indata var oförändrade och fullkörningarna upprepades inte.
Slutrapport finns i `docs/N_MINUS_ONE_VALIDATION.md`. Ingen server startades
vid slutkontrollen. Kod, tester och dokumentation förbereds för commit på
`codex/mvp`; ingen push eller ändring i main ingår.

Arbetet pausades på användarens begäran 2026-10-12. Inga nya körningar ska startas förrän arbetet återupptas.

- Worktree: `C:\Users\bengt\.codex\worktrees\a492\RobustPendling`
- Branch: `codex/mvp`
- HEAD: `c8453d125d98a42fadd2b00ea04194ef5eace7c6`
- N−1-ändringarna är sparade men ännu inte stageade eller committade. Ingen push har gjorts.

## Klart

N−1-motor, exakt turuteslutning, bevarad genomförd resa, villkorade sammanfattningar, oberoende validering, granskningsvy och Leaflet/OSM-bakgrund är implementerade. Kontrakt och valideringsrapport finns i `docs/N_MINUS_ONE.md` och `docs/N_MINUS_ONE_VALIDATION.md`.

De tre relationerna har körts två gånger med identiska analysresultat och GeoJSON. Varje repetition omfattar 241 tillämpliga och nåbara scenarier samt 119 ej tillämpliga scenarier. Basresultaten reproduceras. Alla sex sparade resultat passerar den oberoende valideringen, inklusive checksummegranskning.

63 tester passerade före de senaste mindre ändringarna i checksumme- och cachevalideringen. Webbläsargranskning har genomförts för alla tre relationer, kartbakgrund, genomförd del och reservväg, ej tillämpligt scenario samt kartfel och lokal SVG-fallback. En ny tvåminutersanalys och dess tidigare ocachade N−1-resultat har också hämtats genom vyn.

## Säker stoppunkt

Den lokala servern och routingworkern har stoppats ordnat. Servern avslutades med exitkod 0. Senaste workern, PID 28964, avslutades med exitkod 0 och dess temporära R5-katalog togs bort. Inga analyser eller tester pågår. Datorn kan sättas i sleep.

Diagnostik finns i den ignorerade filen `outputs/review/detail-worker-exit.json`. Reproducerbara resultat och kördiagnostik finns under ignorerade `outputs/nminus`. Sparad granskningsbild: `outputs/review/nminus-lomma.jpg`.

## Kvar före commit

1. Kör testsviten igen efter de senaste checksumme- och cachekontrollerna; komplettera checksummetest vid behov.
2. Granska slutdiffen och komplettera valideringsrapporten med webbläsargranskningen och slutligt testresultat.
3. Kontrollera att main är oförändrad och att endast kod, tester och dokumentation stageas. Data, lokal konfiguration, miljö, cache och resultat ska förbli ignorerade.
4. Committa det färdiga uppdraget på `codex/mvp`, rapportera commit-hash och git status. Pusha inte.

## Exakt återupptagning

Kör följande först när arbetet uttryckligen återupptas:

```powershell
Set-Location C:\Users\bengt\.codex\worktrees\a492\RobustPendling
git branch --show-current
git status --short
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B -m unittest discover -s tests -v
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/validate_nminus.py --check-existing
.\.venv\tools\Library\bin\micromamba.exe run -r .\.venv\mamba -n robustpendling python -B scripts/review_server.py
```

Öppna därefter `http://127.0.0.1:8765/` för eventuell sista visuell kontroll. Servern laddar då de senaste cachekontrollerna. De sex fullständiga routingkörningarna behöver inte upprepas om routinglogik och indata är oförändrade. Granska, dokumentera och committa enligt listan ovan.
