# Release Notes

---

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
