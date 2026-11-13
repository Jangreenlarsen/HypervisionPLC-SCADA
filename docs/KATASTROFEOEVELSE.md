# Katastrofeøvelse: gendan på en ny maskine

Formål (produktionsanalysen, afsnit C): bevise, at en ny maskine kan overtage fra en backup — tegninger, tags, brugere og opsætning. Øvelsen tager cirka en time. Gentag den efter store ændringer og mindst en gang om året.

## Hvad der ligger hvor
| Hvad | Hvor | I backup? |
| --- | --- | --- |
| Tegninger, tags, bindinger, symboler, signalveje, brugere, alarmer, ugeprogrammer | `scada.db` | **Ja** (System › Backup, JSON; `scada-tool backup create`, SQLite-kopi) |
| PLC-adgangskoder, tokens, sessionsnøgle | `data/secrets.json` | **Nej — med vilje.** Skal gemmes særskilt (se nedenfor) |
| Trend-historik | `trends.db` | Eget øjebliksbillede (`trends-auto-*.db.gz`) |
| Miljøfil, certifikater | `/etc/hypervisionplc-scada.env`, `data/` | Nej — sæt op igen (`install.sh`) |

## Forberedelse (én gang)
- Gem `secrets.json` et sikkert sted (adgangskodehvælv, ikke i git): `cp /var/lib/hypervisionplc-scada/secrets.json …`.
- Hav en nylig backup liggende uden for maskinen (System › Backup › *Hent*, eller et backup-mål under *Backup*).
- Hav den seneste OTA-pakke (`scada-<version>-b<build>.tar`).

## Øvelsen
1. **Ny maskine** (Raspberry Pi eller VM) med Raspberry Pi OS / Debian. Giv den adgang til PLC'erne.
2. **Installér:** pak pakken ud, og kør `sudo sh scada/deploy/install.sh` (se `docs/TEST_PI.md`).
3. **Første login:** `admin` oprettes med adgangskoden fra `SCADA_ADMIN_PASSWORD` (miljøfilen), ellers med en genereret engangsadgangskode i `<data>/initial-admin-password.txt` — skift den ved første login.
4. **Gendan backup:** System › Backup › *Gendan* (JSON). Alternativt, på maskinen: stop tjenesten og brug `scada-tool backup restore FIL.db`.
5. **Hemmeligheder:** læg `secrets.json` tilbage (ejer `scada`, rettigheder `0600`), `scada-tool restart`. Uden den skal PLC-adgangskoder og tokens sættes igen under PLC'er.
6. **Tjek:**
   - [ ] `scada-tool check` — alt OK.
   - [ ] Brugerne kan logge ind (roller og tegningsadgang er som før).
   - [ ] Tags kan læses fra PLC'erne (Status: ingen *kommunikation tabt*).
   - [ ] Overview viser tegningerne med live-værdier; en signalvej løber.
   - [ ] Alarmer og ugeprogrammer er der; en test-alarm kommer.
   - [ ] Trends: historikken er gendannet fra øjebliksbilledet (hvis det er med).
7. **Noter:** hvor lang tid det tog, og hvad der manglede. Ret `scada-tool`/manualen, så næste gang er hurtigere.

## Typiske forskelle
- **Forskellig IP/netværk:** ret under System › Konfiguration, eller `scada-tool config` for at se, hvad maskinen lytter på.
- **Backup fra en ældre version:** den gendannes og opgraderes ved første start (backup tages automatisk før opgradering).
- **En PLC findes ikke mere:** tags til den springes over med en besked; ret under PLC'er.
