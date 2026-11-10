// Rullemenuen i Tegn-værktøjslinjen: åbner og lukker (klik udenfor, Esc).
import { flushSync, mount, unmount } from 'svelte';
import { afterEach, describe, expect, it } from 'vitest';
import MenuHost from './MenuHost.test.svelte';

let target: HTMLElement;
let app: Record<string, unknown>;
afterEach(() => { unmount(app); target.remove(); });

function open() {
  target = document.createElement('div');
  document.body.appendChild(target);
  app = mount(MenuHost, { target });
  flushSync();
}
const panel = () => target.querySelector('[role="group"][aria-label="Vis"]');
const button = () => target.querySelector<HTMLButtonElement>('button[aria-haspopup]')!;

describe('Menu', () => {
  it('opens on click and closes on Esc, on a click outside, and on a second click', () => {
    open();
    expect(panel()).toBeNull();
    button().click();
    flushSync();
    expect(panel()).not.toBeNull();
    expect(panel()!.textContent).toContain('Indhold');
    expect(button().getAttribute('aria-expanded')).toBe('true');
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    flushSync();
    expect(panel()).toBeNull();
    button().click();
    flushSync();
    document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    flushSync();
    expect(panel()).toBeNull();
    button().click();
    flushSync();
    panel()!.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));      // et klik i selve panelet lukker ikke
    flushSync();
    expect(panel()).not.toBeNull();
    button().click();
    flushSync();
    expect(panel()).toBeNull();
  });
});
