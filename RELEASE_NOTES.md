# Release Notes

---

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
