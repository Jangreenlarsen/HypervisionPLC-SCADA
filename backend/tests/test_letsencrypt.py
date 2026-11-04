"""Let's Encrypt (certbot + deSEC): deploy-hooken cert-deploy.sh, deSEC-hooken desec-acme-hook.sh og styringsscriptet
tls-letsencrypt.sh med falske certbot/nginx/systemctl/apt-get/curl og rigtig openssl (til testcertifikater)."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SH = shutil.which("sh")
OPENSSL = shutil.which("openssl")
DEPLOY = Path(__file__).resolve().parents[2] / "deploy"
HOOK = DEPLOY / "cert-deploy.sh"
AUTH = DEPLOY / "desec-acme-hook.sh"
LE = DEPLOY / "tls-letsencrypt.sh"
needs_tools = pytest.mark.skipif(SH is None or OPENSSL is None, reason="sh/openssl findes ikke")

TOKEN = "TESTTOKEN_abcdefghijklmnop1234"
VALIDATION = "gfj9Xq-Ln6vQXeWQ3sQ8bK2PqZrA1dEfGhIjKlMnOpQ"


def make_cert(directory: Path, cn: str, ca: tuple[Path, Path] | None = None) -> tuple[Path, Path]:
    """(certifikat, nøgle). Uden `ca`: selvsigneret. Med `ca`: underskrevet af den (udsteder ≠ emne, som hos Let's Encrypt)."""
    directory.mkdir(parents=True, exist_ok=True)
    key, crt = directory / "privkey.pem", directory / "fullchain.pem"
    base = [OPENSSL, "req", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-keyout", str(key)]
    if ca is None:
        subprocess.run([*base, "-x509", "-days", "30", "-subj", f"/CN={cn}", "-out", str(crt)], check=True, capture_output=True)
    else:
        csr = directory / "x.csr"
        subprocess.run([*base, "-subj", f"/CN={cn}", "-out", str(csr)], check=True, capture_output=True)
        subprocess.run([OPENSSL, "x509", "-req", "-in", str(csr), "-CA", str(ca[0]), "-CAkey", str(ca[1]), "-CAcreateserial",
                        "-days", "30", "-out", str(crt)], check=True, capture_output=True)
    return crt, key


FAKE = "#!/bin/sh\necho \"{name} $@\" >> \"$FAKE_LOG\"\n{body}\nexit 0\n"
# curl: skriver kaldet, indholdet af en "-H @fil" (hvordan tokenet sendes) og kroppen fra stdin; svarer med en HTTP-kode som -w
CURL = '''#!/bin/sh
echo "curl $@" >> "$FAKE_LOG"
for a in "$@"; do case "$a" in @-) ;; @*) cat "${a#@}" >> "$FAKE_LOG.hdr"; echo "$a" > "$FAKE_LOG.hdrfile" ;; esac; done
cat > "$FAKE_LOG.stdin"
printf '%s' "${FAKE_HTTP:-201}"
[ -n "${FAKE_CURL_FAIL:-}" ] && exit 7
exit 0
'''


@pytest.fixture
def box(tmp_path):
    for name, body in (("nginx", '[ -n "${FAKE_NGINX_FAIL:-}" ] && [ "$1" = "-t" ] && exit 1'),
                       ("systemctl", ""),
                       ("apt-get", '[ -n "${FAKE_APT_FAIL:-}" ] && exit 100'),
                       ("certbot", '[ -n "${FAKE_CERTBOT_FAIL:-}" ] && exit 1')):
        f = tmp_path / f"fake-{name}"
        f.write_text(FAKE.format(name=name, body=body), newline="\n")
        f.chmod(0o755)
    (tmp_path / "fake-curl").write_text(CURL, newline="\n")
    (tmp_path / "fake-curl").chmod(0o755)
    tls, state, conf = tmp_path / "tls", tmp_path / "state", tmp_path / "le"
    make_cert(tls, "Hypervision-SCADA")                                    # det selvsignerede, der ligger i dag
    ca = make_cert(tmp_path / "ca", "Test CA")
    lineage = tmp_path / "live"
    make_cert(lineage, "scada.laces.dk", ca=ca)                            # det "rigtige" (udsteder ≠ emne)
    for name in ("hook.sh", "auth-hook.sh"):
        h = tmp_path / name
        h.write_text(f'#!/bin/sh\necho "{name} $@" >> "$FAKE_LOG"\n', newline="\n")
        h.chmod(0o755)
    env = {**os.environ, "FAKE_LOG": str(tmp_path / "calls.log"), "TLSDIR": str(tls), "STATE": str(state),
           "RENEWED_LINEAGE": lineage.as_posix(), "LINEAGE_ROOT": tmp_path.as_posix(), "NGINX": str(tmp_path / "fake-nginx"),
           "SYSTEMCTL": str(tmp_path / "fake-systemctl"), "CERTBOT": str(tmp_path / "fake-certbot"),
           "APT_GET": str(tmp_path / "fake-apt-get"), "LE_CONF": str(conf), "HOOK": str(tmp_path / "hook.sh"),
           "AUTH_HOOK": str(tmp_path / "auth-hook.sh"), "CURL": str(tmp_path / "fake-curl"), "SLEEP_S": "0", "TMPDIR": str(tmp_path)}
    return tmp_path, env, tls, lineage, state, conf


def calls(tmp):
    p = tmp / "calls.log"
    return p.read_text().splitlines() if p.exists() else []


def run(script, env, *args, stdin=b""):
    raw = stdin.encode("utf-8") if isinstance(stdin, str) else stdin      # bytes: ingen CRLF-omskrivning på Windows
    r = subprocess.run([SH, str(script), *args], env=env, input=raw, capture_output=True, timeout=60)
    r.stdout, r.stderr = r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    return r


def configure(env, zone="mitnavn.dedyn.io"):
    assert run(LE, env, "set-token", stdin=TOKEN + "\n").returncode == 0
    assert run(LE, env, "set-target", zone).returncode == 0


# ------------------------------------------------------------------ deploy-hook

@needs_tools
def test_deploy_installerer_atomisk_gemmer_det_gamle_og_genindlaeser_nginx(box):
    tmp, env, tls, lineage, state, _ = box
    old = (tls / "fullchain.pem").read_bytes()
    r = run(HOOK, env)
    assert r.returncode == 0, r.stderr
    assert (tls / "fullchain.pem").read_bytes() == (lineage / "fullchain.pem").read_bytes()
    assert (tls / "privkey.pem").read_bytes() == (lineage / "privkey.pem").read_bytes()
    assert (tls / "fullchain.pem.prev").read_bytes() == old and (tls / "fullchain.pem.selfsigned").read_bytes() == old
    assert not list(tls.glob("*.new")) and not list(tls.glob("*.rst"))
    if os.name == "posix":
        assert oct((tls / "privkey.pem").stat().st_mode & 0o777) == "0o600"          # nøglen må ikke være læsbar for andre
        assert oct((tls / "privkey.pem.prev").stat().st_mode & 0o777) == "0o600"
    log = calls(tmp)
    assert any(c.startswith("nginx -t") for c in log) and any("systemctl reload nginx" in c for c in log)
    assert log.index(next(c for c in log if c.startswith("nginx -t"))) < log.index(next(c for c in log if "reload nginx" in c))
    info = json.loads((state / "cert.json").read_text())
    assert info["self_signed"] is False and "Test CA" in info["issuer"] and "scada.laces.dk" in info["subject"]
    assert len(info["fingerprint"]) > 20 and info["not_after"]


@needs_tools
def test_deploy_afviser_en_noegle_der_ikke_passer_og_aendrer_intet(box):
    tmp, env, tls, lineage, state, _ = box
    other = make_cert(tmp / "other", "andet")
    shutil.copy(other[1], lineage / "privkey.pem")                         # nøgle fra et andet certifikat
    before = (tls / "fullchain.pem").read_bytes(), (tls / "privkey.pem").read_bytes()
    r = run(HOOK, env)
    assert r.returncode != 0 and "passer ikke" in r.stderr
    assert ((tls / "fullchain.pem").read_bytes(), (tls / "privkey.pem").read_bytes()) == before
    assert not any("reload" in c for c in calls(tmp)) and not (tls / "fullchain.pem.prev").exists()


@needs_tools
def test_deploy_gendanner_det_forrige_hvis_nginx_afviser(box):
    tmp, env, tls, lineage, state, _ = box
    old = (tls / "fullchain.pem").read_bytes(), (tls / "privkey.pem").read_bytes()
    r = run(HOOK, {**env, "FAKE_NGINX_FAIL": "1"})
    assert r.returncode != 0 and "gendannet" in (r.stdout + r.stderr)
    assert ((tls / "fullchain.pem").read_bytes(), (tls / "privkey.pem").read_bytes()) == old     # ingen lockout
    assert not any("reload" in c for c in calls(tmp)) and not list(tls.glob("*.rst"))


@needs_tools
def test_deploy_uden_forrige_certifikat_og_uden_nginx_siger_det_aerligt(box):
    """Der var intet at gendanne: beskeden må ikke påstå, at det forrige er gendannet."""
    tmp, env, tls, *_ = box
    shutil.rmtree(tls)
    r = run(HOOK, {**env, "FAKE_NGINX_FAIL": "1"})
    assert r.returncode != 0 and "gendannet" not in (r.stdout + r.stderr) and "intet forrige" in r.stderr


@needs_tools
def test_deploy_gentaget_beholder_det_selvsignerede_og_gemmer_det_forrige(box):
    tmp, env, tls, lineage, state, _ = box
    selfsigned = (tls / "fullchain.pem").read_bytes()
    assert run(HOOK, env).returncode == 0
    first = (tls / "fullchain.pem").read_bytes()
    make_cert(lineage, "scada.laces.dk", ca=(tmp / "ca" / "fullchain.pem", tmp / "ca" / "privkey.pem"))   # en fornyelse
    assert run(HOOK, env).returncode == 0
    assert (tls / "fullchain.pem.selfsigned").read_bytes() == selfsigned                      # aldrig overskrevet af et LE-certifikat
    assert (tls / "fullchain.pem.prev").read_bytes() == first
    assert (tls / "fullchain.pem").read_bytes() == (lineage / "fullchain.pem").read_bytes()


@needs_tools
@pytest.mark.parametrize("bad", ["/etc/passwd-dir", "/etc/letsencrypt/live/../../tmp", "relativ/sti"])
def test_deploy_accepterer_kun_certifikater_under_letsencrypt_mappen(box, bad):
    tmp, env, tls, *_ = box
    before = (tls / "fullchain.pem").read_bytes()
    r = run(HOOK, {**env, "RENEWED_LINEAGE": bad})
    assert r.returncode != 0 and "Ugyldig certifikatsti" in r.stderr and (tls / "fullchain.pem").read_bytes() == before


@needs_tools
def test_deploy_afviser_sti_med_punktummer_selv_under_roden(box):
    tmp, env, tls, *_ = box
    before = (tls / "fullchain.pem").read_bytes()
    r = run(HOOK, {**env, "RENEWED_LINEAGE": f"{tmp.as_posix()}/../live"})
    assert r.returncode != 0 and "Ugyldig certifikatsti" in r.stderr and (tls / "fullchain.pem").read_bytes() == before


@needs_tools
def test_info_beskriver_det_selvsignerede_certifikat_uden_at_aendre_noget(box):
    tmp, env, tls, _, state, _ = box
    before = (tls / "fullchain.pem").read_bytes()
    assert run(HOOK, env, "info").returncode == 0
    info = json.loads((state / "cert.json").read_text())
    assert info["self_signed"] is True and info["subject"] == info["issuer"] == "CN=Hypervision-SCADA"
    assert (tls / "fullchain.pem").read_bytes() == before and calls(tmp) == []


@needs_tools
def test_info_giver_gyldig_json_ogsaa_med_ikke_ascii_tegn(box):
    tmp, env, tls, _, state, _ = box
    make_cert(tls, "Ærø-Åbent SCADA")
    assert run(HOOK, env, "info").returncode == 0
    info = json.loads((state / "cert.json").read_text(encoding="utf-8"))          # skal kunne parses (ingen afskårne UTF-8-tegn)
    assert info["not_after"] and info["self_signed"] is True


# ------------------------------------------------------------------ styringsscript

@needs_tools
def test_install_henter_certbot_og_aktiverer_fornyelse(box):
    tmp, env, *_, conf = box
    r = run(LE, env, "install")
    assert r.returncode == 0, r.stderr
    log = calls(tmp)
    assert any(c.startswith("apt-get install -y certbot curl") for c in log) and not any("dns-desec" in c for c in log)
    assert any("systemctl enable --now certbot.timer" in c for c in log) and conf.is_dir()


@needs_tools
def test_install_fejler_tydeligt_uden_internet(box):
    r = run(LE, {**box[1], "FAKE_APT_FAIL": "1"}, "install")
    assert r.returncode != 0 and "internet" in r.stderr


@needs_tools
def test_set_token_gemmer_kun_i_filen_og_viser_det_aldrig(box):
    tmp, env, *_, conf = box
    r = run(LE, env, "set-token", stdin=TOKEN + "\n")
    assert r.returncode == 0, r.stderr
    assert TOKEN not in r.stdout + r.stderr
    assert (conf / "desec.ini").read_text() == f"dns_desec_token = {TOKEN}\n"
    if os.name == "posix":
        assert oct((conf / "desec.ini").stat().st_mode & 0o777) == "0o600"
    assert TOKEN not in "\n".join(calls(tmp))


@needs_tools
def test_set_token_tager_imod_crlf(box):
    *_, conf = box
    assert run(LE, box[1], "set-token", stdin=TOKEN + "\r\n").returncode == 0
    assert (conf / "desec.ini").read_text() == f"dns_desec_token = {TOKEN}\n"


@needs_tools
@pytest.mark.parametrize("bad", ["kort", "med mellemrum i tokenet 123456789", "x" * 150, "aeoe-æøå-1234567890123456", ""])
def test_set_token_afviser_ugyldigt_token(box, bad):
    *_, conf = box
    r = run(LE, box[1], "set-token", stdin=bad + "\n")
    assert r.returncode != 0 and not (conf / "desec.ini").exists()


@needs_tools
def test_set_target_gemmer_zone_og_viser_cname_vaerdien(box):
    *_, conf = box
    r = run(LE, box[1], "set-target", "mitnavn.dedyn.io")
    assert r.returncode == 0 and "scada-acme.mitnavn.dedyn.io" in r.stdout
    assert (conf / "target.conf").read_text() == "DESEC_ZONE=mitnavn.dedyn.io\nDESEC_SUB=scada-acme\n"
    assert run(LE, box[1], "set-target", "andet.dedyn.io", "acme-pi").returncode == 0
    assert "DESEC_SUB=acme-pi" in (conf / "target.conf").read_text()


@needs_tools
@pytest.mark.parametrize("args", [("",), ("ikke-en-zone",), ("Zone.dedyn.io",), ("a.dk;reboot",), ("a.dk", "to.led"), ("a.dk", "-x"), ("a.dk\nb.dk",)])
def test_set_target_afviser_ugyldigt_input(box, args):
    *_, conf = box
    r = run(LE, box[1], "set-target", *args)
    assert r.returncode != 0 and not (conf / "target.conf").exists()


@needs_tools
def test_issue_bygger_certbot_kaldet_uden_hemmeligheder_paa_kommandolinjen(box):
    tmp, env, *_, conf = box
    configure(env)
    r = run(LE, env, "issue", "scada.laces.dk", "jan@laces.dk")
    assert r.returncode == 0, r.stderr
    call = next(c for c in calls(tmp) if c.startswith("certbot "))
    for part in ("certonly", "--non-interactive", "--agree-tos", "-m jan@laces.dk", "--manual", "--preferred-challenges dns",
                 "--manual-auth-hook", "auth-hook.sh auth", "--manual-cleanup-hook", "auth-hook.sh cleanup",
                 "--cert-name hypervision-scada", "-d scada.laces.dk", "--deploy-hook"):
        assert part in call, part
    assert "--dry-run" not in call and TOKEN not in call
    assert any(c.startswith("hook.sh info") for c in calls(tmp))              # metadata til Status opdateres


@needs_tools
def test_issue_dry_run_bruger_staging_og_roerer_intet(box):
    tmp, env, tls, *_ = box
    configure(env)
    before = (tls / "fullchain.pem").read_bytes()
    r = run(LE, env, "issue", "scada.laces.dk", "jan@laces.dk", "--dry-run")
    assert r.returncode == 0 and "STAGING" in r.stdout
    assert "--dry-run" in next(c for c in calls(tmp) if c.startswith("certbot "))
    assert not any(c.startswith("hook.sh") for c in calls(tmp)) and (tls / "fullchain.pem").read_bytes() == before


@needs_tools
@pytest.mark.parametrize("host, email", [("-d", "a@b.dk"), ("scada", "a@b.dk"), ("Scada.Laces.DK", "a@b.dk"), ("scada.laces.dk;reboot", "a@b.dk"),
                                         ("scada.laces.dk\nevil.dk", "a@b.dk"), ("scada.laces.dk,evil.dk", "a@b.dk"), ("a.dk", "a@b.dk\n,x@y.dk"),
                                         ("scada.laces.dk", "ikke-en-mail"), ("scada.laces.dk", "-x@b.dk"), ("scada.laces.dk", "a b@c.dk"),
                                         ("scada.laces.dk", "a@b.dk,c@d.dk"), ("", "")])
def test_issue_afviser_ugyldigt_input_uden_at_kalde_certbot(box, host, email):
    tmp, env, *_ = box
    configure(env)
    r = run(LE, env, "issue", host, email)
    assert r.returncode != 0 and not any(c.startswith("certbot ") for c in calls(tmp))


@needs_tools
def test_issue_kraever_token_og_zone(box):
    tmp, env, *_ = box
    r = run(LE, env, "issue", "scada.laces.dk", "jan@laces.dk")
    assert r.returncode != 0 and "set-token" in r.stderr and not any(c.startswith("certbot ") for c in calls(tmp))
    assert run(LE, env, "set-token", stdin=TOKEN + "\n").returncode == 0
    r = run(LE, env, "issue", "scada.laces.dk", "jan@laces.dk")
    assert r.returncode != 0 and "set-target" in r.stderr and not any(c.startswith("certbot ") for c in calls(tmp))


@needs_tools
def test_issue_kraever_at_nginx_tls_er_sat_op_men_ikke_til_proeven(box):
    tmp, env, tls, *_ = box
    configure(env)
    shutil.rmtree(tls)
    r = run(LE, env, "issue", "scada.laces.dk", "jan@laces.dk")
    assert r.returncode != 0 and "--with-nginx" in r.stderr and not any(c.startswith("certbot ") for c in calls(tmp))
    assert run(LE, env, "issue", "scada.laces.dk", "jan@laces.dk", "--dry-run").returncode == 0      # selve DNS-forløbet kan prøves


@needs_tools
def test_issue_http01_bruger_webroot_og_kraever_hverken_token_eller_zone(box):
    tmp, env, *_ = box
    webroot = tmp / "acme"
    webroot.mkdir()
    env = {**env, "WEBROOT": webroot.as_posix()}
    r = run(LE, env, "issue", "scada.laces.dk", "jan@laces.dk", "--method", "http", "--dry-run")
    assert r.returncode == 0, r.stderr
    call = next(c for c in calls(tmp) if c.startswith("certbot "))
    assert f"--webroot -w {webroot.as_posix()}" in call and "--manual" not in call and "--dry-run" in call
    assert run(LE, env, "issue", "scada.laces.dk", "jan@laces.dk", "--method", "ftp").returncode != 0
    assert run(LE, env, "issue", "scada.laces.dk", "jan@laces.dk", "--method").returncode != 0
    webroot.rmdir()
    assert "Webroot" in run(LE, env, "issue", "scada.laces.dk", "jan@laces.dk", "--method", "http").stderr


@needs_tools
def test_issue_fejl_efterlader_det_nuvaerende_certifikat(box):
    tmp, env, tls, *_ = box
    configure(env)
    before = (tls / "fullchain.pem").read_bytes()
    r = run(LE, {**env, "FAKE_CERTBOT_FAIL": "1"}, "issue", "scada.laces.dk", "jan@laces.dk")
    assert r.returncode != 0 and "letsencrypt.log" in r.stderr and "status" in r.stderr
    assert (tls / "fullchain.pem").read_bytes() == before and not any(c.startswith("hook.sh") for c in calls(tmp))


@needs_tools
def test_ukendt_kommando_giver_brug(box):
    r = run(LE, box[1], "noget")
    assert r.returncode == 2 and "Brug" in r.stderr


# ------------------------------------------------------------------ deSEC-hook (certbot --manual-auth-hook)

def hook_env(env, **kw):
    return {**env, "CERTBOT_DOMAIN": "scada.laces.dk", "CERTBOT_VALIDATION": VALIDATION, **kw}


@needs_tools
def test_desec_hook_auth_saetter_txt_i_zonen_og_sender_tokenet_kun_i_en_headerfil(box):
    tmp, env, *_ = box
    configure(env)
    r = run(AUTH, hook_env(env), "auth")
    assert r.returncode == 0, r.stderr
    call = next(c for c in calls(tmp) if c.startswith("curl "))
    assert "-X PUT" in call and "https://desec.io/api/v1/domains/mitnavn.dedyn.io/rrsets/scada-acme/TXT/" in call
    assert TOKEN not in call and TOKEN not in r.stdout + r.stderr                       # aldrig på kommandolinjen eller i udskrift
    assert (tmp / "calls.log.hdr").read_text().strip() == f"Authorization: Token {TOKEN}"   # kun i headerfilen
    assert not Path((tmp / "calls.log.hdrfile").read_text().strip()[1:]).exists()           # og den er slettet igen
    body = json.loads((tmp / "calls.log.stdin").read_text())
    assert body == {"subname": "scada-acme", "type": "TXT", "ttl": 3600, "records": [f'"{VALIDATION}"']}


@needs_tools
@pytest.mark.parametrize("code, message", [("401", "afviste tokenet"), ("403", "afviste tokenet"), ("404", "findes ikke"), ("500", "HTTP 500")])
def test_desec_hook_auth_fejl_giver_forstaaelig_besked(box, code, message):
    tmp, env, *_ = box
    configure(env)
    r = run(AUTH, hook_env(env, FAKE_HTTP=code), "auth")
    assert r.returncode != 0 and message in r.stderr and TOKEN not in r.stderr


@needs_tools
def test_desec_hook_auth_fejler_uden_forbindelse(box):
    tmp, env, *_ = box
    configure(env)
    r = run(AUTH, hook_env(env, FAKE_CURL_FAIL="1"), "auth")
    assert r.returncode != 0


@needs_tools
@pytest.mark.parametrize("validation", ["", "kort", 'a"b' + "c" * 30, "x y" + "c" * 30, "x" * 150])
def test_desec_hook_afviser_forkert_udfordring(box, validation):
    tmp, env, *_ = box
    configure(env)
    r = run(AUTH, hook_env(env, CERTBOT_VALIDATION=validation), "auth")
    assert r.returncode != 0 and not any(c.startswith("curl ") for c in calls(tmp))


@needs_tools
def test_desec_hook_kraever_token_og_zone(box):
    tmp, env, *_ = box
    r = run(AUTH, hook_env(env), "auth")
    assert r.returncode != 0 and "deSEC-token" in r.stderr and not any(c.startswith("curl ") for c in calls(tmp))
    assert run(LE, env, "set-token", stdin=TOKEN + "\n").returncode == 0
    r = run(AUTH, hook_env(env), "auth")
    assert r.returncode != 0 and "set-target" in r.stderr and not any(c.startswith("curl ") for c in calls(tmp))


@needs_tools
def test_desec_hook_cleanup_sletter_posten_og_fejler_aldrig(box):
    tmp, env, *_ = box
    configure(env)
    assert run(AUTH, hook_env(env, FAKE_HTTP="204"), "cleanup").returncode == 0
    assert "-X DELETE" in next(c for c in calls(tmp) if c.startswith("curl "))
    assert run(AUTH, hook_env(env, FAKE_HTTP="404"), "cleanup").returncode == 0            # findes ikke = fint
    r = run(AUTH, hook_env(env, FAKE_HTTP="500"), "cleanup")
    assert r.returncode == 0 and "ADVARSEL" in r.stderr                                      # en oprydningsfejl må ikke vælte udstedelsen


@needs_tools
def test_desec_hook_ukendt_tilstand(box):
    assert run(AUTH, hook_env(box[1]), "noget").returncode != 0
