// Tager skærmbillederne til brugermanualen fra en KØRENDE SCADA-server og lægger dem i public/manual/.
// Kør igen, når skærmene ændrer sig:
//   SCADA_URL=https://10.1.1.31 SCADA_USER=claude SCADA_PASS=… npm run manual:screenshots
// Brugeren skal være admin (System-siderne). Scriptet LÆSER kun: det åbner siderne og guiden, men gemmer, skriver og
// sletter aldrig noget. Billederne viser serverens egne data — kør mod en server med pæne eksempeldata.
// Filnavnene bruges i frontend/src/manual/*.md; en test sikrer at alle findes, og at ingen ligger som forældreløse.
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';

const BASE = (process.env.SCADA_URL ?? 'https://10.1.1.31').replace(/\/$/, '');
const USER = process.env.SCADA_USER ?? 'admin';
const PASS = process.env.SCADA_PASS;
const OUT = join(process.cwd(), 'public', 'manual');
const ONLY = process.env.ONLY ? new Set(process.env.ONLY.split(',')) : null;   // fx ONLY=overview,tags
if (!PASS) {
  console.error('Sæt SCADA_PASS (og evt. SCADA_URL, SCADA_USER)');
  process.exit(2);
}
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1180, height: 760 }, deviceScaleFactor: 1, locale: 'da-DK', timezoneId: 'Europe/Copenhagen' });
const login = await ctx.request.post(`${BASE}/api/auth/login`, { data: { username: USER, password: PASS } });
if (!login.ok()) {
  console.error(`Login fejlede (${login.status()}) — tjek bruger og adgangskode`);
  process.exit(2);
}
const api = async (path) => (await ctx.request.get(`${BASE}${path}`)).json();
const drawings = await api('/api/drawings');
const tags = await api('/api/tags');
const startDrawing = drawings.find((d) => d.start)?.id ?? drawings[0]?.id;
const trendTags = tags.filter((t) => t.trend).slice(0, 3).map((t) => t.name);

const page = await ctx.newPage();
await page.addInitScript((sel) => { try { localStorage.setItem('trend.selected', JSON.stringify(sel)); } catch { /* ingen localStorage */ } }, trendTags);

const results = [];
const settle = (ms = 1200) => page.waitForTimeout(ms);
const go = async (hash, ready) => {
  await page.goto(`${BASE}/#${hash}`);
  await page.reload();               // hash-skift alene genindlæser ikke altid siden
  if (ready) await page.waitForSelector(ready, { timeout: 20000 });
  await settle();
};
const shot = async (name, fn, opts = {}) => {
  if (ONLY && !ONLY.has(name)) return;
  try {
    await fn();
    const path = join(OUT, `${name}.png`);
    if (opts.top) {   // toppen af et højt element (fx symbolpaletten): højst opts.top.height pixel
      await page.evaluate(() => window.scrollTo(0, 0));
      const box = await page.locator(opts.top.locator).first().boundingBox();
      await page.screenshot({ path, clip: { x: box.x, y: box.y, width: box.width, height: Math.min(box.height, opts.top.height) }, fullPage: true });
    } else if (opts.locator) await page.locator(opts.locator).first().screenshot({ path });
    else await page.screenshot({ path, clip: opts.clip });
    results.push([name, 'ok']);
    console.log(`ok   ${name}`);
  } catch (e) {
    results.push([name, `FEJL: ${e.message.split('\n')[0]}`]);
    console.log(`FEJL ${name}: ${e.message.split('\n')[0]}`);
  }
};
const hover = async (text) => { await page.locator('.menu', { hasText: text }).first().hover(); await page.waitForTimeout(350); };
const openGuide = async (drawing, element) => {
  await go(`editor/${drawing}/${element}`, '.symbol-cfg');
  await page.getByRole('button', { name: /Opsæt symbol|Ret symbol/ }).first().click();
  await page.waitForSelector('.guide');
  await settle(500);
};
const guideStep = async (n) => { await page.locator('.guide .steps button', { hasText: new RegExp(`^${n}\\.`) }).click(); await settle(400); };
const GUIDE = '.guide';
const valve = drawings.find((d) => d.id === 'test-ventil3') ? 'test-ventil3' : null;

// ------------------------------------------------------------------ menu
await shot('menu-opsaetning', async () => { await go('overview', '.menubar'); await hover('Opsætning'); }, { clip: { x: 0, y: 0, width: 640, height: 300 } });
await shot('menu-bruger', async () => { await go('overview', '.menubar'); await hover('Bruger'); }, { clip: { x: 640, y: 0, width: 540, height: 280 } });
// ------------------------------------------------------------------ drift
await shot('overview', async () => { await go(`overview/${startDrawing}`, 'svg'); await page.mouse.move(600, 740); await settle(2500); });
await shot('alarmer', async () => { await go('alarms', 'text=Aktive'); });
await shot('alarmer-historik', async () => { await go('alarms', 'text=Aktive'); await page.getByRole('button', { name: 'Historik' }).click(); await settle(); });
await shot('trends', async () => { await go('trends', 'text=15 min'); await page.getByRole('button', { name: '1 time' }).click(); await settle(2500); });
await shot('energi', async () => { await go('energy', 'h1, h2, h3'); await settle(1500); });
// ------------------------------------------------------------------ PLC'er og tags
await shot('plcer', async () => { await go('plcs', 'text=Tilføj PLC'); });
await shot('tags', async () => { await go('tags', 'text=Nyt tag'); });
await shot('tag-redigeer', async () => {
  await go('tags', 'text=Nyt tag');
  await page.locator('tbody tr', { hasText: tags.find((t) => t.writable)?.name ?? '' }).first().getByRole('button', { name: 'Redigér' }).click();
  await page.waitForSelector('.edit-panel');
  // panelet ruller normalt internt med fast knaplinje — fold det helt ud, så alle felter (alarmer, energi) kan ses
  await page.addStyleTag({ content: '.edit-panel { max-height: none !important; overflow: visible !important; } .edit-panel .actions, .edit-panel [class*="sticky"] { position: static !important; }' });
  await settle(500);
}, { locator: '.edit-panel' });
// ------------------------------------------------------------------ tegninger og Tegn
await shot('tegninger', async () => { await go('drawings', 'text=Upload tegning'); });
await shot('tegninger-versioner', async () => { await go('drawings', 'text=Upload tegning'); await page.getByRole('button', { name: 'Versioner' }).first().click(); await settle(800); await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight)); await settle(300); });
await shot('tegn', async () => { await go(`draw/${startDrawing}`, 'iframe'); await settle(3500); });
await shot('tegn-gitter', async () => {
  await go(`draw/${startDrawing}`, 'iframe');
  await settle(3500);
  await page.getByLabel('Vis gitter').check();     // kun visning i browseren (localStorage) — gemmer intet på serveren
  await page.getByLabel('Fang til gitter').check();
  await page.getByLabel('Fang til objekter').check();
  await settle(800);
}, { clip: { x: 0, y: 84, width: 1180, height: 480 } });
await shot('tegn-symboler', async () => {
  await go(`draw/${startDrawing}`, 'iframe');
  await settle(3000);
  await settle(500);
}, { top: { locator: 'aside', height: 760 } });
// ------------------------------------------------------------------ Bindinger
await shot('bindinger', async () => {
  await go(`editor/${startDrawing}`, '.editor');
  await page.locator('aside li button', { hasText: /bundet/ }).first().click();
  await settle(800);
});
// ------------------------------------------------------------------ guiden (læser kun — der trykkes aldrig Gem)
if (valve) {
  await shot('bindinger-symbol', async () => { await go(`editor/${valve}/V3`, '.symbol-cfg'); await settle(600); });
  await shot('guide-1', async () => { await openGuide(valve, 'V3'); await guideStep(1); }, { locator: GUIDE });
  await shot('guide-2', async () => { await guideStep(2); }, { locator: GUIDE });
  await shot('guide-3', async () => { await guideStep(3); }, { locator: GUIDE });
  await shot('guide-4', async () => { await guideStep(4); }, { locator: GUIDE });
  await shot('guide-hurtig', async () => { await guideStep(4); await page.locator('.guide .notice', { hasText: 'Hurtig opsætning' }).scrollIntoViewIfNeeded(); }, { locator: `${GUIDE} .notice` });
  await shot('guide-logik', async () => {
    await guideStep(4);
    await page.getByRole('button', { name: '+ Logikblok' }).click();
    await settle(500);
    await page.locator('.guide .logic').first().scrollIntoViewIfNeeded();
  }, { locator: GUIDE });
  await shot('guide-5', async () => { await guideStep(5); }, { locator: GUIDE });
  await shot('guide-6', async () => { await guideStep(6); await settle(1500); }, { locator: GUIDE });
}
// ------------------------------------------------------------------ ugeprogrammer og System
await shot('ugeprogrammer', async () => { await go('schedules', 'text=Nyt ugeprogram'); });
await shot('log', async () => { await go('audit', 'text=Log'); await settle(1000); });
await shot('brugere', async () => { await go('users', 'text=Ny bruger'); });
await shot('backup', async () => { await go('backup', 'text=Hent backup'); });
await shot('opdatering', async () => { await go('update', 'text=Installeret version'); });

await browser.close();
const failed = results.filter(([, r]) => r !== 'ok');
console.log(`\n${results.length - failed.length} af ${results.length} billeder taget → ${OUT}`);
process.exit(failed.length ? 1 : 0);
