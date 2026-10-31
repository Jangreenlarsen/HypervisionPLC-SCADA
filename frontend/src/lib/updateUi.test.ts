import { describe, expect, it } from 'vitest';
import { canInstall, fmtSize, githubOffer, isFinished, progressText, resultOf, type LastRun, type Relation, type Staged, type UpdateStatus } from './updateUi';

const staged = (relation: Staged['relation']): Staged => ({
  version: '0.50.0', build: '0071', sha256: 'a'.repeat(64), size: 1000, files: 10, relation, uploaded_by: 'jan', uploaded_at: 1,
});
const status = (over: Partial<UpdateStatus> = {}): UpdateStatus => ({
  enabled: true, current: { version: '0.49.0', build: '0070' }, staged: staged('newer'), state: 'idle', last: null, busy: false, log: [], ...over,
});
const last = (state: string, ts = 100): LastRun => ({ state, message: 'besked', from: '0.49.0', to: '0.50.0', by: 'jan', ts });

describe('canInstall', () => {
  it('nyere pakke kan installeres', () => expect(canInstall(status(), false)).toBe(true));
  it('ældre pakke kan aldrig installeres', () => {
    expect(canInstall(status({ staged: staged('older') }), true)).toBe(false);
  });
  it('samme version kræver den ekstra bekræftelse', () => {
    expect(canInstall(status({ staged: staged('same') }), false)).toBe(false);
    expect(canInstall(status({ staged: staged('same') }), true)).toBe(true);
  });
  it('ikke aktiveret, optaget, ingen pakke eller ingen status giver nej', () => {
    expect(canInstall(status({ enabled: false }), false)).toBe(false);
    expect(canInstall(status({ busy: true, state: 'applying' }), false)).toBe(false);
    expect(canInstall(status({ staged: null }), false)).toBe(false);
    expect(canInstall(null, false)).toBe(false);
  });
});

describe('resultOf', () => {
  it('succes, tilbagerulning og fejl får hver sin slags besked', () => {
    expect(resultOf(last('done'))).toMatchObject({ kind: 'ok' });
    expect(resultOf(last('rolled_back'))).toMatchObject({ kind: 'warn' });
    expect(resultOf(last('failed'))).toMatchObject({ kind: 'error' });
    expect(resultOf(last('done'))!.text).toContain('0.49.0 → 0.50.0');
  });
  it('en igangværende eller ingen kørsel giver intet resultat', () => {
    expect(resultOf(last('applying'))).toBeNull();
    expect(resultOf(null)).toBeNull();
  });
});

describe('forløbet', () => {
  it('progressText: genstart, optaget, gået i stå og ingenting', () => {
    expect(progressText(null, true)).toContain('genstarter');
    expect(progressText(status({ busy: true, state: 'applying', last: last('applying') }), false)).toBe('besked');
    expect(progressText(status({ state: 'stalled' }), false)).toContain('gået i stå');
    expect(progressText(status(), false)).toBe('');
  });

  it('isFinished kun for en endelig tilstand fra efter vi startede', () => {
    expect(isFinished(status({ last: last('done', 200) }), 100)).toBe(true);
    expect(isFinished(status({ last: last('done', 50) }), 100)).toBe(false);        // en gammel kørsel
    expect(isFinished(status({ last: last('applying', 200), busy: true }), 100)).toBe(false);
    expect(isFinished(status({ last: last('rolled_back', 200) }), 100)).toBe(true);
    expect(isFinished(null, 0)).toBe(false);
  });
});

describe('fmtSize', () => {
  it('kB og MB', () => {
    expect(fmtSize(500)).toBe('1 kB');
    expect(fmtSize(2048)).toBe('2 kB');
    expect(fmtSize(6.5 * 1024 * 1024)).toBe('6.5 MB');
  });
});

describe('githubOffer', () => {
  const rel = (relation: Relation) => ({ tag: 'v9.0.0', name: 'scada-9.0.0-b0009.tar', size: 1, published_at: null, url: null,
    notes: '', version: '9.0.0', build: '0009', relation });
  it('tilbyder hentning af en nyere version og genhentning af samme, men aldrig en ældre', () => {
    expect(githubOffer(null)).toBeNull();
    expect(githubOffer(rel('newer'))).toMatchObject({ canDownload: true, label: 'Hent og klargør' });
    expect(githubOffer(rel('same'))).toMatchObject({ canDownload: true, label: 'Hent igen' });
    expect(githubOffer(rel('older'))?.canDownload).toBe(false);
    expect(githubOffer(rel('unknown'))?.canDownload).toBe(false);
  });
});
