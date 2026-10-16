# Tegninger og Tegn

En **tegning** er et SVG-billede af anlægget. Du kan **uploade** en tegning lavet i et andet program (fx Inkscape) eller **tegne** den i systemets egen editor. Begge dele ligger under **Opsætning** (kræver rollen tekniker).

## Tegninger

Siden **Tegninger** er listen over alle tegninger.

- **Upload tegning**: vælg en SVG-fil (højst 5 MB), giv den et **navn** og evt. en **kommentar**. Serveren renser filen (scripts og andet farligt fjernes) og viser en rapport over, hvad der blev fjernet.
- **Versioner**: hver gang du uploader eller gemmer, opstår en ny **version**. **Versioner** viser listen; **Gør aktiv** vælger, hvilken version Overview viser. Du kan derfor forberede en ny version uden at brugerne ser den, og gå tilbage, hvis noget går galt. **Upload ny version** lægger en ny version til en eksisterende tegning.
- **Gør start-tegning**: Overview åbner med denne tegning. **Fjern** start-tegningen, og Overview åbner med den første i listen.
- **Slet**: sletter tegningen med alle versioner og bindinger. Før du bekræfter, viser systemet **hvad det rammer**: antal versioner og bindinger, andre tegninger med en "gå til"-knap hertil (de holder op med at virke), om det er start-tegningen, og hvilke brugere der har adgang til den.

> Bindinger følger tegningens **element-id'er**. Ændrer en ny version et elements id, mister det sin binding; **Bindinger** viser *Forsvundne elementer*, som du kan rydde op i.

## Tegn

**Tegn** er en indbygget tegneeditor (SVG-Edit). Brug den til at tegne rør, tanke og tekst, eller til at indsætte færdige **symboler** fra biblioteket.

### Sådan tegner du

1. Vælg en eksisterende tegning (og version) i rullelisterne øverst, eller start en ny (**— Ny tegning —**).
2. Tegn med værktøjerne i editoren: linjer, rektangler, cirkler, tekst, farver og lag.
3. Til højre ser du **Valgt element**. Giv det et **Navn**, hvis det skal være et symbol, der senere kan sættes op med guiden. **Avanceret** viser elementets tekniske **id**.
4. Tryk **Gem kladde** (gemmer en ny version, men viser den ikke endnu) eller **Gem og udgiv** (gemmer og gør den aktiv). En ny tegning skal have et navn.
5. **Slet tegning** fjerner hele tegningen (med samme oversigt over, hvad det rammer).
6. **Bindinger** åbner bindingsiden for tegningen.

Er der ændringer, du ikke har gemt, spørger systemet, før de kasseres.

### Symbolbiblioteket

Under tegneområdet finder du **symbolbiblioteket**, sorteret i kategorier (*Betjening*, *Proces og visning*, *Rør og VVS*, *Elektrisk*, *Solcelleanlæg*). Søg efter et symbol (fx *bøjning* eller *kontaktor*), og tryk på det for at sætte det ind midt på tegningen; flyt og tilpas det bagefter. Hvert indsat symbol får et **navn** (fx *Pumpe 2*), som du kan ændre.

Et nyindsat symbol skal **sættes op**: vælg symbolet og tryk **Opsæt symbol (6 trin)**. Tegningen gemmes og udgives først (du bliver spurgt), fordi guiden arbejder på den aktive version. Se *Symboler og guiden*.

**Omskifter med egne positioner**: under *Betjening* kan du skrive positionernes navne (2–8, adskilt med komma, fx *Hånd, 0, Auto*) og indsætte en omskifter med lige det antal positioner.

> Rør og fittings (bøjninger, T-stykker, kryds) er tegnet i samme tykkelse, så de passer sammen. Brug **Løbelys** på rør for at vise strømning.
