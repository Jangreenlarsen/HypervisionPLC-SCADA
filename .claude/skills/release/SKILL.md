---
name: release
description: Afslut en kodeændring — versionsbump, CHANGELOG/RELEASE_NOTES, commit, push til dev, OTA-pakke, deploy til scada.laces.dk og kontrol af tegningerne. Brug når en ændring er implementeret og testet og skal ud (/release [bug|feature|build]).
---

Kør trinnene i rækkefølge og stop ved første fejl. Forudsætning: arbejdet er på `dev`, tests/build er kørt (CLAUDE.md regel 8 og 10), og FEATURES.md/BUGS.md er opdateret. Doku-only commits: spring trin 1, 5, 6 og 7 over.

1. **Type**: `bug` → `patch`, `feature` → `minor`, ellers `build` (se regel 1; `major` kun ved skema-migration). Kør `python deploy/bump_version.py <type>` og notér den nye version.
2. **Dokumentation** efter ændringens størrelse:
   - Altid: entry øverst i `CHANGELOG.md` (`## [version build NNNN] — YYYY-MM-DD — beskrivelse`, berørte filer).
   - `RELEASE_NOTES.md` når brugeren kan mærke ændringen (feature, synlig fejlrettelse). Rent interne ændringer kan springe den over.
   - Feature: sæt status i `FEATURES.md`. Bug: løsning i `BUGS.md`. Ændret UI: manualtekst og berørte skærmbilleder i samme commit.
3. **Commit** kun de berørte filer (aldrig `git add -A`): `vX.Y.Z-bNNNN: beskrivelse`. `.githooks/pre-commit` afviser commit på `main`, nøgler i indekset, manglende versionsbump og manglende CHANGELOG-entry; ret årsagen i stedet for at omgå den.
4. **Push** `origin dev` uden at spørge.
5. **OTA-pakke**: `sh deploy/make-package.sh` → `scada-<version>-b<build>.tar` i projektets rod. Kontrollér at navnet matcher `version.json`.
6. **Deploy til demoen** (altid, uden at spørge): hent login til scada.laces.dk fra memory `demo-plc-access`, og sæt det kun som miljøvariabler på selve kommandoen (aldrig i filer, logs eller svar):
   `SCADA_USER=… SCADA_PASS=… PYTHONIOENCODING=utf-8 python deploy/ota_deploy.py https://scada.laces.dk`
   Scriptet logger ind, uploader, anvender, venter på ny version i `/api/health` og kører `audit_drawings.py` (kun læsning). Returkode 3 = auditten fandt problemer.
7. **Afrapportér kort**: version og build, pakkens filnavn/størrelse/SHA256, om deployen lykkedes (og backupnavn fra apply-svaret), og audit-resultatet sammenlignet med forrige kørsel. Nye flow-beskeder, bindinger uden element eller manglende tags tages alvorligt før næste opgave.
8. **Spørg**: *"Vil du også merge til `main`?"* — ja/"main" = merge `dev` → `main` med `--no-ff` og push `origin main`. Har Jan sagt "merge automatisk i denne session", spring spørgsmålet over, og meld at det er sket.
