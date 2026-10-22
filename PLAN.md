# Plan: System › Konfiguration (lagring, netværk, første-gangs-adgang)

Beslutninger (Jan, 2026-10-22): omfang **lagring + netværk + status**; første gang uden seriel via **fast fallback-IP når DHCP mangler**; datamappen flyttes **guidet med genstart**.

## Mål
Ny admin-side **System › Konfiguration** (ved siden af Backup/Opdatering) hvor man kan:
1. **Lagring**: se hvor data ligger (`SCADA_DATA_DIR`, `trends.db`, `scada.db`), størrelse, ledig plads og skrivemængde pr. døgn; **flytte datamappen** til en anden monteret disk (fx USB-SSD).
2. **Trend-indstillinger**: opbevaring (`SCADA_TREND_DAYS`), flush-interval (`SCADA_TREND_FLUSH_S`) — kræver genstart af tjenesten.
3. **Netværk**: DHCP eller fast IP (adresse/præfiks, gateway, DNS), værtsnavn; vis aktuel adresse, MAC, link.
4. **Netværkstilstande** (Jans præcisering 2026-10-22): **DHCP forsøges hele tiden**; en fast IP er enten **sekundær** (ligger altid ved siden af DHCP-adressen, så siden altid kan nås) eller **reserve** (tages først efter N mislykkede DHCP-forsøg, standard 5, og slippes igen når DHCP lykkes). Valg: *Kun DHCP* · *DHCP + fast IP som sekundær (anbefalet, også første gang uden seriel)* · *DHCP, fast IP efter N fejl* · *Kun fast IP*. Forslag til fast nødadresse `192.168.100.10/24`. Siden viser hvilken adresse der er aktiv og om DHCP lige nu virker.

**Præcisering (Jan, 2026-10-22):** *alle* indstillinger — IP, subnet, gateway, DNS, værtsnavn, datamappe — sættes fra websiden. Netværk indtastes **færdigt i en formular** (alle parametre), valideres, og anvendes først ved et eksplicit tryk på **Anvend/Deploy** (med 60 s fortryd). Ingen indstillinger via kommandolinjen/install.sh kræves (install.sh opretter blot grund-profilen med nødadressen).

**Ændret trin 5 (2026-10-22):** i stedet for at flytte hele datamappen flyttes kun **trend-databasen** (`trends.db`), online og uden root-hjælper. Begrundelse: den fylder og skriver mest (SD-slid), og de faste stier i systemd-.path-enhederne (OTA, netværk) peger på `/var/lib/hypervisionplc-scada` — flyttes hele mappen, holder de op med at virke. Kun mapper under `/mnt`/`/media` på en anden disk; mappen oprettes én gang med `sudo install -d -o scada -g scada`; `ReadWritePaths` i tjenesten udvides med `-/mnt -/media`. Kopi via SQLites backup-API, kontrol (quick_check + antal rækker), skift af forbindelse, gammel fil gemmes som `.moved`; mangler disken ved opstart, startes en tom database i datamappen med advarsel.

**Trin 4 (2026-10-22):** DHCP-vagt `deploy/net-watchdog.sh` (root, systemd-timer hvert 30. s). Tilstand `dhcp_fallback`: tæller kontroller uden DHCP-lease og lægger reserve-IP'en på MIDLERTIDIGT efter N; fjerner den igen ved lease. Konfigurationen (`watchdog.conf`) skrives af `apply-config.sh` først efter bekræftelse. Samlet testvejledning til en rigtig Pi: `docs/TEST_PI.md`.

## Fast ramme / sikkerhed
- Tjenesten kører som ikke-privilegeret `scada` med `ProtectSystem=strict`; den **må ikke selv ændre netværk eller flytte filer uden for datamappen**. Samme mønster som OTA: tjenesten skriver en **anmodningsfil** (`<data>/config/apply.request`, kun tegn der er sikre), en root-ejet **systemd .path-enhed** udløser `deploy/apply-config.sh`, som validerer, udfører, skriver `status.json` og logger. Intet shell-input fra browseren; alle værdier valideres (IPv4/præfiks/gateway/DNS/værtsnavn, sti findes og er monteret, ligger ikke under `/`-systemmapper).
- **Ingen lockout** (QUALITY_CHECKLIST): netværksændring anvendes med **60 s fortryd** — den gamle opsætning gendannes automatisk, hvis browseren ikke bekræfter fra den nye adresse. Håndhæves i scriptet (ikke kun i UI).
- Kun **admin**; alle ændringer i **audit-loggen** (hvem, hvad, gammelt/nyt — aldrig hemmeligheder).
- Flytning af data: stop tjenesten → `rsync` til ny sti → `PRAGMA quick_check` på kopierne → opdatér `SCADA_DATA_DIR` i `/etc/hypervisionplc-scada.env` og `ReadWritePaths` (drop-in) → start → `/api/health`. Fejl = rul tilbage til gammel sti. Den gamle mappe **bevares** til admin sletter den.
- Ingen nye afhængigheder (NetworkManager/`nmcli` findes på Raspberry Pi OS Bookworm; scriptet falder tilbage til en fejlmelding, hvis det ikke findes).

## Trin (hver en egen commit/version)
1. **Skrivemåling + visning (kun læsning)**: backend `GET /api/system/config` (datasti, størrelser, ledig plads, skrevne rækker/bytes pr. døgn, aktuel netværksstatus). Side med visning. *(MINOR)*
2. **Trend-indstillinger** (opbevaring/flush) gemt i `<data>/config/settings.json` som overstyring af env, + genstart-knap. *(MINOR)*
3. **Root-hjælper `apply-config.sh` + .path/.service + install.sh**, kun netværk: DHCP/fast IP, værtsnavn, 60 s fortryd. Test: shell-tests af validering + backend-tests af anmodningen. *(MINOR)*
4. **DHCP + fast IP**: NetworkManager-profil med `ipv4.method=auto` + `ipv4.addresses` (sekundær adresse, `may-fail=yes`) oprettes af install.sh. En lille root-**watchdog** (systemd-timer, 30 s) tæller mislykkede DHCP-forsøg, gentager DHCP uden ende (`nmcli device reapply`) og styrer *reserve*-tilstanden (fast IP først efter N fejl, væk igen ved lease). Tæller og tilstand vises på siden. **Åbent teknisk punkt:** hvor længe NetworkManager selv gentager DHCP med `may-fail` skal verificeres på en Pi — watchdog'en gør det uafhængigt. *(MINOR)*
5. **Guidet datamappe-flytning** i `apply-config.sh` med rollback. *(MINOR)*
6. Manual (nyt afsnit under System) + QUALITY_CHECKLIST gennemgang + reviewer-agent (auth, root-hjælper, input).

## Berørte filer
`backend/app/api/system_config.py` (ny), `backend/app/services/sysconfig.py` (ny), `backend/app/config.py`, `backend/app/main.py`, `deploy/apply-config.sh` + `hypervisionplc-scada-config.{path,service}` (nye), `deploy/install.sh`, `frontend/src/pages/SystemConfig.svelte` (ny), `frontend/src/lib/nav.ts` (+ test), `frontend/src/manual/`, tests, FEATURES/CHANGELOG/RELEASE_NOTES, `ARCHITECTURE.md` (root-hjælper-lag).

## Risici / åbne punkter
- **Netværk kan låse en ude**: afbødet med 60 s fortryd + nødadresse; skal testes på en rigtig Pi (ikke kun testserveren 10.1.1.31 — fejl her kan afskære SSH). Jeg foreslår at teste netværkstrin på Pi'en med fysisk adgang.
- **Nødadressen** skal vælges så den ikke støder ind i kundens net (forslag `192.168.100.10/24`, kan ændres).
- **Skrivemåling**: rækker/bytes pr. døgn tælles i optageren (tæller i hukommelsen + daglig værdi i `trends.db`).
- Windows-dev kan ikke afprøve root-hjælperen; den testes som shell-script med mock-`nmcli` og på testserveren/Pi.
