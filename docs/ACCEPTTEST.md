# Accepttest på `main` (v5.7.0) — til Jan

Formål: lukke de punkter i `FEATURES.md`, der siden v0.27–v0.58 står som *in-progress, afventer Jans test*, og afprøve det nyeste. Gå listen igennem på en server med `main`. **Sæt X ved det, der virker**, og skriv en linje om det, der ikke gør — så markerer jeg `FEATURES.md` (done / fejl i `BUGS.md`).

Forberedelse: åbn en kopi af en rigtig tegning (fx *varme*) og tag en backup først (System › Backup, eller `scada-tool backup create` på serveren).

## A. Drift og system (v0.50–v0.54)
- [ ] **OTA fra web (v0.50)** — System › Opdatering: upload en pakke, tryk *Installér*, siden viser forløbet; en pakke, der ikke starter, rulles tilbage (afprøvet på testserveren 2026-10-16; mangler kun browser-testen).
- [ ] **Hovedmenu (v0.51)** — Drift, Opsætning, System og Bruger åbner ved klik; Escape lukker; versionen står yderst til højre.
- [ ] **Manual (v0.52–v0.53)** — Bruger › Manual: søg, åbn et kapitel, skærmbillederne vises.
- [ ] **Tegnehjælp (v0.54)** — Tegn › Fang: gitter, fang til gitter/objekter, rotation i 15°-trin (Shift = fri).

## B. Symboler og guiden (v0.27–v0.49)
- [ ] **Alt under Bindinger (v0.27)** — navn og forklaring på et symbol; listen viser navngivne og bundne elementer.
- [ ] **Beregning på tekst (v0.41)** — en tekst-binding med `x / 10` viser 128 som 12,8.
- [ ] **Slet tegning fra Tegn (v0.42)** — bekræftelsen viser versioner, bindinger og links, der rammes. *(Afprøv på en kopi!)*
- [ ] **Guiden i 6 trin (v0.43–v0.45)** — *Opsæt symbol (6 trin)* på et navngivet symbol; en logikblok med to tags (OG) styrer en animation; en blok kan bruges af et andet symbol.
- [ ] **3-vejs motorventil (v0.46–v0.48)** — begge varianter; hurtig opsætning med ét til/fra-tag giver tre farve-animationer.
- [ ] **Betjeningsformer i trin 1 (v0.49)** — kun de formål, der giver mening for symbolet; *Vis alle* åbner for resten.

## C. Erstat med symbol (v0.55–v0.58)
- [ ] Vælg en tegnet pumpe → forslag → symbolet kommer samme sted, i samme størrelse og med samme retning (v0.55–v0.56).
- [ ] Flere løse figurer (en ventil) erstattes af ét symbol; *spejlvend uden at spejle teksten* (v0.57).
- [ ] Ventilens akse aflæses, kontraventilen drejes efter sin trekant (v0.58).

## D. Det nyeste (v5.0–v5.7)
- [ ] **Signalvej** — Tegn › Signalveje: start, slut, *Find vej*, gem; løbelyset kører på Overview.
- [ ] **Vejen som symbol (v5.4)** — *Ret som symbol*: en egen animation på et element, gem vejen igen — animationen består.
- [ ] **Symbol-oversigt (v5.5)** — træet viser grundsymboler, veje og grupper; klik vælger; *Opsæt* åbner guiden.
- [ ] **Forbindelser (v5.3)** — Tjek forbindelser → *Bind forbindelser* → flyt et rør → orange → *Ret*.
- [ ] **Symbol-rapport (v5.1)** — Tegn › Meddelelser: konverteringsrapporten efter opgraderingen; intet "manuelt" står tilbage uden grund.
- [ ] **Ur (v5.7)** — System › Status: kortet *Ur (NTP)* siger *synkroniseret*.

## E. Serveren (v5.6)
Som root på serveren (`su -`):
- [ ] `scada-tool status` og `scada-tool check` — alt OK.
- [ ] `scada-tool logs --fejl` — ingen uventede fejl.
- [ ] `scada-tool backup create` og `backup list`.
- [ ] *(Valgfrit, på en testmaskine)* `scada-tool user reset NAVN` og derefter login; `scada-tool update apply FIL.tar`.

## Resultat
Skriv fund her eller direkte til mig: _________________________________________

Når A–C er afkrydset, markerer jeg de 19 punkter som **done** i `FEATURES.md`; det, der ikke virker, bliver til poster i `BUGS.md`.
