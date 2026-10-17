// Cache-sikring af SVG-Edit-værten (scripts/versionHost.mjs).
import { describe, expect, it } from 'vitest';
// @ts-expect-error — ren JS-fil i scripts (ingen typer)
import { stampBuild, versionRefs } from '../../scripts/versionHost.mjs';

describe('versionsadresser for editorværten', () => {
  it('relative importer og script/stylesheet-adresser får ?v=build', () => {
    const js = "import Editor from './Editor.js';\nimport { a } from \"./snap.js\";\nimport './side.js';\nimport x from 'https://cdn/x.js';";
    expect(versionRefs(js, '0093')).toBe("import Editor from './Editor.js?v=0093';\nimport { a } from \"./snap.js?v=0093\";\nimport './side.js?v=0093';\nimport x from 'https://cdn/x.js';");
    const html = '<link rel="stylesheet" href="./scada-editor.css"><script type="module" src="./scada-editor.js"></script><img src="./images/a.svg">';
    expect(versionRefs(html, '0093')).toBe('<link rel="stylesheet" href="./scada-editor.css?v=0093"><script type="module" src="./scada-editor.js?v=0093"></script><img src="./images/a.svg">');
  });
  it('buildnummeret bygges ind; mangler pladsholderen, fejler det', () => {
    expect(stampBuild("const HOST_BUILD = '__HOST_BUILD__';", '0093')).toBe("const HOST_BUILD = '0093';");
    expect(() => stampBuild('intet her', '0093')).toThrow(/__HOST_BUILD__/);
  });
});
