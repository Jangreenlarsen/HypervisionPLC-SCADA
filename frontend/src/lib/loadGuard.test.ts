import { describe, expect, it } from 'vitest';
import { createLoadGuard, shouldLoadFromHash } from './loadGuard';

describe('createLoadGuard', () => {
  it('kun den nyeste indlæsning er gældende', () => {
    const g = createLoadGuard();
    const a = g.begin('a');
    const b = g.begin('b');
    expect(g.isLatest(a)).toBe(false);
    expect(g.isLatest(b)).toBe(true);
    expect(g.inFlight).toBe('b');
  });

  it('hurtige klik: den forældede indlæsning kan ikke rydde "i gang" for den nyeste', () => {
    const g = createLoadGuard();
    const a = g.begin('a');
    const b = g.begin('b');
    g.finish(a);                       // a bliver færdig EFTER b er startet
    expect(g.inFlight).toBe('b');
    g.finish(b);
    expect(g.inFlight).toBeNull();
  });

  it('en ny indlæsning efter en afsluttet er igen den nyeste', () => {
    const g = createLoadGuard();
    g.finish(g.begin('a'));
    const c = g.begin('c');
    expect(g.isLatest(c)).toBe(true);
    expect(g.inFlight).toBe('c');
  });
});

describe('shouldLoadFromHash', () => {
  it('intet i gang: indlæs kun hvis tegningen ikke allerede vises', () => {
    expect(shouldLoadFromHash('b', 'a', null)).toBe(true);
    expect(shouldLoadFromHash('a', 'a', null)).toBe(false);
  });

  it('i gang med samme tegning: ingen dobbelt indlæsning', () => {
    expect(shouldLoadFromHash('b', 'a', 'b')).toBe(false);
  });

  it('i gang med en anden: skiftet gælder (også tilbage til den viste tegning)', () => {
    expect(shouldLoadFromHash('c', 'a', 'b')).toBe(true);
    expect(shouldLoadFromHash('a', 'a', 'b')).toBe(true);     // tilbage-knap mens b hentes: a skal vinde
  });
});
