"""Alarmnotifikation: validering, hemmeligheder (skriv-kun), filtre, batching, forsøg igen, webhook/e-mail og hele vejen fra en alarm."""

import json
import logging
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.errors import ServiceError
from app.services.notifier import MAX_PER_MESSAGE, NotificationService
from app.storage.secrets import SecretStore

pytestmark = pytest.mark.anyio

URL = "https://hooks.example.test/webhook/SECRET-WEBHOOK-ID-123"
TOKEN = "bearer-token-0123456789"
SMTP_PW = "smtp-password-xyz-987"
ADMIN_PW = "test-admin-pw-1"


def row(key="tag:T:high", priority="high", message="Kedel for høj", tag="T", plc="plc1", level="H", kind="high"):
    return {"key": key, "tag": tag, "plc": plc, "level": level, "priority": priority, "message": message, "kind": kind}


class Recorder:
    """En falsk webhook-modtager (httpx MockTransport) og en falsk SMTP-afsendelse."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.mails: list[tuple[dict, object]] = []
        self.status = 200
        self.raise_exc: Exception | None = None
        self.mail_exc: Exception | None = None
        self.fail_first = 0
        self.response_json = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.raise_exc is not None:
            raise self.raise_exc
        if self.fail_first > 0:
            self.fail_first -= 1
            return httpx.Response(503)
        if self.response_json is not None:
            return httpx.Response(self.status, json=self.response_json)
        return httpx.Response(self.status)

    def smtp(self, conn, _unused, msg):
        self.mails.append((conn, msg))
        if self.mail_exc is not None:
            raise self.mail_exc


@pytest.fixture
def env(tmp_path):
    rec = Recorder()
    transport = httpx.MockTransport(rec.handler)
    svc = NotificationService(tmp_path, SecretStore(tmp_path / "secrets.json"), instance="testanlæg",
                              client_factory=lambda: httpx.AsyncClient(transport=transport, timeout=5), smtp_send=rec.smtp)
    svc.retry_delays = (0.0, 0.0, 0.0)
    return svc, rec, tmp_path


def configure(svc, **extra):
    body = {"enabled": True, "webhook": {"enabled": True, "url": URL, "token": TOKEN}, **extra}
    return svc.update(body)


# ------------------------------------------------------------------ konfiguration og hemmeligheder

def test_defaults_are_off_and_public_view_has_no_secrets(env):
    svc, *_ = env
    p = svc.public()
    assert p["config"]["enabled"] is False and p["config"]["min_priority"] == "high" and p["config"]["on_clear"] is True
    assert p["config"]["webhook"]["has_url"] is False and p["config"]["email"]["has_password"] is False


def test_secrets_are_write_only_and_only_the_host_is_shown(env):
    svc, rec, tmp = env
    configure(svc, email={"enabled": False, "host": "smtp.laces.dk", "password": SMTP_PW})
    p = svc.public()
    shown = json.dumps(p)
    for secret in (URL, "SECRET-WEBHOOK-ID-123", TOKEN, SMTP_PW):
        assert secret not in shown
    assert p["config"]["webhook"] == {"enabled": True, "has_url": True, "host": "hooks.example.test", "has_token": True}
    assert p["config"]["email"]["has_password"] is True and p["config"]["email"]["host"] == "smtp.laces.dk"
    settings = (tmp / "config" / "settings.json").read_text()
    assert URL not in settings and TOKEN not in settings and SMTP_PW not in settings       # hemmeligheder kun i secrets.json


def test_update_keeps_secrets_when_fields_are_empty_and_removes_them_on_request(env):
    svc, *_ = env
    configure(svc)
    svc.update({"min_priority": "medium", "webhook": {"url": "", "token": ""}})              # tomme felter ændrer ikke hemmeligheder
    assert svc.public()["config"]["webhook"]["has_url"] and svc.public()["config"]["webhook"]["has_token"]
    svc.update({"webhook": {"clear_token": True}})
    assert svc.public()["config"]["webhook"]["has_token"] is False and svc.public()["config"]["webhook"]["has_url"] is True
    with pytest.raises(ServiceError, match="uden en adresse"):
        svc.update({"webhook": {"clear_url": True}})                                          # slået til uden adresse afvises
    svc.update({"webhook": {"enabled": False, "clear_url": True}})
    assert svc.public()["config"]["webhook"]["has_url"] is False


@pytest.mark.parametrize("body, message", [
    ({"min_priority": "kritisk"}, "min_priority"), ({"batch_s": 1}, "5-300"), ({"batch_s": 9999}, "5-300"), ({"batch_s": True}, "5-300"),
    ({"enabled": "ja"}, "sand eller falsk"),
    ({"webhook": {"url": "ftp://x.dk/a"}}, "http://"), ({"webhook": {"url": "https://"}}, "http://"), ({"webhook": {"url": "https://a b.dk"}}, "Ugyldig webhook"),
    ({"webhook": {"url": "https://x.dk/\nHost: evil"}}, "Ugyldig webhook"), ({"webhook": {"url": "https://x.dk/" + "a" * 600}}, "Ugyldig webhook"),
    ({"webhook": {"token": "kort"}}, "Token"), ({"webhook": {"token": "har et mellemrum 12345"}}, "Token"),
    ({"webhook": {"enabled": True}}, "uden en adresse"),
    ({"email": {"host": "ikke gyldig!"}}, "SMTP-server"), ({"email": {"port": 0}}, "SMTP-port"), ({"email": {"port": "587"}}, "SMTP-port"),
    ({"email": {"security": "magic"}}, "Sikkerhed"), ({"email": {"sender": "ikke-en-mail"}}, "afsender"),
    ({"email": {"recipients": ["a@b.dk", "ugyldig"]}}, "Modtagere"), ({"email": {"recipients": ["a@b.dk"] * 11}}, "Modtagere"),
    ({"email": {"recipients": ["a@b.dk,c@d.dk"]}}, "Modtagere"), ({"email": {"enabled": True}}, "kræver SMTP-server"),
    ({"email": {"password": "x\ny"}}, "adgangskode"),
])
def test_update_rejects_invalid_input_and_changes_nothing(env, body, message):
    svc, *_ = env
    before = (svc.config(), svc.public()["config"]["webhook"]["has_url"])
    with pytest.raises(ServiceError, match=message):
        svc.update(body)
    assert (svc.config(), svc.public()["config"]["webhook"]["has_url"]) == before


# ------------------------------------------------------------------ hændelser og filtre

def test_only_enabled_high_priority_raise_and_clear_events_are_queued(env):
    svc, *_ = env
    svc.on_alarm_event(row(), "raise", 1.0)
    assert svc.pending == []                                                    # slået fra
    configure(svc)
    svc.on_alarm_event(row(), "raise", 1.0)
    svc.on_alarm_event(row(priority="medium"), "raise", 2.0)                    # under filteret
    svc.on_alarm_event(row(), "ack", 3.0)
    svc.on_alarm_event(row(), "change", 3.0)
    svc.on_alarm_event(row(key="sys:notify_webhook", tag="", plc=""), "raise", 4.0)   # aldrig en løkke
    svc.on_alarm_event(row(), "clear", 5.0)
    assert [(e["event"], e["priority"]) for e in svc.pending] == [("raise", "high"), ("clear", "high")]


def test_min_priority_and_on_clear_are_respected(env):
    svc, *_ = env
    configure(svc, min_priority="medium", on_clear=False)
    svc.on_alarm_event(row(priority="medium"), "raise", 1.0)
    svc.on_alarm_event(row(priority="low"), "raise", 1.0)
    svc.on_alarm_event(row(priority="medium"), "clear", 2.0)                    # on_clear slået fra
    assert [e["event"] for e in svc.pending] == ["raise"]


def test_queue_is_capped_and_counts_dropped(env):
    svc, *_ = env
    configure(svc)
    for i in range(510):
        svc.on_alarm_event(row(key=f"tag:T{i}:high"), "raise", float(i))
    assert len(svc.pending) == 500 and svc.dropped == 10 and svc.pending[0]["key"] == "tag:T10:high"


# ------------------------------------------------------------------ afsendelse

async def test_webhook_payload_headers_and_counters(env, caplog):
    svc, rec, _ = env
    configure(svc)
    caplog.set_level(logging.INFO)
    r = await svc.deliver([{"event": "raise", "time": 1.0, "key": "k", "tag": "T", "plc": "p", "kind": "high", "level": "H",
                            "priority": "high", "message": "Kedel for høj"}])
    assert r == {"webhook": {"ok": True, "attempts": 1, "error": ""}}
    (req,) = rec.requests
    assert str(req.url) == URL and req.headers["authorization"] == f"Bearer {TOKEN}"
    body = json.loads(req.content)
    assert body["type"] == "alarm" and body["instance"] == "testanlæg" and body["version"] and body["more"] == 0
    ev = body["events"][0]
    assert ev["event"] == "raise" and ev["message"] == "Kedel for høj" and ev["priority"] == "high" and ev["time"].endswith("+00:00")
    assert svc.sent["webhook"] == 1 and svc.failed["webhook"] == 0 and svc.fail_streak["webhook"] == 0
    assert URL not in caplog.text and TOKEN not in caplog.text                  # aldrig hemmeligheder i loggen


async def test_retries_until_success_and_records_attempts(env):
    svc, rec, _ = env
    configure(svc)
    rec.fail_first = 2
    r = await svc.deliver([{"event": "raise", "time": 1.0, "key": "k", "tag": "", "plc": "", "kind": "", "level": "H", "priority": "high", "message": "m"}])
    assert r["webhook"]["ok"] is True and r["webhook"]["attempts"] == 3 and len(rec.requests) == 3
    assert svc.sent["webhook"] == 1 and svc.failed["webhook"] == 0


async def test_failure_after_all_retries_is_recorded_without_secrets_and_streak_gives_problem(env):
    svc, rec, _ = env
    configure(svc)
    rec.raise_exc = httpx.ConnectError(f"All connection attempts failed for {URL} with {TOKEN}")
    batch = [{"event": "raise", "time": 1.0, "key": "k", "tag": "", "plc": "", "kind": "", "level": "H", "priority": "high", "message": "m"}]
    for n in range(1, 4):
        r = await svc.deliver(batch)
        assert r["webhook"]["ok"] is False and r["webhook"]["attempts"] == 4               # første forsøg + 3 gentagelser
        assert URL not in r["webhook"]["error"] and TOKEN not in r["webhook"]["error"] and "<skjult>" in r["webhook"]["error"]
        assert svc.fail_streak["webhook"] == n
    assert svc.failing() == {"webhook": r["webhook"]["error"]} and svc.failed["webhook"] == 3
    rec.raise_exc = None
    assert (await svc.deliver(batch))["webhook"]["ok"] is True
    assert svc.failing() == {}                                                              # en vellykket afsendelse nulstiller


async def test_http_error_status_is_reported(env):
    svc, rec, _ = env
    configure(svc)
    rec.status = 404
    r = await svc.deliver([{"event": "clear", "time": 1.0, "key": "k", "tag": "", "plc": "", "kind": "", "level": "H", "priority": "high", "message": "m"}])
    assert r["webhook"]["ok"] is False and "HTTP 404" in r["webhook"]["error"]


async def test_email_subject_text_and_password_never_in_message(env):
    svc, rec, _ = env
    configure(svc, email={"enabled": True, "host": "smtp.laces.dk", "port": 587, "security": "starttls", "username": "jan",
                          "sender": "scada@laces.dk", "recipients": ["jan@laces.dk", "drift@laces.dk"], "password": SMTP_PW},
              webhook=None) if False else None
    svc.update({"enabled": True, "webhook": {"enabled": False},
                "email": {"enabled": True, "host": "smtp.laces.dk", "port": 587, "security": "starttls", "username": "jan",
                          "sender": "scada@laces.dk", "recipients": ["jan@laces.dk", "drift@laces.dk"], "password": SMTP_PW}})
    batch = [{"event": "raise", "time": 1.0, "key": "k1", "tag": "Temp", "plc": "plc1", "kind": "high", "level": "H", "priority": "high", "message": "Kedel for høj"},
             {"event": "clear", "time": 2.0, "key": "k2", "tag": "", "plc": "", "kind": "sys", "level": "SYS", "priority": "high", "message": "System: Lav spænding"}]
    r = await svc.deliver(batch)
    assert r == {"email": {"ok": True, "attempts": 1, "error": ""}}
    conn, msg = rec.mails[0]
    assert conn["host"] == "smtp.laces.dk" and conn["password"] == SMTP_PW and conn["security"] == "starttls"
    assert msg["Subject"] == "[SCADA testanlæg] 1 alarm, 1 ophørt" and msg["To"] == "jan@laces.dk, drift@laces.dk" and msg["From"] == "scada@laces.dk"
    text = msg.get_content()
    assert "[HØJ] Kedel for høj (Temp)" in text and "Ophørt:" in text and "System: Lav spænding" in text
    assert SMTP_PW not in text and SMTP_PW not in str(msg)


async def test_email_failure_is_reported_without_the_password(env):
    svc, rec, _ = env
    svc.update({"enabled": True, "email": {"enabled": True, "host": "smtp.laces.dk", "sender": "s@laces.dk", "recipients": ["j@laces.dk"],
                                           "password": SMTP_PW}})
    rec.mail_exc = RuntimeError(f"535 login failed for password {SMTP_PW}")
    r = await svc.deliver([{"event": "raise", "time": 1.0, "key": "k", "tag": "", "plc": "", "kind": "", "level": "H", "priority": "high", "message": "m"}])
    assert r["email"]["ok"] is False and SMTP_PW not in r["email"]["error"] and "<skjult>" in r["email"]["error"]


async def test_large_batches_are_capped_per_message(env):
    svc, rec, _ = env
    configure(svc)
    batch = [{"event": "raise", "time": float(i), "key": f"k{i}", "tag": "", "plc": "", "kind": "", "level": "H", "priority": "high", "message": f"m{i}"}
             for i in range(MAX_PER_MESSAGE + 7)]
    await svc.deliver(batch)
    body = json.loads(rec.requests[0].content)
    assert len(body["events"]) == MAX_PER_MESSAGE and body["more"] == 7
    subject, text = svc.subject_and_text(batch)
    assert subject.endswith(f"{MAX_PER_MESSAGE + 7} alarmer") and "… og 7 flere" in text


async def test_test_message_needs_a_channel_and_tries_once(env):
    svc, rec, _ = env
    with pytest.raises(ServiceError, match="Ingen kanal"):
        await svc.send_test()
    configure(svc)
    rec.status = 500
    r = await svc.send_test()
    assert r["webhook"]["ok"] is False and r["webhook"]["attempts"] == 1 and len(rec.requests) == 1       # ingen gentagelser ved test
    assert svc.sent["webhook"] == 0 and svc.failed["webhook"] == 0 and svc.fail_streak["webhook"] == 0     # tæller ikke med
    assert svc.deliveries[-1]["test"] is True


async def test_run_collects_events_into_one_batch(env):
    import asyncio
    svc, rec, _ = env
    configure(svc)
    real = svc.config
    svc.config = lambda: {**real(), "batch_s": 0.2}                    # kort samletid i testen
    task = asyncio.create_task(svc.run())
    try:
        for i in range(5):
            svc.on_alarm_event(row(key=f"tag:T{i}:high", message=f"alarm {i}"), "raise", float(i))
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.8)
    finally:
        task.cancel()
    assert len(rec.requests) == 1 and len(json.loads(rec.requests[0].content)["events"]) == 5     # ét parti, ikke fem beskeder
    assert svc.pending == []


# ------------------------------------------------------------------ rettelser efter gennemgang

BATCH = [{"event": "raise", "time": 1.0, "key": "k", "tag": "", "plc": "", "kind": "", "level": "H", "priority": "high", "message": "m"}]


async def test_secrets_are_replaced_before_the_error_text_is_truncated(env):
    svc, rec, _ = env
    configure(svc)
    # en lang fejltekst, hvor adressen krydser 300-tegnsgrænsen: hele adressen skal være væk, ikke en afskåret rest
    rec.raise_exc = httpx.ConnectError("x" * 285 + URL + " " + TOKEN)
    r = await svc.deliver(BATCH)
    err = r["webhook"]["error"]
    assert len(err) <= 300 and "SECRET-WEBHOOK-ID" not in err and "hooks.example.test/webhook" not in err and TOKEN not in err


@pytest.mark.parametrize("leak", [
    "/webhook/SECRET-WEBHOOK-ID-123",                                   # kun stien
    "SECRET-WEBHOOK-ID-123",                                            # kun id'et
    "https%3A%2F%2Fhooks.example.test%2Fwebhook%2FSECRET-WEBHOOK-ID-123",   # URL-kodet
    "%2Fwebhook%2FSECRET-WEBHOOK-ID-123",
])
async def test_parts_and_encoded_forms_of_the_url_are_hidden(env, leak):
    svc, rec, _ = env
    configure(svc)
    rec.raise_exc = httpx.InvalidURL(f"Invalid URL near {leak}")
    err = (await svc.deliver(BATCH))["webhook"]["error"]
    assert "SECRET-WEBHOOK-ID" not in err and "SECRET%2DWEBHOOK" not in err and "<skjult>" in err


async def test_url_with_query_and_userinfo_is_hidden_in_parts(env):
    svc, rec, _ = env
    svc.update({"enabled": True, "webhook": {"enabled": True, "url": "https://bruger:hemmeligt-pw@h.example.test/a/b?key=QUERYSECRET99&x=1"}})
    rec.raise_exc = httpx.ConnectError("fejl for hemmeligt-pw og QUERYSECRET99 og bruger:hemmeligt-pw")
    err = (await svc.deliver(BATCH))["webhook"]["error"]
    assert "hemmeligt-pw" not in err and "QUERYSECRET99" not in err


async def test_failing_ignores_channels_and_notifications_that_are_switched_off(env):
    svc, rec, _ = env
    configure(svc)
    rec.status = 500
    for _ in range(3):
        await svc.deliver(BATCH)
    assert "webhook" in svc.failing()
    svc.update({"webhook": {"enabled": False}})                       # kanalen slås fra: fejlen forsvinder med den
    assert svc.failing() == {} and svc.fail_streak["webhook"] == 0
    svc.update({"webhook": {"enabled": True}})
    for _ in range(3):
        await svc.deliver(BATCH)
    assert "webhook" in svc.failing()
    svc.update({"enabled": False})
    assert svc.failing() == {}


async def test_nothing_is_sent_when_notifications_are_switched_off_even_for_queued_events(env):
    svc, rec, _ = env
    configure(svc)
    svc.on_alarm_event(row(), "raise", 1.0)
    svc.update({"enabled": False})
    assert await svc.deliver(svc.pending) == {} and rec.requests == []


async def test_channels_are_sent_in_parallel_so_a_dead_one_does_not_delay_the_other(env):
    import time as _t
    svc, rec, _ = env
    svc.update({"enabled": True, "webhook": {"enabled": True, "url": URL},
                "email": {"enabled": True, "host": "smtp.laces.dk", "sender": "s@laces.dk", "recipients": ["j@laces.dk"]}})
    svc.retry_delays = (0.25, 0.25)
    rec.status = 500                                                  # webhook: 3 forsøg med 0,5 s i alt

    def slow_smtp(conn, _u, msg):
        _t.sleep(0.45)
        rec.mails.append((conn, msg))

    svc._smtp_send = slow_smtp
    t0 = _t.monotonic()
    r = await svc.deliver(BATCH)
    took = _t.monotonic() - t0
    assert r["webhook"]["ok"] is False and r["email"]["ok"] is True
    assert took < 0.85                                                # parallelt ≈ 0,5 s; efter hinanden ≈ 0,95 s


def test_cannot_set_and_clear_the_same_secret_in_one_save(env):
    svc, *_ = env
    for body in ({"webhook": {"url": URL, "clear_url": True}}, {"webhook": {"token": TOKEN, "clear_token": True}},
                 {"email": {"password": SMTP_PW, "clear_password": True}}):
        with pytest.raises(ServiceError, match="både sætte og fjerne"):
            svc.update(body)
    assert svc.public()["config"]["webhook"]["has_url"] is False


def test_smtp_login_requires_encryption(env):
    svc, *_ = env
    base = {"host": "smtp.laces.dk", "sender": "s@laces.dk", "recipients": ["j@laces.dk"], "security": "none"}
    with pytest.raises(ServiceError, match="klartekst"):
        svc.update({"email": {**base, "username": "jan"}})
    with pytest.raises(ServiceError, match="klartekst"):
        svc.update({"email": {**base, "password": SMTP_PW}})
    svc.update({"email": {**base, "enabled": True}})                   # uden login er "Ingen" tilladt (lokalt relay)
    assert svc.public()["config"]["email"]["security"] == "none"
    svc.update({"email": {"security": "starttls", "username": "jan", "password": SMTP_PW}})
    with pytest.raises(ServiceError, match="klartekst"):
        svc.update({"email": {"security": "none"}})                    # login og adgangskode findes allerede


def test_config_is_cached_in_memory_and_refreshed_after_an_update(env):
    svc, _, tmp = env
    svc.update({"enabled": True, "min_priority": "medium"})
    (tmp / "config" / "settings.json").unlink()                       # selv uden filen bruges den indlæste konfiguration
    assert svc.config()["min_priority"] == "medium"
    svc.update({"min_priority": "low"})
    assert svc.config()["min_priority"] == "low"


def test_a_broken_settings_file_is_logged_and_notifications_stay_off(env, caplog):
    svc, _, tmp = env
    (tmp / "config").mkdir(exist_ok=True)
    (tmp / "config" / "settings.json").write_text("{ikke json", encoding="utf-8")
    assert svc.config()["enabled"] is False
    assert "kunne ikke læses" in caplog.text


async def test_default_client_does_not_use_proxy_or_netrc_from_the_environment(tmp_path):
    svc = NotificationService(tmp_path, SecretStore(tmp_path / "s.json"))
    async with svc._client_factory() as client:
        assert client.trust_env is False and client.follow_redirects is False


# ------------------------------------------------------------------ Resend (HTTPS-API som e-mail-udbyder)

RESEND_KEY = "re_AbCdEfGhIjKlMnOpQrStUvWxYz_0123"


def resend(svc, **extra):
    return svc.update({"enabled": True, "webhook": {"enabled": False},
                       "email": {"enabled": True, "provider": "resend", "sender": "alarm@laces.dk",
                                 "recipients": ["jan@laces.dk", "drift@laces.dk"], "resend_key": RESEND_KEY, **extra}})


async def test_resend_posts_to_the_fixed_api_with_bearer_key_and_never_uses_smtp(env):
    svc, rec, _ = env
    resend(svc, host="smtp.skal-ignoreres.dk")                         # værten gælder kun SMTP
    r = await svc.deliver([{"event": "raise", "time": 1.0, "key": "k", "tag": "Temp", "plc": "plc1", "kind": "high", "level": "H",
                            "priority": "high", "message": "Kedel for høj"}])
    assert r == {"email": {"ok": True, "attempts": 1, "error": ""}}
    (req,) = rec.requests
    assert str(req.url) == "https://api.resend.com/emails" and req.method == "POST"       # fast adresse
    assert req.headers["authorization"] == f"Bearer {RESEND_KEY}"
    body = json.loads(req.content)
    assert body["from"] == "alarm@laces.dk" and body["to"] == ["jan@laces.dk", "drift@laces.dk"]
    assert body["subject"] == "[SCADA testanlæg] 1 alarm" and "[HØJ] Kedel for høj (Temp)" in body["text"]
    assert rec.mails == [] and RESEND_KEY not in json.dumps(body)


@pytest.mark.parametrize("status, payload, expected", [
    (403, {"name": "validation_error", "message": "The laces.dk domain is not verified."}, "HTTP 403: The laces.dk domain is not verified."),
    (401, {"message": "API key is invalid"}, "HTTP 401: API key is invalid"),
    (429, {"error": "rate limited"}, "HTTP 429: rate limited"),
    (500, None, "HTTP 500"),
])
async def test_resend_errors_show_the_providers_message(env, status, payload, expected):
    svc, rec, _ = env
    resend(svc)
    rec.response_json = payload
    rec.status = status
    err = (await svc.send_test())["email"]["error"]
    assert expected in err and RESEND_KEY not in err


async def test_resend_key_is_hidden_even_if_the_provider_echoes_it(env, caplog):
    svc, rec, _ = env
    resend(svc)
    rec.status, rec.response_json = 401, {"message": f"Invalid key {RESEND_KEY} and also re_AbCdEfGhIjKlMnOpQ"}
    err = (await svc.send_test())["email"]["error"]
    assert RESEND_KEY not in err and "<skjult>" in err
    rec.raise_exc = httpx.ConnectError(f"boom {RESEND_KEY}")
    assert RESEND_KEY not in (await svc.deliver(BATCH))["email"]["error"]
    assert RESEND_KEY not in caplog.text


def test_resend_key_is_write_only(env):
    svc, _, tmp = env
    resend(svc)
    p = svc.public()
    assert p["config"]["email"]["has_resend_key"] is True and p["config"]["email"]["provider"] == "resend"
    assert RESEND_KEY not in json.dumps(p) and RESEND_KEY not in (tmp / "config" / "settings.json").read_text()
    svc.update({"email": {"enabled": False, "clear_resend_key": True}})
    assert svc.public()["config"]["email"]["has_resend_key"] is False


@pytest.mark.parametrize("email, message", [
    ({"provider": "mailgun"}, "udbyder"),
    ({"provider": "resend", "enabled": True, "sender": "a@laces.dk", "recipients": ["j@laces.dk"]}, "API-nøgle"),
    ({"provider": "resend", "enabled": True, "recipients": ["j@laces.dk"], "resend_key": RESEND_KEY}, "afsender"),
    ({"provider": "resend", "enabled": True, "sender": "a@laces.dk", "resend_key": RESEND_KEY}, "modtager"),
    ({"resend_key": "ikke-en-nøgle-1234567890"}, "starte med re_"),
    ({"resend_key": "re_kort"}, "starte med re_"),
    ({"resend_key": RESEND_KEY, "clear_resend_key": True}, "både sætte og fjerne"),
])
def test_resend_validation(env, email, message):
    svc, *_ = env
    with pytest.raises(ServiceError, match=message):
        svc.update({"email": email})
    assert svc.public()["config"]["email"]["has_resend_key"] is False


def test_switching_between_providers_keeps_both_secret_sets(env):
    svc, *_ = env
    resend(svc)
    svc.update({"email": {"provider": "smtp", "enabled": True, "host": "smtp.laces.dk", "password": SMTP_PW, "security": "ssl"}})
    e = svc.public()["config"]["email"]
    assert e["provider"] == "smtp" and e["has_resend_key"] is True and e["has_password"] is True
    svc.update({"email": {"provider": "resend"}})
    assert svc.public()["config"]["email"]["provider"] == "resend"


async def test_smtp_requirements_do_not_apply_to_resend(env):
    svc, *_ = env
    resend(svc, security="none", username="x")                         # login-reglen gælder kun SMTP
    assert svc.public()["config"]["email"]["enabled"] is True


# ------------------------------------------------------------------ API

@pytest.fixture
def api(tmp_path, mock_plc):
    s = Settings(data_dir=tmp_path, poll_fast_s=0.05, poll_slow_s=0.2, plc_rate=9, frontend_dir=tmp_path / "nope",
                 admin_password=ADMIN_PW, backup_hours=0, alarm_tick_s=0.1)
    with TestClient(create_app(s)) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
        c.post("/api/plcs", json={"key": "plc1", "base_url": mock_plc.url, "username": "scada", "password": "scada123", "sse_enabled": False})
        c.tmp = tmp_path
        yield c


def test_api_is_admin_only(api):
    api.post("/api/users", json={"username": "tek", "role": "engineer", "password": "Hemmelig-kode-12345"})
    eng = TestClient(api.app)
    eng.post("/api/auth/login", json={"username": "tek", "password": "Hemmelig-kode-12345"})
    eng.post("/api/auth/password", json={"old_password": "Hemmelig-kode-12345", "new_password": "Nyt-hemmeligt-kode-9876"})
    for method, path in (("get", ""), ("put", ""), ("post", "/test")):
        assert getattr(eng, method)("/api/system/notifications" + path).status_code == 403
        assert getattr(TestClient(api.app), method)("/api/system/notifications" + path).status_code == 401


def test_api_config_roundtrip_never_returns_or_audits_secrets(api):
    r = api.put("/api/system/notifications", json={"enabled": True, "min_priority": "medium",
                                                   "webhook": {"enabled": True, "url": URL, "token": TOKEN},
                                                   "email": {"host": "smtp.laces.dk", "password": SMTP_PW}})
    assert r.status_code == 200, r.text
    for text in (r.text, api.get("/api/system/notifications").text, api.get("/api/audit?limit=50").text):
        for secret in (URL, "SECRET-WEBHOOK-ID-123", TOKEN, SMTP_PW):
            assert secret not in text
    cfg = api.get("/api/system/notifications").json()["config"]
    assert cfg["enabled"] and cfg["min_priority"] == "medium" and cfg["webhook"]["has_url"] and cfg["webhook"]["host"] == "hooks.example.test"
    audit = api.get("/api/audit?limit=50").json()
    assert any(a["action"] == "system.notifications.config" for a in audit)
    assert "webhook_url" in json.dumps(audit) and "smtp_password" in json.dumps(audit)       # at de blev sat, ikke hvad de er


def test_api_rejects_unknown_fields_and_invalid_values(api):
    assert api.put("/api/system/notifications", json={"uventet": 1}).status_code == 422
    assert api.put("/api/system/notifications", json={"webhook": {"url": "ftp://x"}}).status_code == 400
    assert api.put("/api/system/notifications", json={"min_priority": "x"}).status_code == 400


def test_api_test_message_reports_each_channel(api):
    assert api.post("/api/system/notifications/test").status_code == 409                     # ingen kanal slået til
    rec = Recorder()
    api.put("/api/system/notifications", json={"enabled": True, "webhook": {"enabled": True, "url": URL}})
    transport = httpx.MockTransport(rec.handler)
    api.app.state.notifier._client_factory = lambda: httpx.AsyncClient(transport=transport, timeout=5)
    r = api.post("/api/system/notifications/test")
    assert r.status_code == 200 and r.json()["results"]["webhook"]["ok"] is True
    assert json.loads(rec.requests[0].content)["events"][0]["message"].startswith("Prøvebesked")
    rec.status = 500
    r = api.post("/api/system/notifications/test").json()
    assert r["results"]["webhook"]["ok"] is False and "HTTP 500" in r["results"]["webhook"]["error"]


# ------------------------------------------------------------------ hele vejen: alarmmotor → webhook

def _wait(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while not (value := predicate()):
        if time.monotonic() > deadline:
            raise AssertionError("timeout")
        time.sleep(0.05)
    return value


def test_alarm_raise_and_clear_reach_the_webhook_in_batches(api, mock_plc):
    rec = Recorder()
    transport = httpx.MockTransport(rec.handler)
    n = api.app.state.notifier
    n._client_factory = lambda: httpx.AsyncClient(transport=transport, timeout=5)
    api.put("/api/system/notifications", json={"enabled": True, "webhook": {"enabled": True, "url": URL}})
    real = n.config
    n.config = lambda: {**real(), "batch_s": 0.3}
    assert api.post("/api/tags", json={"name": "Temp", "source": "plc1:hr:5", "scale": 0.1, "unit": "°C", "description": "Kedel",
                                       "alarm_hh": 90, "alarm_h": 80, "alarm_deadband": 1}).status_code == 201
    mock_plc.state.hr[5] = 950                      # 95 °C → HH (høj prioritet)
    _wait(lambda: rec.requests)
    body = json.loads(rec.requests[0].content)
    assert body["events"][0]["event"] == "raise" and body["events"][0]["priority"] == "high" and "Kedel" in body["events"][0]["message"]
    mock_plc.state.hr[5] = 100                      # tilbage til normal → ophører
    _wait(lambda: any(e["event"] == "clear" for r in rec.requests for e in json.loads(r.content)["events"]))
    assert n.sent["webhook"] >= 2 and n.failing() == {}
    ack = api.post("/api/alarms/ack", json={"keys": None})
    assert ack.status_code == 200
    time.sleep(0.6)
    assert not any(e["event"] == "ack" for r in rec.requests for e in json.loads(r.content)["events"])     # kvittering giver ingen besked
