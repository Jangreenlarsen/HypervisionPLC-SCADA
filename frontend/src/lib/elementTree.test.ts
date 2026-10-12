import { describe, expect, it } from 'vitest';
import { ancestorsOf, buildElements, defaultExpanded, descendantCount, displayName, showsId, visibleRows } from './elementTree';

function svg(markup: string): Element {
  return new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${markup}</svg>`, 'image/svg+xml').documentElement;
}

const ROOT = svg(
  '<rect id="baggrund"/>' +
  '<g id="Ventilator" data-hv-name="Vippekontakt" data-hv-desc="Starter ventilatoren" data-hv-auto="[]">' +
  '<rect id="v_spor"/><circle id="v_vippe"/><g><text id="v_tekst"/></g></g>' +
  '<g id="gruppe"><rect id="g_a"/><rect/></g>',
);

describe('buildElements', () => {
  const els = buildElements(ROOT);
  it('forælder og dybde via nærmeste forfader med id (grupper uden id springes over)', () => {
    const by = Object.fromEntries(els.map((e) => [e.id, e]));
    expect(by.baggrund).toMatchObject({ parent: null, depth: 0, children: 0, symbol: false });
    expect(by.Ventilator).toMatchObject({ parent: null, depth: 0, children: 3, symbol: true, name: 'Vippekontakt', desc: 'Starter ventilatoren' });
    expect(by.v_tekst).toMatchObject({ parent: 'Ventilator', depth: 1 });
    expect(by.g_a).toMatchObject({ parent: 'gruppe', depth: 1 });
    expect(by.gruppe.symbol).toBe(false);
  });
  it('rækkefølge som i tegningen; id-løse elementer er ikke med', () => {
    expect(els.map((e) => e.id)).toEqual(['baggrund', 'Ventilator', 'v_spor', 'v_vippe', 'v_tekst', 'gruppe', 'g_a']);
  });
  it('dele af et symbol får kort navn; kun under symboler', () => {
    const by = Object.fromEntries(els.map((e) => [e.id, e]));
    expect(by.v_spor.short).toBe('spor');
    expect(by.v_tekst.short).toBe('tekst');
    expect(by.g_a.short).toBeNull();            // under en almindelig gruppe røres id'et ikke
    expect(displayName(by.v_spor)).toBe('spor');
    expect(showsId(by.v_spor)).toBe(true);      // fuldt id vises som sekundær
    expect(showsId(by.baggrund)).toBe(false);
  });
  it('standard: rene grupper foldet ud, symboler foldet sammen', () => {
    expect([...defaultExpanded(els)]).toEqual(['gruppe']);
    expect(visibleRows(els, defaultExpanded(els), '').map((r) => r.id)).toEqual(['baggrund', 'Ventilator', 'gruppe', 'g_a']);
  });
  it('displayName: navn, så label, så id', () => {
    expect(displayName({ id: 'a', name: 'N', label: 'L' })).toBe('N');
    expect(displayName({ id: 'a', name: null, label: 'L' })).toBe('L');
    expect(displayName({ id: 'a', name: null, label: null })).toBe('a');
  });
  it('ancestorsOf og descendantCount', () => {
    expect(ancestorsOf(els, 'v_tekst')).toEqual(['Ventilator']);
    expect(ancestorsOf(els, 'baggrund')).toEqual([]);
    expect(descendantCount(els, 'Ventilator')).toBe(3);
    expect(descendantCount(els, 'baggrund')).toBe(0);
  });
});

describe('visibleRows', () => {
  const els = buildElements(ROOT);
  it('sammenfoldet: kun øverste niveau; udfoldet: delene med', () => {
    expect(visibleRows(els, new Set(), '').map((r) => r.id)).toEqual(['baggrund', 'Ventilator', 'gruppe']);
    expect(visibleRows(els, new Set(['Ventilator']), '').map((r) => r.id)).toEqual(
      ['baggrund', 'Ventilator', 'v_spor', 'v_vippe', 'v_tekst', 'gruppe']);
  });
  it('søgning matcher id, navn og forklaring og viser forfædre som kontekst', () => {
    const rows = visibleRows(els, new Set(), 'tekst');
    expect(rows.map((r) => [r.id, r.context])).toEqual([['Ventilator', true], ['v_tekst', false]]);
    expect(visibleRows(els, new Set(), 'starter').map((r) => r.id)).toEqual(['Ventilator']);
    expect(visibleRows(els, new Set(), 'vippekontakt').map((r) => r.id)).toEqual(['Ventilator']);
    expect(visibleRows(els, new Set(), 'findes ikke')).toEqual([]);
  });
});
