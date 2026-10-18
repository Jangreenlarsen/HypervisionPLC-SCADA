import { describe, expect, it } from 'vitest';
import { alarmBadge, applyAlarmBadges, markNavClickable, navTarget } from './navSymbols';
import { SYMBOLS } from './symbols';

const mount = (svg: string) => {
  const box = document.createElement('div');
  box.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg">${svg}</svg>`;
  return box;
};

describe('genvejssymboler (v0.75.0)', () => {
  it('kun Alarmer, Trends og Energi godtages som mål — også ved klik på en del', () => {
    const box = mount('<g data-hv-nav="alarms"><rect id="r"/></g><g data-hv-nav="users"><rect id="u"/></g><rect id="x"/>');
    expect(navTarget(box.querySelector('#r'))).toBe('alarms');
    expect(navTarget(box.querySelector('#u'))).toBeNull();      // ikke et tilladt mål
    expect(navTarget(box.querySelector('#x'))).toBeNull();
    expect(navTarget(null)).toBeNull();
  });

  it('alarmmærket: skjult uden alarmer, orange når kvitteret, rødt når ukvitteret; højst 99+', () => {
    expect(alarmBadge({ active: 0, unacked: 0 })).toEqual({ text: '', state: 'none' });
    expect(alarmBadge({ active: 3, unacked: 0 })).toEqual({ text: '3', state: 'active' });
    expect(alarmBadge({ active: 2, unacked: 1 })).toEqual({ text: '2', state: 'unack' });
    expect(alarmBadge({ active: 0, unacked: 1 })).toEqual({ text: '1', state: 'unack' });   // ophørt men ukvitteret
    expect(alarmBadge({ active: 150, unacked: 0 }).text).toBe('99+');
    expect(alarmBadge(null).state).toBe('none');
  });

  it('bibliotekets alarmknap får tal og farve i Overview; genvejene bliver klikbare', () => {
    const svg = SYMBOLS.filter((s) => s.category === 'genveje').map((s) => s.svg).join('');
    const box = mount(svg);
    markNavClickable(box);
    expect([...box.querySelectorAll('[data-hv-nav]')].map((e) => [e.getAttribute('data-hv-nav'), e.classList.contains('hv-clickable')]))
      .toEqual([['alarms', true], ['trends', true], ['energy', true]]);
    // som efter indsættelse i Tegn: id → data-hv-pid
    box.querySelectorAll('[id]').forEach((el) => el.setAttribute('data-hv-pid', el.id));
    applyAlarmBadges(box, { active: 4, unacked: 1 });
    expect(box.querySelector('[data-hv-pid="antal"]')!.textContent).toBe('4');
    expect(box.querySelector('[data-hv-pid="maerke"]')!.classList.contains('hv-nav-badge-unack')).toBe(true);
    applyAlarmBadges(box, { active: 0, unacked: 0 });
    expect((box.querySelector('[data-hv-pid="maerke"]') as SVGElement).style.display).toBe('none');
  });
});
