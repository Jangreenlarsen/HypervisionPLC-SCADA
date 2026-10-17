import { describe, expect, it } from 'vitest';
import { candidates, pasteReport, pasteTargets, pipes, rowLabel, sameType, summary, typeLabel, type SymbolRow } from './symbolCopy';

const rows: SymbolRow[] = [
  { element: 'R1', name: 'Rør 1', type: 'roer_v', configured: true },
  { element: 'R2', name: 'Rør 2', type: 'roer_v', configured: false },
  { element: 'B1', name: 'Bøjning 1', type: 'boejning90', configured: false },
  { element: 'T1', name: null, type: 't_stykke', configured: false },
  { element: 'P1', name: 'Pumpe 1', type: 'pumpe', configured: true },
  { element: 'E1', name: 'Eget', type: 'custom', configured: false },
  { element: 'E2', name: '  ', type: 'custom', configured: false },
];

describe('kopiér opsætning til flere', () => {
  it('kandidater udelader kilden og filtrerer på navn, id og type', () => {
    expect(candidates(rows, 'R1', '').map((r) => r.element)).toEqual(['R2', 'B1', 'T1', 'P1', 'E1', 'E2']);
    expect(candidates(rows, 'R1', 'RØR').map((r) => r.element)).toEqual(['R2']);
    expect(candidates(rows, 'R1', 't1').map((r) => r.element)).toEqual(['T1']);
    expect(candidates(rows, 'R1', 'pumpe').map((r) => r.element)).toEqual(['P1']);
    expect(candidates(rows, 'R1', '   ').length).toBe(6);
  });

  it('samme type og alle rør/fittings', () => {
    expect(sameType(rows, 'R1', 'roer_v')).toEqual(['R2']);
    expect(sameType(rows, 'E1', 'custom')).toEqual([]);   // egne symboler matcher ikke hinanden
    expect(sameType(rows, 'E1', '')).toEqual([]);
    expect(pipes(rows, 'R1')).toEqual(['R2', 'B1', 'T1']);
  });

  it('navne og opsummering', () => {
    expect(rowLabel(rows[3])).toBe('T1');
    expect(rowLabel(rows[6])).toBe('E2');                 // kun mellemrum tæller som intet navn
    expect(typeLabel('custom')).toBe('Eget symbol');
    expect(typeLabel('ukendt_type')).toBe('ukendt_type');
    expect(typeLabel('pumpe')).not.toBe('pumpe');
    expect(summary({ source: 'R1', results: [], ok: 3, skipped: 0, error: 0 })).toBe('3 kopieret.');
    expect(summary({ source: 'R1', results: [], ok: 1, skipped: 2, error: 1 })).toBe('1 kopieret, 2 sprunget over (havde allerede en opsætning), 1 med fejl.');
  });
});

describe('kopiér/indsæt i Tegn', () => {
  const clip = { drawingId: 'd', element: 'R1', name: 'Rør 1' };
  it('mål er de valgte symboler med navn, uden kilden', () => {
    expect(pasteTargets([{ id: 'R2', name: 'Rør 2' }, { id: 'x', name: '' }, { id: 'y', name: '  ' }, { id: 'z' }], clip))
      .toEqual({ targets: ['R2'], unnamed: 3, self: false });
    expect(pasteTargets([{ id: 'R1', name: 'Rør 1' }], clip)).toEqual({ targets: [], unnamed: 0, self: true });
  });
  it('rapport: info for kopierede, problemer og noter pr. symbol', () => {
    const name = (id: string) => ({ R2: 'Rør 2', B1: 'Bøjning 1', L: 'Lampe' } as Record<string, string>)[id] ?? id;
    const one = pasteReport({ source: 'R1', ok: 1, skipped: 0, error: 0, results: [{ element: 'R2', status: 'ok', message: '', notes: [] }] }, 'Rør 1', name);
    expect(one).toEqual({ info: 'Opsætningen fra "Rør 1" er indsat i "Rør 2".', problems: [] });
    const mixed = pasteReport({ source: 'R1', ok: 2, skipped: 0, error: 1, results: [
      { element: 'R2', status: 'ok', message: '', notes: [] },
      { element: 'B1', status: 'ok', message: '', notes: ['Animation 2 … sprunget over.'] },
      { element: 'L', status: 'error', message: 'Trin 4: Løbelys kræver streger', notes: [] },
    ] }, 'Rør 1', name);
    expect(mixed.info).toBe('Opsætningen fra "Rør 1" er indsat i 2 symboler.');
    expect(mixed.problems).toEqual(['Bøjning 1: Animation 2 … sprunget over.', 'Lampe: Trin 4: Løbelys kræver streger']);
    expect(pasteReport({ source: 'R1', ok: 0, skipped: 0, error: 1, results: [{ element: 'L', status: 'error', message: 'x', notes: [] }] }, 'Rør 1', name).info).toBe('');
  });
});
