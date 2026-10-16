// 3-vejs motorventil og statusfelt i symbolbiblioteket (v0.46.0): delene og guidens forslag.
import { describe, expect, it } from 'vitest';
import { SYMBOLS } from './symbols';
import { emptyConfig, isValveType, libraryDefault, MAX_ANIMS, partLabel, POS, valveFromTag, type SymbolInfo } from './symbolConfig';

const sym = (id: string) => SYMBOLS.find((s) => s.id === id)!;
const partIds = (id: string) => [...new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${sym(id).svg}</svg>`, 'image/svg+xml').querySelectorAll('[id]')].map((e) => e.id);
/** Som tegningen ser ud efter indsættelse: delenes id'er får præfiks, deres bibliotekssnavn står i data-hv-pid. */
const info = (type: string, pids: string[]): SymbolInfo => ({
  tag: 'g', line: false, type, name: 'Ventil 1',
  parts: Object.fromEntries(pids.map((p) => [`V1_${p}_2`, { tag: 'path', line: false, pid: p }])),
});

describe('3-vejs motorventil', () => {
  it('findes under Rør og VVS med portene A, B, AB og motoren som egne dele', () => {
    expect(sym('trevejs_motorventil').category).toBe('vvs');
    expect(partIds('trevejs_motorventil')).toEqual(['port_a', 'port_b', 'port_ab', 'motor']);
  });

  it('guiden foreslår positionerne AB → A og AB → B med farver pr. port', () => {
    const r = libraryDefault(info('trevejs_motorventil', ['port_a', 'port_b', 'port_ab', 'motor']))!;
    expect(r.config.op).toBe('positions');
    expect(r.config.positions.map((p) => p.label)).toEqual(['AB → A', 'AB → B']);
    expect(r.config.planes).toEqual([{ signal: 'S1', values: [0, 1] }]);
    const colors = Object.fromEntries(r.config.anims.map((a) => [a.part, a.params.colors]));
    expect(r.config.anims.every((a) => a.type === 'fill' && a.src === POS)).toBe(true);
    expect(colors['V1_port_a_2']).toEqual(['#7cc47f', '#ffffff']);     // A åben i AB → A
    expect(colors['V1_port_b_2']).toEqual(['#ffffff', '#7cc47f']);     // B åben i AB → B
    expect(colors['V1_port_ab_2']).toEqual(['#7cc47f', '#7cc47f']);    // AB altid åben
    expect(r.note).toContain('AB → A');
  });

  it('manglende dele springes over, og ukendte symboler får intet forslag', () => {
    expect(libraryDefault(info('trevejs_motorventil', ['port_a']))!.config.anims).toHaveLength(1);
    expect(libraryDefault(info('omskifter3', ['greb']))).toBeNull();
    expect(libraryDefault(null)).toBeNull();
  });

  it('delene har danske navne', () => {
    const i = info('trevejs_motorventil', ['port_a', 'port_b', 'port_ab', 'motor']);
    expect(['V1_port_a_2', 'V1_port_b_2', 'V1_port_ab_2'].map((p) => partLabel(p, i))).toEqual(['Port A', 'Port B', 'Port AB']);
  });
});

describe('3-vejs motorventil (AB i midten)', () => {
  it('har de samme dele og samme forslag som den første variant', () => {
    expect(sym('trevejs_motorventil_ab').category).toBe('vvs');
    expect(partIds('trevejs_motorventil_ab')).toEqual(['port_a', 'port_b', 'port_ab', 'motor']);
    const r = libraryDefault(info('trevejs_motorventil_ab', ['port_a', 'port_b', 'port_ab', 'motor']))!;
    expect(r.config.positions.map((p) => p.label)).toEqual(['AB → A', 'AB → B']);
    expect(r.config.anims.map((a) => a.params.colors)).toEqual([['#7cc47f', '#ffffff'], ['#ffffff', '#7cc47f'], ['#7cc47f', '#7cc47f']]);
  });
});

describe('statusfelt', () => {
  it('findes under Proces og visning med feltet og teksten som dele', () => {
    expect(sym('statusfelt').category).toBe('proces');
    expect(partIds('statusfelt')).toEqual(['felt', 'tekst']);
  });

  it('guiden foreslår at feltets farve følger et register (tag vælges bagefter)', () => {
    const r = libraryDefault(info('statusfelt', ['felt', 'tekst']))!;
    expect(r.config.op).toBe('view');
    expect(r.config.anims).toHaveLength(1);
    expect(r.config.anims[0]).toMatchObject({ part: 'V1_felt_2', type: 'fill', src: '' });
    expect(r.config.anims[0].params.thresholds.length).toBeGreaterThan(0);
    expect(libraryDefault(info('statusfelt', ['tekst']))).toBeNull();
  });
});

describe('3-vejs ventil styret af ét til/fra-tag', () => {
  const sy = info('trevejs_motorventil', ['port_a', 'port_b', 'port_ab', 'motor']);

  it('Til = AB → A, Fra = AB → B, og AB er altid åben', () => {
    const cfg = emptyConfig(sy.type);
    expect(valveFromTag(cfg, sy, 'PLC1_DI8')).toBe(3);
    const by = Object.fromEntries(cfg.anims.map((a) => [a.part, a]));
    expect(cfg.anims.every((a) => a.type === 'fill' && a.src === 'PLC1_DI8' && a.only === null)).toBe(true);
    expect(by['V1_port_a_2'].params).toEqual({ on: '#7cc47f', off: '#ffffff' });
    expect(by['V1_port_b_2'].params).toEqual({ on: '#ffffff', off: '#7cc47f' });
    expect(by['V1_port_ab_2'].params).toEqual({ on: '#7cc47f', off: '#7cc47f' });
  });

  it('erstatter kun animationer på de tre porte og bevarer resten', () => {
    const cfg = emptyConfig(sy.type);
    cfg.anims = [
      { part: 'V1_port_ab_2', type: 'fill', src: '@L2', params: {}, only: null },
      { part: 'V1_motor_2', type: 'blink', src: 'Motor', params: {}, only: null },
    ];
    expect(valveFromTag(cfg, sy, 'T')).toBe(3);
    expect(cfg.anims).toHaveLength(4);
    expect(cfg.anims.filter((a) => a.part === 'V1_port_ab_2')).toHaveLength(1);     // ikke to på samme del (den nederste vinder)
    expect(cfg.anims.find((a) => a.part === 'V1_motor_2')!.src).toBe('Motor');
  });

  it('ingen porte = 0, ingen plads = -1 uden at ændre noget', () => {
    expect(valveFromTag(emptyConfig('x'), info('trevejs_motorventil', ['motor']), 'T')).toBe(0);
    const full = emptyConfig(sy.type);
    full.anims = Array.from({ length: MAX_ANIMS }, (_, i) => ({ part: `x${i}`, type: 'blink' as const, src: 'T', params: {}, only: null }));
    expect(valveFromTag(full, sy, 'T')).toBe(-1);
    expect(full.anims).toHaveLength(MAX_ANIMS);
  });

  it('isValveType kender begge varianter', () => {
    expect(isValveType('trevejs_motorventil')).toBe(true);
    expect(isValveType('trevejs_motorventil_ab')).toBe(true);
    expect(isValveType('trevejsventil')).toBe(false);
  });
});
