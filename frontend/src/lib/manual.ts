// Brugermanualen: kapitlerne er markdown-filer i src/manual/ (nummeret i filnavnet giver rækkefølgen).
// Vises med `marked` (MIT) og renses med DOMPurify. Ren logik her — testet i manual.test.ts.
import DOMPurify from 'dompurify';
import { Marked } from 'marked';

export interface Chapter { slug: string; title: string; md: string; headings: { id: string; text: string }[] }

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
      return { slug: name, title, md, headings };
    });
}

/** Markdown → ren HTML. Overskrifter (##, ###) får anker-id'er; alt renses, så intet kan køre script. */
export function renderMarkdown(md: string): string {
  const seen = new Map<string, number>();
  const marked = new Marked({
    gfm: true,
    renderer: {
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

export interface Hit { chapter: Chapter; count: number; snippets: string[] }

/** Søg i alle kapitler (uden hensyn til store/små bogstaver). Tomme søgninger giver ingen resultater. */
export function searchChapters(chapters: Chapter[], query: string): Hit[] {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  const hits: Hit[] = [];
  for (const chapter of chapters) {
    const lines = chapter.md.split('\n').map(plain).filter(Boolean);
    const matching = lines.filter((l) => l.toLowerCase().includes(q));
    if (!matching.length) continue;
    hits.push({ chapter, count: matching.length, snippets: matching.slice(0, 3).map((l) => (l.length > 140 ? `${l.slice(0, 137)}…` : l)) });
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
