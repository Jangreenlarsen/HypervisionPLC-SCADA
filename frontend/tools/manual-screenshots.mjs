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

// Sikring: browseren må kun LÆSE. Alt andet end GET mod API'et afvises, før det når serveren (guidens løbende kontrol,
// /preview, ændrer intet og slipper igennem) — så et klik på et symbol aldrig kan skrive til en PLC.
await ctx.route('**/api/**', (r) => {
  const q = r.request();
  return q.method() === 'GET' || q.method() === 'HEAD' || q.url().endsWith('/preview') ? r.continue() : r.abort();
});
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
    } else if (opts.locator && opts.pad) {   // elementet med luft omkring (fx ét symbol på tegningen)
      const b = await page.locator(opts.locator).first().boundingBox();
      const x = Math.max(0, b.x - opts.pad), y = Math.max(0, b.y - opts.pad);
      await page.screenshot({ path, clip: { x, y, width: b.width + 2 * opts.pad, height: b.height + 2 * opts.pad } });
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
await shot('tegn-erstat', async () => {
  // Opløs den store gruppe i browseren (gemmer ikke), vælg en pille-etiket og åbn "Erstat med symbol" med Statusfelt valgt
  await go(`draw/${startDrawing}`, 'iframe');
  await settle(3500);
  const f = page.frames().find((x) => x.url().includes('scada-editor'));
  await f.evaluate(() => {
    const big = [...document.querySelectorAll('#svgcontent g.layer > g')].find((g) => g.children.length > 20);
    if (big) { window.scada.selectById(big.id); window.scada.ungroupSelected(); }
    const pill = document.querySelector('#svgcontent g.layer > rect[rx]');
    if (pill) window.scada.selectById(pill.id);
  });
  await settle(500);
  await page.getByRole('button', { name: /Erstat med symbol/ }).click();
  await page.waitForSelector('.dlg');
  await page.locator('.dlg .sym', { hasText: 'Statusfelt' }).first().click();
  await settle(500);
}, { locator: '.dlg' });
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

// ------------------------------------------------------------------ flere billeder (v2.7.0)
const cfgOf = async (d, el) => (await api(`/api/drawings/${d}/symbols/${el}/config`).catch(() => ({}))).config ?? null;
const lockedSel = valve && (await cfgOf(valve, 'omskifter3_2'))?.lock?.positions?.some(Boolean) ? 'omskifter3_2' : null;
const stepSel = valve && (await cfgOf(valve, 'omskifter3'))?.op === 'positions' ? 'omskifter3' : null;
const extTag = tags.find((t) => /:(rtu|mbx):/.test(t.source))?.name;
const editTag = async (name) => {
  await go('tags', 'text=Nyt tag');
  await page.locator('tbody tr', { hasText: name }).first().getByRole('button', { name: 'Redigér' }).click();
  await page.waitForSelector('.edit-panel');
  await page.addStyleTag({ content: '.edit-panel { max-height: none !important; overflow: visible !important; } .edit-panel .actions, .edit-panel [class*="sticky"] { position: static !important; }' });
  await settle(500);
};
// 01 — login (egen kontekst uden cookie)
if (!ONLY || ONLY.has('login')) {
  const anon = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1180, height: 760 }, locale: 'da-DK' });
  const p2 = await anon.newPage();
  try {
    await p2.goto(`${BASE}/`);
    await p2.waitForSelector('input[type=password]', { timeout: 20000 });
    await p2.waitForTimeout(1200);
    await p2.screenshot({ path: join(OUT, 'login.png') });
    results.push(['login', 'ok']);
    console.log('ok   login');
  } catch (e) {
    results.push(['login', `FEJL: ${e.message.split('\n')[0]}`]);
    console.log(`FEJL login: ${e.message.split('\n')[0]}`);
  }
  await anon.close();
}
// 02 — drift: betjeningsdialogen for en omskifter med nøglelås (skrivninger er blokeret ovenfor)
if (lockedSel) {
  await shot('drift-dialog', async () => {
    await go(`overview/${valve}`, 'svg');
    await settle(2500);
    const b = await page.locator(`#${lockedSel}`).first().boundingBox();
    // Den synlige del af symbolet; højre for midten = næste position, venstre = forrige (en låst position åbner dialogen med koden)
    const cx = b.x + b.width / 2, cy = Math.min(Math.max(b.y + b.height / 2, 150), 700);
    const right = Math.min(b.x + b.width - 10, 1170), left = Math.max(b.x + 10, 10);
    for (const x of [(cx + right) / 2, (cx + left) / 2]) {
      await page.mouse.click(x, cy);
      await settle(1000);
      if (await page.locator('.dialog').count()) break;
    }
    await page.waitForSelector('.dialog', { timeout: 5000 });
    await settle(600);
  }, { locator: '.dialog' });
}
await shot('trends-analyse', async () => {
  await go('trends', 'text=15 min');
  await page.getByRole('button', { name: '1 time' }).click();
  await page.getByLabel('Analysér data').check();   // kun visning i browseren
  await settle(2500);
});
// 03 — PLC'er og tags
await shot('plc-ny', async () => { await go('plcs', 'text=Tilføj PLC'); }, { locator: '.panel:has(h2:text-is("Tilføj PLC"))' });
if (extTag) await shot('tag-ekstern', async () => { await editTag(extTag); }, { locator: '.edit-panel' });
// 04 — tegninger og Tegn
await shot('tegninger-upload', async () => { await go('drawings', 'text=Upload tegning'); }, { locator: '.panel:has(h2:text-is("Upload tegning"))' });
await shot('tegn-hjaelp', async () => {
  await go(`draw/${startDrawing}`, 'iframe');
  await settle(3000);
  await page.getByLabel('Skalér symmetrisk').check();
  await settle(300);
}, { locator: 'label:has-text("Skalér symmetrisk") >> xpath=..' });
await shot('tegn-grupper', async () => { await go(`draw/${startDrawing}`, 'iframe'); await settle(3000); }, { locator: 'details:has(> summary:text-is("Grupper"))' });
for (const [id, label] of [['betjening', 'Betjening'], ['proces', 'Proces og visning'], ['vvs', 'Rør og VVS'], ['el', 'Elektrisk'], ['sol', 'Solcelleanlæg'], ['genveje', 'Genveje']]) {
  await shot(`bibliotek-${id}`, async () => {
    if (!page.url().includes('#draw/')) {
      await go(`draw/${startDrawing}`, 'iframe');
      await settle(3000);
      // sidepanelet ruller normalt for sig selv — fold det ud, så hele kategorien kan fotograferes
      await page.addStyleTag({ content: 'aside, .sym-panel { max-height: none !important; height: auto !important; overflow: visible !important; }' });
      await settle(300);
    }
    await page.locator(`details:has(> summary:has-text("${label}")) .symbols`).first().scrollIntoViewIfNeeded();
  }, { locator: `details:has(> summary:has-text("${label}")) .symbols` });
}
// 06 — guiden (der trykkes aldrig Gem; Gem ville også blive blokeret)
if (valve) {
  await shot('guide-former', async () => {
    await openGuide(valve, 'V3');
    await guideStep(1);
    await page.getByLabel(/Vis alle betjeningsformer/).check().catch(() => {});
    await settle(400);
  }, { locator: GUIDE });
}
if (stepSel) {
  await shot('guide-kontaktplan', async () => { await openGuide(valve, stepSel); await guideStep(3); await settle(600); }, { locator: GUIDE });
  await shot('guide-animation', async () => {
    await guideStep(4);
    await page.locator('.guide .anim:not(.logic)').first().scrollIntoViewIfNeeded();
    await settle(400);
  }, { locator: '.guide .anim:not(.logic)' });
  await shot('guide-interaktiv', async () => { await guideStep(5); await settle(400); }, { locator: GUIDE });
}
if (lockedSel) await shot('guide-noeglelaas', async () => { await openGuide(valve, lockedSel); await guideStep(5); await settle(500); }, { locator: GUIDE });
await shot('symboltest', async () => {
  await go('symboltest', '.tile');
  await page.locator('.tile', { hasText: 'Omskifter Hånd/0/Auto' }).first().click();
  await settle(1200);
});
// 09 — System
await shot('konfiguration', async () => { await go('config', 'text=Konfiguration'); await settle(800); });
await shot('netvaerk', async () => {
  await go('config', 'text=Netværk');
  await page.locator('h3', { hasText: 'Netværk' }).scrollIntoViewIfNeeded();
  await settle(500);
}, { locator: '.panel:has(h3:text-is("Netværk"))' });

await browser.close();
const failed = results.filter(([, r]) => r !== 'ok');
console.log(`\n${results.length - failed.length} af ${results.length} billeder taget → ${OUT}`);
process.exit(failed.length ? 1 : 0);
