// Simpel matematik på en tekst-binding: fx "x / 10" så registerværdien 128 vises som 12,8.
// Egen lille parser — ingen eval. Samme grammatik som backendens validering (backend/app/services/expression.py).
//
//   tal        1   2.5   2,5        (decimalkomma eller -punktum)
//   værdien    x   værdi   parameter  (tagets værdi efter skala/offset; store/små bogstaver er ens)
//   regnearter + - * / %  (rest)  og parenteser; fortegn: -x
//   funktioner abs(x)  round(x)  floor(x)  ceil(x)  sqrt(x)  min(a; b; …)  max(a; b; …)
//              — flere værdier adskilles med ; (komma er decimalkomma)
//
// Division med 0 og andre ugyldige resultater giver "ingen værdi" (vises som —).

export const MAX_EXPRESSION_LENGTH = 80;
const VARS = new Set(['x', 'værdi', 'vaerdi', 'parameter']);
const FUNCS: Record<string, { min: number; max: number; fn: (a: number[]) => number }> = {
  abs: { min: 1, max: 1, fn: (a) => Math.abs(a[0]) },
  round: { min: 1, max: 1, fn: (a) => Math.sign(a[0]) * Math.floor(Math.abs(a[0]) + 0.5) }, // .5 rundes væk fra 0
  floor: { min: 1, max: 1, fn: (a) => Math.floor(a[0]) },
  ceil: { min: 1, max: 1, fn: (a) => Math.ceil(a[0]) },
  sqrt: { min: 1, max: 1, fn: (a) => Math.sqrt(a[0]) },
  min: { min: 2, max: 8, fn: (a) => Math.min(...a) },
  max: { min: 2, max: 8, fn: (a) => Math.max(...a) },
};

type Tok = { t: 'num'; v: number } | { t: 'id'; v: string } | { t: 'op'; v: string };
export type Compiled = (x: number) => number;

function tokenize(src: string): Tok[] {
  const out: Tok[] = [];
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (/\s/.test(c)) {
      i++;
      continue;
    }
    const num = /^(\d+([.,]\d+)?|[.,]\d+)/.exec(src.slice(i));
    if (num) {
      out.push({ t: 'num', v: Number(num[0].replace(',', '.')) });
      i += num[0].length;
      continue;
    }
    const id = /^[A-Za-zÆØÅæøå_][A-Za-zÆØÅæøå_0-9]*/.exec(src.slice(i));
    if (id) {
      out.push({ t: 'id', v: id[0].toLowerCase() });
      i += id[0].length;
      continue;
    }
    if ('+-*/%();'.includes(c)) {
      out.push({ t: 'op', v: c });
      i++;
      continue;
    }
    throw new Error(`Uventet tegn "${c}"`);
  }
  return out;
}

/** Oversæt et udtryk til en funktion. Kaster Error med dansk tekst ved ugyldigt udtryk. */
export function compileExpression(src: string): Compiled {
  if (src.length > MAX_EXPRESSION_LENGTH) throw new Error(`For langt (højst ${MAX_EXPRESSION_LENGTH} tegn)`);
  const toks = tokenize(src);
  if (!toks.length) throw new Error('Tomt udtryk');
  let pos = 0;
  const peek = () => toks[pos];
  const isOp = (v: string) => peek()?.t === 'op' && peek().v === v;
  const eat = (v: string) => {
    if (!isOp(v)) throw new Error(v === ')' ? 'Manglende ")"' : `Forventede "${v}"`);
    pos++;
  };

  function expr(): Compiled {
    let left = term();
    while (isOp('+') || isOp('-')) {
      const op = toks[pos++].v;
      const l = left, r = term();
      left = op === '+' ? (x) => l(x) + r(x) : (x) => l(x) - r(x);
    }
    return left;
  }
  function term(): Compiled {
    let left = unary();
    while (isOp('*') || isOp('/') || isOp('%')) {
      const op = toks[pos++].v;
      const l = left, r = unary();
      left = op === '*' ? (x) => l(x) * r(x) : op === '/' ? (x) => l(x) / r(x) : (x) => l(x) % r(x);
    }
    return left;
  }
  function unary(): Compiled {
    if (isOp('-')) {
      pos++;
      const inner = unary();
      return (x) => -inner(x);
    }
    if (isOp('+')) {
      pos++;
      return unary();
    }
    return primary();
  }
  function primary(): Compiled {
    const t = peek();
    if (!t) throw new Error('Udtrykket slutter for tidligt');
    pos++;
    if (t.t === 'num') {
      const v = t.v;
      return () => v;
    }
    if (t.t === 'id') {
      if (isOp('(')) {
        const spec = FUNCS[t.v];
        if (!spec) throw new Error(`Ukendt funktion "${t.v}" (brug ${Object.keys(FUNCS).join(', ')})`);
        pos++;
        const args: Compiled[] = [expr()];
        while (isOp(';')) {
          pos++;
          args.push(expr());
        }
        eat(')');
        if (args.length < spec.min || args.length > spec.max) {
          throw new Error(`${t.v} tager ${spec.min === spec.max ? spec.min : `${spec.min}-${spec.max}`} værdi${spec.max > 1 ? 'er' : ''}${spec.max > 1 ? ' (adskilt med ;)' : ''}`);
        }
        return (x) => spec.fn(args.map((a) => a(x)));
      }
      if (!VARS.has(t.v)) throw new Error(`Ukendt navn "${t.v}" — brug x (tagets værdi)`);
      return (x) => x;
    }
    if (t.v === '(') {
      const inner = expr();
      eat(')');
      return inner;
    }
    throw new Error(`Uventet "${t.v}"`);
  }

  const result = expr();
  if (pos < toks.length) {
    const t = toks[pos];
    throw new Error(`Uventet "${t.v}" — mangler der et regnetegn (+ - * /)?`);
  }
  return result;
}

const cache = new Map<string, Compiled | Error>();

/** Beregn udtrykket for værdien x. null = ugyldigt udtryk eller resultat der ikke er et tal (fx division med 0). */
export function evalExpression(src: string, x: number): number | null {
  let c = cache.get(src);
  if (c === undefined) {
    try {
      c = compileExpression(src);
    } catch (e) {
      c = e as Error;
    }
    cache.set(src, c);
  }
  if (c instanceof Error) return null;
  const v = c(x);
  return Number.isFinite(v) ? v : null;
}

/** Fejltekst til brugeren ('' hvis udtrykket er tomt eller gyldigt). */
export function expressionError(src: string): string {
  if (!src.trim()) return '';
  try {
    compileExpression(src.trim());
    return '';
  } catch (e) {
    return (e as Error).message;
  }
}
