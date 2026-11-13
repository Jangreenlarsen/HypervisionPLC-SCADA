# Udgivelsesproces: `dev` og `main` (feature-frys)

Mål (produktionsanalysen, afsnit C): `main` skal være **stabil** og kun få rettelser, når systemet er i pilot/drift. Nye funktioner bygges på `dev`.

## Grene
| Gren | Indhold | Hvem tester |
| --- | --- | --- |
| `dev` | Alt arbejde, hver ændring får version og build (`version.json`) | Claude + Jan i udvikling |
| `main` | Kun det, der er testet og godkendt | Jan (accepttest, pilot) |

Der arbejdes aldrig direkte på `main`. Efter hver commit på `dev` spørges: *"Vil du også merge til `main`?"* — svaret ja merger `dev` → `main` med `--no-ff` (CLAUDE.md, regel 5).

## To faser
**Fase 1 — udvikling (i dag):** `main` følger `dev` efter Jans OK. Testserveren og demoen kører `main` eller `dev`-pakker.

**Fase 2 — pilot/drift (indføres, når Jan siger det):** *feature-frys.*
1. `main` får kun `fix:`-commits (og dokumentation). En ny funktion får `dev` og går først på `main` i en planlagt udgivelse.
2. En rettelse laves på `dev`, testes, og merges som en **fix-udgivelse** (PATCH: `5.7.0 → 5.7.1`). Fælder, der kun findes på `main`, hentes ned i `dev` med en merge, så grenene ikke glider fra hinanden.
3. En udgivelse (MINOR/MAJOR) har: release notes (`RELEASE_NOTES.md`), en OTA-pakke, en backup før opdatering (sker automatisk i OTA), og et tidspunkt aftalt med driften.
4. **Opdatering på anlæg:** hverken mid-dag eller uden en der kan se serveren. Efter opdateringen: `scada-tool status` og `scada-tool check`; ved problemer `scada-tool update rollback` (se manualen, kap. 13).

## Før en udgivelse på `main`
- [ ] Hele backend-suiten og frontend-suiten er grønne; `npm run build` uden fejl.
- [ ] Appen kan genstartes på eksisterende data (testen *starts again on existing data*).
- [ ] Reviewer har gennemgået alt, der rører adgang, PLC-skrivninger, data og backup.
- [ ] Accepttest for de berørte områder er afkrydset (`docs/ACCEPTTEST.md`).
- [ ] Pakken er afprøvet på testserveren (`scada-tool check` uden fejl), før den lægges på et anlæg.
- [ ] `CHANGELOG.md`, `RELEASE_NOTES.md`, `FEATURES.md` og `BUGS.md` er opdateret.

## Hvis en opdatering fejler
1. `scada-tool status` — hvor langt nåede den?
2. `scada-tool check` — hvorfor starter serveren ikke?
3. `scada-tool logs --fejl`.
4. Står opdateringen som "i gang": `scada-tool update reset`; ellers `scada-tool update rollback`.
5. Skriv fejlen i `BUGS.md`, ret på `dev`, byg ny pakke.
