import { describe, expect, it } from 'vitest';
import { applyView, sameView, viewFrom, type TrendView } from './trendViews';

const view: TrendView = { name: 'Tank temp', tags: ['T1', 'T2', 'T3', 'T4'], assign: { T1: 1, T2: 1, T3: 2 }, range: '8h' };

describe('gemte trend-visninger', () => {
  it('giver kun de tags, brugeren kan se, og melder de manglende', () => {
    const r = applyView(view, new Set(['T1', 'T3', 'T4', 'Andet']), 12);
    expect(r.tags).toEqual(['T1', 'T3', 'T4']);
    expect(r.assign).toEqual({ T1: 1, T3: 2 });
    expect(r.missing).toEqual(['T2']);
    expect(r.over).toEqual([]);
  });
  it('begrænser antallet af kurver og melder resten', () => {
    const r = applyView(view, new Set(view.tags), 2);
    expect(r.tags).toEqual(['T1', 'T2']);
    expect(r.over).toEqual(['T3', 'T4']);
    expect(r.assign).toEqual({ T1: 1, T2: 1 });
  });
  it('gemmer graf-valg kun for de valgte tags, og husker ikke en brugerdefineret periode', () => {
    const periods = ['15m', '1h', '8h'];
    expect(viewFrom(' Ny ', ['T1', 'T2'], { T1: 1, T9: 3 }, '8h', periods)).toEqual({ name: 'Ny', tags: ['T1', 'T2'], assign: { T1: 1 }, range: '8h' });
    expect(viewFrom('Ny', ['T1'], {}, 'custom', periods).range).toBe('1h');
  });
  it('genkender en uændret visning, og en ændret', () => {
    expect(sameView(view, { ...view, assign: { T3: 2, T2: 1, T1: 1 } })).toBe(true);   // rækkefølgen af graf-valg er ligegyldig
    expect(sameView(view, { ...view, range: '1h' })).toBe(false);
    expect(sameView(view, { ...view, tags: ['T2', 'T1', 'T3', 'T4'] })).toBe(false);   // rækkefølgen af tags tæller (farver/rækkefølge)
    expect(sameView(view, { ...view, assign: { T1: 1 } })).toBe(false);
  });
});
