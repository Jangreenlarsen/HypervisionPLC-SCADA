# Testvejledning: System › Konfiguration på en rigtig Pi

Gælder v0.119.0 – v0.125.0 (visning, trend-indstillinger, netværk med DHCP-vagt — både NetworkManager og ifupdown, flyt af trend-databasen, scada-maint).

**Status 2026-10-22:** hele backend-suiten (593 tests) er kørt på testserveren (Debian 13 VM på ESXi, `dash`, Python 3.13) og består, og `ifupdown`-forløbet er kørt mod serverens egen `/etc/network/interfaces` med falske `ifup`/`ifdown` (intet ændret på serverens netværk). Det der **ikke** er prøvet, er de rigtige `ifup`/`ifdown`/`nmcli`-kommandoer.
Alt er testet automatisk mod falske `nmcli`/diske — **intet er afprøvet på en rigtig Pi**. Denne vejledning dækker det, der kun kan ses dér.

Brug en Pi med **fysisk adgang** (skærm + tastatur eller seriel), og helst en testserver — ikke en maskine i drift. Tag et skærmbillede / notér resultatet ved hvert punkt (skema nederst).

---

## 0. Forberedelse

| | |
| --- | --- |
| **Hvad skal du bruge** | En Pi 4 med Raspberry Pi OS Bookworm (NetworkManager), netværkskabel, en router med DHCP, en pc på samme net, en USB-SSD (eller USB-stik) til punkt 6 |
| **Tjek NetworkManager** | `command -v nmcli && nmcli general status` — skal vise `connected`. Mangler `nmcli`, kan netværksdelen ikke testes (siden skal da selv skrive det) |
| **Noter først** | `nmcli -t connection show`, `ip -4 addr`, `ip route` — så du kan gendanne ved et uheld |
| **Nødplan hvis du låser dig ude** | **Genstart Pi'en** (træk strømmen): ændringer under en afprøvning er midlertidige og forsvinder ved genstart. Står en ændring som *bekræftet* (varig), så ret med tastatur/seriel: `sudo nmcli connection modify "<profil>" ipv4.method auto ipv4.addresses "" ipv4.gateway "" && sudo nmcli connection up "<profil>"` |

## 0b. ESXi-/Debian-VM (ifupdown) — testserveren

Testserveren (`10.1.1.31`) er en Debian 13-VM: netværk via `ifupdown` (`/etc/network/interfaces`, kortet hedder `ens3`), **ingen** NetworkManager, **ingen** `sudo` og **ingen DHCP-klient**. Derfor:

1. Kør alt "som root" med `su -` (rod-adgangskoden), eller installér sudo én gang: `su -c 'apt install sudo && usermod -aG sudo jgl'` (log ud og ind igen).
2. `cat /var/lib/hypervisionplc-scada-net/capabilities` skal vise `backend=ifupdown` (og `dhcp=0`, indtil `dhcpcd` er installeret). Hvis den viser `backend=none` eller filen mangler: den nyeste pakke er ikke installeret — installér den fra **System › Opdatering** (`install.sh` ligger kun i opdateringspakken, ikke på serveren). Filen opdateres selv hvert halve minut (DHCP-vagtens timer).
3. **Fast IP** kan prøves med det samme (4.1 – 4.5 nedenfor, men med `ip -4 addr` og `cat /etc/network/interfaces` i stedet for `nmcli`). Brug **en adresse i samme net**, og hav ESXi-konsollen åben (VM'ens skærm i vSphere/ESXi), hvis SSH/web falder ud.
4. For at prøve **DHCP** på VM'en: `su -c 'apt install dhcpcd-base'` (kun **dhcpcd** godkendes — `dhclient` kører med `-1` og `udhcpc` giver ingen levetid), vent et halvt minut (så står der `dhcp=1` i `capabilities`), og sørg for at ESXi-netværket har DHCP. Netkortet bør også have `iface ens3 inet dhcp`-blokken efter en bekræftet ændring, og `ip -4 addr show dev ens3` skal vise flaget `dynamic` på DHCP-adressen.
5. Kontroller efter en bekræftet ændring: `cat /etc/network/interfaces` (den nye blok + `# Sat af HypervisionPLC SCADA`), `ls /etc/network/interfaces.hypervision-bak-*` (sikkerhedskopi), `cat /etc/resolv.conf` (nameserver er ændret, `domain`/`search` er bevaret).
6. **Nødplan på VM'en:** ESXi-konsollen → log ind → `cp /etc/network/interfaces.hypervision-bak-<nyeste> /etc/network/interfaces && ifdown --force ens3; ifup ens3`. Under en afprøvning (før Bekræft) er filen urørt, så en genstart af VM'en giver den gamle opsætning.
7. VM-hensyn: kortets navn er `ens3`/`ens192` (ikke `eth0`), MAC kan skifte ved kloning, og en VM har ingen USB-SSD — til flytning af trend-databasen (punkt 6) bruges i stedet en **ekstra virtuel disk** monteret på fx `/mnt/data` (`mkfs.ext4`, `mount`, `install -d -o scada -g scada`).

## 1. Installation og kontrol

1. Byg pakken (`sh deploy/make-package.sh`) og installér via **System › Opdatering** — eller første gang som root: `sudo sh deploy/install.sh`.
2. På Pi'en:
   ```
   ls -l /var/lib/hypervisionplc-scada-net        # skal vise filen 'enabled' (root-ejet mappe)
   systemctl status hypervisionplc-scada-config.path hypervisionplc-scada-netwatch.timer
   systemctl show hypervisionplc-scada -p ReadWritePaths   # skal indeholde /mnt og /media
   ```
3. Åbn **System › Konfiguration** som admin.

**Forventet:** siden åbner; **Netværksopsætning** viser en formular (ikke en gul besked).
- Ser du *"Maskinens netværkssystem understøttes ikke"* → hverken NetworkManager eller ifupdown blev fundet (`cat /var/lib/hypervisionplc-scada-net/capabilities`).
- Ser du *"Netværkshjælperen er ikke installeret"* → den nyeste pakke er ikke installeret (installér den fra System › Opdatering; `install.sh` ligger kun i pakken).

## 2. Visning (v0.119.0)

- **Lagring**: datamappen er `/var/lib/hypervisionplc-scada`; filstørrelser og ledig plads stemmer med `df -h /var/lib` og `ls -l`.
- **Netværk**: netkort, link, MAC, IPv4-adresser, gateway og DNS stemmer med `ip -4 addr`, `ip route`, `cat /etc/resolv.conf`.
- **Skrivemåling**: efter 10 min vises et overslag rækker/døgn. Sammenlign groft med `sudo cat /sys/block/mmcblk0/stat` før/efter en time (kolonne 7 = sektorer skrevet).

## 3. Trend-indstillinger (v0.120.0)

1. Sæt *Skriveinterval* til 60 s og *Opbevaring* til 14 dage → **Gem**. **Forventet:** "Gemt — gælder straks".
2. `cat /var/lib/hypervisionplc-scada/config/settings.json` viser værdierne. Genstart tjenesten (`sudo systemctl restart hypervisionplc-scada`) — værdierne er stadig dér.
3. Forkerte værdier (0 eller 9999) afvises med en besked.
4. Auditloggen (System › Log) har linjen `system.config.trends`.

## 4. Netværk (v0.121.0) — vigtigst

**Før hver prøve:** hav en anden vej ind (tastatur/seriel) og noter Pi'ens nuværende IP.

| # | Prøve | Sådan | Forventet |
| --- | --- | --- | --- |
| 4.1 | **Fast IP, bekræft** | Tilstand *Fast IP*, en ledig adresse i dit net (fx .50), subnet 24, gateway = routeren, DNS = routeren → Anvend. Åbn `http://<ny IP>/` på pc'en og tryk **Bekræft** inden 90 s | Siden på den nye adresse viser *Bekræftet*. `ip -4 addr` viser den nye adresse. Genstart Pi'en: adressen er **stadig** den nye (varig) |
| 4.2 | **Fortryd** | Anvend en ny fast adresse, tryk **Fortryd nu** (eller vent) | Den gamle adresse er tilbage inden for få sekunder; status *Gendannet* |
| 4.3 | **Ingen bekræftelse** | Anvend og lad være med at trykke | Efter 90 s er den gamle opsætning gendannet; status *Gendannet — ingen bekræftelse* |
| 4.4 | **Strøm/proces dør midt i** | Anvend en ny adresse. Mens der ventes: træk strømmen — eller `sudo systemctl kill -s KILL hypervisionplc-scada-config.service` | Efter genstart / få sekunder er den **gamle** opsætning aktiv (ændringen var kun midlertidig) |
| 4.5 | **Forkert gateway** | Gateway uden for subnettet | Afvises med en besked, intet ændres |
| 4.6 | **DHCP** | Skift tilbage til *DHCP* | Adressen kommer fra routeren. Du kender den ikke på forhånd — find den i routeren og tryk **Bekræft** derfra. (Forvent ofte *Gendannet*, hvis du ikke når det — det er ikke en fejl.) |
| 4.7 | **DHCP + fast IP som sekundær** | Tilstand *DHCP + fast IP*, fx 192.168.100.10/24 | `ip -4 addr` viser **både** DHCP-adressen og 192.168.100.10. **Test uden DHCP-server:** fjern routerens DHCP / tag kablet direkte til en pc med adresse i 192.168.100.x og tryk Anvend — **skal netkortet stadig komme op?** (se "Uafklarede punkter") |
| 4.8 | **Værtsnavn** | Skift værtsnavn og bekræft | `hostname` viser det nye først efter bekræftelse; ved Fortryd er det uændret |
| 4.9 | **Standardprofilen** | Gentag 4.1 på en ny Pi med profilen "Wired connection 1" | Virker. Mislykkes det med *"ændring afvist"* eller *"Profilen kunne ikke læses"*, notér teksten fra `/var/lib/hypervisionplc-scada-net/network.log` |

Log under prøverne: `sudo tail -f /var/lib/hypervisionplc-scada-net/network.log` og `sudo journalctl -u hypervisionplc-scada-config -f`.

## 5. DHCP-vagt og reserve-IP (v0.123.0)

1. Tilstand *DHCP, fast IP først efter N fejl*, reserve-IP fx 192.168.100.10/24, N = 3 → Anvend og **bekræft** (kræver at DHCP virker).
2. Siden viser *DHCP-vagt: DHCP svarer*. `cat /var/lib/hypervisionplc-scada-net/watchdog.json`.
3. **Fjern DHCP**: tag kablet ud af routeren og sæt det direkte i en pc (pc'en får adressen 192.168.100.20/24 manuelt) — eller sluk routerens DHCP. Vent ~2 minutter.
   **Forventet:** siden/`watchdog.json` tæller 1, 2, 3 (*"Ingen DHCP-svar"*), og derefter *"kører på reserve-IP 192.168.100.10"*; `ip -4 addr` viser adressen; pc'en kan åbne `http://192.168.100.10/`.
4. **Tilbage på routeren**: DHCP svarer igen → inden for ~1 minut er reserve-IP'en fjernet og tælleren nulstillet.
5. **Kablet ud** (ingen link): tælleren skal **ikke** stige (*"ikke tilsluttet"*).
6. **Genstart** mens reserve-IP'en er aktiv: Pi'en starter forfra med ren DHCP og tæller igen.

`sudo tail -f /var/lib/hypervisionplc-scada-net/watchdog.log` og `systemctl list-timers | grep netwatch`.

## 6. Flyt trend-databasen (v0.122.0)

1. Tilslut USB-SSD'en og monter den, fx på `/mnt/ssd` (`lsblk`, `sudo mkdir -p /mnt/ssd && sudo mount /dev/sda1 /mnt/ssd`).
2. `sudo install -d -o scada -g scada -m 0750 /mnt/ssd/scada`.
3. Skriv `/mnt/ssd/scada` i **Flyt til mappe** → **Flyt databasen** → bekræft.
   **Forventet:** *"Databasen ligger nu i /mnt/ssd/scada/trends.db"*; Trends viser samme historik; `ls -l /mnt/ssd/scada` og `ls -l /var/lib/hypervisionplc-scada` (der ligger nu `trends.db.moved`).
4. Prøv ugyldige: `/etc`, `relativ/sti`, en sti på SD-kortet (`/var/tmp`), en mappe uden skriveret → hver afvises med en klar besked.
5. Genstart tjenesten og Pi'en: historikken er stadig der, og skrivningerne går til SSD'en (`sudo cat /sys/block/sda/stat`).
6. **Disk mangler**: sluk, tag SSD'en ud, start. **Forventet:** SCADA'en starter alligevel; siden viser en gul advarsel; Trends er tomme. Sæt SSD'en i igen, monter, skriv stien og flyt — historikken er tilbage (hvis `trends.db` i datamappen er den tomme, skal den først omdøbes; siden skriver det).
7. **Tilbage til datamappen**-knappen virker.

## 6b. Fuld disk: `scada-maint`

På testserveren (som root; `su -` hvis `sudo` mangler):
1. `scada-maint status` — viser størrelser; tallene stemmer med `du -sh /var/lib/hypervisionplc-scada/*`.
2. `scada-maint emergency` (tørkørsel) — viser trinnene; intet ændres (`ls -l` før/efter).
3. `scada-maint logs --yes` og `scada-maint backups --keep 1 --yes` — logfilerne er tomme, kun den nyeste backup er tilbage; websiden virker stadig.
4. `scada-maint trends --keep-days 7 --yes` — Trends viser kun de seneste 7 dage; energi-tags (Energi-siden) er urørt.
5. **Fuld disk-prøve** (kun testserver): fyld en lille partition/loop-fil, eller `fallocate -l <næsten alt> /var/lib/fyld.bin`, kør `scada-maint emergency --yes` og se at den stopper, når der er plads nok. Slet `fyld.bin` bagefter.
6. `scada-maint trends-reset --archive /root/arkiv --yes` — tjenesten stoppes og startes igen, og der ligger en `.db.gz` i arkivet.

## 7. Uafklarede punkter — find svar på disse

1. Virker `nmcli connection modify --temporary` rent på standardprofilen "Wired connection 1" (kan ligge kun i hukommelsen)? → prøve 4.1 og 4.9. (kun NetworkManager)
1b. **ifupdown:** kører `ifup`/`ifdown` via `systemd-run` (egen transient enhed, så DHCP-klienten overlever scriptet)? Efter en bekræftet DHCP-ændring: `pgrep -a dhcpcd` viser stadig klienten, når `apply-config`-tjenesten er færdig (`systemctl status hypervisionplc-scada-config`). Virker `ifdown --force -i <fil> ens3` + `ifup -i <ny fil> ens3` rent (tilstanden i `/run/network/ifstate`), og kommer kortet op igen med den gamle fil ved Fortryd? Opfører ifup sig ens med `dhcpcd-base` og `isc-dhcp-client`? Viser iproute2 flaget `dynamic` på DHCP-adressen (vagtens lease-test)?
2. Kommer netkortet op i tilstand *DHCP + fast IP* uden en DHCP-server (`connection up --wait 30`)? → 4.7. Mislykkes det, skal tilstanden ændres (fx aktiveres uden at vente på DHCP).
3. Gendanner `connection reload` + `up` virkelig den gemte profil efter en midlertidig ændring? → 4.2 – 4.4.
4. Tager reserve-IP'en (`--temporary` + `device reapply`) effekt uden at slippe DHCP-klienten? → 5.3.
5. Er `ProtectSystem=strict`/`ReadWritePaths` i de to root-enheder for stramt (hostnamectl, nmcli over D-Bus)? Se `journalctl -u hypervisionplc-scada-config` for "Read-only file system"-fejl.
6. Er 90 sekunder nok til at bekræfte? Skal fristen være længere ved DHCP-skift?

## 8. Resultatskema (send tilbage)

| Punkt | OK / Fejl | Besked / log (kort) |
| --- | --- | --- |
| 1 Installation | | |
| 2 Visning | | |
| 3 Trend-indstillinger | | |
| 4.1 – 4.9 Netværk | | |
| 5.1 – 5.6 DHCP-vagt | | |
| 6.1 – 6.7 Flyt database | | |

Vedhæft ved fejl: `sudo cat /var/lib/hypervisionplc-scada-net/network.log /var/lib/hypervisionplc-scada-net/watchdog.log`, `nmcli -t connection show`, `journalctl -u hypervisionplc-scada-config -n 100`.
