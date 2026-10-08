// Kopiér SVG-Edit (npm-pakken `svgedit`) + vores værtsside til public/svgedit/,
// så Vite serverer/bygger den som statiske filer på /svgedit/.
// Køres automatisk før `npm run dev` og `npm run build`.
import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

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
cpSync(join(root, 'svgedit-host'), dest, { recursive: true });
console.log('SVG-Edit kopieret til public/svgedit/');
