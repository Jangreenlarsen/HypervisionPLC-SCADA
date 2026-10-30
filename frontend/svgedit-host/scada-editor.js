// Værtsside for SVG-Edit inde i SCADA'en (indlæses i en iframe fra samme origin).
// Forældresiden (DrawEditor.svelte) bruger `window.scada` nedenfor.
// Al vores egen logik ligger i scada-core.js (deles med den nye editor); her er kun SVG-Edit-specifikt.
import Editor from './Editor.js';
import { createScada } from './scada-core.js';
import { DA, DA_EXT, merge } from './locale-da.js';


const editor = new Editor(document.getElementById('container'));
editor.setConfig({
  lang: 'da',
  imgPath: './images',
  extPath: './extensions',
  noDefaultExtensions: true,
  // Kun udvidelser der arbejder lokalt — ingen browser-lagring eller filåbning udenom SCADA'en
  // (ikke ext-connector: dens forbindelser bygger på SVG-Edits egne attributter, som serveren renser væk ved gem — så de
  // holder op med at følge symbolerne; v0.92.0)
  extensions: ['ext-eyedropper', 'ext-markers', 'ext-panning', 'ext-polystar', 'ext-shapes'],
  noStorageOnLoad: true,
  forceStorage: false,
  emptyStorageOnDecline: true,
  showRulers: true,
  dimensions: [1200, 700],
  allowInitialUserOverride: false,
});
editor.init();

/**
 * SVG-Edits højreklikmenu lukker ikke, når et punkt vælges — den står åben, til man venstreklikker på tegningen, og et
 * nyt højreklik oven på den gamle menu rammer menuen i stedet for tegningen (så det forkerte element kopieres, eller der
 * sker ingenting — BUGS.md v0.66.0). Luk den, når et punkt er valgt, og ved Escape.
 */
function hookContextMenu() {
  const cmenu = document.getElementById('se-cmenu_canvas');
  if (!cmenu) return;
  const hide = () => {
    const dlg = cmenu.$dialog ?? cmenu.shadowRoot?.firstElementChild;
    if (dlg) dlg.style.display = 'none';
  };
  // efter editorens egen håndtering af valget (den lytter på samme hændelse)
  cmenu.addEventListener('change', () => setTimeout(hide, 0));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
  window.addEventListener('blur', hide);
}

/**
 * Dansk i editoren (v0.92.0): SVG-Edit kender ikke "da" og kører på engelsk. De danske tekster lægges oven på de engelske,
 * sproget skiftes, og knapper/felter oversættes igen (komponenterne oversætter deres title/label, når attributten sættes).
 */
function localize() {
  const i = editor.i18next ?? window.svgEditor?.i18next;
  if (!i?.addResourceBundle) return;
  i.addResourceBundle('da', 'translation', merge(i.getResourceBundle('en', 'translation') || {}, DA), true, true);
  for (const [ns, texts] of Object.entries(DA_EXT)) i.addResourceBundle('da', ns, merge(i.getResourceBundle('en', ns) || {}, texts), true, true);
  i.changeLanguage('da');
  const isKey = (v) => /^[\w-]+(?:[.:][\w-]+)+$/.test(v || '');
  const walk = (root) => {
    for (const el of root.querySelectorAll('[title],[label],[text]')) {
      for (const a of ['title', 'label', 'text']) {
        const v = el.getAttribute(a);
        if (!isKey(v)) continue;
        if (el.tagName.includes('-')) {
          // komponenten oversætter kun, når værdien ÆNDRES — sæt en anden værdi og så nøglen igen
          el.setAttribute(a, `${v} `);
          el.setAttribute(a, v);
        }
        else el.setAttribute(a, i.t(v));                             // almindeligt element: oversæt direkte
      }
    }
  };
  walk(document);
  localizeExtras();
  setTimeout(localizeExtras, 1500);   // udvidelserne kan først være klar lidt efter
}

/**
 * Det, der ikke går gennem oversættelsen: udvidelsernes knapper (de sætter engelsk tekst direkte), farvefelterne og
 * genvejsteksterne. Teksterne må ikke indeholde "." eller ":" (editoren slår titlen op som en nøgle).
 */
const EXTRA_TITLES = {
  tool_shapelib: ['Former (pile, stjerner, talebobler …)', null],
  tools_polygon: ['Stjerne / polygon', undefined],
  tool_star: ['Stjerne', undefined],
  tool_polygon: ['Polygon (mangekant)', undefined],
  tool_eyedropper: ['Pipette — kopiér farverne fra ét element til et andet', 'I'],
  'ext-panning': ['Flyt udsnittet (tegningen ændres ikke)', 'mellemrum + træk'],
  tool_zoom: [null, 'Z / Alt + musehjul'],
};
function localizeExtras() {
  for (const [id, [title, shortcut]] of Object.entries(EXTRA_TITLES)) {
    const el = document.getElementById(id);
    if (!el) continue;
    if (shortcut === null) el.removeAttribute('shortcut');
    else if (shortcut !== undefined) el.setAttribute('shortcut', shortcut);
    const t = title ?? el.getAttribute('title');
    if (t) { el.setAttribute('title', `${t} `); el.setAttribute('title', t); }
  }
  for (const [id, text] of [['fill_color', 'Fyldfarve — klik for at vælge'], ['stroke_color', 'Stregfarve — klik for at vælge']]) {
    document.getElementById(id)?.shadowRoot?.querySelectorAll('[title]').forEach((n) => n.setAttribute('title', text));
  }
  document.getElementById('zoom')?.setAttribute('title', 'Zoom — vælg et niveau, eller Ctrl + musehjul');
  // Formbiblioteket viser altid "[genvej]" — også uden genvej ("[null]"): sæt den indre tekst direkte
  document.getElementById('tool_shapelib')?.shadowRoot?.querySelectorAll('[title]').forEach((n) => n.setAttribute('title', EXTRA_TITLES.tool_shapelib[0]));
}

/** Buildnummeret værten er bygget som (sat af scripts/copy-svgedit.mjs) — Tegn sammenligner med sit eget. */
const HOST_BUILD = '__HOST_BUILD__';

const scada = createScada({
  canvas: () => editor.svgCanvas,
  loadFromString: (svg) => editor.loadFromString(svg, { noAlert: true }),
  updateCanvas: () => editor.updateCanvas?.(),
  gridHost: () => document.getElementById('svgcanvas'),
  curConfig: () => editor.configObj?.curConfig,
  decorate: () => { localize(); hookContextMenu(); },
});
scada.build = HOST_BUILD;
window.scada = scada;
