// Vippekontakten i guiden (v0.97.2): grebets stilling pr. position (Op / Midt / Ned) → animationerne på grebet og knoppen.
// Grebet er tegnet NED; Drej 180° = OP. "Midt" = grebet peger ud mod beskueren (set forfra): grebet skjules og knoppen
// vises. Ren logik — testet i toggleSwitch.test.ts.
import type { Anim } from './symbolConfig';

const POS = '@pos';   // = symbolConfig.POS (ingen værdi-import: symbolConfig bruger denne fil)

export type LeverDir = 'up' | 'mid' | 'down';
export const DIR_TXT: Record<LeverDir, string> = { up: 'Op', mid: 'Midt (knop)', down: 'Ned' };
const ANGLE: Record<LeverDir, number> = { up: 180, mid: 180, down: 0 };

/** Standard: ON/OFF = Ned, Op; ON/OFF/ON = Op, Midt, Ned; ellers skiftevis Op/Ned (Midt kun med en knop). */
export function defaultDirs(n: number, hasKnop: boolean): LeverDir[] {
  if (n === 2) return ['down', 'up'];
  if (n === 3 && hasKnop) return ['up', 'mid', 'down'];
  return Array.from({ length: n }, (_, j) => (j % 2 ? 'down' : 'up'));
}

const managed = (a: Anim, greb: string, knop: string | null) =>
  (a.part === greb || (knop !== null && a.part === knop)) && (a.type === 'rotate' || a.type === 'visible');

/** Stillingerne, som animationerne giver i dag (fx 90° læses som Midt, når der er en knop). */
export function leverDirs(anims: Anim[], greb: string, knop: string | null, n: number): LeverDir[] {
  const rot = anims.find((a) => a.part === greb && a.type === 'rotate' && a.src === POS && Array.isArray(a.params.angles));
  const grebVis = anims.find((a) => a.part === greb && a.type === 'visible' && a.src === POS && Array.isArray(a.params.set));
  const knopVis = knop ? anims.find((a) => a.part === knop && a.type === 'visible' && a.src === POS && Array.isArray(a.params.set)) : undefined;
  if (!rot) return defaultDirs(n, knop !== null);
  return Array.from({ length: n }, (_, j) => {
    if (knop && (knopVis?.params.set[j] === true || grebVis?.params.set[j] === false)) return 'mid';
    const a = Number(rot.params.angles[j] ?? 0);
    const norm = ((a % 360) + 360) % 360;
    if (knop && norm > 45 && norm < 135) return 'mid';
    return norm >= 90 && norm <= 270 ? 'up' : 'down';
  });
}

/** Styres grebet allerede af netop disse animationer (så tabellen og animationerne passer sammen)? */
export function leverInSync(anims: Anim[], greb: string, knop: string | null, n: number): boolean {
  const want = JSON.stringify(leverAnims(greb, knop, leverDirs(anims, greb, knop, n)).map(({ part, type, src, params }) => ({ part, type, src, params: { ...params, glide_s: undefined } })));
  const have = JSON.stringify(anims.filter((a) => managed(a, greb, knop)).map(({ part, type, src, params }) => ({ part, type, src, params: { ...params, glide_s: undefined } })));
  return want === have;
}

/** Animationerne for stillingerne: Drej pr. position, grebet skjult og knoppen vist i Midt. */
export function leverAnims(greb: string, knop: string | null, dirs: LeverDir[], glide: number | null = null): Anim[] {
  const out: Anim[] = [{ part: greb, type: 'rotate', src: POS, params: { angles: dirs.map((d) => ANGLE[d]), ...(glide !== null ? { glide_s: glide } : {}) }, only: null }];
  if (knop) {
    out.push({ part: greb, type: 'visible', src: POS, params: { set: dirs.map((d) => d !== 'mid') }, only: null });
    out.push({ part: knop, type: 'visible', src: POS, params: { set: dirs.map((d) => d === 'mid') }, only: null });
  }
  return out;
}

/** Erstat grebets og knoppens Drej/Synlig med stillingerne (andre animationer og en valgt hastighed bevares). */
export function applyLever(anims: Anim[], greb: string, knop: string | null, dirs: LeverDir[]): Anim[] {
  const rot = anims.find((a) => a.part === greb && a.type === 'rotate');
  const glide = typeof rot?.params.glide_s === 'number' ? rot.params.glide_s : null;
  return [...leverAnims(greb, knop, dirs, glide), ...anims.filter((a) => !managed(a, greb, knop))];
}
