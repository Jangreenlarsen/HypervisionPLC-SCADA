#!/usr/bin/env python3
"""Dansk kvalitets- og hastighedsmåling af hjælperens modeller (docs/LLM_ANALYSE.md §7).

Kører det faste målesæt `deploy/llm_bench_questions.json` mod en llama-server, så målingen ligner produktionen, og
scorer svarene. Gentagelig: samme sæt, samme prompt, samme parametre — kør igen med en anden `--model-name`.

Hvad der GENBRUGES fra den rigtige hjælper (importeres fra backend/app, appen startes ikke):
- `SYSTEM_PROMPT`, `ANSWER_TOKENS`, `ANSWER_TOTAL_S` (services/assistant.py)
- manualopslaget: `ManualIndex.search` (BM25, samme stemming) og `excerpt`, med `MANUAL_HITS` og `MANUAL_CHARS`, og
  datablokken samles/afkortes med `Gathered.render` (DATA_BUDGET) (services/assist_tools.py, assist_knowledge.py)
- klienten `LlmClient.stream` (spørgsmål: temperature 0.2, cache_prompt, `chat_template_kwargs.enable_thinking=false`,
  max_tokens 220) og `LlmClient.chat_json` (json_schema strict, temperature 0) (llm/client.py)
- JSON-opgaverne: `TAG_SYSTEM`/`tag_schema` og `SIGNAL_SYSTEM`/`signal_schema` (services/assist_setup.py)

Hvad der GENSKABES (fordi det hører til den kørende app): beskeden til brugeren i `AssistantService.prepare`
(`<data>\\n…\\n</data>\\n\\nSpørgsmål: …`, uden samtalehistorik) og dataliniernes tekst for signal-opgaven (`SignalHelper.prepare`).
Der er INGEN levende data: ingen aktive alarmer, tags eller tegninger (kun "Side"-linjen og manualuddrag), og
alarm-spørgsmålene får ikke blokken "Aktive alarmer". Sprogopgaverne (s1-s4) kaldes uden manualuddrag.

llama-server startes som i produktionen (deploy/hypervisionplc-scada-llm.service):
`--host 127.0.0.1 --port P --model F --threads T --ctx-size C --parallel 1 --jinja --no-webui`. Kun loopback.

Eksempler (Windows, kør med PYTHONIOENCODING=utf-8):
  backend/.venv/Scripts/python.exe deploy/llm_bench.py --model-name qwen3.5-2b --port 8191 --threads 4 \\
      --llama-server C:/.../llama-server.exe --model-file C:/.../Qwen3.5-2B-Q4_K_M.gguf --ctx 8192 --out C:/.../results
  backend/.venv/Scripts/python.exe deploy/llm_bench.py --model-name x --port 8091        # mod en allerede kørende server
  backend/.venv/Scripts/python.exe deploy/llm_bench.py --report results/*.json           # samlet tabel

Tidstal (første token, tokens/s, samlet tid) er kun brugbare, når maskinen ellers er rolig — brug `--timing-note`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_QUESTIONS = HERE / "llm_bench_questions.json"
CATEGORIES = ("manual", "alarm_tag", "sprog", "json")
ENGLISH = re.compile(r"\b(the|and|you|your|with|that|this|is|are|please|connection|lost|retrying)\b", re.I)
_ACCENTS = str.maketrans("éèêáàâíìóòôúùü", "eeeaaaiiooouuu")


# ----------------------------------------------------------------------------------------------- scoring
def norm(text: str) -> str:
    t = text.lower().translate(_ACCENTS).replace("\u00a0", " ").replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    t = t.replace("*", "").replace("`", "")          # markdown-fed/kode må ikke bryde et match
    return re.sub(r"\s+", " ", t)


def _alt_re(alt: str) -> re.Pattern[str]:
    a = re.escape(norm(alt).strip())
    tail = r"(?![\w])" if len(alt.strip()) <= 3 else ""      # korte ord (H, HH, and, or) skal være hele ord
    return re.compile(r"(?<![\w])" + a + tail)


def has_term(text_norm: str, term: str) -> bool:
    """`term` kan være 'a|b' (alternative skrivemåder). Begyndelsen skal være en ordgrænse; endelser er frie (bøjning)."""
    return any(_alt_re(alt).search(text_norm) for alt in term.split("|") if alt.strip())


def score_terms(text: str, must: list[str], forbidden: list[str]) -> dict[str, Any]:
    t = norm(text)
    found = [m for m in must if has_term(t, m)]
    bad = [f for f in forbidden if has_term(t, f)]
    return {"must_found": found, "must_missing": [m for m in must if m not in found],
            "kw_score": round(len(found) / len(must), 3) if must else None, "forbidden_found": bad}


def score_json(q: dict[str, Any], data: Any) -> dict[str, Any]:
    """Andel rigtige felter: tag-opgaven (findes navnet, rigtig enhed, nøgleord i beskrivelsen) og signal-opgaven."""
    checks: list[tuple[str, bool]] = []
    items = data.get("svar") if isinstance(data, dict) else None
    items = items if isinstance(items, list) else []
    if q["json_kind"] == "tags":
        got = {it.get("navn"): it for it in items if isinstance(it, dict)}
        for name, exp in q["expect"].items():
            it = got.get(name)
            checks.append((f"{name}:med", it is not None))
            checks.append((f"{name}:enhed", it is not None and it.get("enhed") in exp["enhed"]))
            desc = norm(str(it.get("beskrivelse") or "")) if it else ""
            checks.append((f"{name}:beskrivelse", bool(desc) and any(has_term(desc, k) for k in exp["beskrivelse"])))
    else:
        got = {it.get("signal"): it for it in items if isinstance(it, dict)}
        for sig, exp in q["expect"].items():
            it = got.get(sig) or {}
            checks.append((f"{sig}:kommando", it.get("kommando") == exp["kommando"]))
            checks.append((f"{sig}:tilbagemelding", it.get("tilbagemelding") == exp["tilbagemelding"]))
    ok = [c for c, v in checks if v]
    return {"kw_score": round(len(ok) / len(checks), 3) if checks else None,
            "must_found": ok, "must_missing": [c for c, v in checks if not v], "forbidden_found": []}


# ----------------------------------------------------------------------------------------------- prompter
def build_prompts(q: dict[str, Any], index: Any) -> dict[str, Any]:
    """Beskeder som i produktionen. → {messages, data_block, sources, schema?, max_tokens?}"""
    from app.services import assist_setup
    from app.services.assist_tools import MANUAL_CHARS, MANUAL_HITS, PAGES, Gathered
    from app.services.assist_knowledge import excerpt
    from app.services.assistant import SYSTEM_PROMPT

    if q["category"] == "json":
        if q["json_kind"] == "tags":
            names = q["names"]
            data = "PLC-variabler:\n" + "\n".join(q["rows"])
            return {"messages": [{"role": "system", "content": assist_setup.TAG_SYSTEM},
                                 {"role": "user", "content": f"<data>\n{data}\n</data>\n\nSkriv beskrivelse og enhed for hver variabel."}],
                    "schema": assist_setup.tag_schema(names), "max_tokens": min(1200, 40 + 32 * len(names)), "data_block": data, "sources": []}
        ids = q["signals"]
        tags = q["tags"]
        writable = [t["name"] for t in tags if t["writable"]]
        lines = [f"- {t['name']} ({t['kind']}{', skrivbar' if t['writable'] else ''}) — {t['description']}" for t in tags]
        data = (f"Symbol: {q['symbol']} (betjeningsform: {q['mode']})\nSignaler: {', '.join(ids)}\n\nTags:\n" + "\n".join(lines))
        return {"messages": [{"role": "system", "content": assist_setup.SIGNAL_SYSTEM},
                             {"role": "user", "content": f"<data>\n{data}\n</data>\n\nBeskrivelse: {q['text']}"}],
                "schema": assist_setup.signal_schema(ids, writable, [t["name"] for t in tags]),
                "max_tokens": 40 + 60 * len(ids), "data_block": data, "sources": []}
    g = Gathered()
    page = PAGES.get(q.get("page", ""), "")
    if page:
        g.add("Side", f"Brugeren står på siden {page}.", "side")
    sources: list[str] = []
    if q.get("manual", True):
        for sec, score in index.search(q["question"], MANUAL_HITS):
            g.add(sec.source, excerpt(sec.text, q["question"], MANUAL_CHARS), "soeg_manual", {"label": sec.source, "href": sec.href})
            sources.append(f"{sec.source} ({score})")
    data = g.render()
    user = (f"<data>\n{data}\n</data>\n\n" if data else "") + f"Spørgsmål: {q['question']}"
    return {"messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
            "data_block": data, "sources": sources}


# ----------------------------------------------------------------------------------------------- kørsel
async def ask_one(client: Any, q: dict[str, Any], index: Any, args: argparse.Namespace) -> dict[str, Any]:
    from app.llm.client import Completion, LlmError
    from app.services.assistant import ANSWER_TOKENS, ANSWER_TOTAL_S

    p = build_prompts(q, index)
    row: dict[str, Any] = {"id": q["id"], "category": q["category"], "question": q["question"], "sources": p["sources"],
                           "data_chars": len(p["data_block"]), "messages": p["messages"], "error": None, "answer": ""}
    t0 = time.monotonic()
    try:
        if q["category"] == "json":
            # = LlmClient.chat_json, men råteksten bevares, også når den ikke er gyldig JSON
            done = await client.chat(p["messages"], schema=p["schema"], max_tokens=p["max_tokens"], timeout=300)
            try:
                data, valid = json.loads(done.text), True
            except ValueError:
                data, valid = None, False
            row.update(answer=done.text, json_valid=valid, ttft_s=None, truncated=done.tokens_out >= p["max_tokens"])
            if not valid and row["truncated"]:
                # Produktionens token-loft (40 + 32/60 pr. post) blev ramt midt i JSON'en: json_valid = False (det er sandt for
                # produktionen), men kvaliteten måles på et genkørt svar med tredobbelt loft, så den ikke skjules af afkortningen
                done2 = await client.chat(p["messages"], schema=p["schema"], max_tokens=p["max_tokens"] * 3, timeout=300)
                row.update(answer_relaxed=done2.text, tokens_out_relaxed=done2.tokens_out)
                try:
                    data = json.loads(done2.text)
                except ValueError:
                    data = None
            s = score_json(q, data)
        else:
            first = None
            parts: list[str] = []
            done = None
            async for part in client.stream(p["messages"], max_tokens=ANSWER_TOKENS, temperature=args.temperature, total_timeout=ANSWER_TOTAL_S):
                if isinstance(part, Completion):
                    done = part
                else:
                    if first is None:
                        first = time.monotonic() - t0
                    parts.append(part)
            text = "".join(parts)
            row.update(answer=text, ttft_s=round(first, 2) if first is not None else None)
            s = score_terms(text, q["must_have"], q["forbidden"])
            # retrieval: hvor stor en del af nøgleordene stod overhovedet i det, modellen fik
            s["retrieval_score"] = (score_terms(p["data_block"], q["must_have"], [])["kw_score"] if q.get("manual", True) and q["must_have"] else None)
            words = len(text.split())
            row.update(words=words, chars=len(text), empty=not text.strip(), truncated=bool(done and done.tokens_out >= ANSWER_TOKENS),
                       english_leak=len(ENGLISH.findall(text)) >= 3, thinking_leak="<think" in text.lower(),
                       cites_source="(manual" in text.lower())
        row.update(s)
        row.update(total_s=round(time.monotonic() - t0, 2), tokens_in=done.tokens_in if done else 0, tokens_out=done.tokens_out if done else 0,
                   prompt_ms=round(done.prompt_ms) if done else 0, tok_s=done.tokens_per_s if done else 0.0)
    except LlmError as exc:
        row.update(error=f"{exc.kind}: {exc.message}", total_s=round(time.monotonic() - t0, 2), kw_score=0.0 if q["category"] != "json" else 0.0,
                   json_valid=False if q["category"] == "json" else None, must_found=[], must_missing=list(q["must_have"]), forbidden_found=[])
    return row


def wait_ready(base: str, proc: subprocess.Popen | None, timeout: float) -> None:
    import urllib.request
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if proc is not None and proc.poll() is not None:
            raise SystemExit(f"llama-server stoppede (kode {proc.returncode}) — se serverloggen")
        try:
            with urllib.request.urlopen(base + "/health", timeout=3) as r:
                if r.status == 200:
                    return
        except Exception:      # noqa: BLE001 — 503 mens modellen indlæses, ellers ikke oppe endnu
            pass
        time.sleep(1.5)
    raise SystemExit("llama-server blev ikke klar i tide")


def props(base: str) -> dict[str, Any]:
    import urllib.request
    try:
        with urllib.request.urlopen(base + "/props", timeout=5) as r:
            d = json.loads(r.read())
        return {"n_ctx": (d.get("default_generation_settings") or {}).get("n_ctx"), "model_path": d.get("model_path"),
                "build": d.get("build_info"), "total_slots": d.get("total_slots")}
    except Exception:      # noqa: BLE001
        return {}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"by_category": {}}
    def block(rs: list[dict[str, Any]]) -> dict[str, Any]:
        kw = [r["kw_score"] for r in rs if r.get("kw_score") is not None]
        ttft = [r["ttft_s"] for r in rs if r.get("ttft_s") is not None]
        toks = [r["tok_s"] for r in rs if r.get("tok_s")]
        tot = [r["total_s"] for r in rs if r.get("total_s") is not None and not r.get("error")]
        words = [r["words"] for r in rs if r.get("words") is not None]
        ret = [r["retrieval_score"] for r in rs if r.get("retrieval_score") is not None]
        return {"n": len(rs), "kw_score": round(statistics.mean(kw), 3) if kw else None,
                "retrieval_score": round(statistics.mean(ret), 3) if ret else None,
                "forbidden_hits": sum(len(r.get("forbidden_found") or []) for r in rs),
                "errors": sum(1 for r in rs if r.get("error")), "empty": sum(1 for r in rs if r.get("empty")),
                "truncated": sum(1 for r in rs if r.get("truncated")), "english_leak": sum(1 for r in rs if r.get("english_leak")),
                "json_valid": f"{sum(1 for r in rs if r.get('json_valid'))}/{len(rs)}" if rs and rs[0]["category"] == "json" else None,
                "words_median": statistics.median(words) if words else None,
                "ttft_s_median": round(statistics.median(ttft), 2) if ttft else None,
                "tok_s_median": round(statistics.median(toks), 2) if toks else None,
                "total_s_median": round(statistics.median(tot), 2) if tot else None}
    for cat in CATEGORIES:
        rs = [r for r in rows if r["category"] == cat]
        if rs:
            out["by_category"][cat] = block(rs)
    out["all"] = block(rows)
    return out


def markdown_for(result: dict[str, Any]) -> str:
    m, s = result["meta"], result["summary"]
    lines = [f"### {m['model_name']}", "",
             f"n_ctx {m.get('n_ctx')}, tråde {m['threads']}, temperatur {m['temperature']}, {m['started']}. "
             f"Tidstal: **{m['timing_note']}**.", "",
             "| Kategori | n | Nøgleord | Retrieval | Forbudt | JSON gyldig | Fejl/tomme | Ord (median) | 1. token s | tok/s | Samlet s |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for cat, b in [*s["by_category"].items(), ("**alt**", s["all"])]:
        lines.append(f"| {cat} | {b['n']} | {b['kw_score']} | {b['retrieval_score']} | {b['forbidden_hits']} | {b['json_valid'] or '-'} | "
                     f"{b['errors']}/{b['empty']} | {b['words_median']} | {b['ttft_s_median']} | {b['tok_s_median']} | {b['total_s_median']} |")
    lines += ["", "JSON gyldig = svaret rummes i produktionens token-loft (40 + 32/60 pr. post). Rammes loftet, genkøres opgaven med "
              "tredobbelt loft, og nøgleord-scoren for json-opgaver måles på det svar. Retrieval = andel af must_have, der stod i "
              "manualuddragene modellen fik."]
    return "\n".join(lines) + "\n"


def report(files: list[str]) -> str:
    results = [json.loads(Path(f).read_text(encoding="utf-8")) for f in files]
    out = ["## Nøgleord-score (andel af must_have fundet)", "",
           "| Model | manual | alarm_tag | sprog | json | **samlet** | forbudte påstande | tomme/fejl | timing |", "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        s = r["summary"]
        c = lambda k: (s["by_category"].get(k) or {}).get("kw_score")      # noqa: E731
        out.append(f"| {r['meta']['model_name']} | {c('manual')} | {c('alarm_tag')} | {c('sprog')} | {c('json')} | **{s['all']['kw_score']}** | "
                   f"{s['all']['forbidden_hits']} | {s['all']['empty']}/{s['all']['errors']} | {r['meta']['timing_note']} |")
    out += ["", "## Hastighed (median)", "", "| Model | 1. token s | tok/s | samlet s | ord | timing |", "|---|---|---|---|---|---|"]
    for r in results:
        a = r["summary"]["all"]
        sp = [x for x in r["rows"] if x["category"] != "json"]
        out.append(f"| {r['meta']['model_name']} | {a['ttft_s_median']} | {a['tok_s_median']} | {a['total_s_median']} | {a['words_median']} | {r['meta']['timing_note']} |")
    ids = [x["id"] for x in results[0]["rows"]]
    out += ["", "## Pr. spørgsmål (nøgleord-score)", "", "| id | " + " | ".join(r["meta"]["model_name"] for r in results) + " |", "|---|" + "---|" * len(results)]
    for i in ids:
        cells = []
        for r in results:
            row = next((x for x in r["rows"] if x["id"] == i), None)
            cells.append("-" if row is None or row.get("kw_score") is None else (f"{row['kw_score']:.2f}" + (" !" if row.get("forbidden_found") else "")))
        out.append(f"| {i} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def rescore(files: list[str], questions: str) -> None:
    """Scorer gemte svar igen mod det nuværende målesæt (fx efter en rettet nøgleordsliste) — modellen kaldes ikke."""
    doc = json.loads(Path(questions).read_text(encoding="utf-8"))
    qs = {q["id"]: q for q in doc["questions"]}
    for f in files:
        path = Path(f)
        result = json.loads(path.read_text(encoding="utf-8"))
        for row in result["rows"]:
            q = qs.get(row["id"])
            if q is None or row.get("error"):
                continue
            if q["category"] == "json":
                try:
                    data = json.loads(row.get("answer_relaxed") or row["answer"])
                except ValueError:
                    data = None
                s = score_json(q, data)
            else:
                s = score_terms(row["answer"], q["must_have"], q["forbidden"])
                data_block = row["messages"][-1]["content"]
                s["retrieval_score"] = score_terms(data_block, q["must_have"], [])["kw_score"] if q.get("manual", True) and q["must_have"] else None
            row.update(s)
        result["summary"] = summarize(result["rows"])
        result["meta"]["rescored"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        path.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        path.with_suffix(".md").write_text(markdown_for(result), encoding="utf-8", newline="\n")
        print(f"{path.name}: samlet nøgleord-score {result['summary']['all']['kw_score']}")


async def run(args: argparse.Namespace) -> int:
    from app.llm.client import LlmClient
    from app.services.assist_knowledge import ManualIndex

    doc = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    qs = [q for q in doc["questions"] if (not args.only or q["id"] in args.only or q["category"] in args.only)]
    if args.limit:
        qs = qs[: args.limit]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"http://127.0.0.1:{args.port}"
    proc: subprocess.Popen | None = None
    log_fh = None
    try:
        if args.llama_server:
            if not args.model_file:
                raise SystemExit("--llama-server kræver --model-file")
            log_fh = open(out_dir / f"{args.model_name}.server.log", "w", encoding="utf-8")
            cmd = [args.llama_server, "--host", "127.0.0.1", "--port", str(args.port), "--model", args.model_file,
                   "--threads", str(args.threads), "--ctx-size", str(args.ctx), "--parallel", "1", "--jinja", "--no-webui"]
            print("starter:", " ".join(cmd), flush=True)
            proc = subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT, cwd=str(Path(args.llama_server).parent))
            print(f"llama-server pid {proc.pid}", flush=True)
        wait_ready(base, proc, 600)
        client = LlmClient(base)
        index = ManualIndex(Path(args.manual_dir))
        print(f"manual: {index.count()} stykker; {len(qs)} opgaver", flush=True)
        # Opvarmning som AssistantService.warm_up: systemprompten læses én gang
        from app.services.assistant import SYSTEM_PROMPT
        t0 = time.monotonic()
        await client.chat([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "Hej"}], max_tokens=1, timeout=600)
        warm_s = round(time.monotonic() - t0, 2)
        rows = []
        for n, q in enumerate(qs, 1):
            row = await ask_one(client, q, index, args)
            rows.append(row)
            print(f"[{n}/{len(qs)}] {q['id']:4s} kw={row.get('kw_score')} forb={row.get('forbidden_found')} {row.get('total_s')}s"
                  + (f" FEJL {row['error']}" if row.get("error") else ""), flush=True)
        meta = {"model_name": args.model_name, "port": args.port, "threads": args.threads, "ctx_arg": args.ctx if args.llama_server else None,
                "temperature": args.temperature, "timing_note": args.timing_note, "started": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "warm_s": warm_s, "questions_file": str(Path(args.questions).name), "questions_version": doc.get("version"), **props(base)}
        result = {"meta": meta, "summary": summarize(rows), "rows": rows}
        (out_dir / f"{args.model_name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        md = markdown_for(result)
        (out_dir / f"{args.model_name}.md").write_text(md, encoding="utf-8", newline="\n")
        print("\n" + md)
        return 0
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(20)
            except subprocess.TimeoutExpired:
                proc.kill()
            print(f"llama-server pid {proc.pid} stoppet", flush=True)
        if log_fh:
            log_fh.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model-name", help="navn i resultaterne (fx qwen3.5-4b)")
    ap.add_argument("--port", type=int, default=8091)
    ap.add_argument("--threads", type=int, default=4, help="-t til llama-server (4 ≈ en 4-vCPU-VM)")
    ap.add_argument("--ctx", type=int, default=8192, help="--ctx-size (Qwen 8192 som i produktionen, Mimir 4096)")
    ap.add_argument("--llama-server", help="sti til llama-server; udelades, hvis en server allerede kører på --port")
    ap.add_argument("--model-file", help="GGUF-fil (kun sammen med --llama-server)")
    ap.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    ap.add_argument("--manual-dir", default=str(REPO / "frontend" / "src" / "manual"))
    ap.add_argument("--out", default=str(REPO / "llm-bench-results"), help="mappe til JSON, markdown og serverlog")
    ap.add_argument("--temperature", type=float, default=0.2, help="spørgsmål: 0.2 som i produktionen")
    ap.add_argument("--only", nargs="*", help="kun disse id'er eller kategorier (manual, alarm_tag, sprog, json)")
    ap.add_argument("--limit", type=int, default=0, help="kun de første N opgaver (afprøvning)")
    ap.add_argument("--timing-note", default="ikke vurderet", help="fx 'under belastning' — står ved alle tidstal")
    ap.add_argument("--report", nargs="+", metavar="JSON", help="skriv en samlet tabel af flere resultatfiler og stop")
    ap.add_argument("--rescore", nargs="+", metavar="JSON", help="scor gemte resultatfiler igen mod --questions (uden at kalde modellen)")
    args = ap.parse_args()
    if args.rescore:
        rescore(args.rescore, args.questions)
        return 0
    if args.report:
        print(report(args.report))
        return 0
    if not args.model_name:
        ap.error("--model-name er påkrævet")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
