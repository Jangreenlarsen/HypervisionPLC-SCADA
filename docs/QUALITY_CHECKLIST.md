# Kodekvalitets-tjekliste

Læses før implementering af auth, permissions, PLC-skrivninger, data-integritet, eksterne API'er og bulk-operationer, og som selvtjek før en feature/fix meldes færdig.

- **Null/fejl-propagering**: Ethvert kald der kan returnere `None`/`null` eller kaste, har sit resultat tjekket før brug. Antag aldrig succes.
- **Fejlbeskeder til brugeren**: Frontend viser altid den specifikke backend-fejl, ikke kun en generisk. Enhver `catch` viser fejlen eller har en begrundet kommentar om hvorfor den undertrykkes.
- **Adgangskontrol-lockout**: Permission-/rollesystemer må aldrig ende uden nogen med adgang til at rette det (fx sidste admin fjernet). Håndhæv i backend, ikke kun i UI.
- **Eksterne API'er og "tomhed"**: Brug `is not None`, aldrig ren truthiness, for felter der lovligt kan være `0`/tomme. Håndtér altid et catch-all for uventede fejlstatusser.
- **"Tomhed" generelt**: Rettes en bug for én repræsentation af tom (`null`), tjek også tom streng og whitespace-only. Ret hele klassen.
- **Sikkerhedskonfiguration**: Usikre default-værdier (hemmeligheder, nøgler, adgangskoder) skal advare eller nægte opstart. Aldrig stille igennem.
- **Samtidige delvise opdateringer**: Ingen read-modify-write af hele dokumentet hvis kald kan ske i hurtig rækkefølge. Brug punkt-sti `$set` på kun de ændrede felter.
- **Bulk mod eksterne API'er**: Batch-dækkende fejl (manglende nøgle, rate-limit) håndteres adskilt fra enkeltelement-fejl. Tjek forudsætninger før løkken, og stop straks ved rate-limit.
- **Test i faktisk runtime-kontekst**: Kører koden i systemd/container/begrænset bruger, verificér dér, ikke kun i et privilegeret shell.
- **Rammeværkets fejlformat**: Rammeværket kaster fejl i eget format (fx valideringsfejl som liste af objekter). Tjek både egne og rammeværkets former.
- **Regler der kun gælder én gren**: Indføres en regel for ét tilfælde, gennemgå straks de øvrige grene (opdatering, anden ressource, import-vejen).
