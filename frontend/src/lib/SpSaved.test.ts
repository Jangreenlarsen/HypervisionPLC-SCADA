// Listen over gemte signalveje: "Ret som symbol" åbner vejen i symbol-guiden (v5.4.0).
import { flushSync, mount, unmount } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import SpSaved from './SpSaved.svelte';

const row = (extra: object = {}) => ({ id: 7, name: 'Kedel til radiator', ends: ['rad'], elements: [{}, {}], conditions: [], missing: [], symbol: 'sv~7', configured: false, ...extra });
let target: HTMLElement;
let app: Record<string, unknown> | undefined;

function show(paths: ReturnType<typeof row>[], onsymbol?: (p: { symbol?: string; name: string }) => void) {
  target = document.createElement('div');
  document.body.appendChild(target);
  app = mount(SpSaved, { target, props: { paths, ready: true, busy: false, onedit: vi.fn(), onremove: vi.fn(), onsymbol } });
  flushSync();
}
afterEach(() => { if (app) unmount(app); app = undefined; target?.remove(); });

describe('SpSaved', () => {
  it('opens the path as a symbol with the symbol id', () => {
    const onsymbol = vi.fn();
    show([row()], onsymbol);
    const btn = [...target.querySelectorAll('button')].find((b) => b.textContent?.includes('Ret som symbol'))!;
    btn.click();
    expect(onsymbol).toHaveBeenCalledWith(expect.objectContaining({ symbol: 'sv~7', name: 'Kedel til radiator' }));
    expect(btn.textContent).not.toContain('✓');
  });
  it('marks a path that already has its own setup', () => {
    show([row({ configured: true })], vi.fn());
    expect(target.textContent).toContain('Ret som symbol ✓');
  });
  it('has no symbol button without a handler (or for a path without a symbol id)', () => {
    show([row()]);
    expect(target.textContent).not.toContain('Ret som symbol');
  });
});
