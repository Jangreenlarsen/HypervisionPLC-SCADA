// Klient-side sanering (forsvar i dybden — serveren har allerede saneret ved upload).
import DOMPurify from 'dompurify';

export function sanitizeSvg(svg: string): string {
  return DOMPurify.sanitize(svg, {
    USE_PROFILES: { svg: true, svgFilters: true },
    FORBID_TAGS: ['foreignObject', 'script', 'animate', 'set', 'animateMotion', 'animateTransform'],
    ADD_ATTR: ['inkscape:label'],
  });
}
