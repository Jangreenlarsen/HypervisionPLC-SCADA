// @ts-nocheck — kontrol af filer på disken (node)
// Rotation i Tegn: 15°-trin, og Shift giver fri rotation. Det er en tekstrettelse i SVG-Edit's editor-fil lavet af
// scripts/copy-svgedit.mjs ved `npm run dev`/`build`; denne test sikrer at den er med i den kopi der leveres.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const editor = join(process.cwd(), 'public', 'svgedit', 'Editor.js');
const host = join(process.cwd(), 'public', 'svgedit', 'scada-editor.js');

describe.skipIf(!existsSync(editor))('SVG-Edit-kopien (public/svgedit)', () => {
  it('rotation snapper til 15° uden Shift og er fri med Shift', () => {
    const js = readFileSync(editor, 'utf-8');
    expect(js).toContain('e.shiftKey || (f = Math.round(f / 15) * 15)');
    expect(js).not.toContain('e.shiftKey && (f = Math.round(f / 45) * 45)');     // SVG-Edits egen 45°-snap med Shift er erstattet
  });

  it('værtssiden bruger vores gitter og fang-funktioner, ikke SVG-Edits eget gitter-udvidelse', () => {
    const js = readFileSync(host, 'utf-8');
    expect(js).toMatch(/from '\.\/scada-core\.js\?v=\d+'/);   // versioneret adresse (cache-sikring, v0.63.2)
    const core = readFileSync(join(process.cwd(), 'public', 'svgedit', 'scada-core.js'), 'utf-8');   // vores logik (delt med ny editor)
    expect(core).toMatch(/from '\.\/snap\.js\?v=\d+'/);
    expect(core).toContain('setGuides');
    expect(js).not.toContain("'ext-grid'");
    expect(existsSync(join(process.cwd(), 'public', 'svgedit', 'snap.js'))).toBe(true);
  });

  it('drejegrebets forbindelsesstreg tager ikke imod musen (ellers flyttede det øverste midtergreb elementet)', () => {
    const css = readFileSync(join(process.cwd(), 'public', 'svgedit', 'scada-editor.css'), 'utf-8');
    expect(css).toMatch(/#selectorGrip_rotateconnector\s*\{\s*pointer-events:\s*none;?\s*\}/);
  });
});
