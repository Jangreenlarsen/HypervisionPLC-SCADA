import { describe, expect, it } from 'vitest';
import { allDefs, emptyLayout, moveSymbol, moveSymbols, newSectionId, OWN_SECTION, ownDef, presetFor, sectionOf, sections, symbolsIn, type Layout, type OwnSymbol } from './library';
import { emptyConfig, libraryDefault, setOwnPresets, type SymbolInfo } from './symbolConfig';
import { CATEGORIES, SYMBOLS } from './symbols';

const own = (type: string, label: string, extra: Partial<OwnSymbol> = {}): OwnSymbol => ({
  type, label, hint: '', svg: '<g><rect id="kasse" width="10" height="10" onclick="x()"/></g>', preset: null, version: 1,
  created_at: 0, created_by: 'a', updated_at: 0, updated_by: 'a', ...extra,
});

describe('symbolbiblioteket med egne symboler', () => {
  it('egne symboler renses igen og ligger i "Egne symboler"', () => {
    const d = ownDef(own('u_kasse', 'Kasse'));
    expect(d.svg).not.toContain('onclick');
    expect(d.svg).toContain('<rect id="kasse"');
    expect(d.category).toBe(OWN_SECTION);
    expect(d.hint).toBe('Eget symbol');
    const all = allDefs([own('u_kasse', 'Kasse')]);
    expect(all.length).toBe(SYMBOLS.length + 1);
    expect(symbolsIn(all, emptyLayout(), OWN_SECTION).map((s) => s.id)).toEqual(['u_kasse']);
  });

  it('sektioner: indbyggede, egne og opdelingens rækkefølge', () => {
    const base = sections(emptyLayout()).map((s) => s.id);
    expect(base).toEqual([...CATEGORIES.map((c) => c.id), OWN_SECTION]);
    const lay: Layout = { ...emptyLayout(), sections: [{ id: 's1', label: 'Varme' }], order: ['s1', 'egne'] };
    expect(sections(lay).map((s) => s.id).slice(0, 2)).toEqual(['s1', 'egne']);
    expect(sections(lay).find((s) => s.id === 's1')?.builtin).toBe(false);
    expect(newSectionId(lay)).toBe('s2');
  });

  it('placering og flytning af symboler', () => {
    const all = allDefs([own('u_a', 'A'), own('u_b', 'B')]);
    let lay: Layout = { ...emptyLayout(), sections: [{ id: 's1', label: 'Varme' }] };
    lay = moveSymbol(all, lay, 'pumpe', 's1', 0);
    lay = moveSymbol(all, lay, 'u_b', 's1', 0);
    expect(symbolsIn(all, lay, 's1').map((s) => s.id)).toEqual(['u_b', 'pumpe']);
    expect(symbolsIn(all, lay, 'proces').some((s) => s.id === 'pumpe')).toBe(false);
    lay = moveSymbol(all, lay, 'u_b', 's1', 5);   // ud over enden → sidst
    expect(symbolsIn(all, lay, 's1').map((s) => s.id)).toEqual(['pumpe', 'u_b']);
    // en placering i en sektion, der ikke findes mere, falder tilbage til symbolets egen kategori
    const gone: Layout = { ...lay, sections: [] };
    expect(sectionOf(all.find((s) => s.id === 'pumpe')!, gone)).toBe('proces');
    expect(symbolsIn(all, lay, 's1', 'pum').map((s) => s.id)).toEqual(['pumpe']);
  });

  it('flyt flere symboler på én gang', () => {
    const all = allDefs([own('u_a', 'A'), own('u_b', 'B'), own('u_c', 'C')]);
    let lay: Layout = { ...emptyLayout(), sections: [{ id: 's1', label: 'Varme' }] };
    lay = moveSymbol(all, lay, 'pumpe', 's1', 0);
    lay = moveSymbols(all, lay, ['u_c', 'u_a'], 's1');
    expect(symbolsIn(all, lay, 's1').map((s) => s.id)).toEqual(['pumpe', 'u_a', 'u_c']);
    expect(symbolsIn(all, lay, 'egne').map((s) => s.id)).toEqual(['u_b']);
    expect(moveSymbols(all, lay, ['findes_ikke'], 's1')).toBe(lay);
  });

  it('guidens standardopsætning for et eget symbol bruger delene i tegningen', () => {
    const preset = { ...emptyConfig('u_kasse'), anims: [
      { part: 'loebehjul', type: 'spin' as const, src: '', params: {}, only: null },
      { part: 'all', type: 'blink' as const, src: '', params: {}, only: null },
      { part: 'mangler', type: 'fill' as const, src: '', params: {}, only: null },
    ] };
    expect(presetFor(null, () => undefined)).toBeNull();
    const map: Record<string, string> = { loebehjul: 'X1_loebehjul' };
    expect(presetFor(preset, (p) => map[p])?.anims.map((a) => a.part)).toEqual(['X1_loebehjul', 'all']);
    setOwnPresets({ u_kasse: preset });
    const info: SymbolInfo = { tag: 'g', line: false, type: 'u_kasse', name: 'K', parts: { X1_loebehjul: { tag: 'circle', line: false, pid: 'loebehjul' } } };
    const d = libraryDefault(info);
    expect(d?.config.anims.map((a) => a.part)).toEqual(['X1_loebehjul', 'all']);
    expect(d?.config.type).toBe('u_kasse');
    expect(preset.anims[0].part).toBe('loebehjul');   // forlægget ændres ikke
    expect(libraryDefault({ ...info, type: 'u_ukendt' })).toBeNull();
    setOwnPresets({});
  });
});
