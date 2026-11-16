import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PRESSED_COLOR, PRESSED_MS, flashPressed } from './pulseFlash';

describe('trykknappen lyser efter et tryk (v6.13.3)', () => {
  let root: HTMLElement;
  beforeEach(() => {
    vi.useFakeTimers();
    root = document.createElement('div');
    root.innerHTML = `<svg><g id="kvit"><circle id="kvit_flade" data-hv-pid="flade" style="fill: rgb(214, 214, 214)"></circle>
      <rect id="kvit_ramme" data-hv-pid="ramme"></rect></g><g id="andet"><circle data-hv-pid="lampe"></circle></g></svg>`;
  });
  afterEach(() => vi.useRealTimers());
  const flade = () => root.querySelector('#kvit_flade') as unknown as HTMLElement;

  it('fladen bliver grøn i 1 s og får så sin farve igen', () => {
    expect(flashPressed(root, 'kvit')).toBe(1);
    expect(flade().style.fill).toBe('rgb(124, 196, 127)');            // #7cc47f
    expect(PRESSED_COLOR).toBe('#7cc47f');
    vi.advanceTimersByTime(PRESSED_MS - 1);
    expect(flade().style.fill).toBe('rgb(124, 196, 127)');
    vi.advanceTimersByTime(2);
    expect(flade().style.fill).toBe('rgb(214, 214, 214)');
    expect((root.querySelector('#kvit_ramme') as HTMLElement).getAttribute('style')).toBeNull();   // kun fladen
  });

  it('et nyt tryk, mens den lyser, forlænger lyset og husker den oprindelige farve', () => {
    flashPressed(root, 'kvit');
    vi.advanceTimersByTime(600);
    flashPressed(root, 'kvit');
    vi.advanceTimersByTime(600);                                       // 1,2 s efter første tryk: stadig tændt
    expect(flade().style.fill).toBe('rgb(124, 196, 127)');
    vi.advanceTimersByTime(500);
    expect(flade().style.fill).toBe('rgb(214, 214, 214)');             // ikke lysfarven
  });

  it('et symbol uden flade, eller et ukendt element, gør ingenting', () => {
    expect(flashPressed(root, 'andet')).toBe(0);
    expect(flashPressed(root, 'findes-ikke')).toBe(0);
  });
});
