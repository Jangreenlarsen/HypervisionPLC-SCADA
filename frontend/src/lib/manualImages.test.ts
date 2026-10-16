// @ts-nocheck — kun en kontrol af filer på disken (node), som frontendens typer ikke kender
// Skærmbillederne i manualen: alle henvisninger peger på en fil, ingen fil ligger som forældreløs, og ingen er tom.
// Billederne tages med `npm run manual:screenshots` (frontend/tools/manual-screenshots.mjs).
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = process.cwd();
const md = readdirSync(join(root, 'src', 'manual')).filter((f) => f.endsWith('.md')).map((f) => readFileSync(join(root, 'src', 'manual', f), 'utf-8')).join('\n');
const used = [...md.matchAll(/!\[([^\]]*)\]\(\/manual\/([^)]+)\)/g)].map((m) => ({ alt: m[1], file: m[2] }));

describe('skærmbilleder i manualen', () => {
  it('der er billeder, og hvert har en billedtekst', () => {
    expect(used.length).toBeGreaterThanOrEqual(20);
    for (const u of used) expect(u.alt.trim().length, u.file).toBeGreaterThan(8);
  });
  it('alle henviste billeder findes og er ikke tomme', () => {
    for (const u of used) {
      const path = join(root, 'public', 'manual', u.file);
      expect(existsSync(path), `${u.file} mangler — kør npm run manual:screenshots`).toBe(true);
      expect(statSync(path).size, u.file).toBeGreaterThan(3000);
    }
  });
  it('ingen billeder ligger som forældreløse (ikke brugt i manualen)', () => {
    const names = new Set(used.map((u) => u.file));
    for (const f of readdirSync(join(root, 'public', 'manual'))) expect(names.has(f), `${f} bruges ikke i manualen`).toBe(true);
  });
  it('filnavne er rene (ingen mellemrum eller specialtegn)', () => {
    for (const f of readdirSync(join(root, 'public', 'manual'))) expect(f, f).toMatch(/^[a-z0-9-]+\.png$/);
  });
});
