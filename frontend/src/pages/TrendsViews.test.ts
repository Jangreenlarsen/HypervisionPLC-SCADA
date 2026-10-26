// Trends som en bruger bruger den: vælg en gemt visning, og graferne tegnes (jsdom, serveren er afløst af en stub).
import { flushSync, mount, tick, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const TAGS = ['T0', 'T1', 'T2'].map((name) => ({ name, unit: '°C', description: `Probe ${name}`, plc: 'plc1', trend: true, trend_interval_s: 10, samples: 100, oldest: 0, is_bool: false }));
const calls: string[] = [];

vi.mock('../lib/api', async () => {
  const actual = await vi.importActual<typeof import('../lib/api')>('../lib/api');
  const route = async (path: string): Promise<unknown> => {
    calls.push(path);
    if (path.startsWith('/api/trends/info')) return { retention_days: 30, db_size: 1, tags: TAGS };
    if (path.startsWith('/api/trends/views')) return [{ name: 'Tank temp', tags: ['T0', 'T1', 'T2'], assign: { T2: 2 }, range: '8h' }];
    if (path.startsWith('/api/trends/symbols')) return [];
    if (path.startsWith('/api/trends/data')) {
      const pts = [[0, 20], [1800, 22], [3600, 24]];
      return { start: 0, end: 3600, series: { T0: pts, T1: pts, T2: pts }, meta: {} };
    }
    return {};
  };
  return { ...actual, get: vi.fn(route), api: vi.fn(async (_m: string, path: string) => route(path)) };
});

// uPlot kræver canvas/matchMedia, som jsdom ikke har: en minimal afløser, der kræver samme data som den rigtige (og kaster ved ugyldige)
const built: { series: number; points: number }[] = [];
vi.mock('uplot', () => {
  class FakeUPlot {
    static fmtDate = () => () => '';
    over = document.createElement('div');
    scales = { x: { min: 0, max: 3600 } };
    height = 300;
    series: unknown[];
    constructor(opts: { series: unknown[] }, data: number[][], el: HTMLElement) {
      if (!Array.isArray(data) || data.length !== opts.series.length) throw new Error(`uPlot: ${data?.length} datarækker til ${opts.series.length} serier`);
      this.series = opts.series;
      built.push({ series: data.length - 1, points: data[0]?.length ?? 0 });
      el.appendChild(this.over);
      el.classList.add('uplot-fake');
    }
    destroy() {}
    setSize() {}
    setData() {}
    setScale() {}
    redraw() {}
    valToPos() { return 0; }
    batch(fn: () => void) { fn(); }
  }
  return { default: FakeUPlot };
});

import Trends from './Trends.svelte';

let target: HTMLElement;
let app: Record<string, any>;
const settle = async () => { for (let i = 0; i < 6; i++) { flushSync(); await tick(); await new Promise((r) => setTimeout(r, 5)); } flushSync(); };

beforeEach(async () => {
  calls.length = 0;
  built.length = 0;
  (globalThis as any).ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
  try { localStorage.clear(); } catch { /* ingen lagring */ }
  target = document.createElement('div');
  document.body.appendChild(target);
  app = mount(Trends, { target, props: { canEdit: true, route: 'trends' } });
  await settle();
});
afterEach(() => {
  unmount(app);
  target.remove();
});

describe('Trends: gemte visninger', () => {
  it('et valg af en visning henter data og tegner graferne', async () => {
    const select = target.querySelector<HTMLSelectElement>('select[aria-label="Gemte visninger"]')!;
    expect(select).not.toBeNull();
    expect([...select.options].map((o) => o.value)).toEqual(['', 'Tank temp']);
    expect(target.querySelectorAll('.charts svg, .charts canvas').length).toBe(0);   // intet valgt endnu
    select.value = 'Tank temp';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    await settle();
    expect(calls.some((c) => c.startsWith('/api/trends/data') && c.includes('tags=T0,T1,T2'))).toBe(true);
    // T2 hører til graf 2, T0/T1 til graf 1 → to grafer
    // to grafer (T0+T1 og T2), begge med data
    expect(target.querySelectorAll('.uplot-fake').length).toBe(2);
    expect(built.at(-1)?.points).toBeGreaterThan(0);
    expect(target.textContent).not.toContain('Vælg et eller flere tags til venstre');
  });

  it('tegner graferne med data fra første billede (data hentes før udvalget skiftes)', async () => {
    const select = target.querySelector<HTMLSelectElement>('select[aria-label="Gemte visninger"]')!;
    select.value = 'Tank temp';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    await settle();
    expect(built.length).toBeGreaterThan(0);
    expect(built.every((b) => b.points > 0)).toBe(true);   // aldrig bygget tom og fyldt op bagefter
  });

  it('en visning med tags uden historik viser resten og en besked; ingen brugbare tags giver en besked', async () => {
    TAGS[2] = { ...TAGS[2], trend: false, samples: 0 };
    try {
      unmount(app);
      target.replaceChildren();
      app = mount(Trends, { target, props: { canEdit: true, route: 'trends' } });
      await settle();
      const select = target.querySelector<HTMLSelectElement>('select[aria-label="Gemte visninger"]')!;
      select.value = 'Tank temp';
      select.dispatchEvent(new Event('change', { bubbles: true }));
      await settle();
      expect(target.textContent).toContain('Ikke tilgængelige');
      expect(target.querySelectorAll('.uplot-fake').length).toBe(1);   // T0+T1 i graf 1; T2 er ikke med
    } finally {
      TAGS[2] = { ...TAGS[2], trend: true, samples: 100 };
    }
  });

  it('Nulstil valg fravælger alle tags og rydder visningen', async () => {
    const select = target.querySelector<HTMLSelectElement>('select[aria-label="Gemte visninger"]')!;
    select.value = 'Tank temp';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    await settle();
    expect(target.querySelectorAll('.uplot-fake').length).toBe(2);
    const reset = [...target.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Nulstil valg')!;
    reset.click();
    await settle();
    expect(target.querySelectorAll('.uplot-fake').length).toBe(0);
    expect(target.querySelector<HTMLSelectElement>('select[aria-label="Gemte visninger"]')!.value).toBe('');
    expect(localStorage.getItem('trend.selected')).toBe('[]');
    expect(target.textContent).toContain('Vælg et eller flere tags til venstre');
  });
});
