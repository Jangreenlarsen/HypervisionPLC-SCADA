# Fejlfinding og ordliste

## Fejlfinding

| Symptom | Mulig årsag | Hvad du gør |
| --- | --- | --- |
| Overview viser **—** eller ingen værdier | PLC'en svarer ikke, eller tagget findes ikke | Se statuschippen øverst og **PLC'er**. Kontrollér adresse og adgangskode. Alarmen *kommunikationsfejl* kommer efter en kort forsinkelse |
| Et element ændrer sig ikke | Det er ikke bundet, tagget er forkert, eller elementets id er ændret | Åbn **Bindinger**, vælg elementet. Findes det under *Forsvundne elementer*, er id'et ændret i en ny version |
| Jeg kan ikke klikke/betjene | Rollen er viewer, tagget er ikke skrivbart, eller elementet er kun til visning | Spørg en tekniker; tjek *Betjening* under **Tags** og symbolets betjeningsform |
| Skrivning afvist med en besked | Værdien er uden for tagets min/max, tagget kan ikke skrives, eller du mangler koden | Læs beskeden — den fortæller præcis hvorfor |
| Positionen viser *afvigelse* | PLC'en står ikke i den valgte position efter valideringstiden | Tjek tilbagemeldingen i guidens trin 6 (Live). Ret evt. *Tid til at bekræfte* |
| Guiden kan ikke gemme | Et trin har en rød prik | Åbn trinnet — fejlen står under det, med forklaring |
| Tag kan ikke slettes | Det bruges af en binding, et symbol, et ugeprogram eller en alarm | Fjern brugen først; beskeden nævner hvor |
| En logikblok kan ikke fjernes | Et andet symbol bruger den | Fjern henvisningen dér først |
| Opdateringen blev rullet tilbage | Den nye version startede ikke | Se loggen nederst på **Opdatering**; ret og prøv igen |
| Ugeprogram skriver ikke | Tagget er ikke skrivbart, PLC'en er utilgængelig, eller værdien er allerede sat | Se programmets status og **Log** |
| Tegningen viser ikke min nye version | Versionen er kun gemt som kladde | **Tegninger › Versioner › Gør aktiv** eller **Gem og udgiv** i Tegn |

## Ordliste

| Ord | Forklaring |
| --- | --- |
| **Tag** | En navngivet værdi fra PLC'en |
| **Kilde** | Hvor tagget hentes fra: `plc1:coil:0` |
| **Coil** | PLC-udgang (til/fra, kan skrives) |
| **DI** | Digital indgang (til/fra, kun læsning) |
| **HR** | Holdingregister (tal, kan skrives) |
| **IR** | Inputregister (tal, kun læsning) |
| **Binding** | Forbindelse mellem et element i tegningen og et tag |
| **Animation** | Hvad et element gør, når tagget ændrer sig |
| **Symbol** | Færdigt element fra biblioteket, sat op med guiden |
| **Guide** | De 6 trin der sætter et symbol op |
| **Position** | En navngiven tilstand for et symbol (*Hånd*, *0*, *Auto*) |
| **Kontaktplan** | Hvad en position skriver til et signal |
| **Signal** | Et tag et symbol skriver (og evt. læser tilbage) |
| **Logikblok** | En betingelse over flere tags (AND/OR/NOT) |
| **Pseudo-tag** | Intern værdi SCADA'en selv beregner (position, tilstand, logik) |
| **Version** | En gemt udgave af en tegning; én er *aktiv* |
| **Start-tegning** | Tegningen Overview åbner med |
| **SSE** | Push-strøm fra PLC'en med ændringer |
| **Dødbånd** | Hvor langt værdien skal bevæge sig tilbage, før en grænsealarm går |
| **Nøglelås** | Kode (4 cifre) der kræves for udvalgte positioner |
| **OTA** | Opdatering af SCADA'en fra websiden |
| **AGPL** | Licensen: programmet er fri software, og kildekoden er tilgængelig |
