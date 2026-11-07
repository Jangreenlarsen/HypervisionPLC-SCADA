# Plan: Manualen gennemgås — mere tekst, flere skærmbilleder, pænere indeks og en skjult LLM-manual (v4.9.0) — 2026-11-07 — godkendt (Jan) — ✅ v4.9.0

Ønske fra Jan: flere afsnit mangler skærmbilleder (fx logikblok), "De seks trin" har næsten ingen tekst, og den lokale LLM fejler, når manualen er for tynd. Indekset skal være pænere. Derudover (Jan): **en særlig manual til LLM'en, som brugerne ikke ser, men som holdes opdateret, når den store manual ændres.**

Måling (`manualstat.py`): 25.132 ord og 79 billeder. Ca. 35 afsnit har under 60 ord. Kap. 08 (Forbindelser) og 15 (Fejlfinding) har 0 billeder; i kap. 13 (System) mangler billeder til Status, Notifikationer, Integrationer, Certifikater og Hjælper.

## Valg: hvordan får LLM'en nok tekst? (3 alternativer)
1. **Kun skrive den store manual tykkere.** Det er godt for brugerne, men LLM'en har brug for korte "sådan gør du"-svar og synonymer. Det gør den læsbare manual tung.
2. **En separat LLM-manual, skrevet uafhængigt.** Den kan løbe ud af trit med den rigtige manual og give forkerte svar, og det var præcis fejlen med "symbol bag et andet".
3. **Valgt: en skjult LLM-manual, som *kompileres automatisk* ud fra den store manual (præcisering fra Jan).** Ingen håndskrevet kopi; den bygges ved hver build/OTA-pakke og er derfor altid opdateret.
   - Kompileren er `tools/compile-llm-manual` (Python i `backend/app/services/manual_compiler.py`, så serveren også kan bygge ved opstart). Den skriver `llm-manual.json`.
   - Hver del er selvstændig:
     - Den har **sti-kontekst** ("Tegn › Vælg › Symbol bag et andet").
     - **Tabeller er foldet ud** til sætninger, så "De seks trin" bliver ét stykke pr. trin.
     - Billedernes alt-tekster og knapnavne er med.
     - Interne links er slået op til navnet på målafsnittet.
     - Der er nøgleord/synonymer.
   - Hver del har en **reference** til afsnittet i den store manual (`07-tegn.md#anker`), så hjælperen altid kan henvise brugeren dertil.
   - Valgfrie **tillæg** i `manual/llm/*.md`: korte spørgsmål og svar pr. afsnit, bundet med `kilde:`+sha. En test fejler, når kildeafsnittet ændres, så tillæggene ikke kan løbe ud af trit.
   - Brugerne ser kun den store manual.

## Trin
1. **Store manual, tekst.** Udvid de tynde afsnit, størst først:
   - kap. 10 "De seks trin" deles i *Trin 1–6* med egen tekst og eget billede pr. trin;
   - kap. 10 "Logikblokke";
   - kap. 03 Alarmer;
   - kap. 08 Forbindelser;
   - kap. 13 System;
   - kap. 02 og 04.
2. **Skærmbilleder.** Udvid `tools/manual-screenshots.mjs` med:
   - logikblok-editoren;
   - De seks trin (ét billede pr. trin);
   - Forbindelser/Signalveje;
   - Hjælper-panelet;
   - System › Status/Notifikationer/Integrationer/Certifikater/Hjælper;
   - Alarmer › Forklar.

   De tages på den lokale testserver med demo-data. Den eksisterende test sikrer, at ingen billeder mangler eller er forældreløse.
3. **Indeks.** Manual-siden får:
   - kapitler grupperet (*Kom i gang · Drift · Opsætning · Tegning · System · Reference*) med ikon og en kort undertekst;
   - kun det aktive kapitels underafsnit foldet ud;
   - markering af det afsnit, man læser (scroll-spy), og "Til toppen";
   - søgning med resultater, der viser kapitel og uddrag;
   - på smal skærm: indekset som en udfoldelig menu.
4. **Kompileret LLM-manual.**
   - `manual_compiler.py`: opdeling, tabel→tekst, sti-kontekst, links og referencer. Den har tests.
   - `assist_knowledge` søger i de kompilerede dele og svarer med reference til den store manual.
   - Kompileringen køres i `make-package.sh` og ved opstart, hvis manualen er nyere.
   - Tillæg med sha-test, og de første tillæg skrives til spørgsmål, der fejlede.
5. **Måling.** `evalsearch.py` udvides til ca. 40 typiske spørgsmål, og træfprocenten (top 3) måles før og efter. Til sidst testes nogle spørgsmål mod Ministral på demoen.
6. Tests og build, visuel kontrol af Manual-siden (bred og smal), docs, version og OTA.

## Berørte filer (ca.)
- `frontend/src/manual/*.md` og ny `frontend/src/manual/llm/`
- `frontend/public/manual/*.png`
- `frontend/tools/manual-screenshots.mjs`
- `frontend/src/pages/Manual.svelte`
- `backend/app/services/assist_knowledge.py` og en ny test
- `deploy/install.sh` og `deploy/make-package.sh`

## Risici
- Det er meget tekst. Det deles i 2–3 commits (tekst+billeder → indeks → LLM-manual), så hver del kan ses for sig.
- sha-testen kan føles irriterende ved små rettelser i den store manual. Sync-scriptet gør det til ét kald, og det er netop meningen, at man skal se efter.
- Skærmbillederne skal tages med samme data og vinduesstørrelse som de eksisterende, så billederne ligner hinanden.

---

# Plan: Vælg LLM-model fra en liste — hentes fra GitHub releases (v4.4.0) — 2026-11-07 — godkendt (Jan: "to-tre varianter på GitHub") — ✅ v4.4.0

Ønske fra Jan: en administrator skal kunne vælge en model fra en liste under *System › Hjælper* uden selv at hente filer fra Hugging Face. LLM-pakkerne udgives derfor som **GitHub releases** i projektets repo, som SCADA-opdateringerne allerede er.

## Valg
| | Alternativ | + | − |
|---|---|---|---|
| **A** | **Færdige LLM-pakker som GitHub releases** (tag `llm-<model>-<llama-build>`), hentet af serveren | samme sted og samme sikkerhed som OTA (SHA256 i releasen); én kendt kilde; virker uden Hugging Face | GitHub tillader højst 2 GiB pr. fil, så pakkerne deles i dele |
| B | Serveren henter llama.cpp og modellen direkte fra GitHub og Hugging Face (`llm-models.json`) | ingen udgivelse | to eksterne kilder, Hugging Face-adresser kan forsvinde, og pakken bygges på serveren |
| C | Kun upload som nu | intet internet | det Jan vil undgå |

**Valg: A.** Upload (C) bevares til lukkede net.

## Trin
1. **Udgivelse:** `deploy/publish-llm-release.sh <arkitektur> <model-id>`:
   - bygger pakken med `make-llm-package.sh` og deler den i dele på 1,9 GB (`….tar.part01`, `….part02`);
   - lægger `….tar.sha256` (hele pakken) og `….tar.json` (manifest: model, størrelse, dele) ved siden af;
   - `gh release create llm-<model>-<build> --latest=false` (prerelease), så SCADA-opdateringerne (`/releases/latest`) aldrig forveksles med en LLM-pakke.
2. **Katalog:** `deploy/llm-models.json` følger med SCADA'en og er listen i UI'et: navn, størrelse, licens, anbefalet RAM/profil og release-tag pr. arkitektur. Kun modeller, der passer til profilen og arkitekturen, kan vælges.
3. **Backend** (`services/llm_catalog.py` + `api/assist.py`):
   - `GET /api/assist/catalog`: listen med status pr. model (installeret / kan hentes / passer ikke til hardwaren).
   - `POST /api/assist/download {model}` (admin):
     - tjekker diskplads (pakke + 1 GB + reserve);
     - henter delene fra GitHub (kun `github.com` og GitHubs download-domæner, ingen proxy fra miljøet, tidsgrænse) og sætter dem sammen i én fil, mens SHA256 beregnes;
     - sammenligner med `.sha256`;
     - klargør pakken som en uploadet pakke (`stage`, samme kontrol);
     - foregår i baggrunden med fremdrift (bytes/s, del x af y) og kan afbrydes. Audit `assist.download`.
   - Installation som i dag: *Installér og slå til* (root-hjælperen tjekker SHA256 igen).
4. **Frontend** (*System › Hjælper*): listen over modeller med størrelse, licens, anbefaling og hastighedsskøn; **Hent og installér** med fremdrift og **Afbryd**. *Upload LLM-pakke …* står under *Lukket net*.
5. **Første udgivelser:** Qwen3.5-4B og Qwen3-4B-Instruct-2507 til x86_64 (begge Apache-2.0; licenserne ligger i pakken). aarch64 (Pi 5) senere.
6. Manual, tests (falsk GitHub via MockTransport: dele, forkert SHA, for lidt plads, afbrudt), review, OTA og afprøvning på demo-VM'en.

## Risici
- **2 GiB pr. fil på GitHub:** løses med dele. Samlet SHA256 tjekkes to gange (SCADA og root-hjælperen).
- **Disk** (demo-VM: 10 GB): delene skrives direkte i den samlede fil, så den kun fylder én gang. Under installationen skal der være plads til både pakken og den udpakkede model. Det tjekkes før hentning, og ellers vises: *fjern den installerede model først*.
- **Kompromitteret GitHub-konto:** samme niveau som OTA i dag (SHA256 fra samme release). Noteres i manualen.
- **Licens:** Apache-2.0 tillader videreudgivelse med licensteksten, og den ligger i pakken (`LICENSES/`).

---

# Plan: Signalvej i Tegn (LLM-hjælper fase 2) — 2026-11-07 — godkendt (Jan) — fase 2a ✅ v4.2.0 — fase 2b ✅ v4.3.0

Mål: brugeren vælger **start** og **slut** i en tegning. Systemet finder rørvejen imellem og spørger om hvert symbol undervejs (ventil, pumpe, kontraventil …): *hvornår går der flow igennem?* Svarene samles til én betingelse, og alle rør på vejen får løbelys, der kører, når betingelsen er opfyldt. Brugeren skal ikke sætte hvert rør op for sig. Til sidst kan man **forklare med egne ord**, og hjælperen (LLM) udfylder svarene som forslag.

## Hvad findes allerede (grundlaget)
- Rør er `<path data-hv-pipe>` med enderne i `data-hv-from`/`data-hv-to` = `"<symbol-id>@fx,fy[,side]"` (svgedit-host/pipes.js). Et T-stykke er et symbol (`t_stykke`) med tre rør. Grafen kan altså bygges ud fra tegningen, deterministisk og uden LLM.
- Løbelys (`flow`) og logikblokke (AND/OR, op til 4 indgange, op til 8 blokke pr. element, kæder via `@L1`) findes i symbolopsætningen. Et løbelys kan have en logikblok som kilde (`@<element>:<blok>`), også fra et andet element.
- Symbolernes egne tilstande findes som pseudo-tags (position, tilstand), så en ventils *åben* kan bruges direkte, hvis ventilen er sat op.

## Valg: hvor gemmes signalvejen? (3 alternativer)
| | Alternativ | + | − |
|---|---|---|---|
| A | Kun som opsætning på rørene (logikblok på første rør, løbelys på alle) | ingen ny tabel | kan ikke vises/rettes som én signalvej; start/slut og svar går tabt |
| **B** | **Ny tabel `signal_paths`** (navn, tegning, start, slut, vej, svar) **+ opsætningen på rørene genereres ud fra den** | kan listes, rettes, slettes samlet; svar kan genåbnes; additiv tabel (MINOR) | to steder at holde i takt (løses: rørenes genererede dele mærkes `sp:<id>` og genskabes ved hver gem) |
| C | Egen runtime-motor for signalveje (uden rør-opsætning) | uafhængig | dobbelt logik ved siden af symbol-runtime; **fravalgt** |

**Valg: B.**

## Trin
**Fase 2a, v4.2.0: signalvej uden LLM**

> **Ændring under implementeringen:**
> - Grafen bygges i frontend (`scada-core.js connectionGraph` + `lib/signalPath.ts`), ikke i `services/signal_path.py`. Tilslutningspunkterne findes automatisk ud fra symbolernes geometri, og den kendes kun i browseren. Demo-tegningen bruger desuden rør-symboler og håndtegnede streger, ikke kun `data-hv-pipe`. Grafen skal derfor også kende sammenfaldende punkter og afgreninger midt på en streg.
> - Backend validerer alt (elementer, dele, tags) og gemmer.
> - Betingelserne er tags (til/fra eller sammenligning), fordi logikblokke ikke kan bruge pseudo-tags. Symbolets egne tags foreslås.
1. `services/signal_path.py` (deterministisk, testes grundigt):
   - graf fra tegningens aktive version: symboler = knuder, rør = kanter (begge ender fast);
   - korteste veje mellem start og slut: op til 3 alternativer og højst 40 led;
   - rollen for hvert symbol på vejen ud fra type:
     - **ventil** (kugleventil, magnetventil, motorventil, regventil): *åben?*;
     - **3-vejs** (trevejs_motorventil): *hvilken stilling leder fra indgang til udgang?*;
     - **pumpe/motor**: *kører?*;
     - **kontraventil**: retning, intet spørgsmål;
     - **T-stykke/bøjning/reduktion/flange**: passiv, intet spørgsmål;
     - **ukendt**: valgfrit spørgsmål;
   - rørets tegneretning mod vejens retning giver `reverse` pr. rør.
2. Tabel `signal_paths` (additiv) + `services/signal_paths.py` (CRUD). Ved gem:
   - **betingelsen:** svarene bliver til logikblokke på startrøret (op til 4 indgange pr. blok; flere kædes) med navnet *Signalvej: <navn>*;
   - **rørene:** hvert rør på vejen får et løbelys (kilde = blokken, retning efter vejen), mærket `sp:<id>`. Rørets øvrige opsætning bevares;
   - **validering og samtidighed:** alt valideres med den eksisterende `validate_config` og gemmes i én transaktion;
   - **ret og slet:** ved rettelse fjernes og genskabes de mærkede dele; ved sletning fjernes de.
3. API (`api/signal_paths.py`, tekniker og op, audit):
   - `POST /api/drawings/{id}/signal-paths/find` {start, slut} → veje + spørgsmål;
   - `GET`/`POST`/`PUT`/`DELETE` på `/signal-paths`.
4. Tegn: knappen **Signalvej …** og `lib/SignalPathGuide.svelte`:
   - (1) klik start- og slutsymbol;
   - (2) vejen fremhæves, og man kan vælge mellem alternativer;
   - (3) ét spørgsmål pr. symbol: tag/stilling/"altid", med svar foreslået ud fra symbolets egen opsætning;
   - (4) navn, farve og fart på løbelyset, forhåndsvisning, *Gem*;
   - listen over signalveje med *Ret* og *Slet*.

   Som *Ret tilslutningspunkter* kræver guiden, at tegningen er gemt (ingen kladde-ændringer). Ellers spørges der først.
5. Manual (*Tegn › Signalvej*, + skærmbilleder), tests, review (opsætning af mange elementer samlet = data-integritet), OTA.

**Fase 2b, v4.3.0: "Forklar med egne ord"**

6. I trin 3: et tekstfelt, fx *"vand fra kedlen til radiatorerne, når pumpe P1 kører og ventil V2 er åben"*.
7. Backend sender kun vejen (symbolernes navne og typer i rækkefølge) og kandidat-tags (navn, beskrivelse, enhed) til LLM'en og beder om et fast JSON-skema: `{element, kilde: tag|stilling|altid, tag?, cmp?, værdi?, stilling?}` pr. symbol.
8. Svaret valideres:
   - **symbol:** skal være på vejen;
   - **tag:** skal findes og være synligt;
   - **værdier:** stillinger og sammenligninger skal være gyldige.

   Ugyldige forslag kasseres og vises som *"ikke udfyldt"*. Forslagene udfyldes i guiden og markeres *forslag fra hjælperen*; **intet gemmes, før brugeren trykker Gem**. Svartiden er 1–3 min (kø, Stop). Uden LLM er knappen der ikke.

## Sikkerhed / integritet
- Kun tekniker og op. Alt skrives gennem den eksisterende validering af opsætninger. Én transaktion pr. gem, og audit på `signal_path.save`/`delete`.
- Kun læsning af tegningen. SVG'en ændres ikke; kun symbolopsætninger og den nye tabel.
- En kopi/backup før en signalvej overskriver eksisterende løbelys på et rør: guiden viser *"rør X har allerede løbelys — erstattes"*, og man skal bekræfte.
- LLM-delen: samme regler som fase 1 (data markeret som data, ingen adresser, kun forslag, rate-grænse).

## Risici
- **Rodede tegninger** (løse rørender, rør der rører hinanden uden T-stykke): de giver ingen kant i grafen. Guiden viser *"vejen stopper ved <rør> (løs ende)"* og peger på det.
- **Tegningen ændres efter en signalvej er gemt** (rør slettes eller tegnes om): ved åbning valideres vejen. Manglende rør markeres, og man kan *Find vejen igen*.
- **Grænser i logikken** (4 indgange, 8 blokke): højst 28 betingelser pr. signalvej. Det er rigeligt; guiden afviser flere.
- **Små modeller misforstår dansk fritekst:** kun forslag, valideres, brugeren godkender.

## Berørte filer (ca.)
- **Nye:**
  - backend: `services/signal_path.py`, `services/signal_paths.py`, `api/signal_paths.py`, `tests/test_signal_path*.py`;
  - frontend: `lib/SignalPathGuide.svelte`, `lib/signalPath.ts` + test.
- **Ændres:**
  - `storage/db.py` (tabel), `main.py`, `services/symbols.py` (fjern/genskab mærkede dele), `services/assistant.py` (2b);
  - `pages/DrawEditor.svelte`, manual 08/10, dokumentation.

---

# Plan: LLM-hjælper integreret i SCADA'en — 2026-11-06 — godkendt (Jan: lokal, én samlet pakke, til/fra) — fase 0 ✅ v4.0.0 — fase 1 ✅ v4.1.0

Baggrund og modelvalg: [docs/LLM_ANALYSE.md](docs/LLM_ANALYSE.md). Ønske fra Jan: en lokal LLM som **hjælper** i SCADA'en, der kører på VM'en (16 GB / 4 vCPU, kun CPU). Hardwaren angives ved installationen og åbner for LLM-funktionerne.

## Mål
- En **Hjælper** (sidepanel), der svarer på spørgsmål om anlægget og systemet, forklarer alarmer og trends, og hjælper i Tegn. Den foreslår fx signal- og rørveje ud fra en forklaring med egne ord.
- **Kun læsning og forslag.** Hjælperen skriver aldrig til en PLC og ændrer aldrig opsætning selv. Forslag anvendes af brugeren med de normale knapper, API'er og rettigheder.
- SCADA'en virker uændret uden LLM (Pi 4, lille VM, model ikke hentet).

## Arkitektur — alternativer
| | Alternativ | Fordele | Ulemper |
|---|---|---|---|
| **A** | **llama.cpp `llama-server` som egen systemd-service** på `127.0.0.1`; styres af en root-hjælper via `.path` (samme mønster som power/update) | Hurtigst på CPU, MIT, ét binært program, OpenAI-kompatibelt API, `json_schema`, fuld kontrol over CPU og RAM (cgroups) | Binært program og model skal installeres og opdateres |
| B | Ollama som service | Nem modelstyring (`pull`) | Større, ekstra dæmon, mindre kontrol over versioner og ressourcer |
| C | llama-cpp-python i SCADA-processen | Ingen ekstra service | Deler proces med live-data og alarmer. **Fravalgt** |

**Valg: A.** Klientlaget taler "OpenAI-kompatibelt", så en admin også kan pege på en **ekstern** server i LAN'et (URL + nøgle i `secrets.json`) med den samme kode, hvis VM'en er for lille. Ekstern kræver et eksplicit valg, fordi data så forlader maskinen.

### Lag
```
Frontend: Hjælper-panel (Tegn, Alarmer, Trends, Overview) ── /api/assist/* (+ SSE-strøm)
API-lag:  api/assist.py (rolle-tjek, pydantic)
Service:  services/assistant.py — samtale, værktøjer (kun læsning), validering, kø (1 ad gangen), tællere
          services/assist_tools.py — værktøjer, der kalder EKSISTERENDE services med brugerens rettigheder
          services/signal_path.py — grafsøgning i tegningen (deterministisk, ingen LLM)
Lag 4c:   backend/app/llm/client.py — ENESTE sted med HTTP til LLM'en (timeout, størrelsesgrænse, ingen hemmeligheder i log)
Service:  scada-llm.service (llama-server, 127.0.0.1:8091, lav prioritet, MemoryMax)
```
`ARCHITECTURE.md` får lag 4c (LLM-klient) med samme regler som undtagelserne for notifier/github: kun den konfigurerede adresse, `trust_env=False` og tidsgrænser.

## Trin
**Fase 0: hardwareprofil og LLM-service (infrastruktur)**
1. Hardwareprofil:
   - `install.sh --hw <pi4|pi5|vm-8|vm-16|vm-32>`;
   - uden parameteren foreslås en profil ud fra `nproc`, `MemTotal` og AVX2, og den skrives i `config/hw.json`;
   - *System › Konfiguration* viser og retter profilen (admin);
   - profilen bestemmer, om LLM kan slås til, og hvilken model der er standard.
2. `deploy/scada-llm.service` + `deploy/apply-llm.sh` (root, `.path`-udløst, samme sikkerhed som apply-power: flyt anmodningen, afvis symlinks, kendte handlinger):
   - **install:** hent llama-server-binær og model fra en fast liste med SHA256, eller brug en fil uploadet til `data/models/` (lukkede net);
   - **start**, **stop**, **skift model**;
   - systemd: bruger `scada-llm` (ikke `scada`), `CPUWeight=20`, `Nice=10`, `MemoryMax` efter profil, `--threads` = vCPU−1, `--parallel 1`.
3. `backend/app/llm/client.py` + `services/assistant.py` grundlag: `health`, `complete(json_schema)` og `stream`. Status, model, svartider og fejl vises på *Status* og i metrics (observability).
4. *System › Hjælper (LLM)* (admin): profil, slå til/fra, model (hentet/mangler, størrelse), lokal/ekstern, test-knap med svartid.

**Fase 1: Hjælper-panel med viden og læse-værktøjer**
5. Viden: manualen (`frontend/src/manual/*.md`) opdelt i afsnit og søgt med BM25 i ren Python. Det kræver ingen embeddings-model og ingen ny afhængighed. Bedste afsnit lægges i prompten, og svaret viser kilden ("Manual › Tags").
6. Værktøjer (kun læsning, med brugerens rolle og tegningsadgang som i `api/trends.py::_allowed`):
   - `aktive_alarmer`;
   - `tag_vaerdi(navne)`;
   - `trend_resume(tag, periode)`: min/max/middel/ændringer, ingen rådata;
   - `tegning_oversigt(id)`: symboler, navne, typer, bindinger;
   - `soeg_manual(tekst)`.

   Højst 4 værktøjstrin pr. spørgsmål og 60 s i alt. Svar strømmes til panelet.

   **Beslutning (v4.1.0, efter målingen på 2–4 tokens/s):** værktøjerne vælges deterministisk ud fra siden og spørgsmålets ord, ikke af modellen. Det giver ét LLM-kald i stedet for op til fire, og tekst fra anlægget kan ikke udløse værktøjskald. Tidsgrænsen er 90 s til første ord og 240 s i alt.
7. Panelet (Svelte):
   - kontekst følger siden (valgt alarm, åben tegning, valgt trend);
   - knappen *Forklar* ved en alarm;
   - samtalen gemmes kun i browserens session (ikke i DB). Audit `assist.ask` logger kun metadata: bruger, side, svartid og tokens.

**Fase 2: signalvej i Tegn**
8. `signal_path.py`:
   - graf fra `data-hv-from`/`data-hv-to` og symbolernes tilslutningspunkter;
   - korteste veje mellem start og slut;
   - symboler på vejen, der skal tolkes (ventil, 3-vejs motorventil, pumpe, kontraventil, forgrening).
9. Signalvej-guide **uden LLM**:
   - vælg start og slut, og vejen fremhæves;
   - spørgsmål pr. symbol (tag, stilling, retning);
   - løbelys/farve på rørene med en samlet betingelse (logik-blokke);
   - gemmes som en navngiven signalvej, der kan rettes.
10. *Forklar med egne ord*: LLM'en får vejen og kandidat-tags (kort prompt) og svarer i fast JSON-skema. Backend validerer (tags findes, stillinger gyldige, symboler på vejen), og svarene udfyldes i guiden, hvor brugeren godkender.

**Fase 3 — ✅ v4.10.0 (Jan 2026-11-07: "lave det"):** forslag til tags ud fra ST-variabler (beskrivelse + enhed), hjælp i symbolguiden (trin 2: kommando/tilbagemelding), opsummering af døgnets alarmer (tal beregnes deterministisk). Samme mønster som signalvejen: JSON-skema, validering, intet gemmes.

## Sikkerhed
- Ingen PLC-skrivning og ingen konfigurationsændringer fra LLM'en. Værktøjerne er rene læsefunktioner, der kalder services med brugerens rettigheder.
- Ingen hemmeligheder i prompts: PLC-adresser, adgangskoder, tokens og API-nøgler sendes aldrig med. Tags sendes med navn og enhed, ikke kilde.
- Prompt-injektion via elementnavne og alarmtekster: alt data fra anlægget markeres som data. Værktøjerne har ingen sideeffekter, og output valideres.
- Hvem må hvad:
  - operatør: hjælper med læse-værktøjer inden for egne tegninger;
  - tekniker: også signalvej;
  - admin: også opsætning.
- Rate-grænse pr. bruger og kø (1 ad gangen). Status viser kø og belastning.
- Ekstern LLM kun via eksplicit admin-valg, med advarsel. URL og nøgle er skriv-kun i `secrets.json`.

## Afhængigheder (kræver godkendelse)
- llama.cpp (`llama-server`, MIT) som binær fil på serveren, ikke i Python. Ingen nye Python-pakker; `httpx` findes.
- Modelfiler (GGUF), fx Qwen3.5-4B Q4_K_M (Apache-2.0) med Ministral-3-8B (Apache-2.0) som alternativ. Hentes separat, ikke i git eller OTA.

## Berørte filer (cirka)
- **Nye:**
  - `deploy/`: `scada-llm.service`, `hypervisionplc-scada-llm.path`/`.service`, `apply-llm.sh`, `llm-models.json`;
  - backend: `backend/app/llm/client.py`, `services/assistant.py`, `services/assist_tools.py`, `services/assist_knowledge.py`, `services/signal_path.py`, `api/assist.py`;
  - frontend: `frontend/src/lib/AssistPanel.svelte`, `pages/SystemAssist.svelte`, `lib/SignalPathGuide.svelte`.
- **Ændres:**
  - `deploy/install.sh` (`--hw`), `make-package.sh`;
  - `main.py`, `config.py`, `sysconfig.py`, `health.py`/`metrics.py`;
  - `App.svelte` (panel og menupunkt), `DrawEditor.svelte`;
  - `ARCHITECTURE.md`, manualen (nyt kapitel *Hjælperen*).

## Risici
- Svartid på 4 vCPU (15–40 s): korte prompts, strømmede svar, 4B-model og kø.
- Forkerte svar: kildehenvisninger, kun forslag, validering og brugerens godkendelse.
- RAM og CPU-konkurrence med SCADA: egen service med cgroup-grænser. Måles i fase 0, inden noget mere bygges.
- Mamba/MoE-modellers understøttelse i llama.cpp: standardmodellen er tæt (Qwen3.5-4B).

## Rækkefølge og versioner
Fase 0 → måling på VM'en (`docs/LLM_ANALYSE.md` § 7) → fase 1 → fase 2. Hver fase er sin egen MINOR-version med test, review (reviewer: sikkerhed, rettigheder, root-hjælperen) og OTA-pakke.

---

# Plan: Fjern PLC — flyt tags til en anden PLC eller fjern alt — 2026-11-06 — ✅ færdig (v3.34.0)

**Problem (Jan):** En PLC kan ikke fjernes. `PlcService.delete` afviser med 409, så længe PLC'en har tags. Hvert tag kan igen kun slettes, når ingen binding, symbolopsætning eller ugeprogram bruger det. Det er umuligt i praksis.

**Ønske:** Fjern-dialogen skal give to valg (Jan: "begge muligheder"):
1. **Flyt tags til en anden PLC**, fx når en PLC er udskiftet. Tags, bindinger, opsætninger og historik bevares, og kun kilden skifter fra `plcA:…` til `plcB:…`.
2. **Fjern alt:** PLC'en, dens tags og alle henvisninger til dem fjernes i én handling, efter en oversigt over konsekvenserne og en backup.

En PLC uden tags fjernes som i dag.

## Trin
1. **Backend** (`services/plc_removal.py`, ny; lag 2):
   - **`usage(key)`** giver tags (antal og navne), tegninger med bindinger, symbolopsætninger (også grupper), ugeprogrammer, trendvisninger, API-nøgler med tagsene i scope, aktive alarmer, antal tags med historik og de andre PLC'er, der kan flyttes til.
   - **`move(key, target)`:**
     - Hver kilde valideres med `TagService._validate` (skrivbarhed, energi og alarm). Ved fejl afbrydes der, før noget ændres, og listen over problemer vises.
     - Derefter opdateres `tags.source`/`plc` i én transaktion, og PLC'en og dens adgangskode slettes.
     - Til sidst `reload_plc` (begge PLC'er) og `reload_tags`.
   - **`remove_all(key)`:**
     - Først backup (`save_to_server("foer-plc-fjern")`). Fejler den, afbrydes der.
     - Derefter i én transaktion:
       - bindinger med tagsene (også `dir_tag`) slettes;
       - i symbolopsætninger og grupper fjernes animationer, der bruger tagsene, og signal-, fejl-, logik- og graf-henvisninger tømmes (symbolet skal sættes op igen);
       - ugeprogrammer på tagsene slettes;
       - tagsene fjernes fra trendvisninger og API-nøglers scope;
       - `alarm_state` slettes (alarmhændelser bevares som historik);
       - tags og PLC slettes.
     - Efter commit: trendhistorikken glemmes (`trend_recorder.forget`), adgangskoden slettes, og der reloades.
   - Alt logges og auditeres med optælling.
2. **API** (kun admin):
   - `GET /api/plcs/{key}/usage`;
   - `POST /api/plcs/{key}/remove` med `{mode: "move" | "all", target?, confirm: "<key>"}`. Ved "all" skal PLC'ens nøgle tastes som bekræftelse.
3. **Frontend:** `PlcRemove.svelte`, en dialog fra knappen *Fjern* på siden PLC'er:
   - en oversigt over konsekvenserne;
   - valget *Flyt tags til* (rulleliste med PLC'er) eller *Fjern alt* (tast nøglen);
   - resultat og fejl vises som tekst.
4. **Tests:**
   - flyt (kilder, bindinger og historik intakte; valideringsfejl ændrer intet);
   - fjern alt (alle henvisninger væk, backup-fil skrevet, alarmhændelser bevaret);
   - uden tags, roller og forkert bekræftelse;
   - frontend: hjælpefunktioner.
5. **Dokumentation:** manual (kapitlet om PLC'er og tags), CHANGELOG, RELEASE_NOTES, FEATURES og version 3.34.0.

## Risici
- Hovedbasen og trend-databasen er adskilte. Historikken slettes derfor først efter commit; fejler det, logges det, og en senere oprydning tager resten.
- Symboler, der mister animationer eller signaler, viser derefter "ikke sat op" og kan sættes op igen med guiden. Oversigten siger hvilke.
- Flyt til en PLC af en anden type (fx uden RTU/MBX): valideringen afviser samlet, før noget ændres.

---

# Plan: SVG-import af symboler + flere tegneredskaber i Tegn — 2026-11-06

**Mål (Jan 2026-11-06):**
- **Import af SVG-symboler:** flere filer ad gangen til biblioteket, SVG ind i en åben tegning, og bibliotekspakke (eksport/import af egne symboler med opsætning).
- **Nye tegneredskaber i Tegn:** polygon, stjerne og billede. Desuden stiplet streg, pile og linjeender, gradient og skygge, samt lag og z-orden.

**Rammer:**
- Al SVG saneres i backend (`svg_sanitize.py` tillader allerede `image` med raster-data-URI, `marker`, gradienter og `filter`/`feDropShadow`).
- Egne symboler følger reglerne fra del 1 (`library.py`: ét `<g>`, højst 256 KB, defs omdøbes til `def_*`).
- Ingen nye afhængigheder. Pakken er **JSON** (`.hvlib.json`), ikke zip, så der er ingen zip-bomber og ingen ny pakke.

## Del A — v3.31.0: import til biblioteket + Opsætning › Symboler (= del 2 af egne symboler) — ✅ færdig

1. **Backend `library.py`:**
   - `import_svg(user, filename, svg, label, section, replace)` gør hele filen til ét symbol. Den saneres, og viewBox (eller width/height) bliver til `translate`/`scale` ind i et 0-baseret `<g>`. Elementer med id bliver dele (`data-hv-pid`), og defs omdøbes. Der er ingen standardopsætning, kun grafik og dele.
   - Labelkonflikt giver en ny version (`replace`) eller et nyt navn med `_2`, som ved eksport.
2. **API:**
   - `POST /api/library/import` (engineer): multipart med én eller flere filer, højst 50 filer og 5 MB i alt. Svaret giver en status pr. fil (oprettet, ny version eller fejl med begrundelse). Hver fil auditeres.
   - `GET /api/library/package?types=…` (engineer) eksporterer egne symboler med grafik, preset, version og deres placering i opdelingen.
   - `POST /api/library/package` (engineer) importerer en pakke. Alt valideres som i backup (clean_fragment, check_preset), og der vælges mellem *spring over*, *ny version* og *nyt navn* ved konflikter. Pakkens tags medtages ikke.
3. **Frontend, Opsætning › Symboler (ny side):**
   - sektioner: opret, omdøb, slet, rækkefølge;
   - symboler: flyt og ordn, omdøb og slet egne symboler med "bruges i"-advarsel;
   - knapperne *Importér SVG…* (flere filer, vælg sektion, resultattabel), *Eksportér pakke* og *Importér pakke*.
4. **Tegn-paletten:** *Importér SVG…* i sektionen Egne symboler.
5. **Symboltest/symbol-editoren:** egne symboler kan vælges (rest fra del 1).
6. **Tests:**
   - backend: import af én og flere filer, viewBox-normalisering, script/ekstern href fjernet, for stor fil, labelkonflikt, pakke-roundtrip, pakke med ugyldigt preset;
   - frontend: hjælpere til opdelingen.
7. **Manual:** afsnit + skærmbilleder.

## Del B — v3.32.0: SVG ind i en åben tegning — ✅ færdig (endpoint: `POST /api/library/fragment`)
1. **Backend:** `POST /api/svg/sanitize` (engineer) returnerer en saneret SVG og advarsler, så frontenden aldrig indsætter usaneret SVG. Den gemte version saneres igen ved gem.
2. **Tegn:** *Indsæt › SVG-fil…* og træk og slip af en .svg på lærredet indsætter filen som én gruppe ved musen og skaleret til at passe. Defs-id'er omdøbes, så de ikke kolliderer med tegningens egne. Kan fortrydes. Gruppen kan derefter gemmes som symbol (del 1).
3. **Tests:** sanitize-endpointet, id-omdøbning (frontend-test).

## Del C — v3.33.0: nye tegneredskaber — ✅ færdig (+ bue-værktøj efter ønske fra Jan)
1. **Former:**
   - **polygon:** klik punkt for punkt, dobbeltklik afslutter;
   - **stjerne og regulær polygon:** træk, med antal hjørner og indre radius i Inspector;
   - **billede:** PNG/JPG/WebP/GIF indlejret som data-URI, højst 2 MB, med bevaret proportion.
   SVG-Edit's egne moduser (`polygon`/`star` via udvidelse, `image`) bruges, hvor de findes, ellers eget værktøj i `scada-core.js`.
2. **Streg** (Inspector):
   - stiplet/prikket/stiplet-prikket med `stroke-dasharray` (skaleres med stregtykkelsen);
   - pile i start og slut via `marker`, som oprettes i tegningens `<defs>` pr. farve;
   - `stroke-linecap` og `stroke-linejoin`.
3. **Gradient og skygge:**
   - fyld: ensfarvet, lineær (vinkel og 2 farver) eller radial;
   - skygge: til/fra, forskydning, sløring og farve via `filter`/`feDropShadow`.
   Defs genbruges og ryddes op, når de ikke længere bruges.
4. **Lag og z-orden:**
   - lagpanel i objekttræet: opret, omdøb, skjul, lås, slet (tomt lag) og flyt markerede til lag;
   - z-orden: ét trin op eller ned (+ Ctrl+[ ]).
5. **Hvidlisten** i `scada-core.js:1789` udvides med `stroke-dasharray`, `stroke-linecap`, `stroke-linejoin`, `marker-start`/`marker-end`, `filter` og `fill-opacity`. Kopiér, indsæt, symbol-eksport og Erstat med symbol tager markører, gradienter og filtre med, hvilket del 1's def-kopiering allerede håndterer.
6. **Tests:** engine-hjælpere (dash-skalering, markør-/gradient-defs, oprydning, lag-operationer), backend roundtrip af en tegning med alle nye elementer gennem sanitizeren.
7. **Manual:** afsnit om værktøjerne, opdaterede skærmbilleder af værktøjslinjen og Inspector.

## Risici
- **SVG-Edit 7's polygon/stjerne** er udvidelser, der måske ikke er med i `@svgedit/svgcanvas`. I så fald bygges et eget værktøj (mere arbejde i C1).
- **Billeder gør tegningerne store** (grænsen er 5 MB pr. tegning). Derfor maks 2 MB pr. billede og en tydelig fejl ved for stor tegning.
- **Lag:** symbolkonfigurationer er knyttet til element-id, ikke lag, så det er sikkert at flytte mellem lag. Låste lag skal også respekteres af markering med træk.
- **Overview's live-binding** skal tåle `filter`/`marker` på bundne elementer (fill-animationer må ikke overskrive gradient-fyld utilsigtet). Det tjekkes visuelt.

Rækkefølge: A → B → C. Hver del er sin egen MINOR-version med commit, OTA og merge-spørgsmål.

---

# Plan: Egne symboler — eksport fra Tegn til symbolbiblioteket — 2026-11-05

**Mål:** en tekniker/admin kan markere et objekt eller en gruppe i Tegn og gemme det som et nyt symbol i biblioteket — med alt hvad et bibliotekssymbol har: grafik, navngivne dele, tilslutningspunkter og standardopsætning (betjeningsform, positioner, signaler, kontaktplaner, animationer, graf). Symbolet kan derefter indsættes, sættes op med guiden og afprøves i Symboltest som de indbyggede. Biblioteket kan organiseres: egne sektioner, flytte symboler (også indbyggede) mellem sektioner og ordne dem.

**Jans krav (2026-11-05):** (1) kun admin og tekniker · (2) nye symboler med alt hvad det indebærer · (3) i en "Egne symboler"-sektion, gerne organisering af symboler generelt · (4) ingen automatisk opdatering af tegninger — en ny version af et symbol tages i brug med den eksisterende *Erstat med symbol*.

## Arkitekturvalg

Hvor bor egne symboler?
- (a) Statisk fil i frontend-bygget — kræver nyt build/OTA for hvert symbol. Fravalgt.
- (b) Som "skabelon-tegninger" i drawings-tabellen — genbruger versionering, men blander tegninger og bibliotek. Fravalgt.
- (c) **Valgt:** egne tabeller i SQLite + REST under `/api/library`; frontend fletter dem ind i `SYMBOLS`. Følger mønstret fra tilslutningspunkterne (`symbol_ports`), kommer med i backup, og SVG renses på serveren med den eksisterende `svg_sanitize`.

## Datamodel (ny, additiv — ingen ændring af eksisterende tabeller)

- `library_symbols`: `type` (PK, `u_<slug>` — kan ikke kollidere med indbyggede), `label`, `hint`, `svg` (renset fragment, ét `<g>`, ≤ 256 KB), `preset` (JSON: standardopsætning med del-navne i stedet for element-id'er, tags fjernet), `ports` (JSON), `version` (int, +1 ved hver gem), `created_by`, `updated_by`, `updated_at`.
- `library_sections`: `id`, `label`, `sort` — egne sektioner; "Egne symboler" oprettes automatisk.
- `library_layout`: `type` → `section` + `sort` — placering/rækkefølge for ALLE symboler (indbyggede og egne); uden række står et indbygget symbol i sin oprindelige kategori.

## Trin

1. **Backend** (`services/library.py`, `api/library.py`, `storage/db.py`):
   - `GET /api/library` (VIEWER) → egne symboler, sektioner, layout.
   - `POST/PUT/DELETE /api/library/symbols/{type}` (ENGINEER): rens SVG, validér preset med den eksisterende `validate_config`, ports med `clean_ports`; navn unikt; version +1.
   - `PUT /api/library/layout`, sektioner CRUD (ENGINEER); en sektion med symboler kan ikke slettes.
   - Audit-log + struktureret log på alle ændringer; antal egne symboler på Status/`/metrics`.
   - Med i backup/gendan (validering som `symbol_ports`). Tests.
2. **Udtræk fra Tegn** (`lib/symbolExport.ts`, ren funktion + tests): markering → ét `<g>` flyttet til (0,0); `data-hv-pid` og id'er bliver delnavne (unikke, `[a-z0-9_]`); instans-attributter (`data-hv-name`, rod-id) fjernes; indlejrede bibliotekssymbolers opsætninger flettes til ét preset med del-referencer. Tags fjernes som standard (valg: "behold tags").
3. **Dialogen "Gem som symbol"** i Tegn (Egenskaber-panelet for valgt objekt/gruppe): navn, forklaring, sektion, forhåndsvisning, valget om tags; "Gem som ny version" når navnet findes. Forhåndsvisning i dialogen.
4. **Biblioteket i frontend**: `SYMBOLS` + egne → én kilde (`lib/library.ts`), brugt af paletten i Tegn, *Erstat med symbol*, Symboltest, symbol-editoren og objekttræet; `libraryDefault()` bruger et eget symbols preset. Sektioner og rækkefølge fra layoutet.
5. **Organisering** (Opsætning › Symboler): sektioner (opret/omdøb/slet/ordn), flyt symboler mellem sektioner og ordn dem, omdøb/slet egne symboler, se version og hvem der gemte.
6. **Manual** (nyt afsnit + skærmbilleder af dialogen og organiseringen), CHANGELOG/RELEASE_NOTES, version (MINOR), OTA-pakke, set i browseren.

## Berørte filer
Backend: `storage/db.py`, `services/library.py` (ny), `api/library.py` (ny), `api/routes.py`, `services/backup.py`, tests. Frontend: `lib/library.ts` (ny), `lib/symbolExport.ts` (ny), `pages/DrawEditor.svelte`, `lib/SymbolReplace.svelte`, `pages/SymbolEditor.svelte`, `pages/SymbolTest.svelte`, `lib/draw/ObjectTree.svelte`, `lib/symbolConfig.ts`, `svgedit-host/scada-core.js` (kun hvis indsættelsen skal kende egne typer), manual.

## Risici / åbne punkter
- **Sammenfletning af flere opsatte symboler**: en gruppe med fx to knapper har to betjeningsformer, men et symbol har kun én. Valgt regel: animationer flettes altid; højst ét indlejret symbol må have betjening (ellers vises en fejl, der peger på hvilke); loft 12 animationer/8 signaler som i dag.
- **Sikkerhed**: SVG fra brugere → renses på serveren (samme regler som tegninger), størrelsesloft, kun ENGINEER skriver.
- **Sletning af et symbol, der bruges i tegninger**: tegningerne beholder deres kopi (symboler er altid kopier); dialogen viser hvor mange tegninger der bruger typen.
- **Versionering af SCADA'en**: nye tabeller er additive (ingen migration af eksisterende data) → MINOR-bump.
- Omfanget er stort — leveres i to commits: (1) backend + bibliotek + eksport, (2) organisering + manual.
