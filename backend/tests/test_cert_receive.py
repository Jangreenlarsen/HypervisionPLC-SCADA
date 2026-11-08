"""Certifikat fra proxyen (v4.11.0): deploy/cert-receive.sh tager imod fullchain.pem + privkey.pem som tar på stdin og
installerer dem med den rigtige cert-deploy.sh (falsk nginx/systemctl, rigtig openssl)."""

import io
import tarfile

from tests.test_letsencrypt import DEPLOY, HOOK, box, make_cert, needs_tools, run  # noqa: F401 — fixture

RECV = DEPLOY / "cert-receive.sh"


def pack(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def setup(box):
    tmp, env, tls, lineage, state, _ = box
    env = {**env, "HOOK": str(HOOK), "LIVE": (tmp / "recv").as_posix(), "WANT_NAME": "scada.laces.dk"}
    env.pop("RENEWED_LINEAGE")
    good = pack({"fullchain.pem": (lineage / "fullchain.pem").read_bytes(), "privkey.pem": (lineage / "privkey.pem").read_bytes()})
    return tmp, env, tls, lineage, state, good


@needs_tools
def test_receive_installs_the_proxys_certificate_and_logs_it(box):
    tmp, env, tls, lineage, state, good = setup(box)
    r = run(RECV, env, stdin=good)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tls / "fullchain.pem").read_bytes() == (lineage / "fullchain.pem").read_bytes()
    assert (tls / "privkey.pem").read_bytes() == (lineage / "privkey.pem").read_bytes()
    assert "installeret:" in (state / "cert-receive.log").read_text()
    again = run(RECV, env, stdin=good)                                    # samme certifikat igen: intet at gøre
    assert again.returncode == 0 and "uændret" in again.stdout


@needs_tools
def test_receive_rejects_a_certificate_for_another_name(box):
    tmp, env, tls, lineage, state, _ = setup(box)
    other = make_cert(tmp / "other", "evil.example")
    before = (tls / "fullchain.pem").read_bytes()
    r = run(RECV, env, stdin=pack({"fullchain.pem": other[0].read_bytes(), "privkey.pem": other[1].read_bytes()}))
    assert r.returncode == 1 and "gælder ikke for scada.laces.dk" in r.stdout
    assert (tls / "fullchain.pem").read_bytes() == before


@needs_tools
def test_receive_rejects_missing_files_garbage_and_wrong_key(box):
    tmp, env, tls, lineage, state, _ = setup(box)
    before = (tls / "fullchain.pem").read_bytes()
    assert run(RECV, env, stdin=pack({"fullchain.pem": (lineage / "fullchain.pem").read_bytes()})).returncode == 1
    assert run(RECV, env, stdin=b"ikke en tar").returncode == 1
    assert run(RECV, env, stdin=pack({"fullchain.pem": b"x", "privkey.pem": b"y"})).returncode == 1
    other = make_cert(tmp / "o2", "scada.laces.dk")
    wrong = pack({"fullchain.pem": (lineage / "fullchain.pem").read_bytes(), "privkey.pem": other[1].read_bytes()})
    r = run(RECV, env, stdin=wrong)                                       # nøglen passer ikke: cert-deploy.sh afviser
    assert r.returncode == 1 and "afviste" in r.stdout
    assert (tls / "fullchain.pem").read_bytes() == before
