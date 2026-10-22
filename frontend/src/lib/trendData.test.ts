import { describe, expect, it } from 'vitest';
import { align, assignColors, groupByUnit, groupTags, isolatedPoints, MAX_SERIES, type Point } from './trendData';

describe('align', () => {
  it('fletter tidspunkter, og skelner hul (null) fra manglende punkt (undefined)', () => {
    const a: Point[] = [[1, 10, 10, 10], [3, null, null, null]];
    const b: Point[] = [[2, 5, 4, 6]];
    const [xs, ya, yb] = align([a, b]);
    expect(xs).toEqual([1, 2, 3]);
    expect(ya).toEqual([10, undefined, null]);
    expect(yb).toEqual([undefined, 5, undefined]);
  });
  it('tom input', () => expect(align([])).toEqual([[]]));
  it('til/fra bruger max pr. spand', () => {
    const [, y] = align([[[1, 0.2, 0, 1]]], [true]);
    expect(y).toEqual([1]);
  });
});

describe('isolatedPoints', () => {
  it('ét enkelt punkt (nyligt slået til) vises som prik', () => expect(isolatedPoints([undefined, 5, undefined])).toEqual([1]));
  it('måling mellem to huller', () => expect(isolatedPoints([1, 2, null, 7, null, 3, 4])).toEqual([3]));
  it('sammenhængende linje og huller giver ingen prikker', () => {
    expect(isolatedPoints([1, undefined, 2, 3])).toEqual([]);
    expect(isolatedPoints([null, null])).toEqual([]);
    expect(isolatedPoints([])).toEqual([]);
  });
});

describe('assignColors', () => {
  it('et tag beholder sin farve når andre fjernes', () => {
    const first = assignColors(['A', 'B', 'C'], {});
    expect(first).toEqual({ A: 0, B: 1, C: 2 });
    const second = assignColors(['A', 'C'], first);
    expect(second).toEqual({ A: 0, C: 2 });       // C får ikke B's farve
    expect(assignColors(['A', 'C', 'D'], second)).toEqual({ A: 0, C: 2, D: 1 }); // første ledige
  });
  it('højst MAX_SERIES farver', () => {
    const names = Array.from({ length: MAX_SERIES + 2 }, (_, i) => `T${i}`);
    expect(Object.keys(assignColors(names, {}))).toHaveLength(MAX_SERIES);
  });
});

describe('groupByUnit', () => {
  it('én gruppe pr. enhed, til/fra for sig', () => {
    const groups = groupByUnit([
      { name: 'A', unit: '°C' }, { name: 'B', unit: '%' }, { name: 'C', unit: '°C' },
      { name: 'D', unit: '', isBool: true }, { name: 'E', unit: '' },
    ]);
    expect(groups.map(([k, v]) => [k, v.map((t) => t.name)])).toEqual([
      ['°C', ['A', 'C']], ['%', ['B']], ['Til/fra', ['D']], ['Uden enhed', ['E']],
    ]);
  });
});

describe('groupTags', () => {
  const tags = [
    { name: 'a', unit: '°C' }, { name: 'b', unit: 'bar' }, { name: 'c', unit: '°C' }, { name: 'd', unit: '', isBool: true },
  ];
  it('uden valg er det som pr. enhed', () => {
    expect(groupTags(tags, {})).toEqual(groupByUnit(tags));
  });
  it('valgte tags samles i "Graf N" uanset enhed, de øvrige forbliver pr. enhed', () => {
    const g = groupTags(tags, { a: 2, b: 2, d: 1 });
    expect(g.map(([k, ts]) => [k, ts.map((t) => t.name)])).toEqual([['°C', ['c']], ['Graf 1', ['d']], ['Graf 2', ['a', 'b']]]);
  });
  it('0 eller ukendt nummer betyder Auto', () => {
    expect(groupTags(tags, { a: 0 })).toEqual(groupByUnit(tags));
  });
});
