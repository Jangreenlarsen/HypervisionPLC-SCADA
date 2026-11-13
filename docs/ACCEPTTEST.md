# Accepttest på `main` — prioriteret liste

Test `main` (v5.6.1) i den rækkefølge, der står her. **Prioriteret efter risiko:** først det, der kan skade anlægget eller miste data, derefter det daglige arbejde, og til sidst det nye og det kosmetiske. Stopper du undervejs, har du dækket det vigtigste.

Sæt **X** ved det, der virker. Virker noget ikke: skriv en linje (hvad du gjorde, hvad du så, hvad du ventede) — så lægger jeg en post i `BUGS.md` og retter på `dev`. Når P1–P3 er afkrydset, markerer jeg de 19 gamle punkter i `FEATURES.md` som *done*.

| Trin | Tid | Hvorfor først |
| --- | --- | --- |
| **P1 Kritisk** | ca. 1–2 timer | skriver til PLC'en, mister data, kommer ikke op igen |
| **P2 Daglig drift** | ca. 1½ time | det, operatører og teknikere bruger hver dag |
| **P3 Nyt siden v5.0** | ca. 1 time | ny kode med mindst driftserfaring |
| **P4 Gamle åbne punkter** | ca. 1 time | v0.27–v0.58 — mest kosmetik og guider; har kørt længe |

Forberedelse: tag en backup først (System › Backup, eller `scada-tool backup create`), og brug en **kopi** af en rigtig tegning (fx *varme*) til alt, der ændrer noget.

---

## P1 — Kritisk

### 1. Serveren kommer op og kan genstartes
- [ ] `scada-tool status` og `scada-tool check` (som root, `su -`) — alt **OK**.
- [ ] `scada-tool restart` — `/api/health` svarer igen inden for ca. 30 s; tegninger, tags og brugere er der stadig.
- [ ] Efter en opdatering (System › Opdatering) står versionen yderst til højre i topmenuen, og `scada-tool logs --fejl` viser ingen uventede fejl.

### 2. Adgang og roller
- [ ] En **operatør** kan se Overview og betjene, men ikke åbne Tegn, Bindinger, Brugere, Backup eller Opdatering (siderne mangler i menuen, og direkte adresse giver afvisning).
- [ ] En bruger med adgang til **kun én tegning** ser kun den (også i Trends og Alarmer).
- [ ] Forkert adgangskode 5 gange låser kontoen et stykke tid; en admin kan stadig komme ind.
- [ ] Den sidste admin kan ikke slettes, nedgraderes eller deaktiveres.

### 3. Skrivning til PLC'en (kun mod en PLC, hvor det må ske — gerne med en person ved anlægget)
- [ ] Et symbol med **positioner**: vælg en position → bekræftelsesdialog → PLC'en skifter → symbolet viser den nye position.
- [ ] En **trykknap** (puls) og et **setpunkt** (indtastet værdi uden for området afvises med en klar tekst).
- [ ] Et **låst** symbol (kode) kan ikke betjenes uden koden; en forkert kode afvises.
- [ ] Hver skrivning står i **Log › Audit** med bruger, tag og værdi.
- [ ] Skrivning, mens PLC'en ikke svarer: brugeren får en **specifik fejltekst**, og intet ser ud som "gået godt".

### 4. Kommunikationsfejl og genopkobling
- [ ] Træk netværket til PLC'en: værdierne bliver **grå/tonet**, *Status* viser *kommunikation tabt*, og en **COMM-alarm** kommer efter forsinkelsen.
- [ ] Sæt netværket til igen: værdierne kommer tilbage uden genstart, og alarmen kan kvitteres.

### 5. Alarmer
- [ ] En alarmgrænse udløses → klokken blinker → **kvittér** → alarmen står i historikken.
- [ ] En ukvitteret alarm forsvinder ikke af sig selv.

### 6. Backup og gendannelse
- [ ] System › Backup: *Tag backup nu* → filen findes i listen; *Hent* giver en JSON-fil.
- [ ] **Gendan** den på en testmaskine → tegninger, tags, bindinger og brugere er som før.
- [ ] `scada-tool backup create` giver en `.db`-fil; `scada-tool backup list` viser den.

### 7. Opdatering og tilbagerulning (på testserveren, ikke på anlægget)
- [ ] Upload en pakke → kontrolsum og version vises → *Installér* → serveren kommer op med den nye version.
- [ ] `scada-tool update status` viser *done*.
- [ ] *(Valgfrit)* en pakke, der ikke starter, rulles tilbage af sig selv — eller `scada-tool update rollback`.

---

## P2 — Daglig drift

### 8. Overview og live-data
- [ ] Overview viser en rigtig tegning med levende værdier, farver og animationer; en bruger kan skifte tegning.
- [ ] Et klik på en værdi åbner trendgrafen; *tilbage til tegningen* virker.

### 9. Tegn: tegn, gem, udgiv
- [ ] Tegn nogle former, **Gem kladde**, **Gem og udgiv** → Overview viser den nye version; *Version*-menuen kan åbne den gamle.
- [ ] Fortryd/Gentag (Ctrl+Z/Y), zoom, gitter og fang virker (v0.54).
- [ ] Et rør tegnet mellem to symboler følger med, når symbolet flyttes.

### 10. Symbol-guiden (6 trin) og bindinger
- [ ] *Opsæt symbol (6 trin)* på et nyt symbol: signal, kontaktplan, animationer, test og gem — Overview følger opsætningen.
- [ ] En **logikblok** (to tags, OG) styrer en animation.
- [ ] Under **Bindinger**: en tekst-binding med beregning `x / 10` (128 → 12,8) (v0.41).

### 10b. Flow (v6.1)
- [ ] Tegn › **Forbindelser** › Tjek forbindelser › **Bind forbindelser** → gem og udgiv.
- [ ] Pumpen: guiden trin 4 › **Flow** → Med i flowberegningen, Pumpe, kapacitet 100, flow-rate = pumpens drift-tag → gem. Start pumpen i PLC'en → **løbelys** i alle rør i løkken på Overview, i flowets retning; stop → løbelyset stopper.
- [ ] 3-vejsventil med positioner AB → A / AB → B (tag 10/20): trin 4 › Flow → hakkene står ved den rigtige vej → skift ventilen → flowet skifter gren.
- [ ] Kontraventil vendt forkert → intet flow, og Flow-vinduet siger "ingen åben vej rundt".
- [ ] **Flow**-knappen i Tegn → vinduet kan flyttes og gøres større, huskes efter genindlæsning; vælg to rør → **Opret af valgte** → *Farve efter flow* (grænse 1 l/min) → Gem → Overview viser farven.
- [ ] En animation på pumpen: *Blink* styret af **symbolets flow** (mindst 1) → blinker, når pumpen giver flow.
- [ ] Status: kortet *Flowberegning* viser beregninger og tid; backup → gendan → grupperne er der igen.

### 11. Signalveje (fjernet i v6.0.0 b0395)
- [ ] Tegn har ingen sektion *Signalveje*; Symbol-oversigten viser kun *Grundsymboler* og *Grupper*; *Vis navne* har kun symboler og forbindelser.
- [ ] Efter opdateringen: Log › Audit har `signal_path.removed`, og der ligger en backup *før signalvejene blev fjernet*.
- [ ] Symbol-guiden trin 2: *Kommando* er kun et PLC-tag; tilbagemelding er kun et PLC-tag.
- [ ] *Tjek forbindelser*, *Bind forbindelser* og *Opsætning › Symboler › Ind/ud og veje* virker som før.

### 12. Trends, energi og ugeprogrammer
- [ ] Trends: vælg et tag og en periode; hover viser værdien; *Middel over* virker.
- [ ] Energi viser dagens/ugens tal for et energitag.
- [ ] Ugeprogram: en tidsplan sætter et tag på det rigtige tidspunkt og kan slås fra.

### 13. Brugere og manual
- [ ] Opret en bruger, skift adgangskode (kræves ved første login); `scada-tool user reset NAVN` på en testmaskine nulstiller en glemt adgangskode.
- [ ] Manual: søg, åbn et kapitel, billederne vises (v0.52–v0.53).
- [ ] Hjælperen (hvis installeret): et spørgsmål giver et svar.

---

## P3 — Nyt siden v5.0 (ny kode)

- [ ] **Symbol-oversigt (v5.5):** træet viser grundsymboler og grupper; klik vælger på tegningen; *Opsæt* åbner guiden; *ikke opsatte* indsnævrer.
- [ ] **Forbindelser (v5.3):** *Tjek forbindelser* → *Bind forbindelser* → flyt et rør → orange → *Ret* → grønt. Gem, åbn tegningen igen: forbindelserne er der.
- [ ] **Symbol-rapport (v5.1):** Tegn › Meddelelser viser konverteringsrapporten; intet står som "manuelt" uden grund.
- [ ] **Ur (v5.7, kun `dev`):** *Ur (NTP)* på Status siger *synkroniseret*.
- [ ] **Serveren (v5.6):** `scada-tool logs --fejl` og `scada-tool config` (ingen hemmeligheder i udskriften).

---

## P4 — Gamle åbne punkter (v0.27–v0.58)

**Menu og opdatering**
- [ ] Hovedmenuen (v0.51): Drift, Opsætning, System, Bruger åbner ved klik; Escape lukker.
- [ ] OTA fra web (v0.50): se P1.7.

**Symboler**
- [ ] Alt under Bindinger (v0.27): navn og forklaring på et symbol.
- [ ] *Slet tegning* fra Tegn (v0.42): bekræftelsen viser, hvad der rammes. **Kun på en kopi.**
- [ ] 3-vejs motorventil, begge varianter (v0.46–v0.47); hurtig opsætning med ét til/fra-tag giver tre farve-animationer (v0.48).
- [ ] Trin 1 viser kun de betjeningsformer, der giver mening for symbolet; *Vis alle* åbner for resten (v0.49).
- [ ] Logikblokke kan bruges på tværs af symboler (v0.44–v0.45).

**Erstat med symbol (v0.55–v0.58)**
- [ ] En tegnet pumpe erstattes af et symbol samme sted, i samme størrelse og med samme retning.
- [ ] Flere løse figurer (en ventil) erstattes af ét symbol; *spejlvend uden at spejle teksten*.
- [ ] Ventilens akse aflæses; kontraventilen drejes efter sin trekant.

---

## Resultat
Skriv fund her eller direkte til mig: _______________________________________________

Når P1 er afkrydset uden fund, er `main` klar til en pilot. Først derefter giver det mening at gå videre til udstyrstests (Raspberry Pi, langtidstest, PLC-skrivninger på anlægget) — se `docs/PRODUKTIONSANALYSE_2026-11-10.md`.
