// Kopiér SVG-Edit (npm-pakken `svgedit`) + vores værtsside til public/svgedit/,
// så Vite serverer/bygger den som statiske filer på /svgedit/.
// Køres automatisk før `npm run dev` og `npm run build`.
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { stampBuild, versionRefs } from './versionHost.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = join(root, 'node_modules', 'svgedit', 'dist', 'editor');
const dest = join(root, 'public', 'svgedit');

if (!existsSync(src)) {
  console.error('svgedit er ikke installeret — kør `npm install`');
  process.exit(1);
}
rmSync(dest, { recursive: true, force: true });
mkdirSync(dest, { recursive: true });
const skip = /(^tests$|\.map$|^iife-|^xdomain-|^index\.html$|^browser-not-supported)/;
cpSync(src, dest, {
  recursive: true,
  filter: (path) => {
    const name = path.split(/[\\/]/).pop();
    return path === src || !skip.test(name) || path.includes(join('extensions', ''));
  },
});
// Udvidelser vi ikke bruger (gemmer i browseren / åbner filer udenom SCADA'en)
for (const ext of ['ext-storage', 'ext-opensave', 'ext-helloworld']) {
  rmSync(join(dest, 'extensions', ext), { recursive: true, force: true });
}
// Rotation: SVG-Edit er som standard fri og snapper til 45° med Shift. I Tegn skal den snappe til 15°-trin, og Shift giver fri
// rotation (som man kender det fra andre tegneprogrammer). Rettelsen er en tekstudskiftning i den medfølgende (minificerede)
// editor-fil — passer teksten ikke (ny SVG-Edit-version), stopper kopieringen, så rotationen ikke stille mister sin opførsel.
const editorJs = join(dest, 'Editor.js');
const original = readFileSync(editorJs, 'utf-8');
const ROTATE_OLD = 'q.getCurConfig().gridSnapping && (f = jg(f)), e.shiftKey && (f = Math.round(f / 45) * 45)';
const ROTATE_NEW = 'e.shiftKey || (f = Math.round(f / 15) * 15)';
if (!original.includes(ROTATE_OLD)) {
  console.error('Kunne ikke finde rotationskoden i SVG-Edit (ny version?) — ret ROTATE_OLD i scripts/copy-svgedit.mjs');
  process.exit(1);
}
writeFileSync(editorJs, original.replace(ROTATE_OLD, ROTATE_NEW));
cpSync(join(root, 'svgedit-host'), dest, { recursive: true });
// Cache-sikring (BUGS.md v0.63.1): værtens filer får ?v=<build> i deres adresser, og buildnummeret bygges ind i værten
const { build } = JSON.parse(readFileSync(join(root, '..', 'version.json'), 'utf-8'));
for (const name of readdirSync(join(root, 'svgedit-host'))) {
  if (!/\.(js|html)$/.test(name)) continue;
  const file = join(dest, name);
  let text = versionRefs(readFileSync(file, 'utf-8'), build);
  if (name === 'scada-editor.js') text = stampBuild(text, build);
  writeFileSync(file, text);
}
console.log(`SVG-Edit kopieret til public/svgedit/ (vært build ${build})`);
