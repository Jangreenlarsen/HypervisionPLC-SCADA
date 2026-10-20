// Siden som en bruger bruger den: klik, skriv og se resultatet i symbolet (jsdom).
import { flushSync, mount, tick, unmount } from 'svelte';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import SymbolTest from './SymbolTest.svelte';

let target: HTMLElement;
let app: Record<string, any>;

beforeEach(() => {
  target = document.createElement('div');
  document.body.appendChild(target);
  app = mount(SymbolTest, { target });
  flushSync();
});
afterEach(() => {
  unmount(app);
  target.remove();
});

const settle = async () => { flushSync(); await tick(); flushSync(); };
const tile = (text: string) => [...target.querySelectorAll<HTMLElement>('.tile')].find((e) => (e.textContent ?? '').includes(text))!;
const button = (text: string, root: ParentNode = target) => [...root.querySelectorAll<HTMLElement>('button')].find((e) => (e.textContent ?? '').trim() === text)!;
const typeInto = async (input: HTMLInputElement, value: string, event = 'input') => {
  input.value = value;
  input.dispatchEvent(new Event(event, { bubbles: true }));
  await settle();
};
const stage = () => target.querySelector('.stage')!;
const fills = (sel: string) => [...stage().querySelectorAll<SVGElement>(sel)].map((e) => e.style.fill);

describe('Symboltest som bruger', () => {
  it('Til/Fra: farven for Fra (off) bruges, når tagget er Fra, og farven for Til når det er Til', async () => {
    tile('Lampe').click();
    await settle();
    // standardanimationen er Farve på hele symbolet; felterne Til og Fra er de to hex-felter
    const hex = [...target.querySelectorAll<HTMLInputElement>('input.hex')];
    expect(hex.length).toBe(2);
    await typeInto(hex[0], '#112233');   // Til
    await typeInto(hex[1], '#aa0000');   // Fra
    // Til (tagget starter som Til)
    expect(fills('circle')[0]).toBe('rgb(17, 34, 51)');
    button('Fra').click();
    await settle();
    expect(fills('circle')[0]).toBe('rgb(170, 0, 0)');
    // og tilbage
    button('Til').click();
    await settle();
    expect(fills('circle')[0]).toBe('rgb(17, 34, 51)');
  });

  it('en ændret off-farve slår igennem med det samme, mens tagget står på Fra', async () => {
    tile('Lampe').click();
    await settle();
    button('Fra').click();
    await settle();
    const hex = [...target.querySelectorAll<HTMLInputElement>('input.hex')];
    await typeInto(hex[1], '#00ff00');
    expect(fills('circle')[0]).toBe('rgb(0, 255, 0)');
    await typeInto(hex[1], '#0000ff');
    expect(fills('circle')[0]).toBe('rgb(0, 0, 255)');
  });

  it('en farve valgt i paletten bruges', async () => {
    tile('Lampe').click();
    await settle();
    button('Fra').click();
    await settle();
    const swatch = target.querySelectorAll<HTMLElement>('.cf .current')[1];
    swatch.click();
    await settle();
    const pick = target.querySelector<HTMLElement>('.cf .pal .sw[title="#c62828"]')!;
    pick.click();
    await settle();
    expect(fills('circle')[0]).toBe('rgb(198, 40, 40)');
  });

  it('farvevælgeren (type=color) virker som hex-feltet', async () => {
    tile('Lampe').click();
    await settle();
    button('Fra').click();
    await settle();
    const color = target.querySelectorAll<HTMLInputElement>('.cf input[type=color]')[1];
    await typeInto(color, '#336699');
    expect(fills('circle')[0]).toBe('rgb(51, 102, 153)');
  });

  it('en ugyldig farvekode ødelægger ikke symbolet og kan rettes', async () => {
    tile('Lampe').click();
    await settle();
    button('Fra').click();
    await settle();
    const hex = [...target.querySelectorAll<HTMLInputElement>('input.hex')];
    await typeInto(hex[1], '#12');   // halvt skrevet: ingen ændring endnu
    await typeInto(hex[1], '#123456');
    expect(fills('circle')[0]).toBe('rgb(18, 52, 86)');
  });

  it('en ugyldig farvekode afvises: feltet markeres, og symbolet beholder sin farve', async () => {
    tile('Lampe').click();
    await settle();
    button('Fra').click();
    await settle();
    const hex = [...target.querySelectorAll<HTMLInputElement>('input.hex')];
    await typeInto(hex[1], '#00ff00');
    expect(fills('circle')[0]).toBe('rgb(0, 255, 0)');
    await typeInto(hex[1], 'rød', 'change');
    expect(fills('circle')[0]).toBe('rgb(0, 255, 0)');
    expect(hex[1].classList.contains('invalid')).toBe(true);
    expect(hex[1].value).toBe('#00ff00');   // feltet viser igen den farve symbolet har
    await typeInto(hex[1], 'red');          // et farvenavn er gyldigt
    expect(hex[1].classList.contains('invalid')).toBe(false);
  });

  it('to farve-animationer på samme del giver en advarsel — og den forsvinder igen', async () => {
    tile('Lampe').click();
    await settle();
    expect(target.querySelector('.warn')).toBeNull();
    button('+ Tilføj animation').click();
    await settle();
    expect(target.querySelector('.warn')?.textContent).toContain('den nederste i listen vinder');
    [...target.querySelectorAll<HTMLButtonElement>('button')].filter((b) => b.getAttribute('aria-label') === 'Fjern animation')[1].click();
    await settle();
    expect(target.querySelector('.warn')).toBeNull();
  });
});
