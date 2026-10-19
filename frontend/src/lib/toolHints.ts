// Hjælpelinjen under tegneområdet i Tegn (v0.92.0): hvad det valgte værktøj gør, og hvordan det bruges.
// Nøglerne er SVG-Edits navne på værktøjerne ("mode"). Testet i toolHints.test.ts.

export interface ToolHint { name: string; how: string }

const ESC = 'Esc = tilbage til Vælg';

export const TOOL_HINTS: Record<string, ToolHint> = {
  select: { name: 'Vælg og flyt', how: 'Klik for at vælge · træk for at flytte · træk i et hjørne for at ændre størrelsen · Shift+klik eller en ramme vælger flere · piletaster flytter lidt' },
  zoom: { name: 'Zoom', how: `Træk en ramme om det, du vil se tættere på · Ctrl + musehjul zoomer også · ${ESC}` },
  'ext-panning': { name: 'Flyt udsnittet', how: 'Træk for at flytte det, du ser — tegningen ændres ikke · hold mellemrum nede for at gøre det fra et andet værktøj' },
  fhpath: { name: 'Frihåndstegning', how: `Hold museknappen nede og tegn · ${ESC}` },
  line: { name: 'Streg', how: `Træk fra start til slut · Shift = vandret, lodret eller 45° · ${ESC}` },
  path: { name: 'Sti', how: `Klik for hvert knæk · træk for en kurve · dobbeltklik (eller klik på startpunktet) for at afslutte · ${ESC}` },
  rect: { name: 'Rektangel', how: `Træk for at tegne · Shift = kvadrat · ${ESC}` },
  square: { name: 'Kvadrat', how: `Træk for at tegne · ${ESC}` },
  fhrect: { name: 'Frihånds-rektangel', how: `Tegn omtrent et rektangel med musen — det rettes op · ${ESC}` },
  ellipse: { name: 'Ellipse', how: `Træk for at tegne · Shift = cirkel · ${ESC}` },
  circle: { name: 'Cirkel', how: `Træk fra midten og ud · ${ESC}` },
  fhellipse: { name: 'Frihånds-ellipse', how: `Tegn omtrent en ellipse med musen — den rettes op · ${ESC}` },
  text: { name: 'Tekst', how: `Klik, hvor teksten skal stå, og skriv · dobbeltklik på en tekst for at rette den · ${ESC}` },
  image: { name: 'Billede', how: `Træk et område op til billedet, og angiv billedets adresse · ${ESC}` },
  star: { name: 'Stjerne', how: `Træk fra midten og ud · antal spidser vælges foroven · ${ESC}` },
  polygon: { name: 'Polygon', how: `Træk fra midten og ud · antal sider vælges foroven · ${ESC}` },
  eyedropper: { name: 'Pipette', how: `Vælg først det element, der skal have nye farver · klik så på det element, farverne skal kopieres fra · ${ESC}` },
  shapelib: { name: 'Former', how: `Vælg en form i listen, og træk på tegningen · ${ESC}` },
  pathedit: { name: 'Ret sti', how: 'Træk et punkt for at flytte det · dobbeltklik et punkt for lige/buet · klik uden for stien for at stoppe' },
  textedit: { name: 'Ret tekst', how: 'Skriv for at rette teksten · klik uden for teksten for at stoppe' },
};

/** Hjælpen til et værktøj; ukendte værktøjer får en generel tekst (aldrig tomt). */
export function toolHint(mode: string): ToolHint {
  return TOOL_HINTS[mode] ?? { name: 'Værktøj', how: `Peg på et værktøj til venstre for at se, hvad det gør · ${ESC}` };
}
