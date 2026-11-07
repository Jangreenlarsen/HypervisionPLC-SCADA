# Analyse: lokal LLM til tolkning af signal- og rørveje — 2026-11-06

**Formål:** hjælp i Tegn til at finde en signal- eller rørvej mellem to dele af anlægget og tolke symbolerne på vejen. Brugeren forklarer med egne ord, hvad vejen skal bruges til, og får løbelys/animationer som forslag. Det sparer opsætning af hvert element med signaler og animationer.

**Rammer:**
- Kører på en VM med op til **16 GB RAM og 4 vCPU, uden GPU** (ikke længere kun Raspberry Pi).
- Hardwaren angives ved installationen og afgør, om LLM-funktionerne kan slås til.
- Licens: AGPL-3.0-or-later. Kode og modeller skal have en kompatibel licens (Apache-2.0, MIT, …).
- Al PLC-kommunikation sker kun via PLC-klienten. LLM'en skriver **aldrig** til PLC'en og ser **aldrig** hemmeligheder.

Status: analyse, ingen beslutning om implementering endnu. Tal for hastighed er skøn og skal måles på den rigtige VM (se *Måleplan*).

---

## 1. Hvad skal modellen — og hvad skal den ikke

Det meste kræver **ingen AI**. Tegninger gemmer allerede, hvilket symbol og tilslutningspunkt hver forbindelse sidder i (`data-hv-from` / `data-hv-to`). Tegningen er altså en graf af symboler og forbindelser.

| Opgave | Løses af | Hvorfor |
|---|---|---|
| Find vejen mellem start og slut (rør, T-stykker, ventiler, pumper) | **Grafsøgning** (deterministisk) | Hurtig, korrekt, kan testes, også på Pi |
| Liste over symboler på vejen, der skal tolkes (ventil, 3-vejs motorventil, pumpe, kontraventil, forgrening) | **Regler** pr. symboltype | Kendte typer i biblioteket |
| Spørgsmål pr. symbol ("hvilken stilling åbner denne vej?") | **Guide** med faste svarmuligheder | Brugeren bekræfter alligevel |
| Animationer: løbelys på rørene med betingelse (fx `M1 = AB-A OG P1 kører`) | **Generator**, der bruger guidens logik-blokke | Findes allerede i symbolopsætningen |
| *"Vis varmen fra pillefyret til huset, når M1 står i AB-A"* → start, slut og betingelser | **LLM** (valgfri) | Fri tekst på dansk |
| Forslag til tags pr. symbol ud fra navne (`M1_pos`, `P1_drift` …) | Først simpel navnematch; LLM som supplement | Navnematch klarer det meste |

**Princip:** LLM'en laver kun **udkast** i et fast JSON-format, som valideres i backend: findes tagget, ligger symbolet på vejen, er stillingen gyldig. Udkastet vises i guiden, hvor brugeren retter og godkender. Mangler LLM'en, eller fejler den, virker guiden præcis som uden.

## 2. Hardware og hvad den rækker til

CPU-inferens (llama.cpp) er begrænset af **hukommelsesbåndbredde** ved generering og af **regnekraft** ved indlæsning af prompten. En vCPU er typisk en hyperthread, så 4 vCPU ≈ 2–4 fysiske kerner.

Skøn for 4 vCPU med AVX2 og Q4_K_M-kvantisering:

| Model | Fil ca. | RAM i drift ca. | Generering | Indlæsning af prompt |
|---|---|---|---|---|
| 3–4B tæt | 2–2,5 GB | 3–4 GB | ~6–12 tokens/s | ~30–80 tokens/s |
| 8–9B tæt | 5–5,5 GB | 6–8 GB | ~3–6 tokens/s | ~10–30 tokens/s |
| MoE 7B, 1B aktiv (Granite 4.0 H-Tiny) | ~4 GB | ~5 GB | ~15–25 tokens/s | ~60–150 tokens/s |
| MoE 30–35B, 3B aktiv (Qwen3/3.5-A3B) | 17–20 GB | > 16 GB | — | **passer ikke** ved siden af SCADA |

Til sammenligning: en offentlig måling af en 7B-model (Llama 2, Q4_K_M) på en VM med 4 vCPU Xeon gav ca. 3,6–4 tokens/s. Det passer med skønnet.

**Konsekvenser for designet:**
- **Korte prompts.** Send kun vejen: en liste af symboler med type, navn og kandidat-tags. Aldrig hele SVG'en. 1.000 tokens prompt + 200 tokens svar ≈ 15–40 s for en 4B-model, og en hel tegning ville tage minutter.
- **Svar som JSON med fast skema** (llama.cpp's `json_schema`/grammatik), så modellen ikke kan svare uden for formatet. Det gør små modeller langt mere pålidelige.
- **Asynkront:** "Foreslår …" med fremdrift. Guiden må aldrig blokere.
- **SCADA'en først.** LLM'en kører som **egen proces og systemd-service** med lav prioritet (`CPUWeight`, `Nice`, `MemoryMax`). Live-data, alarmer og WebSocket må aldrig sulte. Højst én forespørgsel ad gangen.
- **VM-opsætning:** CPU-typen skal give AVX2 videre (fx `host` i Proxmox). Ellers bliver llama.cpp flere gange langsommere.

## 3. Modelkandidater (november 2026)

Kun modeller med åbne vægte og **Apache-2.0 eller MIT**. Licenserne skal tjekkes på modelkortet (LICENSE-filen på Hugging Face), før en model tages med.

| Model | Størrelse | Licens | Styrker | Svagheder | Vurdering |
|---|---|---|---|---|---|
| **Qwen3.5-4B** (instruct) | 4B tæt | Apache-2.0 | Stærk for størrelsen, mange sprog, lang kontekst (262K), god til JSON/værktøjer | Dansk ikke dokumenteret særskilt (skal testes) | **Primær kandidat** til 16 GB |
| **Ministral-3-8B-Instruct-2512** | 8B tæt | Apache-2.0 | Indbygget function calling og JSON-output, europæiske sprog, 256K kontekst | Halv hastighed af 4B | **Kvalitetsvalg**, hvis 4B ikke rækker |
| **Ministral-3-3B-Instruct-2512** | 3B tæt | Apache-2.0 | Samme familie, hurtig, function calling | Mindre præcis | Let profil |
| **Qwen3.5-9B** | 9B tæt | Apache-2.0 | Bedste kvalitet i klassen | ~3–5 tokens/s på 4 vCPU | Kun ved 8 vCPU eller højere |
| **Gemma 4 (E4B/4B)** | ~4B | Apache-2.0 (ifølge kilderne; Gemma 3 og ældre havde egne vilkår) | Function calling indbygget, multimodal | Licensen skal bekræftes på Googles side | Kandidat, når licensen er bekræftet |
| **Granite 4.0 H-Tiny** | 7B MoE, 1B aktiv | Apache-2.0 | Meget hurtig på CPU, lavet til tool use | Mamba-hybrid (llama.cpp-understøttelse skal være moden), dansk sandsynligvis svagere | Hastighedsvalg / fallback |
| **Phi-4-mini** | 3,8B | MIT | God engelsk ræsonnering, MIT | Svagere på dansk | Kun hvis prompts er på engelsk |
| **EuroLLM-9B** | 9B | Apache-2.0 (sandsynligt, bekræftes) | Bedst dokumenteret dansk (alle EU-sprog) | Kun 4K kontekst, svagere til værktøjer/JSON | Reserve, hvis dansk er problemet |

**Fravalgt:**

| Model | Grund |
|---|---|
| Llama 3.x/4 | Llama Community License med vilkår (brugergrænse, navngivning); ikke en ren open source-licens |
| Gemma 3 og ældre | Gemma Terms of Use |
| Qwen2.5-3B | Qwen Research License |
| MoE-modeller med ~3B aktive parametre og 30B+ i alt | Passer ikke i RAM ved siden af SCADA på 16 GB |

**Dansk:** Modellen får dansk tekst, men svarer kun i JSON med navne og tags fra tegningen. Den skal altså *forstå* dansk, ikke skrive pænt dansk. Det sænker kravet betydeligt. Det skal testes med rigtige formuleringer (se *Måleplan*).

## 4. Runtime: hvad kører modellen

| Alternativ | Licens | Fordele | Ulemper |
|---|---|---|---|
| **llama.cpp `llama-server`** (separat proces) | MIT | Hurtigst på CPU, OpenAI-kompatibelt API på `localhost`, `json_schema`/grammatik, én binær fil, ingen Python-afhængigheder i SCADA'en | Skal bygges/hentes til arkitekturen |
| Ollama | MIT | Nem modelstyring | Ekstra lag og dæmon, mindre kontrol over ressourcer og versioner |
| llama-cpp-python (i SCADA-processen) | MIT | Ingen ekstra service | **Deler proces med SCADA'en**: hukommelse og CPU-spidser rammer live-data. Fravælges |
| ONNX Runtime GenAI | MIT | Bred hardware | Færre modeller klar, mere arbejde |

**Anbefaling:** `llama-server` som valgfri systemd-service, `scada-llm.service`:
- lytter kun på `127.0.0.1`;
- lav CPU-prioritet og `MemoryMax`;
- modelfilen ligger i `data/models/`, ikke i git og ikke i OTA-pakken (2–5 GB);
- modellen hentes én gang, og SHA256 kontrolleres mod en fast liste.

SCADA-backend kalder den via et nyt, lille klientlag (`backend/app/assist/`) med timeout. Det er ikke et PLC-kald, så reglen om PLC-klient-laget brydes ikke.

## 5. Hardwareprofil ved installation

Ved installation (og under *System › Konfiguration*) angives hardwaren. Backend foreslår selv ud fra RAM, kerner og AVX2, og admin bekræfter.

| Profil | Eksempel | LLM | Standardmodel |
|---|---|---|---|
| `pi4` | Raspberry Pi 4, 4–8 GB | Fra (guiden virker uden) | — |
| `pi5` | Raspberry Pi 5, 8–16 GB | Kan slås til (langsomt) | Ministral-3-3B / Qwen3.5-2B |
| `vm-8` | VM 8 GB / 2–4 vCPU | Kan slås til | Qwen3.5-4B Q4 |
| `vm-16` | VM 16 GB / 4 vCPU | **Til som standard** | Qwen3.5-4B Q4 (eller Ministral-3-8B) |
| `vm-32+` | VM 32 GB / 8+ vCPU | Til | Qwen3.5-9B / Ministral-3-8B Q5 |

- Profilen gemmes i konfigurationen (`hw_profile`) og vises på *Status* sammen med LLM-servicens tilstand: kører, model, sidste svartid og antal forespørgsler.
- Funktionerne skjules i UI'et, når LLM er fra. Backend afviser kaldene, så det ikke kun er UI'et, der styrer det.
- **Observability:** log pr. forespørgsel (tid, tokens, valideringsfejl, men ikke brugerens tekst på INFO), tællere på *Status* og metrics.

## 6. Risici

| Risiko | Modtræk |
|---|---|
| Forkert forslag (forkert ventilstilling) | Kun udkast; brugeren godkender; backend validerer mod tegning og tags; Symboltest/forhåndsvisning før gem |
| SCADA'en bliver langsom | Egen service med lav prioritet og hukommelsesloft; én forespørgsel ad gangen; timeout |
| Svartid 30–60 s irriterer | Korte prompts, 4B-model, fremdrift i UI; guiden kan bruges imens |
| Modelfil på 2–5 GB i et lukket net | Manuel upload af modelfil (`.gguf`) med SHA256-kontrol |
| Licens | Kun Apache-2.0/MIT; LICENSE-filen gemmes ved siden af modellen; listen opdateres i `docs/` |
| Prompt-injektion via elementnavne i tegningen | Modellen har ingen værktøjer med sideeffekter; output er kun data, der valideres |

## 7. Måleplan (før modelvalget låses)

1. **Testsæt** fra demo-tegningen `varme` (pillefyr, brændefyr, akkutank, M1/M2 med AB-A/AB-B, P1/P2 og driftsmodes): 25–30 danske forklaringer med forventet JSON (start, slut, betingelser, tags).
2. **Kandidater:**
   - Qwen3.5-4B, Ministral-3-3B og -8B, Gemma 4 E4B (hvis licensen er bekræftet), Granite 4.0 H-Tiny;
   - hver i Q4_K_M og Q5_K_M.
3. **Mål på den rigtige VM (4 vCPU / 16 GB):**
   - `llama-bench` (prompt og generering i tokens/s);
   - svartid for hele forespørgslen;
   - RAM;
   - andel gyldige JSON-svar;
   - andel korrekte svar;
   - SCADA'ens svartider og WebSocket-forsinkelse **mens** modellen arbejder.
4. **Vælg** den mindste model, der har mindst 85 % korrekte udkast og under 30 s pr. vej. Resultaterne skrives ind her.

### Første måling — demo-VM'en (2026-11-07, v4.0.1)

Maskinen: VM med 4 vCPU (AMD Ryzen Embedded V1500B, AVX2) og 15 GB RAM. Profil vm-16: 3 tråde og MemoryMax 9 GB. Model: Qwen3.5-4B Q4_K_M og llama.cpp b12179.

| Måling | Resultat |
|---|---|
| Selvtest (58 → 38 tokens, JSON-skema, dansk) | 10,4–10,5 s (første kald efter start: 18 s) — ca. 3,6 tokens/s samlet |
| RAM i LLM-tjenesten | 2,0 GB (loft 9 GB); VM'en havde 12,5 GB ledigt |
| SCADA'ens event-loop-lag under kaldet | maks. 0,052 s (0,043 s uden) — ingen mærkbar påvirkning |
| PLC-polling under kaldet | ok, ingen fejl |
| Gyldigt JSON-svar på dansk | ja, 5/5 |

**Konklusion:** V1500B er en svag CPU, så hastigheden ligger under skønnet i § 2. Hjælperens svar skal derfor være korte, og prompts små. Et typisk svar på 100–150 tokens tager 30–45 s. Qwen3.5-4B er det rigtige valg på denne maskine: en 8B-model ville give ca. 1,5 tokens/s. Er hastigheden for lav i praksis, kan Qwen3.5-2B prøves (ca. dobbelt så hurtig).

### Anden måling — hjælper-panelet (2026-11-07, v4.1.0)

Spørgsmålet *"Hvordan kvitterer jeg en alarm?"* fra siden Alarmer: 643 tokens ind (systemprompt, 5 aktive alarmer, 2 manualafsnit), 177–183 tokens ud. Svaret var korrekt og på godt dansk med kilde.

| Måling | 1. kald | 2. kald |
|---|---|---|
| Læsning af prompten | 120 s | 82 s (systemprompten genbrugt) |
| I alt | 191 s | 154 s |
| Skrivehastighed | ca. 2,5 tokens/s | ca. 2,5 tokens/s |

**Læsningen af prompten dominerer** (ca. 6–8 tokens/s på denne CPU). Det er langt under skønnet i § 2. v4.1.1 halverer derfor data i prompten (højst 2000 tegn), og svaret begrænses til ca. 80 ord. Det forventede resultat er ca. 1–1½ minut. Vil man hurtigere, er der to muligheder:
- **Qwen3.5-2B:** ca. dobbelt så hurtig, men svagere på dansk.
- **Flere vCPU:** både læsning og skrivning skalerer næsten lineært med kernerne.

## 8. Anbefaling og rækkefølge

1. **Trin 1, uden AI (alle profiler):** signalvej-guide.
   - Vælg start og slut, se vejen fremhævet, svar på spørgsmål pr. symbol.
   - Løbelys/animationer genereres med betingelser.
   - Vejen gemmes som en navngiven *signalvej*, der kan rettes.
   - Det giver det meste af gevinsten og er grundlaget for trin 3.
2. **Trin 2:** hardwareprofil ved installation, plus *System › Konfiguration* og *Status*.
3. **Trin 3, valgfri LLM:**
   - `scada-llm.service` (llama.cpp) og klientlaget `assist`;
   - feltet *Forklar vejen med egne ord* udfylder guidens svar;
   - startmodel: **Qwen3.5-4B Q4_K_M**, med **Ministral-3-8B** som kvalitetsalternativ. Valget afgøres af måleplanen.

Nye afhængigheder (llama.cpp-binær, modelfiler) kræver godkendelse før trin 3.

---

## Kilder

- Qwen3, licens og størrelser: [qwenlm.github.io/blog/qwen3](https://qwenlm.github.io/blog/qwen3/)
- Qwen3.5 små modeller (0,8B–9B, Apache-2.0): [Artificial Analysis](https://artificialanalysis.ai/articles/qwen3-5-small-models)
- Ministral 3 (3B/8B/14B, Apache-2.0, function calling): [arXiv 2601.08584](https://arxiv.org/abs/2601.08584), [Hugging Face: Ministral-3-3B-Instruct-2512](https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-BF16)
- Gemma 4 (licens og sizes): [Wikipedia: Gemma](https://en.wikipedia.org/wiki/Gemma_(language_model)), [MindStudio](https://www.mindstudio.ai/blog/what-is-gemma-4-google-apache-2-multimodal-model)
- Granite 4.0 (Apache-2.0, H-Tiny 7B/1B aktiv, GGUF): [Hugging Face: granite-4.0-h-tiny-GGUF](https://huggingface.co/ibm-granite/granite-4.0-h-tiny-GGUF), [Unsloth: IBM Granite 4.0](https://unsloth.ai/docs/models/tutorials/ibm-granite-4.0)
- EuroLLM (dansk, 9B/22B): [arXiv 2602.05879](https://arxiv.org/abs/2602.05879), [European Open Source AI Index](https://osai-index.eu/model/eurollm)
- CPU-hastigheder: [PromptQuorum: CPU-only LLM](https://www.promptquorum.com/local-llms/best-cpu-only-llm), [edge-cpu-inference (4 vCPU Xeon)](https://github.com/nandan2003/edge-cpu-inference)
- Oversigter (sekundære, brugt med forsigtighed): [Hugging Face blog](https://huggingface.co/blog/daya-shankar/open-source-llm-models-to-run-locally), [popularai.org](https://www.popularai.org/p/best-cpu-only-local-llm-2026)
