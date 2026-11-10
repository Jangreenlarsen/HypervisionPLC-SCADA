// Tjek af forbindelser i tegningen (signalpath/graph.ts › connectionCheck).
import { describe, expect, it } from 'vitest';
import { connectionCheck, type GNode, type Graph, type Pt } from './signalPath';

const pipe = (id: string, a: Pt, b: Pt): GNode => ({ id, name: '', type: '', pipe: true, terminals: [a, b], lines: [{ part: 'all', a, b }], refs: [null, null] });
const sym = (id: string, type: string, terminals: Pt[]): GNode => ({ id, name: id, type, pipe: false, terminals, lines: [], refs: [] });
const by = (g: Graph) => Object.fromEntries(connectionCheck(g).map((i) => [i.id, i]));

describe('tjek af forbindelser', () => {
  it('marks connected, half-open and isolated elements', () => {
    const r = by({ nodes: [
      sym('kedel', 'kedel', [[0, 0]]), pipe('r1', [0, 0], [50, 0]), sym('rad', 'radiator', [[50, 0]]),        // forbundet
      pipe('r2', [100, 0], [150, 0]), sym('ven', 'kugleventil', [[100, 0], [150, 0]]),                       // r2 sidder i ventilen i begge ender
      pipe('fri', [300, 300], [350, 300]),                                                                    // isoleret
      pipe('halv', [50, 0], [90, 40]),                                                                       // den ene ende hænger fast, den anden er åben
    ] });
    expect(r.kedel.status).toBe('ok');
    expect(r.r1.status).toBe('ok');
    expect(r.rad.status).toBe('ok');
    expect(r.r2.status).toBe('ok');
    expect(r.fri).toMatchObject({ status: 'isolated', open: [[300, 300], [350, 300]] });
    expect(r.halv).toMatchObject({ status: 'open', open: [[90, 40]] });
  });

  it('counts a pipe end that sits on the middle of another pipe as connected', () => {
    const r = by({ nodes: [pipe('hoved', [0, 0], [100, 0]), pipe('gren', [50, 0], [50, 40]), sym('x', 'radiator', [[50, 40]])] });
    expect(r.gren.status).toBe('ok');
    expect(r.hoved.status).toBe('open');          // hovedrørets ender er frie
    expect(r.hoved.open).toHaveLength(2);
  });

  it('skips displays and shapes without terminals', () => {
    const r = by({ nodes: [
      { id: 'tekst', name: 'T', type: 'statusfelt', pipe: false, terminals: [[500, 500]], lines: [], refs: [] },
      { id: 'figur', name: '', type: '', pipe: false, terminals: [], lines: [], refs: [] },
      sym('p', 'pumpe', [[0, 0], [20, 0]]),
    ] });
    expect(r.tekst).toBeUndefined();
    expect(r.figur).toBeUndefined();
    expect(r.p.status).toBe('isolated');
  });

  it('only counts the real ends of a bend and a T-piece, not their curve/centre points', () => {
    // geometri fra en rigtig tegning: bøjningens kurvepunkter ligger tæt ved enderne, T-stykkets midtpunkt midt imellem
    const bend: GNode = { id: 'b', name: '', type: 'boejning90', pipe: false, terminals: [[788, 267], [743, 299.5], [743, 312], [775.5, 267]],
      lines: [{ part: 'all', a: [788, 267], b: [743, 312] }], refs: [] };
    const t: GNode = { id: 't', name: '', type: 't_stykke', pipe: false, terminals: [[882, 267], [792, 267], [837, 312], [837, 267]], lines: [], refs: [] };
    const r = by({ nodes: [bend, t, pipe('a', [743, 312], [743, 400]), pipe('b2', [788, 267], [792, 267]), pipe('c', [882, 267], [950, 267]), pipe('d', [837, 312], [837, 400])] });
    expect(r.b.status).toBe('ok');
    expect(r.t.status).toBe('ok');
    const lonely = by({ nodes: [{ ...bend, id: 'x' }, pipe('only', [743, 312], [743, 400])] });
    expect(lonely.x).toMatchObject({ status: 'open' });                    // den ene ende sidder fast, den anden er åben
    expect(lonely.x.open).toHaveLength(1);
  });
});
