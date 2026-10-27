# Funktionsanalyse — hænger det, systemet tilbyder, sammen med det, man får? (27.10.2026)

**Vinkel:** De to tidligere analyser så på drift/robusthed og sikkerhed. Denne ser på **funktionsniveau**: når brugerfladen tilbyder noget, får man så det, man forventer — og passer de forskellige veje til samme mål sammen? Hovedeksemplet er de to måder at binde tegningen til PLC'en på:

1. **Simple bindinger** — binding-editoren (*Bindinger*): tag + animation pr. element (+ automatiske bindinger, når et element-id/label er lig et tagnavn, og "Tilknyt tag" på betjeningssymboler fra biblioteket).
2. **Wizard** — *Opsæt symbol (6 trin)*: symbolkonfiguration med betjening, positioner, signaler, kontaktplaner, animationer, logik, alarm, nøglelås og trendgraf.

**Version:** v1.21.12. **Metode:** fase 1 kortlægning af alle steder, der opretter, læser eller rydder bindinger; fase 2 verifikation af hvert fund med en test gennem det rigtige API (mock-PLC, tegning, bindinger, konfiguration). Ingen kode er ændret.

---

## Sådan hænger det sammen i dag

Overview får ét samlet sæt "effektive bindinger" fra fem kilder, lagt oven i hinanden:

| Kilde | Oprettes i | Gælder når |
|-------|-----------|------------|
| Simple (eksplicitte) bindinger | *Bindinger* → Tilføj binding | elementet ikke ligger i et wizard-konfigureret symbol |
| Automatiske bindinger | ingen — element-id/label = tagnavn | elementet hverken har simple bindinger eller ligger i et konfigureret symbol |
| Betjeningssymbolets indbyggede | *Bindinger* → Tilknyt tag (`data-hv-auto`) | som simple (gemmes som simple) |
| **Wizard-konfiguration** | *Opsæt symbol* | **altid — og den tilsidesætter alle ovenstående på hele symbolet og dets dele** |
| Gruppe-animationer | *Tegn* → symbolgrupper | lægges efter symbolets egne |

**Det, der holder:**
- **Alle forbrugere bruger samme samlede sæt:** live-data, adgang pr. tegning (synlige tags), operatørers skriveret, deaktiverede tegninger (polling standses), trends (wizardens trendgraf) og backup tager begge veje med.
- **Overview har en håndtering for alle 18 animations- og klik-typer**, som de to editorer tilbyder — intet i editorerne er "dødt" i visningen.
- **Wizardens betjening** (positioner, puls, setpunkt) går gennem sin egen, strengere sti: kommando-tags kan ikke skrives uden om positionerne.
- **Forældreløse wizard-konfigurationer** vises på *Bindinger*, når et symbol er forsvundet fra tegningen.
- **Når man vælger selve det konfigurerede symbol** i binding-editoren, står der: "Symbolets egne bindinger nedenfor bruges ikke".

**Funktionsforskelle (bevidste):** Wizarden kan mere (13 animationstyper inkl. *drej*, *flakker*, *skalér*; positioner med tilbagemelding, kontaktplaner, logik, alarm ved afvigelse, nøglelås, trendgraf). Simple bindinger kan to ting, wizarden ikke kan: **"Gå til tegning"** (`click:goto`) og et frit setpunkt pr. element uden symbol. Det sidste dækker wizarden med *setpunkt*-betjening; det første mangler (se B2).

---

## Fund

| # | Fund | Alvor | Verificeret |
|---|------|-------|-------------|
| B1 | En simpel binding på en **del** af et wizard-konfigureret symbol gemmes (200), men virker ikke — uden besked hverken fra API eller editor | Mellem | Test gennem API |
| B2 | Wizarden har ingen "Gå til tegning", og konfigureres et symbol, forsvinder dets eksisterende navigation uden advarsel | Mellem | Test gennem API |
| B3 | En binding, der ikke virker (dækket af en konfiguration), blokerer alligevel for at slette tagget | Lav-mellem | Test gennem API |
| B4 | Rapporten ved en ny tegningsversion nævner kun forældreløse **simple** bindinger — ikke wizard-konfigurationer eller gruppe-animationer | Mellem | Test gennem API |
| B5 | En gendannelse sletter alle symbolernes PIN-koder (også på samme server) uden at sige det — PIN-låste positioner kan ikke betjenes bagefter | Mellem | Test gennem API |
| B6 | Et tag, der kun vises via en automatisk binding, kan slettes uden advarsel — tegningen mister værdien stille | Lav | Test gennem API |

### B1 · Simple bindinger på dele af et konfigureret symbol er "døde" (Mellem)

**Hvor:** `DrawingService._compute()` springer alle simple bindinger i et konfigureret symbols undertræ over (`covered`). Men `set_element_bindings()` (*Tilføj binding*) og `bind_symbol()` (*Tilknyt tag*) tjekker det ikke, og binding-editoren viser kun advarslen, når man har valgt **selve** symbolet — ikke en af dets dele.

**Bevis:** Pumpe er konfigureret i wizarden; en blink-binding gemmes på delen *Hjul* → svar **200** med bindingen, men den findes ikke blandt de effektive bindinger. I editoren står den som almindelig, redigerbar "Binding 1".

**Konsekvens:** Teknikeren tror, delen er bundet, men intet sker på Overview. Typisk spildt fejlsøgning — og de døde bindinger hober sig op (se B3).

**Forslag:** Når et element ligger i et konfigureret symbol: editoren viser "Del af det konfigurerede symbol *X* — bindinger her bruges ikke; ret animationer i *Opsæt symbol*" og skjuler *Tilføj binding*; backend afviser (409) med samme besked eller returnerer en advarsel. *Tilknyt tag* på et konfigureret symbol afvises tilsvarende.

### B2 · "Gå til tegning" og wizarden (Mellem)

**Hvor:** `SymbolConfig` har ingen navigations-handling; en simpel `click:goto` på symbolet er dækket af konfigurationen.

**Bevis:** Tank har `click:goto` til tegningen *Detalje* (virker). Efter en wizard-konfiguration (kun visning) er navigationen væk fra de effektive bindinger — gemningen siger intet.

**Konsekvens:** Et typisk ønske — fx en tank, der viser niveau og åbner detaljetegningen ved klik — kan ikke laves med wizarden, og en eksisterende navigation forsvinder stille, når man "opgraderer" symbolet.

**Forslag:** Tilføj *Gå til tegning* som klik-valg i wizarden for *kun visning*-symboler (eller lad en simpel `click:goto` på roden gælde, når symbolet ikke selv har en klik-handling). Ved gem af en konfiguration: vis hvilke simple bindinger på symbolet der bliver inaktive, med mulighed for at fjerne dem.

### B3 · Døde bindinger blokerer sletning af tags (Lav-mellem)

**Hvor:** `TagService.delete()` tæller alle gemte simple bindinger (`count_bindings_for_tag`) — også dem, der er dækket af en konfiguration.

**Bevis:** Tagget *Kun_skjult* bruges kun af den døde binding fra B1 → sletning afvises: "bruges i 1 binding(er) i tegninger: Anlæg (1) — fjern dem under Bindinger først". Bindingen ses kun, hvis man finder netop den del i editoren.

**Forslag:** Fejlteksten nævner elementet (og at bindingen er inaktiv); evt. en oprydning af inaktive bindinger, når en konfiguration gemmes (se B2).

### B4 · Versionsrapporten glemmer wizard og grupper (Mellem)

**Hvor:** `DrawingService.add_version()` rapporterer `orphaned_bindings` ud fra simple bindinger; *Tegninger* og *Tegn* viser kun dem.

**Bevis:** En ny version uden Pumpe → `orphaned_bindings: []`, mens `/symbols-orphaned` viser `Pumpe`.

**Konsekvens:** Gemmer man i *Tegn* efter at have slettet eller omdøbt et konfigureret symbol, får man at vide, at alt er i orden; konfigurationen (positioner, signaler, PIN, alarm …) er dog koblet fra, til nogen opdager det på *Bindinger*.

**Forslag:** Tilføj forældreløse symbolkonfigurationer og gruppe-animationer til rapporten og vis dem begge steder (med link til *Bindinger*, hvor de kan flyttes/fjernes).

### B5 · Gendannelse sletter PIN-koder stille (Mellem)

**Hvor:** `restore_project()` sletter alle tegninger og indsætter dem igen; `symbol_pins` forsvinder via `ON DELETE CASCADE`. PIN-hashes er bevidst ikke med i backuppen, og resultatet nævner kun manglende PLC-adgangskoder.

**Bevis:** Pumpe med PIN → backup → gendannelse (samme server) → PIN'en er væk; svaret (`plcs, tags, drawings, …, missing_passwords`) nævner det ikke.

**Konsekvens:** Efter enhver gendannelse kan alle PIN-låste positioner ikke betjenes ("låst, og der er ingen kode — en tekniker skal sætte en kode"), indtil en tekniker sætter nye koder — og ingen har fået det at vide.

**Forslag:** Bevar PIN-hashes på samme server for (tegning, element), der stadig findes efter gendannelsen; og rapportér "symboler med nøglelås uden kode" (som `missing_passwords`), så det kan ses og rettes med det samme. Gendannelsesresultatet bør også tælle symbolkonfigurationer og grupper.

### B6 · Automatisk bundne tags kan slettes uden advarsel (Lav)

**Hvor:** `TagService.delete()` tæller kun gemte bindinger; automatiske bindinger (element-id/label = tagnavn) findes kun "beregnet".

**Bevis:** *Niveau* vises automatisk i tegningen → sletning giver 204, og tegningen viser intet længere.

**Forslag:** Svar med en advarsel/bekræftelse ("vises automatisk i tegning *X*"), eller kræv `force`. Lav prioritet — opførslen er forudsigelig (opretter man tagget igen, bindes det igen).

---

## Anbefalet rækkefølge

1. **B1 + B3** (inaktive bindinger: forhindr dem og ryd op) — ét samlet greb i editor og backend.
2. **B4** (versionsrapport) og **B5** (PIN ved gendannelse) — begge "du får ikke at vide, at noget gik tabt".
3. **B2** (navigation i wizarden).
4. **B6**.
