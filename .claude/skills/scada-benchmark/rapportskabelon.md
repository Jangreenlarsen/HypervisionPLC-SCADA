# Rapportskabelon

Rapporten gemmes som `docs/BENCHMARK_<YYYY-MM-DD>.md` og har altid disse afsnit, i denne rækkefølge og med disse overskrifter. Ingen afsnit udelades; er der intet at skrive, står "Ingen".

```markdown
# SCADA-benchmark <YYYY-MM-DD> — v<version> b<build>

Commit: <hash> · Kriterie-version: <n> · Forrige rapport: <filnavn eller "ingen"> · UI set: <ruter og bredder, eller "ikke set">

Selvvurdering mod branchens forventninger (ISA-101, ISA-18.2/EEMUA 191, IEC 62443 m.fl.). Ikke en certificering og ingen sikkerhedsklassificering (SIL).

## 1. Resumé

| Gruppe | Score | Forrige | Δ | Kritiske (K) opfyldt |
|---|---|---|---|---|
| A. HMI-design | xx % | xx % | ±x | x af y |
| ... B til G ... | | | | |
| **Samlet** | xx % | xx % | ±x | x af y |

Score = sum af vurderinger / (2 × relevante kriterier). U tæller som 0. Til sidst én sætning: den vigtigste enkeltkonklusion.

## 2. Positionering

Fire faste punkter, hver 1-2 linjer: (1) hvilken type anlæg løsningen er klar til nu, (2) hvad den endnu ikke bør bruges til, (3) hvad der adskiller den positivt fra typiske lette web-HMI'er, (4) hvad der først og fremmest skal til for at nå næste niveau.

## 3. Styrker

Højst 5 punkter: kriterie-ID, hvad der er opnået, evidens (fil:linje).

## 4. Huller, rangeret

Sorteret K før V før N, derefter laveste vurdering først. Højst 15 rækker.

| ID | Pri | Hul | Evidens | Forslag | Indsats (S/M/L) |
|---|---|---|---|---|---|

## 5. Ændringer siden forrige

Pr. ID der er ændret: forbedret/forværret og hvorfor (commit/version hvis kendt). Står der "Ingen forrige rapport", skriv det. Er kriterie-versionen ændret, skriv hvilke ID'er der ikke kan sammenlignes.

## 6. Detaljer pr. gruppe

En tabel pr. gruppe A til G med ALLE kriterier: `ID | Pri | Vurdering | Evidens | Note (højst 15 ord)`.

## 7. Forbehold og afgrænsning

Kriterier markeret – (med begrundelse) og U (med hvad der manglede for at kunne vurdere). Hvad der ikke er kontrolleret (fx kun kode læst, ikke kørt på Pi'en). Hvilke vurderinger der er verificeret af orkestratoren, og hvilke der er agentens uverificerede udsagn.

## 8. Anbefalet næste skridt

Højst 5 punkter, hver knyttet til ID'er og klar til at blive en post i FEATURES.md.
```
