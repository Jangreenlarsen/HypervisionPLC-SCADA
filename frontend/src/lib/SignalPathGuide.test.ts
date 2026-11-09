// Signalvej-guiden som en bruger bruger den: vælg start og slut ved at klikke i tegningen eller i listen (jsdom).
import { flushSync, mount, tick, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SignalPathGuide from './SignalPathGuide.svelte';
import { ui } from './signalGuideHarness.svelte';
import type { GNode, Graph, Pt } from './signalPath';

const pipe = (id: string, a: Pt, b: Pt): GNode => ({ id, name: '', type: '', pipe: true, terminals: [a, b], lines: [{ part: 'all', a, b }], refs: [null, null] });
const sym = (id: string, name: string, type: string, terminals: Pt[]): GNode => ({ id, name, type, pipe: false, terminals, lines: [], refs: [] });
const GRAPH: Graph = { nodes: [
  sym('kedel', 'Kedel', 'kedel', [[40, 30]]), pipe('r1', [40, 30], [100, 30]), sym('ven', 'Ventil', 'kugleventil', [[100, 30], [140, 30]]),
  pipe('r2', [140, 30], [200, 30]), sym('rad', 'Radiator', 'radiator', [[200, 30]]),
] };

let target: HTMLElement;
let app: Record<string, unknown>;
let fetched: string[] = [];
const select = vi.fn();
const highlight = vi.fn();

beforeEach(() => {
  fetched = [];
  ui.selected = [];
  select.mockClear();
  highlight.mockClear();
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: { method?: string }) => {
    fetched.push(`${init?.method ?? 'GET'} ${url}`);
    const body = url.endsWith('/info')
      ? { elements: ['kedel', 'r1', 'ven', 'r2', 'rad'].map((e) => ({ element: e, name: e, tags: [], flows: [] })), tags: [], max_conditions: 25 }
      : url.includes('/symbol-flow') ? {} : [];
    return new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } });
  }));
  target = document.createElement('div');
  document.body.appendChild(target);
  app = mount(SignalPathGuide, { target, props: {
    drawingId: 'd', ready: true, get selected() { return ui.selected; }, get rev() { return ui.rev; },
    graph: () => GRAPH, highlight, select, ensureSaved: async () => true,
  } });
  flushSync();
});
afterEach(() => {
  unmount(app);
  target.remove();
  vi.unstubAllGlobals();
});

const settle = async () => { for (let i = 0; i < 4; i++) { flushSync(); await tick(); await new Promise((r) => setTimeout(r, 0)); } flushSync(); };
const button = (text: string) => [...target.querySelectorAll<HTMLElement>('button')].find((e) => (e.textContent ?? '').trim() === text);
const text = () => (target.textContent ?? '').replace(/\s+/g, ' ');
const click = async (el: HTMLElement | undefined) => { expect(el, 'knappen findes').toBeTruthy(); el!.click(); await settle(); };
const clickSymbol = async (id: string) => { ui.selected = [id]; await settle(); };
const startSelect = () => target.querySelectorAll<HTMLSelectElement>('select')[0];

async function open() {
  await click(button('Ny signalvej …'));
}

describe('Signalvej-guiden: vælg start og slut', () => {
  it('"Vælg på tegningen": et klik på start og et klik på slut finder vejen (slutpunkt nr. 0 tæller som i gang)', async () => {
    await open();
    await click(button('Vælg på tegningen'));
    expect(text()).toContain('Klik på startsymbolet');
    await clickSymbol('kedel');
    expect(text()).toContain('Start: Kedel — klik nu på slutsymbolet');
    await clickSymbol('rad');
    expect(text()).toContain('2. Vejen');
    expect(text()).toContain('Brug denne vej');
    expect(fetched.some((f) => f.endsWith('/info'))).toBe(true);
  });

  it('start fra listen, og "Vælg slut på tegningen" vælger slutpunktet — også det symbol, der var valgt før', async () => {
    await open();
    ui.selected = ['rad'];                                        // radiatoren er allerede valgt i tegningen
    await settle();
    startSelect().value = 'kedel';
    startSelect().dispatchEvent(new Event('change', { bubbles: true }));
    await settle();
    await click(button('Vælg slut på tegningen'));
    expect(select).toHaveBeenCalledWith([]);                       // markeringen fjernes, så et klik altid tæller
    ui.selected = [];
    await settle();
    await clickSymbol('rad');
    expect(text()).toContain('2. Vejen');
  });

  it('"← valgt" under Slut bruger det symbol, der er valgt i tegningen', async () => {
    await open();
    startSelect().value = 'kedel';
    startSelect().dispatchEvent(new Event('change', { bubbles: true }));
    await settle();
    const underSlut = [...target.querySelectorAll<HTMLElement>('label.field')].find((l) => (l.textContent ?? '').trim().startsWith('Slut'))!;
    ui.selected = ['rad'];
    await settle();
    await click([...underSlut.querySelectorAll<HTMLElement>('button')].find((b) => (b.textContent ?? '').includes('valgt')));
    expect(text()).toContain('2. Vejen');
  });

  it('et klik på et rør forklarer, hvorfor det ikke kan bruges', async () => {
    await open();
    startSelect().value = 'kedel';
    startSelect().dispatchEvent(new Event('change', { bubbles: true }));
    await settle();
    await click(button('Vælg slut på tegningen'));
    await clickSymbol('r1');
    expect(text()).toContain('rør, en tekst eller en visning');
    expect(text()).not.toContain('2. Vejen');
  });
});
