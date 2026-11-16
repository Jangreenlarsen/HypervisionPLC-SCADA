// Trykknap (puls): efter et tryk lyser knappens flade i 1 s, så man kan se på tegningen, at knappen blev aktiveret (v6.13.3, Jan:
// "man ser ikke den skifter tilstand"). PLC-pulsen er kort (500 ms) og nulstilles af serveren, så der er ingen tilstand at vise fra
// PLC'en — det her er ren visning i den browser, hvor der blev trykket. Delen hedder "flade" (pid) i bibliotekets trykknap.

export const PRESSED_COLOR = '#7cc47f';   // samme grønne som "aktiv" i betjeningssymbolerne
export const PRESSED_MS = 1000;
export const PRESSED_PART = 'flade';

const timers = new WeakMap<Element, ReturnType<typeof setTimeout>>();
const original = new WeakMap<Element, string>();

/**
 * Lys symbolets `flade` i `ms`. Trykkes der igen, mens den lyser, forlænges den (og den oprindelige farve huskes stadig).
 * → antal dele, der lyser (0 = symbolet har ingen flade, fx en anden type, så er der intet at vise).
 */
export function flashPressed(container: ParentNode, element: string, ms = PRESSED_MS, color = PRESSED_COLOR): number {
  const root = container.querySelector(`#${CSS.escape(element)}`);
  if (!root) return 0;
  const parts = [...root.querySelectorAll(`[data-hv-pid="${PRESSED_PART}"]`)] as (HTMLElement | SVGElement)[];
  for (const part of parts) {
    if (!timers.has(part)) original.set(part, part.style.fill);   // kun første gang: ellers huskes lysfarven som "oprindelig"
    clearTimeout(timers.get(part));
    part.style.fill = color;
    timers.set(part, setTimeout(() => {
      part.style.fill = original.get(part) ?? '';
      timers.delete(part);
      original.delete(part);
    }, ms));
  }
  return parts.length;
}
