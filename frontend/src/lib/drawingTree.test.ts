import { describe, expect, it } from 'vitest';
import {
  allowedParents, allowedParentsMap, breadcrumb, buildTree, canSetParent, childrenOf, depthOf, descendantsOf, flatOrder, heightOf, indentedName,
  parentProblem, MAX_DEPTH, type TreeItem,
} from './drawingTree';

const d = (id: string, parent: string | null = null, name = id.toUpperCase()): TreeItem => ({ id, name, parent_id: parent });
// a (anlæg) <- b, c (områder); b <- e (detalje); e <- f (niveau 4)
const sample = [d('a'), d('c', 'a', 'C'), d('b', 'a', 'B'), d('e', 'b'), d('f', 'e'), d('x')];
const ids = (l: TreeItem[]) => l.map((i) => i.id);

describe('buildTree / flatOrder / childrenOf', () => {
  it('tom liste giver tomme resultater', () => {
    expect(buildTree([])).toEqual([]);
    expect(flatOrder([])).toEqual([]);
    expect(childrenOf([], 'a')).toEqual([]);
    expect(descendantsOf([], 'a')).toEqual([]);
    expect(breadcrumb([], 'a')).toEqual([]);
    expect(depthOf([], 'a')).toBe(0);
  });

  it('bygger træet med børn sorteret efter navn og to rødder', () => {
    const t = buildTree(sample);
    expect(ids(t.map((n) => n.item))).toEqual(['a', 'x']);
    expect(ids(t[0].children.map((n) => n.item))).toEqual(['b', 'c']);
    expect(ids(t[0].children[0].children.map((n) => n.item))).toEqual(['e']);
  });

  it('flatOrder: forælder før børn med indrykning', () => {
    expect(flatOrder(sample).map((f) => `${f.item.id}:${f.indent}`)).toEqual(['a:0', 'b:1', 'e:2', 'f:3', 'c:1', 'x:0']);
  });

  it('childrenOf og descendantsOf', () => {
    expect(ids(childrenOf(sample, 'a'))).toEqual(['b', 'c']);
    expect(childrenOf(sample, 'f')).toEqual([]);
    expect(ids(descendantsOf(sample, 'a')).sort()).toEqual(['b', 'c', 'e', 'f']);
    expect(descendantsOf(sample, 'x')).toEqual([]);
  });

  it('manglende forælder: tegningen bliver rod', () => {
    const l = [d('a', 'findes-ikke'), d('b', 'a')];
    expect(ids(buildTree(l).map((n) => n.item))).toEqual(['a']);
    expect(depthOf(l, 'a')).toBe(1);
    expect(depthOf(l, 'b')).toBe(2);
  });

  it('cirkulære data hænger ikke og mister ingen tegninger', () => {
    const l = [d('a', 'b'), d('b', 'c'), d('c', 'a'), d('s', 's'), d('g', 'a')];
    expect(flatOrder(l)).toHaveLength(5);
    expect(ids(flatOrder(l).map((f) => f.item)).sort()).toEqual(['a', 'b', 'c', 'g', 's']);
    expect(breadcrumb(l, 'a').length).toBeGreaterThan(0);
    expect(depthOf(l, 'g')).toBe(2);                 // g hænger under cirklens medlem a, som er rod
    expect(descendantsOf(l, 'a').length).toBeLessThan(5);
    expect(heightOf(l, 'a')).toBeGreaterThan(0);
    expect(() => parentProblem(l, 'a', 'b')).not.toThrow();   // reglerne kan stadig vurderes uden at hænge
  });
});

describe('breadcrumb / depthOf / heightOf', () => {
  it('rod → tegningen', () => {
    expect(ids(breadcrumb(sample, 'f'))).toEqual(['a', 'b', 'e', 'f']);
    expect(ids(breadcrumb(sample, 'a'))).toEqual(['a']);
    expect(breadcrumb(sample, 'nej')).toEqual([]);
    expect(breadcrumb(sample, null)).toEqual([]);
  });

  it('utilgængelig forælder afkorter stien', () => {
    const visible = sample.filter((i) => i.id !== 'b');   // en begrænset bruger ser ikke b (backend sender parent_id null for e)
    expect(ids(breadcrumb(visible, 'e'))).toEqual(['e']);
    expect(ids(breadcrumb(visible.map((i) => (i.id === 'e' ? { ...i, parent_id: 'b' } : i)), 'f'))).toEqual(['e', 'f']);
  });

  it('niveau og højde', () => {
    expect([depthOf(sample, 'a'), depthOf(sample, 'b'), depthOf(sample, 'f')]).toEqual([1, 2, 4]);
    expect([heightOf(sample, 'f'), heightOf(sample, 'b'), heightOf(sample, 'a'), heightOf(sample, 'nej')]).toEqual([1, 3, 4, 0]);
  });
});

describe('canSetParent', () => {
  it('ingen forælder er altid ok (null, tom, whitespace)', () => {
    for (const p of [null, undefined, '', '  ']) expect(canSetParent(sample, 'f', p)).toBe(true);
  });

  it('ikke sig selv, ukendt eller cirkel — med dansk tekst', () => {
    expect(parentProblem(sample, 'a', 'a')).toContain('sin egen');
    expect(parentProblem(sample, 'a', 'nej')).toContain('findes ikke');
    expect(parentProblem(sample, 'a', 'f')).toContain('cirkel');
    expect(parentProblem(sample, 'b', 'e')).toContain('cirkel');
    expect(canSetParent(sample, 'e', 'c')).toBe(true);
  });

  it('dybde 4 ok, 5 afvist — også for undertræet', () => {
    expect(MAX_DEPTH).toBe(4);
    expect(canSetParent(sample, 'x', 'e')).toBe(true);        // x under e = niveau 4
    expect(canSetParent(sample, 'x', 'f')).toBe(false);       // niveau 5
    expect(parentProblem(sample, 'x', 'f')).toContain('4 niveauer');
    const withSub = [...sample, d('y', 'x')];                 // x har et barn → 2 niveauer
    expect(canSetParent(withSub, 'x', 'e')).toBe(false);      // 3 + 2 = 5
    expect(canSetParent(withSub, 'x', 'b')).toBe(true);       // 2 + 2 = 4
  });

  it('allowedParents udelukker sig selv, efterkommere og for stor dybde', () => {
    expect(ids(allowedParents(sample, 'b').map((f) => f.item))).toEqual(['a', 'x']);   // b har e, f under sig (højde 3)
    expect(ids(allowedParents(sample, 'x').map((f) => f.item))).toEqual(['a', 'b', 'e', 'c']);
  });
});

describe('indentedName', () => {
  it('indrykning med — pr. niveau', () => {
    expect(indentedName('Pumpe', 0)).toBe('Pumpe');
    expect(indentedName('Pumpe', 2)).toBe('— — Pumpe');
    expect(indentedName('Pumpe', -1)).toBe('Pumpe');
  });
});

describe('allowedParentsMap', () => {
  // Deterministisk pseudotilfældighed (samme data hver gang)
  const rng = (seed: number) => () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);

  /** Reference: den gamle, langsomme regel pr. tegning (canSetParent) i hierarki-rækkefølge. */
  const reference = (list: TreeItem[], id: string) => flatOrder(list).filter((f) => f.item.id !== id && canSetParent(list, id, f.item.id)).map((f) => f.item.id);

  it('giver samme valg som canSetParent/allowedParents på eksemplet', () => {
    const m = allowedParentsMap(sample);
    for (const t of sample) {
      expect(m.get(t.id)!.map((f) => f.item.id)).toEqual(reference(sample, t.id));
      expect(m.get(t.id)!.map((f) => f.item.id)).toEqual(allowedParents(sample, t.id).map((f) => f.item.id));
    }
  });

  it('tom liste, cirkler og ukendte forældre giver samme valg som den gamle regel', () => {
    expect(allowedParentsMap([]).size).toBe(0);
    const odd = [d('a', 'b'), d('b', 'a'), d('c', 'a'), d('e', 'ukendt'), d('s', 's'), d('t', 'c')];
    const m = allowedParentsMap(odd);
    for (const t of odd) expect(m.get(t.id)!.map((f) => f.item.id)).toEqual(reference(odd, t.id));
  });

  it('300 tegninger: samme valg som den gamle regel og hurtigt (< 200 ms)', () => {
    const rand = rng(42);
    const big: TreeItem[] = [];
    for (let i = 0; i < 300; i++) {
      // forælder er en tidligere tegning (så det er et gyldigt skov), ca. hver 7. er rod; enkelte med ukendt forælder
      const parent = i === 0 || rand() < 0.15 ? null : rand() < 0.02 ? 'findes-ikke' : `t${Math.floor(rand() * i)}`;
      big.push(d(`t${i}`, parent, `Tegning ${i}`));
    }
    const t0 = performance.now();
    const m = allowedParentsMap(big);
    const ms = performance.now() - t0;
    expect(ms).toBeLessThan(200);
    expect(m.size).toBe(300);
    for (const i of [0, 1, 7, 50, 120, 299]) {          // stikprøver mod den gamle regel (som er langsom pr. kald)
      expect(m.get(`t${i}`)!.map((f) => f.item.id)).toEqual(reference(big, `t${i}`));
    }
  });
});
