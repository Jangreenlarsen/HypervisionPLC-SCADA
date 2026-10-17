import { describe, expect, it } from 'vitest';
import { candidates, pipes, rowLabel, sameType, summary, typeLabel, type SymbolRow } from './symbolCopy';

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
