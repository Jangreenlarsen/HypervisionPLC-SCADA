// SPDX-License-Identifier: AGPL-3.0-or-later
// Genererer syms.json (bibliotekssymbolerne til scada_setup.py) fra frontendens symbolbibliotek, så panelets symboler
// er identiske med dem Tegn indsætter. Koeres fra frontend/:
//   npx esbuild ../demo/varme-plc/tools/symgen.ts --bundle --platform=node --format=esm --outfile=../demo/varme-plc/tools/build/symgen.mjs && node ../demo/varme-plc/tools/build/symgen.mjs > ../demo/varme-plc/syms.json
import { SYMBOLS, selectorSymbol, withName } from '../../../frontend/src/lib/symbols';
const pick = (id: string) => SYMBOLS.find((s) => s.id === id)!.svg;
const out: Record<string, string> = {
  trykknap_puls: pick('trykknap_puls'), setpunkt: pick('setpunkt'), vippekontakt: pick('vippekontakt'),
  startstop: pick('startstop'), lampe: pick('lampe'), statusfelt: pick('statusfelt'), vaerdi: pick('vaerdi'),
  omskifter_mode: selectorSymbol(['Fra', 'Auto', 'Sommer', 'Pille', 'Manuel']),
  omskifter_scen: selectorSymbol(['Normal', 'Vinter', 'Sommer', 'Lækage', 'P1-fejl']),
};
console.log(JSON.stringify(out));
