// @ts-nocheck — kun et udviklerværktøj der bruger node (fs/path), som frontendens typer ikke kender
// Genererer frontend/src/manual/07-symbolbibliotek.md ud fra symbolbiblioteket (kør med: GEN_MANUAL=1 npx vitest run src/lib/manualGen.test.ts).
// Uden GEN_MANUAL kontrolleres kun at kapitlet er opdateret, så et nyt symbol ikke kan glemmes i manualen.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { CATEGORIES, SYMBOLS } from './symbols';
import { OP_TXT, allowedOps } from './symbolConfig';

const FILE = join(process.cwd(), 'src', 'manual', '07-symbolbibliotek.md');   // vitest kører fra frontend-mappen

function build(): string {
  const out: string[] = [
    '<!-- GENERERET af src/lib/manualGen.test.ts ud fra symbolbiblioteket — ret ikke i hånden; kør GEN_MANUAL=1 npx vitest run src/lib/manualGen.test.ts -->',
    '# Symbolbiblioteket',
    '',
    `Biblioteket har **${SYMBOLS.length} symboler** i ${CATEGORIES.length} kategorier. Du sætter dem ind i **Tegn** og sætter dem op med **guiden i 6 trin** (se *Symboler og guiden*). Kolonnen **Kan sættes op som** viser de betjeningsformer, guiden som standard tilbyder for symbolet; **Vis alle betjeningsformer** i guidens trin 1 åbner for resten.`,
    '',
  ];
  for (const c of CATEGORIES) {
    const list = SYMBOLS.filter((s) => s.category === c.id);
    // Skærmbillede af kategorien i Tegn (tages med npm run manual:screenshots)
    out.push(`## ${c.label}`, '', `![Symbolerne i kategorien ${c.label.replace(/ \(.*\)$/, '')}](/manual/bibliotek-${c.id}.png)`, '', '| Symbol | Kan sættes op som | Bemærkning |', '| --- | --- | --- |');
    for (const s of list) {
      const ops = allowedOps(s.id).map((o) => OP_TXT[o]).join(', ');
      out.push(`| **${s.label}** | ${ops} | ${s.hint.replace(/\|/g, '/')} |`);
    }
    out.push('');
  }
  out.push('> Symboler uden betjening (rør, tank, målere, lamper, solcelledele) viser kun. Rør og fittings kan få **Løbelys**, der viser strømningsretning.', '');
  return out.join('\n');
}

describe('manualen: symbolbiblioteket', () => {
  it('kapitlet er opdateret (genereres med GEN_MANUAL=1)', () => {
    const wanted = build();
    if (process.env.GEN_MANUAL) writeFileSync(FILE, wanted, 'utf-8');
    expect(readFileSync(FILE, 'utf-8').replace(/\r\n/g, '\n')).toBe(wanted.replace(/\r\n/g, '\n'));
  });
});
