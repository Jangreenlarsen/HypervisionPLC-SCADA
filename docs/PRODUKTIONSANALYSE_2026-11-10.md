# Produktionsanalyse — HypervisionPLC SCADA v5.0.0 (2026-11-10)

Spørgsmål fra Jan: *Er systemet grundlæggende gennemtænkt, så vi kan begynde at bruge det i produktion, og så der fremover kun er fejlretninger?*

**Kort svar:** Fundamentet er på plads og holder. Men systemet er **ikke klar til produktion i dag**, og der er **ikke kun fejlretninger tilbage**. Der mangler fire strukturelle oprydninger og en afprøvning på rigtigt udstyr, som ingen test i udviklingen kan erstatte. Med de punkter nedenfor er en pilot realistisk, og derefter en overgang til en fase med kun fejlretninger.

## 1. Det, der er gennemtænkt og bærer

| Område | Vurdering |
| --- | --- |
| **Lag og PLC-adgang** | Kun PLC-klientlaget taler med PLC'en (REST + SSE); browsere taler kun med SCADA. Reglen er overholdt i hele koden. Det er systemets vigtigste sikkerhedsgrænse, og den er ren. |
| **Live-data** | Én live-cache med kvalitet pr. værdi (good/comm_error), WebSocket-delta og pseudo-tags for afledte værdier (symbolpositioner, logik og nu signalveje). Samme mekanisme bruges overalt. |
| **Visningsmodellen** | Alt i Overview er "bindinger": eksplicitte, automatiske, symbolernes, gruppernes og signalvejenes. Én tegnemotor (`canvas.ts`/`animate.ts`) og én prioritetsregel. Nye funktioner kan bygges uden at røre Overview. Signalveje v5.0.0 var et eksempel på det. |
| **Sikkerhed** | Roller, adgang pr. tegning, håndhævet i backend (REST og WebSocket), audit-log på alle skrivninger, hemmeligheder uden for git og browseren, TLS, kode ved låste positioner. Kritiske ændringer er gennemgået af en uafhængig reviewer. |
| **Drift** | OTA-opdatering med automatisk tilbagerulning, planlagt backup til eksterne mål med validering ved gendannelse, Status/metrics, alarmer på kommunikationsfejl, systemd som ikke-privilegeret bruger. |
| **Data** | SQLite (WAL) med skemaversion og idempotente migreringer, cache med skrivetæller (`config_gen`), trends i egen database (kan flyttes til SSD). |
| **Test** | Backend ~1240 tests, frontend ~1017 tests, komponenttests af de interaktive guider og en reviewer-agent på kritiske ændringer. Ingen åbne fejl i BUGS.md. |

## 2. Det, der skal på plads før produktion

### A. Afprøvning på rigtigt udstyr (blokerende)
- **Raspberry Pi 4:** `docs/TEST_PI.md` siger selv, at netværk, DHCP-vagt, flytning af trend-databasen og vedligehold "intet er afprøvet på en rigtig Pi". LLM-pakkerne til Pi (aarch64) er heller ikke afprøvet. → Kør TEST_PI.md på en Pi og ret det, der dukker op.
- **Langtidskørsel (soak):** systemet har aldrig kørt uafbrudt i uger. Hukommelse, databasevækst (trend/audit/alarm-historik), WebSocket-klienter over døgn og genopkobling efter PLC-udfald er kun testet kortvarigt. → 2 uger på testserveren mod en rigtig PLC, og se Status-siden for lækager og vækst.
- **PLC-skrivninger på anlægget:** skriveveje, bekræftelse og låse er testet mod mock-PLC'en. → En FAT/SAT pr. anlæg: hver betjening afprøves én gang med en person ved anlægget, og resultatet noteres.

### B. Strukturel gæld, der ellers bliver ved med at give fejl
1. **To symbolmodeller i koden.** FEATURES.md: *Symbolstandard — fase 0–8 færdige, mangler kun at fjerne den gamle model*. `legacy_bindings` og `symbol_convert.py` lever stadig. To modeller ved siden af hinanden giver kanttilfælde ved hver ændring. → Konvertér og fjern den gamle model. Det er en MAJOR, men den gøres bedst nu, mens systemet er et udviklingssystem.
2. **Forbindelserne gættes ud fra geometri** (signalveje og Tjek forbindelser). v5.0.0 har gjort vejen til et robust objekt, men *hvor* vejen går, gættes stadig ud fra afstande i tegningen. Det er den største tilbageværende fejlkilde i Tegn. → Mulighed B fra signalvej-analysen: gør forbindelserne til data i tegningen (Ret/Tjek forbindelser skriver dem ned), og lad signalvejen bruge dem.
3. **Store filer:** `scada-core.js` (3387 linjer), `db.py` (1625), `DrawEditor.svelte` (1472), `symbols.py` (1421). De er ikke fejlbehæftede, men rettelser i dem er dyre og risikable. → Del dem langs naturlige grænser (som signalvejen blev delt i v4.15.1), når de alligevel røres.
4. **Bogføringen:** cirka 15 punkter i FEATURES.md står som "in-progress, afventer Jans test" helt tilbage fra v0.27–v0.53. → Gennemgå dem én gang, og markér dem som done eller som fejl. Ellers kan ingen se, hvad der faktisk er godkendt.

### C. Drift og proces
- **Udgivelsesdisciplin:** 444 commits siden 1. oktober og en build pr. ændring. Det er fint i udvikling, men i produktion skal `main` være stabil. → Indfør en **feature-frys** for produktionsgrenen: kun `fix:`-commits på main, nye funktioner på dev, og en udgivelse med release notes og en planlagt opdatering.
- **Lager på Pi'en:** SD-kort slides af SQLite (WAL) og trends. → Brug en USB-SSD til data (funktionen findes; test den i punkt A) og et industrielt SD-kort til systemet.
- **Tid:** live-værdier tidsstemples af SCADA-serveren. → Sørg for, at NTP kører på Pi'en (alarmer, trends og audit bygger på tiden), og vis gerne tidsfejl på Status.
- **Gendannelse:** backup valideres, men en rigtig gendannelse på en ny maskine er ikke øvet. → Lav en "katastrofeøvelse": ny Pi, gendan backup, og tjek at tegninger, tags, brugere og hemmeligheder (separat) virker.
- **Ekstern sikkerhedstest:** reviewer-agenten har gennemgået de kritiske ændringer, men ingen udefra har testet systemet. → Lad nogen anden prøve login, adgang pr. tegning og WebSocket-filteret, før systemet kommer på et net med flere brugere.
- **Certifikater:** Let's Encrypt er parkeret. Interne certifikater er OK på et lukket net.

## 3. Er der fremover kun fejlretninger?

**Ikke endnu, men tæt på.** Grundmodellen (PLC-lag, live-cache, bindinger, symbolstandard, alarmer, trends, adgang) skal ikke bygges om. Den kan bære nye funktioner uden at ændres. Det, der står tilbage og ikke er fejlretning, er afgrænset:

1. Fjern den gamle symbolmodel (B1).
2. Forbindelser som data (B2).
3. Pi-afprøvning og soak-test (A), som giver fejlretninger, men skal gøres.

Når de er gjort, er resten (nye symboler, nye visninger, forbedringer i Tegn) **tilføjelser oven på en stabil model**, ikke ombygninger.

## 4. Anbefalet vej

| Trin | Indhold | Resultat |
| --- | --- | --- |
| 1 | Fjern den gamle symbolmodel (B1), og ryd op i FEATURES.md (B4) | v6.0.0: én model |
| 2 | Forbindelser som data (B2) | Tegn uden gæt; signalveje og tjek på samme grundlag |
| 3 | Pi-afprøvning (TEST_PI.md), USB-SSD, NTP, katastrofeøvelse | Klar hardware og drift |
| 4 | Feature-frys på `main`, soak-test i 2 uger mod en rigtig PLC | Stabil udgivelse |
| 5 | **Pilot** på ét anlæg: først kun visning (ingen skrivninger), derefter betjening efter SAT | Produktion |
| 6 | Herefter: kun `fix:` på `main`; nye funktioner som MINOR fra `dev` | Fejlretningsfase |
