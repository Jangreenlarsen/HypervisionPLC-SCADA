// Cache-sikring af SVG-Edit-værten (BUGS.md v0.63.1): filerne under /svgedit/ har faste navne, så browseren kan genbruge en
// gammel kopi efter en opdatering. Ved build får værtens egne importer og script-adresser `?v=<build>`, og buildnummeret
// bygges ind i værten (window.scada.build), så Tegn kan opdage en forældet editor.

/** Tilføj `?v=<build>` til relative .js/.css-adresser (`from './x.js'`, `src="./x.js"`, `href="./x.css"`). */
export function versionRefs(text, build) {
  const v = encodeURIComponent(build);
  return text
    .replace(/(\bfrom\s+['"])(\.\/[\w./-]+\.js)(['"])/g, `$1$2?v=${v}$3`)
    .replace(/(\bimport\s+['"])(\.\/[\w./-]+\.js)(['"])/g, `$1$2?v=${v}$3`)
    .replace(/(\b(?:src|href)=["'])(\.\/[\w./-]+\.(?:js|css))(["'])/g, `$1$2?v=${v}$3`);
}

/** Byg buildnummeret ind i stedet for pladsholderen. Fejler højlydt, hvis pladsholderen mangler. */
export function stampBuild(text, build) {
  if (!text.includes('__HOST_BUILD__')) throw new Error('Pladsholderen __HOST_BUILD__ mangler i scada-editor.js');
  return text.replaceAll('__HOST_BUILD__', String(build));
}
