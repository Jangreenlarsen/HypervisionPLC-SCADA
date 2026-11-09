// Signalvej-guiden: ret vejen ved at klikke i tegningen — "gå via" rør og symboler, og skift en 3-vejsventils vej (jsdom).
import { flushSync, mount, tick, unmount } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import SignalPathGuide from './SignalPathGuide.svelte';
import { ui } from './signalGuideHarness.svelte';
import type { GNode, Graph, Pt } from './signalPath';

const pipe = (id: string, a: Pt, b: Pt): GNode => ({ id, name: '', type: '', pipe: true, terminals: [a, b], lines: [{ part: 'all', a, b }], refs: [null, null] });
const sym = (id: string, name: string, type: string, terminals: Pt[], fracs: Pt[] | null = null): GNode =>
  ({ id, name, type, pipe: false, terminals, lines: [], refs: [], fracs });

/** Kedel → øverste vej (r1, r2) → T → radiator, en længere vej nedenom (n1, n2, n3) og en blindgyde (b1 → stub). */
const LOOP: Graph = { nodes: [
  sym('kedel', 'Kedel', 'kedel', [[0, 0]]),
  pipe('r1', [0, 0], [50, 0]), pipe('r2', [50, 0], [100, 0]),
  pipe('n1', [0, 0], [0, 40]), pipe('n2', [0, 40], [100, 40]), pipe('n3', [100, 40], [100, 0]),
  sym('t', 'T', 't_stykke', [[100, 0], [150, 0], [100, 40]]),
  pipe('r3', [150, 0], [200, 0]), sym('rad', 'Radiator', 'radiator', [[200, 0]]),
  pipe('b1', [50, 0], [50, -30]), sym('stub', 'Blindgyde', 'ekspansion', [[50, -30]]),
  { id: 'tekst', name: 'Tekst', type: 'statusfelt', pipe: false, terminals: [[300, 300]], lines: [], refs: [] },
] };

/** Kilde → rIn → 3-vejsventil (A til venstre, B øverst, AB til højre) → rA → radA, og rB → radB. */
const WAYS: Graph = { nodes: [
  sym('src', 'Kilde', 'kedel', [[300, 100]]), pipe('rIn', [300, 100], [200, 100]),
  sym('v3', 'V3', 'trevejs_motorventil', [[100, 100], [150, 60], [200, 100]], [[0.07, 0.46], [0.46, 0.08], [0.84, 0.46]]),
  pipe('rA', [100, 100], [50, 100]), sym('radA', 'Radiator A', 'radiator', [[50, 100]]),
  pipe('rB', [150, 60], [150, 0]), sym('radB', 'Radiator B', 'radiator', [[150, 0]]),
] };

let target: HTMLElement;
let app: Record<string, unknown>;
const select = vi.fn();
const highlight = vi.fn();

function open(graph: Graph) {
  ui.selected = [];
  select.mockClear();
  highlight.mockClear();
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: { method?: string; body?: string }) => {
    let body: unknown = [];
    if (url.endsWith('/info')) {
      const els = (JSON.parse(init?.body ?? '{}').elements ?? []) as string[];
      body = { elements: els.map((e) => ({ element: e, name: graph.nodes.find((n) => n.id === e)?.name || e, tags: [], flows: [], parts: [] })), tags: [], max_conditions: 25 };
    } else if (url.includes('/symbol-flow')) body = {};
    return new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } });
  }));
  target = document.createElement('div');
  document.body.appendChild(target);
  app = mount(SignalPathGuide, { target, props: {
    drawingId: 'd', ready: true, get selected() { return ui.selected; }, get rev() { return ui.rev; },
    graph: () => graph, highlight, select, ensureSaved: async () => true,
  } });
  flushSync();
}
afterEach(() => {
  unmount(app);
  target.remove();
  vi.unstubAllGlobals();
});

const settle = async () => { for (let i = 0; i < 4; i++) { flushSync(); await tick(); await new Promise((r) => setTimeout(r, 0)); } flushSync(); };
const button = (label: string) => [...target.querySelectorAll<HTMLElement>('button')].find((e) => (e.textContent ?? '').trim() === label);
const text = () => (target.textContent ?? '').replace(/\s+/g, ' ');
const click = async (el: HTMLElement | undefined) => { expect(el, 'knappen findes').toBeTruthy(); el!.click(); await settle(); };
const chooseStartEnd = async (start: string, end: string) => {
  await click(button('Ny signalvej …'));
  const sel = target.querySelectorAll<HTMLSelectElement>('select');
  sel[0].value = start;
  sel[0].dispatchEvent(new Event('change', { bubbles: true }));
  await settle();
  const endSel = [...target.querySelectorAll<HTMLElement>('label.field')].find((l) => (l.textContent ?? '').trim().startsWith('Slut'))!.querySelector('select')!;
  endSel.value = end;
  endSel.dispatchEvent(new Event('change', { bubbles: true }));
  await settle();
};
/** Et klik på et element i tegningen: først tom markering (som efter forrige klik), så elementet. */
const clickInDrawing = async (id: string) => { ui.selected = []; await settle(); ui.selected = [id]; await settle(); };
const wayValue = () => target.querySelector<HTMLSelectElement>('select.way')?.value;

describe('Signalvej-guiden: klik i tegningen', () => {
  it('et klik på et rør lægger vejen igennem det, og et nyt klik fjerner det igen', async () => {
    open(LOOP);
    await chooseStartEnd('kedel', 'rad');
    expect(text()).toContain('Klik på rør og symboler i tegningen');
    await clickInDrawing('n2');                                  // røret på den lange vej
    expect(text()).toContain('Via n2');
    expect(text()).toContain('n2 er tilføjet');
    expect(select).toHaveBeenCalledWith([]);                     // markeringen fjernes, så et klik kan gentages
    const lastLines = highlight.mock.calls.at(-1)![0] as { pts: Pt[] }[];
    expect(lastLines.some((l) => l.pts.some((p) => p[1] === 40))).toBe(true);   // vejen ligger nu langs den nederste vej (y = 40)
    await clickInDrawing('n2');
    expect(text()).not.toContain('Via n2');
    expect(text()).toContain('n2 er fjernet');
  });

  it('en blindgyde kan ikke bruges som via-punkt, og det siges', async () => {
    open(LOOP);
    await chooseStartEnd('kedel', 'rad');
    await clickInDrawing('stub');
    expect(text()).toContain('kan ikke bruges');
    expect(text()).not.toContain('Via Blindgyde');
  });

  it('tekster og visninger kan ikke bruges, og start/slut er ikke via-punkter', async () => {
    open(LOOP);
    await chooseStartEnd('kedel', 'rad');
    await clickInDrawing('tekst');
    expect(text()).toContain('tekst eller en visning');
    await clickInDrawing('kedel');
    expect(text()).not.toContain('Via Kedel');
  });

  it('Esc (eller Færdig) slår klik-tilstanden fra: så ændrer et klik intet', async () => {
    open(LOOP);
    await chooseStartEnd('kedel', 'rad');
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await settle();
    expect(text()).not.toContain('Klik på rør og symboler i tegningen');
    await clickInDrawing('n2');
    expect(text()).not.toContain('Via n2');
    await click(button('Ret vejen i tegningen'));
    await clickInDrawing('n2');
    expect(text()).toContain('Via n2');
  });

  it('"Vælg via på tegningen" og "← valgt" og rullemenuen lægger også et punkt til', async () => {
    open(LOOP);
    await chooseStartEnd('kedel', 'rad');
    await click(button('Vælg via på tegningen'));
    expect(text()).toContain('Klik på et rør eller symbol, vejen skal gå igennem');
    ui.selected = ['n1'];
    await settle();
    expect(text()).toContain('Via n1');
    // ✕ fjerner det igen
    await click([...target.querySelectorAll<HTMLElement>('button')].find((b) => b.getAttribute('aria-label') === 'Fjern via n1'));
    expect(text()).not.toContain('Via n1');
  });

  it('et klik på en 3-vejsventil på vejen skifter dens vej (automatisk → AB → A → AB → B → automatisk)', async () => {
    open(WAYS);
    await chooseStartEnd('src', 'radA');
    expect(wayValue()).toBe('');                                  // automatisk
    await clickInDrawing('v3');
    expect(wayValue()).toBe('AB>A');
    expect(text()).toContain('V3: AB → A');
    await clickInDrawing('v3');                                   // AB → B fører ikke til radiator A
    expect(text()).toContain('V3: AB → B');
    expect(text()).toContain('Der er ingen sammenhængende vej til Radiator A');
    await clickInDrawing('v3');
    expect(text()).toContain('V3: automatisk');
    expect(text()).not.toContain('Der er ingen sammenhængende vej');
  });

  it('med to grene gælder vejskiftet den valgte gren', async () => {
    open(WAYS);
    await chooseStartEnd('src', 'radA');
    const more = [...target.querySelectorAll<HTMLElement>('label.field')].find((l) => (l.textContent ?? '').includes('Flere slutpunkter'))!.querySelector('select')!;
    more.value = 'radB';
    more.dispatchEvent(new Event('change', { bubbles: true }));
    await settle();
    expect(text()).toContain('Gren 2');
    await click([...target.querySelectorAll<HTMLElement>('button.link')].find((b) => (b.textContent ?? '').includes('Gren 2')));
    expect(text()).toContain('klik gælder her');
    await clickInDrawing('v3');
    expect(text()).toContain('V3: AB → A — gren 2');             // gren 2 går til radB: AB → A fører ikke dertil
    expect(text()).toContain('Der er ingen sammenhængende vej til Radiator B');
  });

  it('Brug denne vej åbner betingelser og udseende, og gem kræver et navn', async () => {
    open(WAYS);
    await chooseStartEnd('src', 'radA');
    await click(button('Brug denne vej →'));
    expect(text()).toContain('3. Hvornår går der flow?');
    expect(target.querySelector('[role="group"][aria-label="Betingelse for V3"]')).toBeTruthy();   // et spørgsmål for ventilen
    expect(text()).toContain('4. Udseende');
    expect(target.querySelectorAll('fieldset.look').length).toBeGreaterThan(1);                    // rør og 3-vejsventil
    expect(text()).toContain('5. Navn og gem');
    expect(button('Gem signalvej')!.hasAttribute('disabled')).toBe(true);                          // uden navn
  });

  it('Vend flowet vender retningen på grenen i tegningen', async () => {
    open(LOOP);
    await chooseStartEnd('kedel', 'rad');
    const dirs = () => (highlight.mock.calls.at(-1)![0] as { flow: number }[]).map((l) => l.flow);
    const before = dirs();
    expect(before.every((f) => f === 1)).toBe(true);
    await click(button('⇄ Vend flowet'));
    expect(text()).toContain('Du har vendt flowets retning');
    expect(dirs().every((f) => f === -1)).toBe(true);
    await click(button('⇄ Vend flowet'));
    expect(dirs()).toEqual(before);
  });
});
