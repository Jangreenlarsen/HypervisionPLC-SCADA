// Klient-side sanering (forsvar i dybden — serveren har allerede saneret ved upload).
import DOMPurify from 'dompurify';

export function sanitizeSvg(svg: string): string {
  return DOMPurify.sanitize(svg, {
    USE_PROFILES: { svg: true, svgFilters: true },
    FORBID_TAGS: ['foreignObject', 'script', 'animate', 'set', 'animateMotion', 'animateTransform'],
    ADD_ATTR: ['inkscape:label'],
  });
}

/** Et SVG-fragment (fx et symbols `<g>`): renses inde i et `<svg>` — løse SVG-elementer uden for et `<svg>` fjerner DOMPurify helt. */
export function sanitizeSvgFragment(fragment: string): string {
  const clean = sanitizeSvg(`<svg xmlns="http://www.w3.org/2000/svg">${fragment}</svg>`);
  const m = clean.match(/^<svg[^>]*>([\s\S]*)<\/svg>\s*$/);
  return m ? m[1] : '';
}
