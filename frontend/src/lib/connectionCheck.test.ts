// Tjek af forbindelser i tegningen (signalpath/graph.ts › connectionCheck).
import { describe, expect, it } from 'vitest';
import { connectionCheck, contacts, pairsToBind, planFixes, type GNode, type Graph, type Pt } from './signalPath';

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

describe('ret brudte forbindelser (planFixes)', () => {
  const plan = (g: Graph, gap?: number) => planFixes(g, connectionCheck(g), gap);

  it('proposes moving a pipe end that lies close to another end, but not one that is far away or already connected', () => {
    const g: Graph = { nodes: [pipe('a', [0, 0], [100, 0]), pipe('b', [115, 0], [200, 0]), pipe('langt', [0, 300], [100, 300]), pipe('c', [100, 305], [150, 305])] };
    const moves = plan(g);
    expect(moves.map((m) => [m.id, m.from, m.to, m.toId])).toContainEqual(['a', [100, 0], [115, 0], 'b']);
    expect(moves.map((m) => [m.id, m.from, m.to, m.toId])).toContainEqual(['b', [115, 0], [100, 0], 'a']);   // begge ender foreslås; kun én flyttes ved rettelsen
    expect(moves.some((m) => m.id === 'langt' && m.from[0] === 0)).toBe(false);                           // den frie ende (0,300) har intet i nærheden
    expect(plan(g, 10).filter((m) => m.id === 'a')).toHaveLength(0);                                      // maxGap 10 < 15
  });

  it('prefers the nearest end and attaches to a symbol port', () => {
    const g: Graph = { nodes: [sym('v', 'kugleventil', [[0, 0], [20, 0]]), pipe('r', [38, 0], [100, 0]), pipe('fjern', [60, 12], [60, 80])] };
    const m = plan(g).filter((x) => x.id === 'r');
    expect(m[0]).toMatchObject({ toId: 'v', to: [20, 0], gap: 18 });
  });

  it('does not touch displays or the elements that are already connected', () => {
    const g: Graph = { nodes: [pipe('a', [0, 0], [100, 0]), pipe('b', [104, 0], [200, 0]), { id: 'tekst', name: 'T', type: 'statusfelt', pipe: false, terminals: [[100, 14]], lines: [], refs: [] }] };
    expect(plan(g)).toEqual([]);                          // a og b rører allerede (4 < 8); statusfeltet er visning
  });

  it('moves a straight pipe symbol only along its own axis', () => {
    const straight = (id: string, a: Pt, b: Pt): GNode => ({ id, name: id, type: 'roer_v', pipe: false, terminals: [a, b], lines: [{ part: 'all', a, b }], refs: [] });
    const on = by({ nodes: [straight('s', [0, 0], [100, 0]), pipe('n', [118, 0], [200, 0])] });
    expect(on.s.status).toBe('isolated');
    expect(planFixes({ nodes: [straight('s', [0, 0], [100, 0]), pipe('n', [118, 0], [200, 0])] }, Object.values(on)).filter((m) => m.id === 's')).toHaveLength(1);
    const off = { nodes: [straight('s', [0, 0], [100, 0]), pipe('n', [118, 40], [200, 40])] };
    expect(planFixes(off, connectionCheck(off)).filter((m) => m.id === 's')).toHaveLength(0);     // ligger ved siden af aksen: kan ikke ordnes ved at forlænge
  });
});

describe('punkter og symboler, der ikke er i brug', () => {
  const pump = (over: Partial<GNode> = {}): GNode => ({ id: 'p', name: 'P', type: 'pumpe', pipe: false, terminals: [[0, 0], [20, 0], [10, 20]],
    lines: [], refs: [], keys: ['0,0.5', '1,0.5', '0.5,1'], ...over });

  it('does not count a point marked as unused, and reports it as ignored', () => {
    const g: Graph = { nodes: [pump({ unused: [2] }), pipe('a', [-40, 0], [0, 0]), pipe('b', [20, 0], [60, 0])] };
    const p = by(g).p;
    expect(p.status).toBe('ok');
    expect(p.open).toEqual([]);
    expect(p.ignored).toEqual([[10, 20]]);
    expect(p.ignoredKeys).toEqual(['0.5,1']);
    const open = by({ nodes: [pump(), pipe('a', [-40, 0], [0, 0]), pipe('b', [20, 0], [60, 0])] }).p;     // uden markering: det tredje punkt er åbent
    expect(open).toMatchObject({ status: 'open', open: [[10, 20]], openKeys: ['0.5,1'], ignored: [] });
  });

  it('an element that is fully unconnected becomes ok when all its points are unused', () => {
    expect(by({ nodes: [pump({ unused: [0, 1, 2] })] }).p.status).toBe('ok');
    expect(by({ nodes: [pump({ unused: [0, 1] })] }).p).toMatchObject({ status: 'isolated', open: [[10, 20]] });
  });

  it('skips an exempt symbol altogether', () => {
    const r = by({ nodes: [pump({ exempt: true })] }).p;
    expect(r).toMatchObject({ exempt: true, status: 'ok', open: [] });
    expect(planFixes({ nodes: [pump({ exempt: true })] }, connectionCheck({ nodes: [pump({ exempt: true })] }))).toEqual([]);
  });
});

describe('gemte forbindelser (data-hv-links, v5.3.0)', () => {
  const p = (id: string, a: Pt, b: Pt, links: GNode['links'] = []): GNode => ({ ...pipe(id, a, b), keys: ['s', 'e'], links });
  const v = (links: GNode['links'] = []): GNode => ({ id: 'v', name: 'V', type: 'kugleventil', pipe: false, terminals: [[100, 0], [120, 0]],
    lines: [], refs: [], keys: ['0,0.5', '1,0.5'], links });

  it('binds what the geometry finds, keeps existing links and drops links to elements that are gone', () => {
    const g: Graph = { nodes: [p('a', [0, 0], [100, 0]), v(), p('b', [120, 0], [200, 0], [{ i: 1, to: 'væk', toKey: 's' }])] };
    const pairs = pairsToBind(g);
    expect(pairs.some((x) => (x.id === 'a' && x.key === 'e' && x.to === 'v' && x.toKey === '0,0.5')
      || (x.id === 'v' && x.key === '0,0.5' && x.to === 'a' && x.toKey === 'e'))).toBe(true);
    expect(pairs.some((x) => (x.id === 'v' && x.to === 'b') || (x.id === 'b' && x.to === 'v'))).toBe(true);
    expect(pairs.some((x) => x.to === 'væk' || x.id === 'væk')).toBe(false);
    expect(pairs.filter((x) => [x.id, x.to].sort().join() === 'a,v')).toHaveLength(1);       // ét par pr. forbindelse
  });

  it('a stored link wins over the geometry: drifted apart still connected (orange), and a stranger close by is not', () => {
    const g: Graph = { nodes: [
      { ...p('a', [0, 0], [80, 0], [{ i: 1, to: 'v', toKey: '0,0.5' }]), unused: [0] },   // a's ende er gledet 20 væk; starten bruges ikke
      v([{ i: 0, to: 'a', toKey: 'e' }]),
      p('fremmed', [100, 0], [100, 50]),                                              // ligger tæt på ventilens punkt, men er ikke bundet
    ] };
    const adj = contacts(g);
    expect(adj.get('a')!.some((c) => c.to === 'v')).toBe(true);
    expect(adj.get('v')!.some((c) => c.to === 'fremmed')).toBe(false);
    const r = Object.fromEntries(connectionCheck(g).map((i) => [i.id, i]));
    expect(r.a.status).toBe('drift');
    expect(r.a.drift).toEqual([[80, 0]]);
    expect(r.a.driftKeys).toEqual(['e']);
    const fix = planFixes(g, connectionCheck(g));
    expect(fix).toContainEqual({ id: 'a', from: [80, 0], to: [100, 0], toId: 'v', gap: 20 });   // Ret: tilbage til den gemte modpart
  });

  it('counts unbound contacts until they are bound', () => {
    const g: Graph = { nodes: [p('a', [0, 0], [100, 0]), v()] };
    expect(connectionCheck(g).find((i) => i.id === 'a')!.unbound).toBe(1);
    const bound: Graph = { nodes: [p('a', [0, 0], [100, 0], [{ i: 1, to: 'v', toKey: '0,0.5' }]), v([{ i: 0, to: 'a', toKey: 'e' }])] };
    const a = connectionCheck(bound).find((i) => i.id === 'a')!;
    expect(a.unbound).toBe(0);
    expect(a.status).toBe('open');                                                    // (ventilens anden side og rørets start er frie)
  });
});

describe('forældede forbindelser (v6.9.3)', () => {
  // en pumpe, hvis punkter er ændret (fire automatiske → IND/UD), og et rør, hvis gemte forbindelse peger på det gamle punkt "0.5,0"
  const pumpNow = (): GNode => ({ id: 'v', name: 'P', type: 'pumpe', pipe: false, terminals: [[100, 0], [120, 0]],
    lines: [{ part: 'all', a: [100, -10], b: [120, -10] }], refs: [], keys: ['0,0.5', '1,0.5'], links: [{ i: -1, to: 'a', toKey: 'e' }] });
  const pipeTo = (): GNode => ({ id: 'a', name: '', type: '', pipe: true, terminals: [[0, 0], [100, 0]], lines: [{ part: 'all', a: [0, 0], b: [100, 0] }],
    refs: [null, null], keys: ['s', 'e'], links: [{ i: 1, to: 'v', toKey: '0.5,0' }] });

  it('a link to a point the symbol no longer has counts as drifted, not as connected', () => {
    const a = connectionCheck({ nodes: [pumpNow(), pipeTo()] }).find((i) => i.id === 'a')!;
    expect(a.drift).toEqual([[100, 0]]);                // den forældede ende er gledet (orange); rørets start er bare åben
  });

  it('Bind forbindelser drops the stale link and binds the real point instead', () => {
    const pairs = pairsToBind({ nodes: [pumpNow(), pipeTo()] });
    expect(pairs.some((x) => x.toKey === '0.5,0' || x.key === '0.5,0')).toBe(false);
    expect(pairs.some((x) => (x.id === 'a' && x.key === 'e' && x.to === 'v' && x.toKey === '0,0.5')
      || (x.id === 'v' && x.key === '0,0.5' && x.to === 'a' && x.toKey === 'e'))).toBe(true);
  });
});
