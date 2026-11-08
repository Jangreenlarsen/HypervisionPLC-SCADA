# HTTPS med et rigtigt certifikat (Let's Encrypt via certbot + deSEC)

Som standard bruger SCADA-siden HTTPS med et **selvsigneret** certifikat (browsere advarer). Her er opskriften på et **Let's Encrypt-certifikat**, så browsere stoler på siden — også når Pi'en kun står på det lokale net (adressen skal ikke kunne nås fra internettet).

## Sådan virker det

Let's Encrypt skal bevise, at du ejer navnet (fx `scada.laces.dk`). Pi'en kan ikke nås udefra, så beviset sker med en **DNS-udfordring** (en midlertidig TXT-post). Fordi one.com ikke har et API, peger `_acme-challenge.scada.laces.dk` med en **CNAME** over på en gratis zone hos **deSEC**. En lille hook (`desec-acme-hook.sh`) skriver TXT-posten direkte i den zone via deSEC's API, og Let's Encrypt følger CNAME'en og læser den. (Debians færdige certbot-plugin til deSEC følger ikke CNAME'er, derfor hooken.) Certifikatet gælder 90 dage og **fornyes automatisk** (Debians `certbot.timer`); efter hver fornyelse lægger scriptet `cert-deploy.sh` det nye certifikat ved nginx og genindlæser nginx.

Slår noget fejl, **bliver det selvsignerede certifikat liggende** — siden kan altid åbnes.

## 1. Én gang: deSEC og DNS

1. **deSEC**: opret en konto på <https://desec.io>. Opret en zone (*Add domain*), fx `mitnavn.dedyn.io` (gratis).
2. **Token**: *Token Management → New token*. Kopiér tokenet (vises kun én gang). Brug en konto kun til dette, så tokenet ikke kan røre andre domæner.
3. **one.com** (DNS for `laces.dk`): opret en CNAME-post
   - Navn: `_acme-challenge.scada`
   - Værdi: `scada-acme.mitnavn.dedyn.io` (et navn i din deSEC-zone; det behøver ikke at findes på forhånd)
4. **Navnet skal pege på Pi'en**: `scada.laces.dk` → `10.1.1.33` (A-post hos one.com, eller i jeres interne DNS). En privat adresse er fin.

Kontrol fra en PC: `nslookup -type=CNAME _acme-challenge.scada.laces.dk` skal give `scada-acme.mitnavn.dedyn.io`.

## 2. På Pi'en (som root / med sudo)

```
sudo hypervision-letsencrypt install          # certbot (apt) og automatisk fornyelse
sudo hypervision-letsencrypt set-token        # indsæt deSEC-tokenet (vises ikke; gemmes kun for root)
sudo hypervision-letsencrypt set-target mitnavn.dedyn.io    # din deSEC-zone (CNAME'en skal pege på scada-acme.mitnavn.dedyn.io)
sudo hypervision-letsencrypt issue scada.laces.dk din@mail.dk --dry-run     # prøve mod Let's Encrypts STAGING — intet gemmes
sudo hypervision-letsencrypt issue scada.laces.dk din@mail.dk               # det rigtige certifikat
sudo hypervision-letsencrypt renew-test       # prøv fornyelsen (dry-run)
```

Kør **altid `--dry-run` først**: Let's Encrypt har grænser (fx 5 mislykkede forsøg i timen pr. navn). Efter udstedelsen: åbn `https://scada.laces.dk` — hængelåsen skal være lukket. **System › Status** viser et kort *HTTPS-certifikat udløber om N dage* (gul under 21 dage, rød under 7 — det betyder, at fornyelsen er stoppet).

## Hvor ligger hvad

| | |
|---|---|
| deSEC-token og zone | `/etc/hypervisionplc-scada/letsencrypt/desec.ini` (token) og `target.conf` (zone/navn) — root, 0600. Aldrig i git, log, backup eller web-API |
| certbots filer | `/etc/letsencrypt/` (certbots egne; navn `hypervision-scada`) |
| certifikat til nginx | `/etc/hypervisionplc-scada/tls/fullchain.pem` + `privkey.pem` (nginx-konfigurationen ændres ikke) |
| tidligere certifikat | `*.prev`; det oprindelige selvsignerede: `*.selfsigned` |
| certifikatets metadata til Status | `/var/lib/hypervisionplc-scada-net/cert.json` |
| certbots log | `/var/log/letsencrypt/letsencrypt.log` |

Tokenet og certifikatet følger **ikke** med i en SCADA-backup. På en ny maskine køres opskriften igen.

## Fejlsøgning

- **`certbot fejlede`** — læs `/var/log/letsencrypt/letsencrypt.log`. Typisk: CNAME-posten mangler/er forkert, tokenet er ugyldigt, zonen i `set-target` findes ikke på deSEC-kontoen (HTTP 404), eller Pi'en har ikke internet/korrekt tid (`timedatectl`). Er certifikatet udstedt, men installationen fejlede, ligger det i `/etc/letsencrypt` — kør `sudo hypervision-letsencrypt status`.
- **Udfordringen finder ikke posten** — det kan tage et par minutter, før one.com har publiceret CNAME'en; prøv `--dry-run` igen lidt senere.
- **Siden kan ikke findes på navnet** — `scada.laces.dk` peger ikke på Pi'en (punkt 4 ovenfor). Certifikatet er i orden.
- **Tilbage til det selvsignerede** — `sudo cp /etc/hypervisionplc-scada/tls/fullchain.pem.selfsigned /etc/hypervisionplc-scada/tls/fullchain.pem`, tilsvarende for `privkey.pem`, derefter `sudo systemctl reload nginx` og `sudo hypervision-letsencrypt status` (så Status-siden viser det rigtige certifikat). `*.prev`/`*.selfsigned` ryddes ikke op.
- **Tjek tilstanden** — `sudo hypervision-letsencrypt status`.

## HSTS

nginx sender endnu **ikke** `Strict-Transport-Security`. Det slås først til, når certifikatet er fra Let's Encrypt og har kørt fornyelse en gang — ellers kan browsere låses ude, hvis certifikatet skiftes.

## Alternativ: samme certifikat som en reverse proxy (v4.11.0)

Står SCADA'en bag en reverse proxy, der allerede har et Let's Encrypt-certifikat for SCADA'ens navn (fx `certbot --nginx` på proxyen, som for scada.laces.dk), kan proxyen sende certifikatet videre efter hver fornyelse. SCADA'en bruger så **samme certifikat**, og klienter på LAN, der går direkte til SCADA'en, kan stole på TLS. Der skal hverken deSEC eller certbot på SCADA'en.

- **Proxyen:** `deploy/proxy-cert-push.sh` installeres som certbot deploy-hook og sender `fullchain.pem` + `privkey.pem` som tar over SSH med en dedikeret nøgle.
- **SCADA'en:** nøglen står i root's `authorized_keys` med `from="<proxyens IP>",command="/usr/local/lib/hypervisionplc-scada/cert-receive.sh",restrict`. Nøglen kan derfor kun aflevere et certifikat.
- **`cert-receive.sh` kontrollerer filerne:**
  - kun de to navne og almindelige filer;
  - PEM, højst 64 KB;
  - certifikatet gælder SCADA'ens navn og er ikke udløbet.
- Derefter installerer `cert-deploy.sh` certifikatet: nøgle og certifikat skal passe sammen, `nginx -t` skal godkende, og det forrige gendannes ved fejl.
- Log: `/var/lib/hypervisionplc-scada-net/cert-receive.log`. *System › Status* viser certifikatets udløb som sædvanligt.

Opskriften står øverst i `deploy/proxy-cert-push.sh`. Prøv i hånden på proxyen med `RENEWED_LINEAGE=/etc/letsencrypt/live/scada.laces.dk /etc/letsencrypt/renewal-hooks/deploy/scada-cert-push.sh`.
