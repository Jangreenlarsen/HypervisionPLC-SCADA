# Release Notes

---

## v0.21.0 — 2026-10-08 — Energirapporter

- Ny side **Energi**: forbrug og produktion i kWh pr. dag, uge eller måned, som søjlediagram og tabel med I alt. Kan hentes som CSV til Excel.
- Under **Tags → Redigér** markeres et tag som energi:
  - **Tæller** passer til fx en kWh-måler. Nulstilles måleren, regnes det med.
  - **Effekt** passer til fx W eller kW og regnes om til kWh over tid.
  - Historik skal være slået til for tagget.
- Energi-tags gemmes i 400 dage (anden historik i 30), så der kan laves måneds- og årsoversigter.
- Perioderne følger dansk tid, også ved skift til og fra sommertid.

## v0.20.1 — 2026-10-08

- Indlæsning af historik viser nu den rigtige fejlbesked (fx "Du er ikke logget ind") i stedet for "Bad Gateway".

## v0.20.0 — 2026-10-08 — Backup af trend-historik

- Under **Backup** kan trend-historikken hentes som en komprimeret fil. Det sker uden at opsamlingen stopper.
- **Indlæs historik** fletter en fil ind i den nuværende historik. Nye værdier tilføjes, og intet overskrives eller slettes. Det kan fx bruges, når der flyttes til en ny server.
- Den automatiske backup tager nu også et øjebliksbillede af historikken. De seneste 2 gemmes og kan hentes fra listen over backups på serveren.

## v0.19.0 — 2026-10-08 — Betjeningssymboler

- Ny sektion **Betjening** i Tegn: trykknap (puls), start/stop, vippekontakt, drejeomskifter 0/1, auto/manuel og setpunkt-felt.
- Indsæt symbolet og vælg et skrivbart tag. Når tegningen er gemt, virker symbolet med det samme på Overview, uden opsætning under Bindinger:
  - Klik skriver til PLC'en.
  - Lampe, vippe, greb og tekst viser tilstanden.
- Tags der ikke er skrivbare, kan ikke vælges til betjeningssymboler. Operatører kan betjene symbolerne i de tegninger, de har adgang til.

## v0.18.1 — 2026-10-08 — Stop og slet historik

- På **Trends** har tekniker og admin fået fluebenet **Administrér**. Det viser knapper ud for hvert tag:
  - **Gem** og **Stop** slår historikken til og fra. Ved Stop bevares det gemte, så det stadig kan vises.
  - **Slet** fjerner tagets gemte værdier, efter du har bekræftet det.
- Ændringer gælder med det samme: "Stop" stopper opsamlingen straks, og "Gem" begynder straks.

## v0.18.0 — 2026-10-08 — Zoom på Overview og start-tegning

- **Zoom og panorering på Overview:** brug musehjulet eller knapperne − / + og træk for at flytte rundt. På mobil og tablet zoomer man med to fingre, og **Tilpas** viser hele tegningen igen. Når man trækker hen over en knap i tegningen, betjenes den ikke. Det gør den kun ved et almindeligt klik.
- **Start-tegning:** under **Tegninger** kan en tekniker eller admin trykke **Gør til start**. Overview åbner så med den tegning for alle, der har adgang til den. Skifter man selv tegning, huskes den, så længe fanen er åben.

## v0.17.0 — 2026-10-08 — Animation "Flyt"

- Ny animation **Flyt** under Bindinger. Ved min står elementet, hvor det er tegnet, og ved max er det flyttet "Flyt X/Y" i tegningens enheder. Det passer fx til spjæld, glidere, cylindre og niveauflydere.
- Flyt kan kombineres med Rotation på samme element.

## v0.16.0 — 2026-10-08 — Symboler til solcelleanlæg

- Ny sektion **Solcelleanlæg** i Tegn med solcellepanel og -streng, sol, inverter, hybridinverter, MPPT-regulator, batteri og batteribank, DC- og AC-afbryder, overspændingsbeskyttelse, elmåler, elnet, forbrug/hus, elbillader og energiflow-pil.
- Batteriets indre felt kan bindes til **Niveau**, så det viser ladetilstanden. Solen kan bindes til **Gennemsigtighed** efter indstrålingen, og elmålerens tal kan bindes til **Tekst**.

## v0.15.0 — 2026-10-08 — Flere symboler: VVS og el

- **Tegn** har nu 59 symboler i tre sektioner med søgefelt. Hver sektion kan klappes sammen.
- **Rør og VVS:**
  - Rør og fittings: bøjninger på 90° og 45°, T-stykke, kryds, reduktion, prop, flange og strømningspil.
  - Ventiler: kugle-, kontra-, 3-vejs-, motor-, magnet-, regulerings- og sikkerhedsventil.
  - Komponenter: varmeveksler, filter, ekspansionsbeholder, radiator, ventilator og kedel.
  - Måleinstrumenter: TT/PT/FT/LT, manometer og termometer.
- **Elektrisk (ny sektion):** ledninger, kontakter, trykknap, nødstop, kontaktor, relæspole, sikring, automatsikring, motorværn, motor 3~, frekvensomformer, transformer, strømforsyning, jord, signallampe, modstand, føler, hovedafbryder og PLC.
- Brug SVG-Edits rotation eller spejling til at vende en bøjning eller et T-stykke. Manometerets viser kan animeres med **Rotation**, og termometerets søjle med **Niveau**.

## v0.14.2 — 2026-10-08 — Alle sider fylder skærmen

- Siderne er ikke længere låst til en smal kolonne på store skærme. Alle sider bruger nu hele bredden.
- **Bindinger:** Tegningen fylder den ledige højde, og sidepanelet er smallere, så tegningen bliver større.
- **Tegn:** Tegne-editoren fylder højden ned til bunden af vinduet og viser altid hele værktøjslinjen.
- **Trends:** Graferne deler den ledige højde mellem sig, og tag-listen går ned til bunden af vinduet, så siden ikke skal scrolles.
- Alt følger med, når vinduet ændres, eller du zoomer i browseren.

## v0.14.1 — 2026-10-08 — Overview fylder skærmen

- Tegningen på Overview tilpasser sig nu browservinduet. Den bruger hele bredden på store skærme og passer i højden på lave skærme, så siden ikke skal scrolles.
- Størrelsen følger med, når vinduet ændres, når du zoomer i browseren (Ctrl + / −), og når menuen fylder to linjer.

## v0.14.0 — 2026-10-08 — Flere animationer i én binding

- Under **Bindinger** samler en binding nu ét tag med en eller flere animationer, fx tekst + blink på `test01`. Hver animation har sine egne indstillinger.
- **+ Animation** tilføjer endnu en animation på samme tag og foreslår en, der ikke allerede er brugt. **×** fjerner én animation, og **Fjern binding** fjerner det hele.
- Et automatisk bundet element beholder sin binding, når du tilføjer mere. Tidligere kunne den forsvinde, når man gemte.

## v0.13.2 — 2026-10-08 — Trends: slå historik til direkte

- Gemmer intet tag historik endnu, forklarer Trends-siden nu, hvorfor alle tags er grå.
- Tekniker og admin kan trykke **Gem historik** ud for et tag direkte på Trends-siden. Tagget bliver valgt med det samme, og kurven fyldes op derfra.
- Den første måling vises som en prik i stedet for en tom graf. Det samme gælder en enkelt måling mellem to perioder uden forbindelse.

## v0.13.1 — 2026-10-08 — Renere serverlog

- Serveren skriver ikke længere fejlmeldingen "Task was destroyed but it is pending!" i loggen, hver gang en browser skifter side eller lukker. Meldingen var harmløs, men gjorde det svært at se de rigtige fejl.

## v0.13.0 — 2026-10-08 — Tekst før og efter værdien

- Tekst-bindinger under **Bindinger** har fået felterne **Tekst før** og **Tekst efter**. Fx giver "Tank : " + værdien + " liter" teksten "Tank : 1002 liter" i tegningen. Fjern fluebenet i "Vis enhed", hvis tagets egen enhed ikke skal med.
- Linjen "Vises som:" viser resultatet med tagets aktuelle værdi, og tegningen opdateres med det samme, inden du gemmer.
- Mangler værdien, vises fx "Tank : — liter", så teksten ikke springer.

## v0.12.0 — 2026-10-08 — Trends

- Under **Tags** kan historik slås til pr. tag, med et minimumsinterval mellem gemte værdier. Til/fra-signaler gemmes ved hvert skift.
- Ny side **Trends**: vælg op til 7 tags og en periode (15 min til 30 dage eller selvvalgt). Tags med samme enhed vises i samme graf; til/fra-signaler vises som trin.
- Graferne opdateres live for perioder op til 24 timer. Træk vandret for at zoome, dobbeltklik for at zoome ud.
- Brud i en kurve betyder, at der ikke var en gyldig værdi, fx fordi PLC'en ikke svarede.
- **CSV**-knappen henter de rå værdier, klar til dansk Excel.
- Historik gemmes på serveren i 30 dage (kan ændres med `SCADA_TREND_DAYS`). Backup indeholder opsætningen pr. tag, men ikke selve historikken.
- Brugere med adgang til udvalgte tegninger ser kun trends for de tags, der hører til.

## v0.11.0 — 2026-10-08 — Alarmer

- Under **Tags** kan hvert tag få alarmgrænser: HH, H, L og LL med dødbånd (så alarmen ikke blafrer) og forsinkelse — eller en alarm når et til/fra-signal er aktivt.
- SCADA'en giver også alarm, hvis en PLC holder op med at svare.
- Alarmklokken i toppen viser antal aktive og nye alarmer og blinker, indtil de er kvitteret.
- Ny side **Alarmer** med aktive alarmer og historik. Operatører kvitterer enkeltvis eller alle på én gang; det registreres hvem der kvitterede.
- I tegningerne blinker elementer rødt, når deres tag er i alarm.
- Aktive alarmer overlever en genstart af serveren, og brugere med adgang til udvalgte tegninger ser kun de alarmer der hører til.

## v0.10.0 — 2026-10-08 — Tegne-editor

- Ny side **Tegn** (tekniker og admin): tegn og ret tegninger direkte i SCADA'en med en fuld tegne-editor (SVG-Edit) — figurer, tekst, linjer, lag, farver, fortryd.
- Symbolbibliotek i ISA-101-stil: pumpe, motor, ventil, tank, værdifelt, lampe, knap og rør.
- Vælg et element og et tag i samme dropdown som under Bindinger — så bindes elementet automatisk.
- **Gem kladde** gemmer en ny version uden at ændre det operatørerne ser; **Gem og udgiv** gør den aktiv. Ældre versioner kan åbnes og udgives igen.

## v0.9.0 — 2026-10-08 — Adgang pr. tegning

- Under **Brugere** kan en viewer eller operatør begrænses til udvalgte tegninger. Brugeren ser så kun de tegninger på Overview, kun de tags der vises i dem, og kan kun betjene det der kan klikkes på i dem.
- Operatører kan generelt kun betjene tags der er sat op med en klik-handling i en tegning de har adgang til.
- Eksisterende brugere har som før adgang til alle tegninger.

## v0.8.1 — 2026-10-08 — Hurtig live-opdatering bekræftet

- Rettelsen fra v0.7.0.1 er bekræftet i drift: alle PLC-udgange og -indgange (fx DO2) opdateres nu lige så hurtigt som DO1.

## v0.8.0 — 2026-10-08 — Backup og gendannelse

- Ny side **Backup** (kun admin): hent en backup af hele opsætningen — PLC-forbindelser, tags, alle tegninger og bindinger — som én fil.
- Gendan en backup: du ser først hvad filen indeholder og skal bekræfte. Er der fejl i filen, ændres intet, og du får en liste over fejlene.
- Før hver gendannelse gemmes den nuværende opsætning automatisk på serveren, og serveren tager desuden en backup hvert døgn (de seneste 7 gemmes).
- Backuppen indeholder ikke adgangskoder eller brugere. Efter gendannelse på en ny server skal PLC-adgangskoderne indtastes igen — siden viser hvilke.
- Rettelsen af den langsomme SSE-opdatering fra v0.7.0.1 er med; den afventer stadig bekræftelse.

## v0.7.0.1 — 2026-10-08 — Fejlsøgning: hurtigere live-opdatering

- Live-værdier fra PLC'en opdateres nu hurtigt igen: SSE-strømmen overvågede kun én adresse pr. type, og ST-variabler blev kun hentet hvert 2. sekund. Nu leverer SSE alle ønskede adresser, og alt andet hentes hvert ½ sekund.
- PLC-siden viser hvor mange adresser SSE dækker.
- Afventer bekræftelse fra drift.

## v0.7.0 — 2026-10-08 — Betjening fra Overview

- Operatører kan nu betjene anlægget direkte i tegningen: klik på et element for at indtaste et setpunkt, slå noget til/fra eller sende en puls. Klik kan også åbne en anden tegning.
- Setpunkter tjekkes mod min/max, og der bedes om bekræftelse, hvor tagget er sat op til det.
- Efter hver skrivning læses værdien tilbage fra PLC'en. Har PLC'ens eget program overskrevet den, får operatøren besked i stedet for en falsk bekræftelse.
- Pulser nulstilles af serveren, selv hvis browseren lukkes.
- Under **Tags** kan et tag gøres skrivbart (kun holding registers og coils) med min/max og bekræftelse.
- I binding-editoren vælges tags nu fra en dropdown-liste.
- Ny side **Log**: hvem skrev hvad til PLC'en, og hvem ændrede opsætningen — også afviste forsøg.
- Roller: viewer kan se, operatør kan betjene, tekniker kan konfigurere, admin styrer PLC'er og brugere.

## v0.6.0 — 2026-10-08 — Binding-editor

- Ny side **Bindinger** (tekniker og admin): klik på et element i tegningen og vælg hvilket tag det skal vise, og hvordan — tekst, farve (også med grænseværdier), synlighed, blink, niveau i en tank, rotation eller gennemsigtighed.
- Ændringer vises live på tegningen med rigtige værdier, før du gemmer.
- Automatiske bindinger (id = tag-navn) kan tilpasses med ét klik.
- Bindinger til elementer, der er forsvundet i en ny version af tegningen, vises samlet og kan fjernes.

## v0.5.0 — 2026-10-07 — HTTPS

- SCADA'en kan nu nås krypteret på `https://scada.laces.dk` / `https://10.1.1.31` via nginx. Almindelig `http://` sendes automatisk videre til HTTPS.
- Certifikatet er indtil videre selvsigneret, så browseren viser en advarsel første gang. Godkend det én gang (eller installér certifikatet som betroet). Senere skiftes det til Let's Encrypt uden andre ændringer.
- Login-cookien sendes kun over HTTPS.

## v0.4.0 — 2026-10-07 — Login og brugerroller

- SCADA'en kræver nu login. Første gang oprettes brugeren `admin` med en engangsadgangskode i `/var/lib/hypervisionplc-scada/initial-admin-password.txt`, som skal skiftes ved første login.
- Fire roller: **viewer** (ser Overview, tegninger og tags), **operatør** (forberedt til betjening), **tekniker/engineer** (tegninger, tags, bindinger) og **admin** (PLC-forbindelser og brugere).
- Admin kan oprette, deaktivere og slette brugere og give nye midlertidige adgangskoder. Den sidste administrator kan ikke fjernes.
- Efter 5 forkerte login-forsøg spærres i 1 minut.
- Serveren lytter fortsat kun på localhost, indtil TLS (nginx + Let's Encrypt) er sat op.

**Næste skridt**: TLS for scada.laces.dk (nginx + certbot med deSEC), derefter fase 3 — binding-editor.

## v0.3.0 — 2026-10-07 — Overview med live SVG-tegninger

- Ny brugerflade i browseren: **Overview**, **Tegninger**, **Tags** og **PLC'er**.
- Upload SVG-tegninger (fx fra Inkscape). Farlige elementer som scripts fjernes automatisk, og du får en rapport over hvad der blev fjernet. Nye versioner kan uploades, og en ældre version kan gøres aktiv igen.
- Elementer hvis id (eller Inkscape-label) er lig et tag-navn bindes automatisk: tekst viser værdien med enhed, figurer bliver grønne når signalet er aktivt.
- Værdierne opdateres live. Mister SCADA'en forbindelsen til en PLC, bliver værdierne tydeligt nedtonet og PLC'ens fejlbesked vises øverst.
- Tags kan oprettes og foreslås fra PLC'ens ST-variabler direkte i brugerfladen; PLC-forbindelser kan tilføjes og overvåges (status, SSE, kald pr. cyklus).
- Endnu intet login — serveren lytter derfor stadig kun på localhost.

**Næste skridt**: Fase 3 — binding-editor (klik på et element og vælg tag + animation).

## v0.2.0 — 2026-10-07 — SCADA-serveren taler med PLC'en

- SCADA-serveren kan forbinde til en eller flere HypervisionPLC'er via REST og holde live-værdier opdateret: bulk-polling, og PLC'ens SSE-strøm som hurtig supplement når den er ledig.
- Tags kan oprettes med kilder som `plc1:hr:100:real`, `plc1:coil:5` eller navngivne ST-variabler (`plc1:logic:1:Niveau`) med skalering og enhed — og foreslås automatisk ud fra PLC'ens ST-programmer.
- PLC-adgangskoder gemmes kun på serveren og vises aldrig.
- Mock-PLC til test uden hardware, og installationsscript + systemd-service til Debian/Raspberry Pi.
- Endnu ingen brugerflade og intet login — API'et lytter derfor kun på localhost som standard.

**Næste skridt**: Fase 2 — SVG-upload og Overview-board med live-værdier.

## v0.1.0 — 2026-10-07 — Projektinitialisering

Projektstruktur, research og arkitektur for HypervisionPLC SCADA er på plads. Der er endnu ingen kørende kode.

**Næste skridt**: Fase 1 — backend-skelet, mock-PLC og PLC-klient (login, bulk-poll, SSE) med tag-model.
