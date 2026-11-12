// Brugermanualen: kapitlerne er markdown-filer i src/manual/ (nummeret i filnavnet giver rækkefølgen).
// Vises med `marked` (MIT) og renses med DOMPurify. Ren logik her — testet i manual.test.ts.
import DOMPurify from 'dompurify';
import { Marked } from 'marked';

export interface Chapter {
  slug: string; title: string; md: string; headings: { id: string; text: string }[];
  group: string; icon: string; blurb: string;   // indeksets gruppe, ikon (NAV_ICON) og korte undertekst
}

/** Indekset (v4.9.0): kapitlerne grupperet efter emne, med ikon og en kort undertekst. Ukendte kapitler havner i "Andet". */
export const GROUPS = ['Kom i gang', 'Drift', 'Opsætning', 'Tegning og symboler', 'System', 'Opslag'];
const META: Record<string, { group: string; icon: string; blurb: string }> = {
  'kom-i-gang': { group: 'Kom i gang', icon: 'manual', blurb: 'Login, menuen, roller og hjælp' },
  drift: { group: 'Drift', icon: 'overview', blurb: 'Overview, betjening og hjælperen' },
  alarmer: { group: 'Drift', icon: 'alarms', blurb: 'Se, kvittér og forklar alarmer' },
  trends: { group: 'Drift', icon: 'trends', blurb: 'Kurver, visninger og analyse' },
  'plcer-og-tags': { group: 'Opsætning', icon: 'plcs', blurb: "PLC'er, tags og alarmgrænser" },
  tegninger: { group: 'Opsætning', icon: 'drawings', blurb: 'Upload, versioner og start-tegning' },
  ugeprogrammer: { group: 'Opsætning', icon: 'schedules', blurb: 'Tidsstyring over ugen' },
  tegn: { group: 'Tegning og symboler', icon: 'draw', blurb: 'Tegne-editoren: værktøjer og bibliotek' },
  forbindelser: { group: 'Tegning og symboler', icon: 'integration', blurb: 'Rør, ledninger og forbindelser' },
  'bindinger-og-animationer': { group: 'Tegning og symboler', icon: 'bindings', blurb: 'Bind elementer til tags' },
  'symboler-og-guiden': { group: 'Tegning og symboler', icon: 'symbols', blurb: 'Guiden i 6 trin og logikblokke' },
  symbolbibliotek: { group: 'Tegning og symboler', icon: 'symboltest', blurb: 'Alle symboler i biblioteket' },
  system: { group: 'System', icon: 'config', blurb: 'Status, brugere, backup, opdatering' },
  eksempler: { group: 'Opslag', icon: 'manual', blurb: 'Opgaver trin for trin' },
  'fejlfinding-og-ordliste': { group: 'Opslag', icon: 'status', blurb: 'Når noget ikke virker, og ord' },
};

/** Kapitlerne i indeksets grupper (tomme grupper udelades), i GROUPS' rækkefølge. */
export function groupChapters(chapters: Chapter[]): { name: string; chapters: Chapter[] }[] {
  const names = [...GROUPS, ...new Set(chapters.map((c) => c.group).filter((g) => !GROUPS.includes(g)))];
  return names.map((name) => ({ name, chapters: chapters.filter((c) => c.group === name) })).filter((g) => g.chapters.length);
}

/** Dansk-venlig kortnavn til anker og adresse: "Hvad rammer det?" → "hvad-rammer-det", æøå → ae/oe/aa. */
export function slugify(text: string): string {
  return text.toLowerCase()
    .replace(/æ/g, 'ae').replace(/ø/g, 'oe').replace(/å/g, 'aa')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'afsnit';
}

/** Teksten uden markdown-tegn, til overskrifter og søgning. */
const plain = (s: string) => s.replace(/[*_`>#|]/g, '').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/\s+/g, ' ').trim();

/** Byg kapitlerne af filerne ({ "../manual/01-kom-i-gang.md": "# …" }), sorteret efter filnavn. */
export function buildChapters(files: Record<string, string>): Chapter[] {
  return Object.entries(files)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([path, raw]) => {
      const md = raw.replace(/\r\n/g, '\n').replace(/^<!--[\s\S]*?-->\n?/, '');
      const name = path.split('/').pop()!.replace(/\.md$/, '').replace(/^\d+-/, '');
      const title = /^#\s+(.+)$/m.exec(md)?.[1].trim() ?? name;
      const seen = new Map<string, number>();
      const headings = [...md.matchAll(/^##\s+(.+)$/gm)].map((m) => {
        const text = plain(m[1]);
        const base = slugify(text);
        const n = (seen.get(base) ?? 0) + 1;
        seen.set(base, n);
        return { id: `m-${n > 1 ? `${base}-${n}` : base}`, text };
      });
      const meta = META[name] ?? { group: 'Andet', icon: 'manual', blurb: '' };
      return { slug: name, title, md, headings, ...meta };
    });
}

/** Markdown → ren HTML. Overskrifter (##, ###) får anker-id'er; alt renses, så intet kan køre script. */
/**
 * Billedets adresse i programmet. I markdown-filerne står billederne med den relative sti i repoet
 * (`../../public/manual/x.png`), så de også vises, når filen læses på GitHub; serveren leverer dem på `/manual/x.png`.
 */
export function manualImageSrc(href: string): string {
  return href.replace(/^(?:\.\.\/)*public\/manual\//, '/manual/');
}

export function renderMarkdown(md: string): string {
  const seen = new Map<string, number>();
  const marked = new Marked({
    gfm: true,
    renderer: {
      // Skærmbilleder: billedet med billedteksten (alt-teksten) under. Klik på et billede åbner det stort (Manual.svelte)
      image({ href, text }) {
        const esc = (v: string) => v.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return `<figure><img src="${esc(manualImageSrc(href))}" alt="${esc(text)}" loading="lazy" decoding="async"><figcaption>${esc(text)}</figcaption></figure>`;
      },
      // Et afsnit der kun er et billede bliver til en figur uden <p> omkring (en <figure> må ikke ligge i et <p>)
      paragraph({ tokens }) {
        const inner = this.parser.parseInline(tokens);
        return tokens.length === 1 && tokens[0].type === 'image' ? inner : `<p>${inner}</p>
`;
      },
      heading({ tokens, depth }) {
        const inner = this.parser.parseInline(tokens);
        const text = plain(tokens.map((t) => ('text' in t ? String(t.text) : t.raw)).join(''));
        const base = slugify(text);
        const n = (seen.get(`${depth}:${base}`) ?? 0) + 1;
        seen.set(`${depth}:${base}`, n);
        const id = depth === 2 ? `m-${n > 1 ? `${base}-${n}` : base}` : `m${depth}-${n > 1 ? `${base}-${n}` : base}`;
        return `<h${depth} id="${id}">${inner}</h${depth}>\n`;
      },
    },
  });
  const html = marked.parse(md, { async: false }) as string;
  return DOMPurify.sanitize(html, { ADD_ATTR: ['id'] });
}

export interface Snippet { text: string; heading: string; anchor: string }
export interface Hit { chapter: Chapter; count: number; snippets: Snippet[] }

/**
 * Søg i alle kapitler (uden hensyn til store/små bogstaver). Tomme søgninger giver ingen resultater. Hvert uddrag ved,
 * hvilket afsnit (## eller ###) det står i, så et klik kan åbne netop det afsnit (ankrene som i renderMarkdown).
 */
export function searchChapters(chapters: Chapter[], query: string): Hit[] {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  const hits: Hit[] = [];
  for (const chapter of chapters) {
    const seen = new Map<string, number>();
    let heading = '';
    let anchor = '';
    const matching: Snippet[] = [];
    for (const raw of chapter.md.split('\n')) {
      const h = /^(#{2,3})\s+(.+)$/.exec(raw);
      if (h) {
        const depth = h[1].length;
        const text = plain(h[2]);
        const base = slugify(text);
        const n = (seen.get(`${depth}:${base}`) ?? 0) + 1;
        seen.set(`${depth}:${base}`, n);
        heading = text;
        anchor = `${depth === 2 ? 'm' : 'm3'}-${n > 1 ? `${base}-${n}` : base}`;
      }
      const line = plain(raw.replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1'));
      if (line && line.toLowerCase().includes(q)) {
        matching.push({ text: line.length > 140 ? `${line.slice(0, 137)}…` : line, heading: h ? '' : heading, anchor });
      }
    }
    if (!matching.length) continue;
    hits.push({ chapter, count: matching.length, snippets: matching.slice(0, 4) });
  }
  return hits.sort((a, b) => b.count - a.count);
}

/** Fremhæv søgeordet i et stykke HTML — kun i tekst, aldrig i tags eller attributter. */
export function highlight(root: HTMLElement, query: string): number {
  const q = query.trim();
  if (q.length < 2) return 0;
  const source = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(source, 'gi');
  const has = new RegExp(source, 'i');   // uden g-flag: .test() med g husker ellers sidste position og springer tekstnoder over
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) if (has.test((n as Text).data)) nodes.push(n as Text);
  let count = 0;
  for (const node of nodes) {
    re.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let last = 0;
    for (const m of node.data.matchAll(re)) {
      frag.append(node.data.slice(last, m.index));
      const mark = document.createElement('mark');
      mark.textContent = m[0];
      frag.append(mark);
      last = m.index! + m[0].length;
      count++;
    }
    frag.append(node.data.slice(last));
    node.replaceWith(frag);
  }
  return count;
}
