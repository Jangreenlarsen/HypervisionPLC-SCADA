---
name: scada-benchmark
description: Analysér projektet mod hvad branchen forventer af et SCADA/HMI (ISA-101, ISA-18.2/EEMUA 191, IEC 62443 m.fl.) med en fast kriterieliste, pointskala og rapportskabelon, så to kørsler kan sammenlignes. Brug til status på modenhed, før en større release eller for at prioritere næste features (/scada-benchmark).
---

Resultatet skal være ens i form fra gang til gang. Derfor: kriterierne står i `kriterier.md`, rapporten følger `rapportskabelon.md`, og vurderingerne gives efter fast skala med evidens. Begge filer ligger i denne skills mappe (`.claude/skills/scada-benchmark/`). Afvig ikke fra dem, og tilføj eller fjern ingen kriterier undervejs. Er listen forældet, rettes den som en særskilt ændring med hævet kriterie-version.

Metoden er en selvvurdering. Skriv aldrig at løsningen er "certificeret", "SIL-egnet" eller "overholder" en standard; skriv hvad den opfylder af *principperne*.

1. **Forberedelse** (selv, uden agent): læs `kriterier.md` og `rapportskabelon.md`. Notér version og build fra `version.json` og commit-hash (`git rev-parse --short HEAD`). Find den nyeste `docs/BENCHMARK_*.md`; findes den, er den sammenligningsgrundlag. Hold projektets faste ramme (CLAUDE.md) for øje: Raspberry Pi, al PLC-kommunikation via REST, én server. Kriterier der strider mod rammen kan markeres – med begrundelse.
2. **Se UI'et** (gælder gruppe A): brug `/screenshot` mod demoen på mindst Overview (fx `#/overview/varme`), Alarmer og en trend (find rutenavnene i `frontend/src`), og se billederne med Read. Meld i rapporten hvilke ruter og bredder der er *set*. Kan UI'et ikke nås, markeres A-kriterier uden kodebevis som U.
3. **Tre research-agenter parallelt** (`general-purpose`, skrivebeskyttede, i samme kald; skriv en linje om model/effort og hvorfor):

   | Agent | Grupper | Model / effort | Hvorfor |
   |---|---|---|---|
   | 1 | A og B | sonnet / high | vurdering af UI og alarmer ud fra kode og tests |
   | 2 | C og E | opus / high | PLC-skrivninger og sikkerhed: størst konsekvens ved fejlvurdering |
   | 3 | D, F og G | sonnet / high | data, drift og vedligehold |

   Giv hver agent samme faste opgave (udfyld kun gruppebogstaverne): *"Læs `.claude/skills/scada-benchmark/kriterier.md` og vurdér kun kriterierne i gruppe X efter skalaen dér. Søg i backend/, frontend/src/, docs/, deploy/, tests og CLAUDE.md/ARCHITECTURE.md. Returnér én linje pr. kriterium: `ID | 0/1/2/U/– | evidens (fil:linje, testnavn eller dokument) | note, højst 15 ord`. Gæt aldrig: kan du ikke påvise det, svar U. Ændr ingen filer, og kontakt ingen server."*
4. **Verificér** (selv, mod koden): kontrollér hver K-vurdering på 2 i gruppe C og E, hver 0 og U på et K-kriterium, og mindst 5 andre stikprøver. Ret vurderingen, hvis evidensen ikke holder, og noter i afsnit 7 hvad der er verificeret. Kriterier uden evidens sættes til U.
5. **Beregn**: score pr. gruppe og samlet = sum / (2 × relevante) afrundet til hele procent, og antal opfyldte K-kriterier (vurdering 2) af alle K. Sammenlign pr. kriterie-ID med forrige rapport; er kriterie-versionen anderledes, sammenlignes kun ID'er der findes i begge.
6. **Skriv rapporten** efter `rapportskabelon.md` til `docs/BENCHMARK_<dato>.md`. Alle otte afsnit, alle kriterier, samme overskrifter.
7. **Commit** som doku-commit (ingen versionsbump): `docs: SCADA-benchmark <dato> (<samlet score> %)`, og push `origin dev`. Spørg derefter om merge til `main`, jf. CLAUDE.md regel 5.
8. **Afrapportér i chatten**, højst 15 linjer: gruppetabellen med score og ændring, de 5 vigtigste huller, hvad der er forbedret eller forværret siden sidst, og stien til rapporten. Spørg hvilke huller der skal registreres i `FEATURES.md`; registrér dem ikke uden svar.
