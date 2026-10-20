// Gennemgang af hele siden: alle symboler, alle valg i menuerne, alle tag-arter — og ingen fejl undervejs.
import { flushSync, mount, tick, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SYMBOLS } from '../lib/symbols';
import SymbolTest from './SymbolTest.svelte';

let target: HTMLElement;
let app: Record<string, any>;
let errors: unknown[][];

beforeEach(() => {
  errors = [];
  vi.spyOn(console, 'error').mockImplementation((...a) => { errors.push(a); });
  vi.spyOn(console, 'warn').mockImplementation((...a) => { errors.push(a); });
  target = document.createElement('div');
  document.body.appendChild(target);
  app = mount(SymbolTest, { target });
  flushSync();
});
afterEach(() => {
  unmount(app);
  target.remove();
  vi.restoreAllMocks();
});

const settle = async () => { flushSync(); await tick(); flushSync(); };
const tiles = () => [...target.querySelectorAll<HTMLElement>('.tile')];
const status = () => target.querySelector('.status')?.textContent ?? '';
const choose = async (sel: HTMLSelectElement, value: string) => {
  sel.value = value;
  sel.dispatchEvent(new Event('change', { bubbles: true }));
  await settle();
};
const allSelects = (root: ParentNode) => [...root.querySelectorAll<HTMLSelectElement>('select')];

describe('Symboltest: gennemgang af siden', () => {
  it('alle symboler kan vælges og viser en anvendt opsætning uden fejl', async () => {
    const t = tiles();
    expect(t.length).toBe(SYMBOLS.length);
    for (const tile of t) {
      tile.click();
      await settle();
      expect(status(), tile.textContent ?? '').toContain('Anvendt');
      expect(status(), tile.textContent ?? '').not.toContain('findes ikke');
    }
    expect(errors).toEqual([]);
  });

  it('alle valg i alle menuer under en animation kan vælges uden fejl, og den bliver ved med at kunne anvendes', async () => {
    // et udvalg af symboler med forskellige dele og opsætninger
    for (const name of ['Lampe', 'Vippekontakt ON/OFF/ON', 'Pumpe', 'Setpunkt-felt', 'Tank', 'Rør (vandret)', 'Varmepumpe']) {
      const tile = tiles().find((e) => (e.textContent ?? '').includes(name));
      if (!tile) continue;
      tile.click();
      await settle();
      const card = target.querySelector<HTMLElement>('details.card')!;
      expect(card, name).toBeTruthy();
      // første række i kortet: Del, Animation, Følger
      const selects = () => allSelects(card.querySelector('.row')!);
      for (let i = 0; i < selects().length; i++) {
        for (const o of [...selects()[i].options]) {
          await choose(selects()[i], o.value);
          expect(status(), `${name}: ${o.textContent}`).toContain('Anvendt');
        }
      }
    }
    expect(errors).toEqual([]);
  });

  it('alle tag-arter og alle animationstyper kan vælges i brugerfladen uden fejl', async () => {
    tiles().find((e) => (e.textContent ?? '').includes('Lampe'))!.click();
    await settle();
    const kindSel = target.querySelector<HTMLSelectElement>('.card select')!;   // tagets Art
    for (const kind of ['num', 'pos', 'bool']) {
      await choose(kindSel, kind);
      const card = target.querySelector<HTMLElement>('details.card')!;
      const animSel = allSelects(card.querySelector('.row')!)[1];
      for (const o of [...animSel.options]) {
        await choose(animSel, o.value);
        expect(status(), `${kind}/${o.value}`).toContain('Anvendt');
        // parameterfelterne er tegnet
        expect(card.querySelectorAll('.params .field').length, `${kind}/${o.value}`).toBeGreaterThan(0);
      }
    }
    expect(errors).toEqual([]);
  });

  it('værdier kan skiftes for alle tag-arter (knapper, skyder, tal) og afspilning kan startes og stoppes', async () => {
    tiles().find((e) => (e.textContent ?? '').includes('Tank'))!.click();
    await settle();
    const kindSel = target.querySelector<HTMLSelectElement>('.card select')!;
    for (const kind of ['bool', 'num', 'pos']) {
      await choose(kindSel, kind);
      for (const b of [...target.querySelectorAll<HTMLButtonElement>('.card .row button')].filter((x) => !['Fjern'].includes((x.textContent ?? '').trim()))) {
        b.click();
        await settle();
      }
      const range = target.querySelector<HTMLInputElement>('.card input[type=range]');
      if (range) { range.value = '60'; range.dispatchEvent(new Event('input', { bubbles: true })); await settle(); }
    }
    const play = [...target.querySelectorAll<HTMLSelectElement>('.card select')].find((s) => s.getAttribute('aria-label')?.startsWith('Afspil'))!;
    await choose(play, 'loop');
    await new Promise((r) => setTimeout(r, 160));
    await settle();
    expect(target.textContent).toContain('Stop afspilning');
    [...target.querySelectorAll<HTMLButtonElement>('button')].find((b) => (b.textContent ?? '').includes('Stop afspilning'))!.click();
    await settle();
    expect(target.textContent).not.toContain('Stop afspilning');
    expect(errors).toEqual([]);
  });

  it('tilføj og fjern tags og animationer, nulstil, hent opsætning — uden fejl', async () => {
    tiles().find((e) => (e.textContent ?? '').includes('Vippekontakt ON/OFF/ON'))!.click();
    await settle();
    const click = async (text: string) => {
      const b = [...target.querySelectorAll<HTMLButtonElement>('button')].find((x) => (x.textContent ?? '').trim().startsWith(text));
      expect(b, text).toBeTruthy();
      b!.click();
      await settle();
    };
    for (const t of ['+ Til/fra', '+ Tal', '+ Position', '+ Tilføj animation', '+ Tilføj animation']) await click(t);
    expect(status()).toContain('Anvendt');
    await click('Hent bibliotekets opsætning');
    await click('Hent symbolets egne');
    await click('Anvend igen');
    expect(status()).toContain('Anvendt');
    await click('Nulstil');
    expect(status()).toContain('0 animationer');
    // fjern alle tags — der oprettes altid ét nyt
    for (let i = 0; i < 6; i++) {
      const rm = [...target.querySelectorAll<HTMLButtonElement>('button')].find((x) => (x.getAttribute('aria-label') ?? '').startsWith('Fjern tag'));
      if (!rm) break;
      rm.click();
      await settle();
    }
    expect(target.querySelectorAll('input.name').length).toBeGreaterThan(0);
    expect(errors).toEqual([]);
  });
});
