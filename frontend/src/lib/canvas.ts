// Fælles tegning af en SVG med bindinger — bruges af Overview og binding-editoren.
import { applyBinding } from './animate';
import type { Binding, LiveValue, TagMeta } from './api';
import { sanitizeSvg } from './svg';

/** Indsæt (saneret) SVG i containeren og gør den skalerbar. */
export function mountSvg(container: HTMLElement, svg: string): SVGSVGElement | null {
  container.innerHTML = sanitizeSvg(svg);
  const root = container.querySelector('svg');
  root?.removeAttribute('width');
  root?.removeAttribute('height');
  return root;
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

export function byTag(bindings: Binding[]): Map<string, Binding[]> {
  const map = new Map<string, Binding[]>();
  for (const b of bindings) map.set(b.tag, [...(map.get(b.tag) ?? []), b]);
  return map;
}

export function findElement(container: HTMLElement, id: string): Element | null {
  return container.querySelector(`#${CSS.escape(id)}`);
}

export function renderBinding(
  container: HTMLElement, b: Binding, values: Record<string, LiveValue>, tags: Record<string, TagMeta>,
): void {
  const el = findElement(container, b.element);
  if (el) applyBinding(el, b, values[b.tag], tags[b.tag]);
}

export function renderAll(
  container: HTMLElement, bindings: Binding[], values: Record<string, LiveValue>, tags: Record<string, TagMeta>,
): void {
  for (const b of bindings) renderBinding(container, b, values, tags);
}
