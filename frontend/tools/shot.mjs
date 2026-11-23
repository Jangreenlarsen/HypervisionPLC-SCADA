// Visuel verifikation (CLAUDE.md regel 9): tag ét skærmbillede af en side i SCADA-UI'et med Playwright.
//
//   node tools/shot.mjs <rute> <ud.png> [--base=URL] [--width=1600] [--height=1000] [--wait=3000] [--selector=CSS] [--text]
//
//   <rute>   hash-rute, fx "#/overview/varme", eller en fuld URL
//   --base   standard http://127.0.0.1:8000 (SCADA_BASE)
//   --selector  vent på og fotografér kun dette element
//   --text   skriv også sidens tekst (første 1500 tegn) til <ud>.txt
// Login (valgfrit): SCADA_USER og SCADA_PASS som miljøvariabler — aldrig på kommandolinjen (CLAUDE.md regel 3).
// Scriptet afviser alle skrivende /api-kald (kun login slipper igennem), så det ikke kan ændre PLC'en eller serverens data.
// Smal visning: Edge/Chromium headless har en minimumsbredde; test mobil ved ca. 500 px.
import { chromium } from 'playwright';
import fs from 'fs';

const pos = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const opt = Object.fromEntries(process.argv.slice(2).filter((a) => a.startsWith('--')).map((a) => {
  const [k, v] = a.slice(2).split('='); return [k, v ?? true];
}));
const [route, out] = pos;
if (!route || !out) { console.error('Brug: node tools/shot.mjs <rute> <ud.png> [--base= --width= --height= --wait= --selector= --text]'); process.exit(1); }

const base = String(opt.base || process.env.SCADA_BASE || 'http://127.0.0.1:8000').replace(/\/$/, '');
const url = /^https?:\/\//.test(route) ? route : `${base}/${route.startsWith('#') ? route : '#' + route}`;
const browser = await chromium.launch();
try {
  const ctx = await browser.newContext({
    viewport: { width: Number(opt.width || 1600), height: Number(opt.height || 1000) },
    locale: 'da-DK', ignoreHTTPSErrors: true,
  });
  await ctx.route('**/api/**', (r) => {
    const q = r.request();
    if (q.method() === 'GET' || q.url().endsWith('/api/auth/login')) return r.continue();
    return r.abort('blockedbyclient');
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
  if (process.env.SCADA_USER && process.env.SCADA_PASS) {
    await page.goto(`${base}/api/health`);
    const st = await page.evaluate(async ([u, p]) => (await fetch('/api/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: u, password: p }),
    })).status, [process.env.SCADA_USER, process.env.SCADA_PASS]);
    console.log('login', st);
  }
  await page.goto(url, { waitUntil: 'networkidle' });
  if (opt.selector) await page.waitForSelector(String(opt.selector), { timeout: 15000 });
  await page.waitForTimeout(Number(opt.wait || 3000));
  if (opt.selector) await page.locator(String(opt.selector)).first().screenshot({ path: out });
  else await page.screenshot({ path: out });
  if (opt.text) fs.writeFileSync(out + '.txt', await page.evaluate(() => document.body.innerText.slice(0, 1500)), 'utf-8');
  console.log(`Gemt ${out}${errors.length ? ` — ${errors.length} sidefejl:\n` + errors.join('\n') : ''}`);
} finally {
  await browser.close();
}
