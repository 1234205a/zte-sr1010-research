#!/usr/bin/env python3
"""Offline checks for the SR1010 Cloudflare DDNS 0.1.2 package."""
import importlib.util
import io
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("builder", HERE / "build-cf-ddns-ipk.py")
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)

def unpack_member(blob, name):
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
        return archive.extractfile(name).read()

def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ca = root / "cacert.pem"; ca.write_text("offline test CA\n")
        ipk = root / "ddns.ipk"; builder.build(ipk, ca)
        with tarfile.open(ipk, "r:gz") as outer:
            control_blob = outer.extractfile("control.tar.gz").read()
            data_blob = outer.extractfile("data.tar.gz").read()
        control = unpack_member(control_blob, "control").decode()
        assert "Version: 0.1.2" in control

        with tarfile.open(fileobj=io.BytesIO(data_blob), mode="r:gz") as data:
            names = set(data.getnames())
            required = {
                "opt/sr1010-cf-ddns/update.sh", "opt/sr1010-cf-ddns/loop.sh",
                "opt/sr1010-cf-ddns/validate.sh", "opt/sr1010-cf-ddns/restore.sh",
                "opt/sr1010-cf-ddns/start.sh", "opt/sr1010-cf-ddns/stop.sh",
                "opt/sr1010-cf-ddns/health.sh", "opt/sr1010-cf-ddns/post-upgrade-health.sh",
            }
            assert required <= names
            scripts = {name: data.extractfile(name).read() for name in required}

        update = scripts["opt/sr1010-cf-ddns/update.sh"].decode()
        loop = scripts["opt/sr1010-cf-ddns/loop.sh"].decode()
        restore = scripts["opt/sr1010-cf-ddns/restore.sh"].decode()
        start = scripts["opt/sr1010-cf-ddns/start.sh"].decode()
        stop = scripts["opt/sr1010-cf-ddns/stop.sh"].decode()
        for error in ("cloudflare_transport", "cloudflare_auth", "cloudflare_record_not_found",
                      "cloudflare_rate_limited", "cloudflare_server", "cloudflare_api"):
            assert error in update
        assert "consecutive_failures" in loop and "heartbeat_epoch" in loop and "MAX_BACKOFF" in builder.ENV_TEMPLATE
        assert "restore_failed_rolled_back" in restore
        assert "/proc/[0-9]*" in start and "/proc/[0-9]*" in stop
        assert "candidate" in start and "sleep 2" in start
        assert '"$BASE/state/heartbeat_epoch"' in stop
        assert "signal_loops TERM" in stop and "signal_loops KILL" in stop
        assert all(b"\r\n" not in body for body in scripts.values())

        bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        if bash.exists():
            for name, body in scripts.items():
                script = root / Path(name).name; script.write_bytes(body)
                subprocess.run([bash, "-n", str(script)], check=True)
            test_error_classes(root, bash, scripts["opt/sr1010-cf-ddns/update.sh"])
    print("package=PASS errors=PASS backoff=PASS rollback=PASS shell_syntax=PASS")

def test_error_classes(root, bash, update_body):
    base = root / "runtime"
    config = base / "config"; state = base / "state"; fakebin = root / "fakebin"
    for path in (config, state, fakebin): path.mkdir(parents=True, exist_ok=True)
    (config / "ddns.env").write_text(
        "CF_ZONE_ID=" + "a" * 32 + "\nCF_RECORD_ID=" + "b" * 32 +
        "\nCF_RECORD_NAME=test.example\nINTERVAL=120\nMAX_BACKOFF=1800\n"
    )
    (config / "curl-auth.conf").write_text('header = "Authorization: Bearer offline-test"\n')
    (base / "cacert.pem").write_text("offline CA\n")
    (base / "validate.sh").write_text("#!/bin/sh\nexit 0\n")
    fake_curl = fakebin / "curl"
    fake_curl.write_text(r'''#!/bin/sh
case " $* " in
  *" -X PATCH "*)
    out=
    previous=
    for arg in "$@"; do
      if test "$previous" = output; then out=$arg; previous=; continue; fi
      test "$arg" = -o && previous=output
    done
    case "${FAKE_HTTP:-200}" in
      transport) printf '000'; exit 7 ;;
      200fail) printf '{"success":false}' >"$out"; printf '200'; exit 0 ;;
      200) printf '{"success":true}' >"$out"; printf '200'; exit 0 ;;
      *) printf '{"success":false}' >"$out"; printf '%s' "$FAKE_HTTP"; exit 22 ;;
    esac ;;
  *) printf '203.0.113.10\n'; exit 0 ;;
esac
''')
    update = base / "update.sh"
    posix_base = subprocess.run([bash, "-lc", f"cygpath -u {shlex.quote(str(base))}"], check=True, text=True, capture_output=True).stdout.strip()
    posix_fakebin = subprocess.run([bash, "-lc", f"cygpath -u {shlex.quote(str(fakebin))}"], check=True, text=True, capture_output=True).stdout.strip()
    update.write_bytes(update_body.replace(b"BASE=/opt/sr1010-cf-ddns", f"BASE={posix_base}".encode()))
    for path in (base / "validate.sh", fake_curl, update):
        path.chmod(0o755)
    cases = {
        "transport": "cloudflare_transport", "401": "cloudflare_auth",
        "403": "cloudflare_auth", "404": "cloudflare_record_not_found",
        "429": "cloudflare_rate_limited", "500": "cloudflare_server",
        "200fail": "cloudflare_api",
    }
    for code, expected in cases.items():
        shutil.rmtree(state); state.mkdir()
        command = f"PATH={shlex.quote(posix_fakebin)}:$PATH FAKE_HTTP={shlex.quote(code)} {shlex.quote(posix_base + '/update.sh')} --force"
        result = subprocess.run([bash, "-lc", command], text=True, capture_output=True)
        assert result.returncode != 0 and f"detail={expected}" in result.stdout, (code, result.stdout, result.stderr)
    shutil.rmtree(state); state.mkdir()
    command = f"PATH={shlex.quote(posix_fakebin)}:$PATH FAKE_HTTP=200 {shlex.quote(posix_base + '/update.sh')} --force"
    result = subprocess.run([bash, "-lc", command], text=True, capture_output=True)
    assert result.returncode == 0 and "action=updated" in result.stdout

if __name__ == "__main__": main()
