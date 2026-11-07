"""Klient til den lokale LLM-tjeneste (llama.cpp `llama-server`, OpenAI-kompatibelt API) — lag 4c.

Regler (ARCHITECTURE.md):
- kun loopback (127.0.0.1/::1) — adressen kan ikke pege ud af maskinen;
- `trust_env=False` (ingen proxy/netrc fra miljøet), faste tidsgrænser og størrelsesgrænse på svaret;
- returnerer typede resultater eller `LlmError` — aldrig rå httpx-undtagelser op til service-laget;
- logger aldrig prompt- eller svartekst (kun tider og antal tokens).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator
from urllib.parse import urlparse

import httpx

log = logging.getLogger("scada.llm")
logging.getLogger("httpx").setLevel(logging.WARNING)

MAX_RESPONSE_BYTES = 512 * 1024
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


class LlmError(Exception):
    """`kind`: 'unavailable' (tjenesten svarer ikke), 'timeout', 'bad_response', 'busy'."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass
class Completion:
    text: str
    tokens_in: int
    tokens_out: int
    ms: float
    model: str
    prompt_ms: float = 0.0      # tid til at læse prompten (fra llama-servers timings; 0 = ukendt)

    @property
    def tokens_per_s(self) -> float:
        """Skrivehastighed: tokens pr. sekund efter at prompten er læst (prompt_ms), ellers over hele tiden."""
        gen_ms = self.ms - self.prompt_ms if 0 < self.prompt_ms < self.ms else self.ms
        return round(self.tokens_out / (gen_ms / 1000), 2) if gen_ms > 0 and self.tokens_out else 0.0


class LlmClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8091", transport: httpx.AsyncBaseTransport | None = None):
        host = urlparse(base_url).hostname or ""
        if host not in LOOPBACK:
            raise ValueError(f"LLM-tjenesten skal ligge på loopback, ikke '{host}'")
        self.base_url = base_url.rstrip("/")
        self._transport = transport

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(timeout, connect=3.0), trust_env=False,
                                 transport=self._transport)

    async def health(self) -> dict[str, Any]:
        """{'ok': bool, 'status': 'ok'|'loading'|'unavailable', 'model': str|None}. Kaster aldrig."""
        try:
            async with self._client(3.0) as c:
                r = await c.get("/health")
                if r.status_code == 503:
                    return {"ok": False, "status": "loading", "model": None}
                if r.status_code != 200:
                    return {"ok": False, "status": "unavailable", "model": None}
                model = None
                try:
                    m = await c.get("/v1/models")
                    data = m.json().get("data") if m.status_code == 200 else None
                    model = data[0].get("id") if isinstance(data, list) and data else None
                except (httpx.HTTPError, ValueError, AttributeError):
                    pass
                return {"ok": True, "status": "ok", "model": model}
        except httpx.HTTPError:
            return {"ok": False, "status": "unavailable", "model": None}

    async def chat(self, messages: list[dict[str, str]], *, schema: dict[str, Any] | None = None, max_tokens: int = 400,
                   temperature: float = 0.0, timeout: float = 90.0) -> Completion:
        """Ét svar (ikke strømmet). `schema`: JSON-skema, som svaret SKAL følge (llama-server håndhæver det med grammatik)."""
        body: dict[str, Any] = {
            "messages": messages, "max_tokens": max_tokens, "temperature": temperature, "stream": False,
            # Qwen3.x m.fl. "tænker" ellers højt før svaret — det koster minutter på CPU og bruges ikke
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if schema is not None:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "svar", "schema": schema, "strict": True}}
        t0 = time.monotonic()
        try:
            async with self._client(timeout) as c:
                r = await c.post("/v1/chat/completions", json=body)
        except httpx.TimeoutException:
            raise LlmError("timeout", f"LLM-tjenesten svarede ikke inden for {int(timeout)} s") from None
        except httpx.HTTPError as exc:
            raise LlmError("unavailable", f"LLM-tjenesten kan ikke nås ({type(exc).__name__})") from None
        ms = (time.monotonic() - t0) * 1000
        if r.status_code == 503:
            raise LlmError("busy", "LLM-tjenesten indlæser modellen eller er optaget — prøv igen om lidt")
        if r.status_code != 200:
            raise LlmError("bad_response", f"LLM-tjenesten svarede {r.status_code}")
        if len(r.content) > MAX_RESPONSE_BYTES:
            raise LlmError("bad_response", "LLM-svaret er for stort")
        try:
            data = r.json()
            text = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage") or {}
            done = Completion(text=text, tokens_in=int(usage.get("prompt_tokens") or 0),
                              tokens_out=int(usage.get("completion_tokens") or 0), ms=ms, model=str(data.get("model") or ""))
        except (ValueError, KeyError, IndexError, TypeError):
            raise LlmError("bad_response", "LLM-svaret kunne ikke læses") from None
        log.info("LLM-svar: %d→%d tokens på %.0f ms (%.1f tok/s)", done.tokens_in, done.tokens_out, ms, done.tokens_per_s)
        return done

    async def stream(self, messages: list[dict[str, str]], *, max_tokens: int = 300, temperature: float = 0.2,
                     first_timeout: float = 90.0, total_timeout: float = 240.0) -> AsyncIterator[str | Completion]:
        """Strømmet svar: giver tekststykker (str) efterhånden og til sidst én `Completion` (tider og tokens).
        `first_timeout`: hvor længe der må gå mellem to stykker (første stykke venter på, at prompten er læst);
        `total_timeout`: hele svaret. Afbrydes iteratoren (fx brugeren lukker panelet), lukkes forbindelsen, og
        llama-server stopper genereringen."""
        body: dict[str, Any] = {
            "messages": messages, "max_tokens": max_tokens, "temperature": temperature, "stream": True,
            "stream_options": {"include_usage": True}, "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        t0 = time.monotonic()
        parts: list[str] = []
        size = 0
        usage: dict[str, Any] = {}
        timings: dict[str, Any] = {}
        model = ""
        try:
            async with self._client(first_timeout) as c:
                async with c.stream("POST", "/v1/chat/completions", json=body) as r:
                    if r.status_code == 503:
                        raise LlmError("busy", "LLM-tjenesten indlæser modellen eller er optaget — prøv igen om lidt")
                    if r.status_code != 200:
                        raise LlmError("bad_response", f"LLM-tjenesten svarede {r.status_code}")
                    async for line in r.aiter_lines():
                        if time.monotonic() - t0 > total_timeout:
                            raise LlmError("timeout", f"Svaret tog mere end {int(total_timeout)} s og blev afbrudt")
                        if not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if payload == "[DONE]":
                            break
                        size += len(payload)
                        if size > MAX_RESPONSE_BYTES:
                            raise LlmError("bad_response", "LLM-svaret er for stort")
                        try:
                            data = json.loads(payload)
                        except ValueError:
                            continue
                        if not isinstance(data, dict):
                            continue
                        model = str(data.get("model") or model)
                        if isinstance(data.get("usage"), dict):
                            usage = data["usage"]
                        if isinstance(data.get("timings"), dict):
                            timings = data["timings"]
                        choices = data.get("choices") or []
                        delta = (choices[0].get("delta") or {}).get("content") if choices and isinstance(choices[0], dict) else None
                        if isinstance(delta, str) and delta:
                            parts.append(delta)
                            yield delta
        except httpx.TimeoutException:
            raise LlmError("timeout", f"LLM-tjenesten svarede ikke inden for {int(first_timeout)} s") from None
        except httpx.HTTPError as exc:
            raise LlmError("unavailable", f"LLM-tjenesten kan ikke nås ({type(exc).__name__})") from None
        ms = (time.monotonic() - t0) * 1000
        done = Completion(text="".join(parts), tokens_in=int(usage.get("prompt_tokens") or timings.get("prompt_n") or 0),
                          tokens_out=int(usage.get("completion_tokens") or timings.get("predicted_n") or 0), ms=ms, model=model)
        done.prompt_ms = float(timings.get("prompt_ms") or 0.0)
        log.info("LLM-svar (strøm): %d→%d tokens på %.0f ms (prompt %.0f ms, %.1f tok/s)", done.tokens_in, done.tokens_out,
                 ms, done.prompt_ms, done.tokens_per_s)
        yield done

    async def chat_json(self, messages: list[dict[str, str]], schema: dict[str, Any], **kw: Any) -> tuple[Any, Completion]:
        done = await self.chat(messages, schema=schema, **kw)
        try:
            return json.loads(done.text), done
        except ValueError:
            raise LlmError("bad_response", "LLM-svaret var ikke gyldig JSON") from None
