import { describe, expect, it } from 'vitest';
import { alarmMarks } from './alarmMark';

describe('alarmmarkering kun på værdivisninger (v0.87.0)', () => {
  it('Værdi og Niveau markeres; animationer der blot bruger tagget gør ikke', () => {
    const b = [
      { element: 'kedel_tekst', tag: 'T', anim: 'text' as const },
      { element: 'ramme', tag: 'T', anim: 'flicker' as const },
      { element: 'pil', tag: 'T', anim: 'scale' as const },
      { element: 'tank', tag: 'T', anim: 'level' as const },
      { element: 'andet', tag: 'U', anim: 'text' as const },
    ];
    expect(alarmMarks(b, new Map([['T', 'unack']]))).toEqual(new Map([['kedel_tekst', 'unack'], ['tank', 'unack']]));
  });
  it('flere tags på samme element: ukvitteret vinder', () => {
    const b = [{ element: 'e', tag: 'A', anim: 'text' as const }, { element: 'e', tag: 'B', anim: 'text' as const }];
    expect(alarmMarks(b, new Map([['A', 'unack'], ['B', 'ack']])).get('e')).toBe('unack');
    expect(alarmMarks([...b].reverse(), new Map([['A', 'unack'], ['B', 'ack']])).get('e')).toBe('unack');
    expect(alarmMarks(b, new Map([['B', 'ack']])).get('e')).toBe('ack');
  });
});
