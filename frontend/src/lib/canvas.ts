// Fælles tegning af en SVG med bindinger — bruges af Overview og binding-editoren.
import { applyBinding, bindingActive, resetAnim } from './animate';
import type { Binding, LiveValue, TagMeta } from './api';
import { sanitizeSvg } from './svg';

/** Indsæt (saneret) SVG i containeren og gør den skalerbar. */
export function mountSvg(container: HTMLElement, svg: string, descriptions: Record<string, string> = {}): SVGSVGElement | null {
  container.innerHTML = sanitizeSvg(svg);
  const root = container.querySelector('svg');
  root?.removeAttribute('width');
  root?.removeAttribute('height');
  addTooltips(root, descriptions);
  return root;
}

/**
 * Symbolets navn (sat i Tegn) og forklaring (sat under Bindinger) som tooltip: et <title> på elementet. Ikke på tekst-elementer —
 * en tekst-binding skriver værdien med textContent og ville slette titlen.
 */
export function addTooltips(root: Element | null, descriptions: Record<string, string> = {}): void {
  if (!root) return;
  for (const el of Array.from(root.querySelectorAll('[id]'))) {
    const tag = el.tagName.toLowerCase();
    if (tag === 'text' || tag === 'tspan') continue;
    const name = el.getAttribute('data-hv-name')?.trim();
    // Forklaringen sættes under Bindinger (gemmes ved bindingerne); ældre tegninger kan have den i selve SVG'en
    const desc = (descriptions[el.id] ?? el.getAttribute('data-hv-desc'))?.trim();
    const textContent = [name, desc].filter(Boolean).join('\n');
    if (!textContent) continue;
    const title = el.ownerDocument.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = textContent;
    el.insertBefore(title, el.firstChild);
  }
}

/**
 * Største størrelse med tegningens proportioner (viewBox) der passer i den ledige plads — som
 * "contain". Højden har et minimum, så et meget lavt vindue ikke gør tegningen ulæselig (så scrolles).
 */
export function fitSize(vbW: number, vbH: number, availW: number, availH: number, minH = 200): { width: number; height: number } {
  if (!(vbW > 0 && vbH > 0 && availW > 0)) return { width: Math.max(0, availW), height: 0 };
  const h = Math.max(minH, availH);
  const scale = Math.min(availW / vbW, h / vbH);
  const px = (v: number) => Math.floor(v + 1e-6); // 1879.9999… er 1880
  return { width: px(vbW * scale), height: px(vbH * scale) };
}

/** Ledig højde fra elementets top ned til sidefoden (vinduets bund minus sidefod og sidens polstring). */
export function availableHeight(el: HTMLElement): number {
  const top = el.getBoundingClientRect().top + window.scrollY;
  const footer = (document.querySelector('footer') as HTMLElement | null)?.offsetHeight ?? 0;
  const main = el.closest('main');
  const pad = main ? parseFloat(getComputedStyle(main).paddingBottom) : 0;
  return Math.floor(window.innerHeight - top - footer - pad - 1);
}

/** Giv en monteret SVG den største størrelse med dens proportioner, der passer i containeren og vinduet. */
export function fitSvg(svg: SVGSVGElement | null, container: HTMLElement | null): void {
  if (!svg || !container) return;
  const vb = svg.viewBox.baseVal;
  const style = getComputedStyle(container);
  const padX = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
  const padY = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom) + parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
  const { width, height } = fitSize(vb?.width ?? 0, vb?.height ?? 0, container.clientWidth - padX, availableHeight(container) - padY);
  if (!height) return; // ingen brugbar viewBox — CSS-standarden (fuld bredde) gælder
  svg.style.width = `${width}px`;
  svg.style.height = `${height}px`;
}

/**
 * Kald `fn` når layoutet kan have ændret sig: vinduesstørrelse/browser-zoom, menuen ombrydes
 * (header ændrer højde) eller de givne elementer ændrer størrelse. Returnerer en oprydningsfunktion.
 */
export function onLayoutChange(fn: () => void, ...elements: (Element | null | undefined)[]): () => void {
  window.addEventListener('resize', fn);
  const ro = new ResizeObserver(() => fn());
  for (const el of [document.querySelector('header'), ...elements]) if (el) ro.observe(el);
  return () => {
    window.removeEventListener('resize', fn);
    ro.disconnect();
  };
}

/** Alle tags en binding læser: dens eget og evt. løbelysets retnings-tag (samme regel som backendens binding_tags). */
export function bindingTags(b: Pick<Binding, 'tag' | 'anim' | 'params'>): string[] {
  const tags = b.tag && b.tag !== '@on' && !b.tag.startsWith('@val:') ? [b.tag] : [];   // "Altid til" og en fast værdi er ikke tags
  const extra = [b.anim === 'flow' ? b.params?.dir_tag : '', b.params?.pos_tag];
  for (const x of extra) if (x && !tags.includes(x)) tags.push(x);
  return tags;
}

/** Bindinger pr. tag — en binding står under hvert tag den læser, så den gentegnes når et af dem ændres. */
export function byTag(bindings: Binding[]): Map<string, Binding[]> {
  const map = new Map<string, Binding[]>();
  for (const b of bindings) for (const t of bindingTags(b)) map.set(t, [...(map.get(t) ?? []), b]);
  return map;
}

export function findElement(container: HTMLElement, id: string): Element | null {
  return container.querySelector(`#${CSS.escape(id)}`);
}

const ALWAYS_ON: LiveValue = { value: true, quality: 'good', ts: 0, error: null };

/**
 * Prioritetsgrupper (v0.72.0): animationer af samme slags på samme del, hvor mindst én er "aktiv/passiv" (`params.when`).
 * Den øverste, der er aktiv (en "aktiv/ikke aktiv" tæller altid som aktiv), vinder; er ingen aktive, vises delen som tegnet.
 * Farve og Blafrer deler fyldfarven og er derfor samme slags.
 */
const channel = (anim: string): string => (anim === 'flicker' ? 'fill' : anim);
const groupKey = (b: Pick<Binding, 'element' | 'anim'>): string => `${b.element}\u0000${channel(b.anim)}`;
const groupsOf = new WeakMap<HTMLElement, Map<string, Binding[]>>();

/** Byg prioritetsgrupperne for en tegning (bindingerne i deres rækkefølge). Kaldes af renderAll. */
export function priorityGroups(bindings: Binding[]): Map<string, Binding[]> {
  const all = new Map<string, Binding[]>();
  for (const b of bindings) {
    if (b.anim.startsWith('click:')) continue;
    const k = groupKey(b);
    all.set(k, [...(all.get(k) ?? []), b]);
  }
  const out = new Map<string, Binding[]>();
  // Også uden "passiv", når flere tags styrer samme del og slags (symbolets egen + grupper): ellers vinder den, hvis tag
  // sidst ændrede sig, fordi kun den ændrede binding tegnes om — nu vinder altid den sidste i rækkefølgen
  for (const [k, list] of all) {
    if (list.some((b) => b.params?.when) || new Set(list.map((b) => b.tag)).size > 1) {
      out.set(k, [...list].sort((x, y) => (x.position ?? 0) - (y.position ?? 0)));
    }
  }
  return out;
}

/** Live-værdien for en binding: "Altid til", en fast værdi (`@val:75`) eller tagets værdi. */
const liveFor = (tag: string, values: Record<string, LiveValue>): LiveValue | undefined => {
  if (tag === '@on') return ALWAYS_ON;
  if (tag.startsWith('@val:')) {
    const n = Number(tag.slice(5));
    return Number.isFinite(n) && tag.length > 5 ? { value: n, quality: 'good', ts: 0, error: null } : undefined;
  }
  return values[tag];
};
const liveOf = (b: Binding, values: Record<string, LiveValue>): LiveValue | undefined => liveFor(b.tag, values);
const dirOf = (b: Binding, values: Record<string, LiveValue>) => (b.anim === 'flow' && b.params?.dir_tag ? values[b.params.dir_tag] : undefined);
const posOf = (b: Binding, values: Record<string, LiveValue>) => (b.params?.pos_tag ? values[b.params.pos_tag] : undefined);

/** Den animation i gruppen, der skal vises nu (null = ingen — delen som tegnet). */
export function groupWinner(members: Binding[], values: Record<string, LiveValue>): Binding | null {
  if (!members.some((m) => m.params?.when)) {
    // Uden "passiv": den sidste AKTIVE vinder (som et "eller" mellem kilderne — fx et rør med løbelys fra to pumper);
    // er ingen aktive, vises den sidstes fra-tilstand
    for (let i = members.length - 1; i >= 0; i--) {
      const m = members[i];
      if (bindingActive(m, liveOf(m, values), dirOf(m, values), posOf(m, values))) return m;
    }
    return members[members.length - 1] ?? null;
  }
  for (const m of members) {
    if (!m.params?.when || bindingActive(m, liveOf(m, values), dirOf(m, values), posOf(m, values))) return m;
  }
  return null;
}

function renderGroup(container: HTMLElement, members: Binding[], values: Record<string, LiveValue>, tags: Record<string, TagMeta>): void {
  const el = findElement(container, members[0].element);
  if (!el) return;
  const winner = groupWinner(members, values);
  // de andre rydder op efter sig (samme slags som vinderen overskrives af den)
  const cleared = new Set<string>();
  for (const m of members) {
    if (m === winner || (winner && m.anim === winner.anim) || cleared.has(m.anim)) continue;
    cleared.add(m.anim);
    resetAnim(el, m.anim, m.params ?? {});
  }
  if (winner) applyBinding(el, winner, liveOf(winner, values), tags[winner.tag], dirOf(winner, values), posOf(winner, values));
}

export function renderBinding(
  container: HTMLElement, b: Binding, values: Record<string, LiveValue>, tags: Record<string, TagMeta>,
): void {
  const group = groupsOf.get(container)?.get(groupKey(b));
  if (group) {
    renderGroup(container, group, values, tags);
    return;
  }
  const el = findElement(container, b.element);
  // "Altid til" (symbolguiden): altid aktiv, uden et tag
  const own = liveFor(b.tag, values);
  if (el) applyBinding(el, b, own, tags[b.tag], b.anim === 'flow' && b.params?.dir_tag ? values[b.params.dir_tag] : undefined,
    b.params?.pos_tag ? values[b.params.pos_tag] : undefined);
}

export function renderAll(
  container: HTMLElement, bindings: Binding[], values: Record<string, LiveValue>, tags: Record<string, TagMeta>,
): void {
  groupsOf.set(container, priorityGroups(bindings));
  for (const b of bindings) renderBinding(container, b, values, tags);
}
