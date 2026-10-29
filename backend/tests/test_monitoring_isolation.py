import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from threading import Thread
import time
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from app.integrations import deployment_collector as sender
from app.integrations import deployment_exporter as exporter
from test_monitoring import source, write_state


def snapshot(tmp_path):
    write_state(tmp_path)
    return exporter.collect(tmp_path, read_docker=False, containers={})


@pytest.mark.skipif(os.geteuid() != 0, reason="Run permission integration tests as root inside the isolated test container")
def test_exporter_to_root_owned_atomic_snapshot_preserves_contract(tmp_path):
    report = snapshot(tmp_path)
    path = tmp_path / "snapshot.json"
    exporter.write_snapshot(path, report)
    first_inode = path.stat().st_ino
    assert stat.S_IMODE(path.stat().st_mode) == 0o640
    assert path.stat().st_uid == 0 and path.stat().st_gid == tmp_path.stat().st_gid
    assert sender.read_snapshot(path) == report
    updated = {**report, "observed_at": report["observed_at"] + 1}
    exporter.write_snapshot(path, updated)
    assert path.stat().st_ino != first_inode and sender.read_snapshot(path) == updated
    assert not list(tmp_path.glob(".snapshot-*"))
    from app.routers.monitoring import Report
    Report.model_validate_json(json.dumps(updated))


@pytest.mark.parametrize("kind", ["writable-file", "public-file", "symlink", "hardlink", "fifo", "writable-parent", "symlink-parent", "wrong-owner"])
@pytest.mark.skipif(os.geteuid() != 0, reason="Requires isolated root test container")
def test_sender_rejects_untrusted_files_and_paths(tmp_path, kind):
    path = tmp_path / "snapshot.json"
    exporter.write_snapshot(path, snapshot(tmp_path))
    if kind == "writable-file": path.chmod(0o660)
    elif kind == "public-file": path.chmod(0o644)
    elif kind == "symlink":
        target = tmp_path / "original"
        path.rename(target)
        path.symlink_to(target)
    elif kind == "hardlink": os.link(path, tmp_path / "linked")
    elif kind == "fifo":
        path.unlink()
        os.mkfifo(path, 0o600)
    elif kind == "writable-parent": tmp_path.chmod(0o770)
    elif kind == "symlink-parent":
        link = tmp_path / "alias"
        link.symlink_to(tmp_path, target_is_directory=True)
        path = link / "snapshot.json"
    elif kind == "wrong-owner": os.chown(path, 65534, 65534)
    with pytest.raises((ValueError, OSError)):
        sender.read_snapshot(path)


@pytest.mark.skipif(os.geteuid() != 0, reason="Requires isolated root test container")
def test_exporter_refuses_user_controlled_output_and_symlink_parents(tmp_path):
    report = snapshot(tmp_path)
    folder = tmp_path / "output"
    folder.mkdir(mode=0o770)
    folder.chmod(0o770)
    with pytest.raises(ValueError): exporter.write_snapshot(folder / "snapshot.json", report)
    folder.chmod(0o750)
    alias = tmp_path / "alias"
    alias.symlink_to(folder, target_is_directory=True)
    with pytest.raises(OSError): exporter.write_snapshot(alias / "snapshot.json", report)
    with pytest.raises(ValueError): exporter.write_snapshot("relative.json", report)
    assert not list(folder.iterdir())


@pytest.mark.skipif(os.geteuid() != 0, reason="Requires isolated root test container")
def test_sender_rejects_stale_future_secret_bearing_and_ambiguous_snapshots(tmp_path):
    path = tmp_path / "snapshot.json"
    valid = snapshot(tmp_path)
    for change in ({"observed_at": int(time.time()) - 91}, {"observed_at": int(time.time()) + 70},
                   {"secret": "must-not-be-sent"}, {"schema_version": True}, {"complete": "true"}):
        exporter.write_snapshot(path, {**valid, **change})
        with pytest.raises(ValueError): sender.read_snapshot(path)
    changed = copy.deepcopy(valid)
    changed["deployments"][0]["password"] = "must-not-be-sent"
    exporter.write_snapshot(path, changed)
    with pytest.raises(ValueError): sender.read_snapshot(path)
    path.write_text('{"schema_version":1,"schema_version":1}')
    with pytest.raises(ValueError, match="Duplicate"): sender.read_snapshot(path)
    path.write_bytes(b"x" * (sender.MAX_BODY + 1))
    with pytest.raises(ValueError): sender.read_snapshot(path)


@pytest.mark.parametrize("changes", [
    {"url": "https://user:secret@example.com"}, {"url": "https://example.com/?token=secret"},
    {"url": "https://example.com:0/"},
    {"running_count": True}, {"running_count": 2}, {"application_id": "x" * 201},
    {"metadata_error": "false"}, {"expires_at": -1}, {"container_count": None},
])
def test_sender_validates_metadata_before_any_upload(tmp_path, changes):
    report = snapshot(tmp_path)
    report["deployments"][0].update(changes)
    with pytest.raises(ValueError): sender.validate_snapshot(report)


def test_sender_refuses_root_docker_group_and_socket_acl(monkeypatch):
    monkeypatch.setattr(sender.os, "geteuid", lambda: 0)
    with pytest.raises(ValueError): sender.service_account()
    monkeypatch.setattr(sender.os, "geteuid", lambda: 10001)
    monkeypatch.setattr(sender.grp, "getgrnam", lambda name: SimpleNamespace(gr_gid=999))
    monkeypatch.setattr(sender.os, "getgroups", lambda: [999])
    monkeypatch.setattr(sender.os, "getegid", lambda: 10001)
    with pytest.raises(ValueError): sender.service_account()
    monkeypatch.setattr(sender.os, "getgroups", lambda: [])
    monkeypatch.setattr(sender.os, "access", lambda *args: True)
    with pytest.raises(ValueError): sender.service_account()
    monkeypatch.setattr(sender.os, "access", lambda *args: False)
    sender.service_account()


def test_token_file_is_private_and_environment_token_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / "token"
    path.write_text("a" * 54 + "\n")
    path.chmod(0o600)
    monkeypatch.setenv("SEMAPORTER_MONITOR_TOKEN_FILE", str(path))
    monkeypatch.delenv("SEMAPORTER_MONITOR_TOKEN", raising=False)
    assert sender.read_token() == "a" * 54
    path.chmod(0o640)
    with pytest.raises(ValueError): sender.read_token()
    path.chmod(0o600)
    monkeypatch.setenv("SEMAPORTER_MONITOR_TOKEN", "a" * 54)
    with pytest.raises(ValueError): sender.read_token()


def test_exporter_has_no_credentials_and_requires_root(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["exporter", "--output", str(tmp_path / "snapshot.json")])
    monkeypatch.setattr(exporter.os, "geteuid", lambda: 10001)
    with pytest.raises(SystemExit): exporter.main()
    monkeypatch.setattr(exporter.os, "geteuid", lambda: 0)
    monkeypatch.setenv("SEMAPORTER_MONITOR_TOKEN_FILE", "/private/token")
    with pytest.raises(SystemExit): exporter.main()


def test_sender_does_not_restamp_or_repeatedly_upload_the_same_snapshot(tmp_path, monkeypatch):
    report = snapshot(tmp_path)
    sent = []
    monkeypatch.setattr(sys, "argv", ["sender", "--snapshot", "/snapshot"])
    monkeypatch.setenv("SEMAPORTER_URL", "https://semaporter.example")
    monkeypatch.setattr(sender, "service_account", lambda: None)
    monkeypatch.setattr(sender, "read_token", lambda: "a" * 54)
    monkeypatch.setattr(sender, "read_snapshot", lambda path: report)
    monkeypatch.setattr(sender, "send", lambda url, token, data: sent.append(copy.deepcopy(data)) or True)
    sleeps = []
    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2: raise KeyboardInterrupt()
    monkeypatch.setattr(sender.time, "sleep", sleep)
    with pytest.raises(KeyboardInterrupt): sender.main()
    assert sent == [report] and sent[0]["observed_at"] == report["observed_at"]


def test_retry_after_restart_accepts_conflict_but_never_hides_auth_failures(monkeypatch):
    for code in (409, 401):
        def opener(*args):
            def open(*args, **kwargs): raise HTTPError("https://example", code, "failure", {}, None)
            return SimpleNamespace(open=open)
        monkeypatch.setattr(sender, "build_opener", opener)
        if code == 409: assert sender.send("https://example", "a" * 54, {}) is False
        else:
            with pytest.raises(HTTPError): sender.send("https://example", "a" * 54, {})


@pytest.mark.skipif(os.geteuid() != 0, reason="Requires privilege drop inside an isolated root test container")
def test_real_unprivileged_sender_can_only_read_export_and_upload_to_api(tmp_path, client, admin_headers):
    # A fresh, network-isolated test container supplies root solely so we can
    # drop to nobody and exercise Linux DAC. No host Docker socket is mounted.
    assert os.geteuid() == 0
    for parent in [tmp_path, *tmp_path.parents]:
        if parent == Path("/tmp"): break
        parent.chmod(0o755)
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o750)
    os.chown(shared, 0, 65534)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    secret = private / "application.env"
    secret.write_text("not-for-the-sender")
    path = shared / "snapshot.json"
    exporter.write_snapshot(path, snapshot(tmp_path))
    src = source(client, admin_headers)
    credential = shared / "token"
    credential.write_text(src["token"])
    credential.chmod(0o400)
    os.chown(credential, 65534, 65534)
    received = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append(json.loads(body))
            result = client.post(self.path, content=body, headers={"Authorization": self.headers["Authorization"]})
            self.send_response(result.status_code)
            self.end_headers()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        environment = {"PATH": "/usr/bin:/bin", "SEMAPORTER_URL": f"http://127.0.0.1:{server.server_port}",
                       "SEMAPORTER_MONITOR_TOKEN_FILE": str(credential)}
        result = subprocess.run([sys.executable, "-I", sender.__file__, "--snapshot", str(path), "--once", "--allow-http"],
            env=environment, capture_output=True, text=True, timeout=20, user=65534, group=65534, extra_groups=[], cwd="/tmp")
        assert result.returncode == 0, result.stderr
        assert len(received) == 1 and received[0]["observed_at"] == sender.read_snapshot(path)["observed_at"]
        assert client.get("/api/admin/deployments").json()["deployments"][0]["deployment_id"] == "demo-1"
        # The exact same uid cannot modify the status file/directory or read
        # another application's private files. Its own credential is readable.
        code = "import os,sys; a,b,c=sys.argv[1:]; assert os.access(a,os.R_OK); assert not os.access(a,os.W_OK); assert not os.access(os.path.dirname(a),os.W_OK); assert not os.access(b,os.R_OK); assert os.access(c,os.R_OK)"
        result = subprocess.run([sys.executable, "-I", "-c", code, str(path), str(secret), str(credential)],
            capture_output=True, text=True, timeout=5, user=65534, group=65534, extra_groups=[], cwd="/tmp")
        assert result.returncode == 0, result.stderr
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
