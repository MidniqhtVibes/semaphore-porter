#!/usr/bin/env python3
"""Local, privileged, offline deployment exporter (stdlib only).

No compose files, task logs, application environments, secrets or Docker inspect
results are read. This file also runs independently of the Semaporter backend.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import secrets
from urllib.parse import urlsplit

MAX_DEPLOYMENTS = 1000
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")


def read_file(path, maximum=131_072):
    # Do not follow symlinks or open pipes/devices in a deployment directory.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise ValueError("invalid metadata file")
        data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError("metadata file too large")
        return data.decode("utf-8")


def env_values(path):
    if not path.exists():
        return {}
    values = {}
    for line in read_file(path).splitlines():
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or key in values:
            raise ValueError("ambiguous metadata")
        values[key] = value
    return values


def text(value, maximum=200):
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ValueError("invalid metadata text")
    return value


def epoch(value):
    if value in (None, "", 0, "0"):
        return None
    result = int(value)
    if not 0 < result <= 32_503_680_000:
        raise ValueError("invalid timestamp")
    return result


def safe_endpoint(value):
    value = text(value, 2000)
    if not value:
        return ""
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or any(ord(c) < 33 for c in value)):
        return ""  # Never transmit credential-bearing URLs.
    _ = parsed.port
    return value


def read_deployment(directory, containers):
    meta = env_values(directory / "metadata.env")
    status = env_values(directory / "status.env")
    state = {}
    state_path = directory / "state.json"
    if state_path.exists():
        state = json.loads(read_file(state_path))
        if not isinstance(state, dict) or state.get("schema_version") != 7:
            raise ValueError("unsupported state schema")
    if not state and not meta and not status:
        return None
    identifier = state.get("deployment_id", meta.get("DEPLOYMENT_ID", directory.name))
    if identifier != directory.name or not IDENTIFIER.fullmatch(identifier):
        raise ValueError("deployment identity mismatch")
    app, database, dataset, endpoint, lifecycle = (state.get(k, {}) for k in ("application", "database", "dataset", "endpoint", "lifecycle"))
    if not all(isinstance(v, dict) for v in (app, database, dataset, endpoint, lifecycle)):
        raise ValueError("invalid state shape")
    raw_phase = status.get("STATUS", "unknown")
    phase = raw_phase if raw_phase in {"running", "cleanup_pending", "unknown"} else "preparing"
    host_port = endpoint.get("host_port", meta.get("HOST_PORT"))
    host_port = int(host_port) if host_port not in (None, "", "0", 0) else None
    if host_port is not None and not 1 <= host_port <= 65535:
        raise ValueError("invalid port")
    counts = containers.get(identifier, []) if containers is not None else None
    return {
        "deployment_id": identifier,
        "application_id": text(app.get("id", meta.get("APPLICATION_ID"))),
        "application_name": text(app.get("display_name", meta.get("APPLICATION_ID"))),
        "release_id": text(app.get("release_id", meta.get("APPLICATION_RELEASE_ID"))),
        "tenant_slug": text(state.get("tenant_slug", meta.get("TENANT_SLUG"))),
        "runtime_scope_id": text(state.get("runtime_scope_id", meta.get("RUNTIME_SCOPE_ID"))),
        "database_type": text(database.get("type", meta.get("DATABASE_TYPE"))),
        "provider_id": text(database.get("provider_id", meta.get("PROVIDER_ID"))),
        "database_mode": text(database.get("mode", meta.get("DATABASE_MODE"))),
        "dataset_id": text(dataset.get("id", meta.get("DATASET_ID"))),
        "source_git_commit": text(meta.get("SOURCE_GIT_COMMIT")),
        "url": safe_endpoint(endpoint.get("url", "")),
        "host_port": host_port,
        "created_at": epoch(lifecycle.get("created_at", meta.get("CREATED_AT"))),
        "ready_at": epoch(lifecycle.get("ready_at", meta.get("READY_AT"))),
        # status.env is updated by lifecycle operations; prefer it over state.json.
        "expires_at": epoch(status.get("EXPIRES_AT", lifecycle.get("expires_at", meta.get("EXPIRES_AT")))),
        "lifecycle_status": phase,
        "container_count": len(counts) if counts is not None else None,
        "running_count": sum(c["State"] == "running" for c in counts) if counts is not None else None,
        "unhealthy_count": sum(c["State"] == "running" and "(unhealthy)" in c["Status"] for c in counts) if counts is not None else None,
        "starting_count": sum(c["State"] == "running" and "(health: starting)" in c["Status"] for c in counts) if counts is not None else None,
        "metadata_error": not bool(status),
    }


def docker_containers(docker_bin="/usr/bin/docker"):
    if not Path(docker_bin).is_absolute():
        raise ValueError("Docker executable must be an absolute trusted path")
    result = subprocess.run([docker_bin, "ps", "--all", "--format", "{{json .}}"],
                            capture_output=True, text=True, timeout=10, check=True,
                            env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LC_ALL": "C",
                                 "DOCKER_CONFIG": "/nonexistent", "DOCKER_HOST": "unix:///var/run/docker.sock",
                                 "DOCKER_CONTEXT": "default"})
    projects = {}
    for line in result.stdout.splitlines():
        row = json.loads(line)
        labels = dict(part.split("=", 1) for part in row.get("Labels", "").split(",") if "=" in part)
        project = labels.get("com.docker.compose.project")
        if project:
            projects.setdefault(project, []).append({"State": row["State"], "Status": row["Status"]})
    return projects


def collect(root, *, containers=None, read_docker=True, docker_bin="/usr/bin/docker"):
    root = Path(root)
    warnings, deployments = set(), []
    if read_docker:
        try:
            containers = docker_containers(docker_bin)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            warnings.add("docker_unavailable")
            containers = None
    try:
        if root.is_symlink() or not root.is_dir():
            raise OSError("root unavailable")
        directories = sorted(root.iterdir())
        for directory in directories:
            if directory.is_symlink() or not directory.is_dir() or not IDENTIFIER.fullmatch(directory.name):
                continue
            if not any((directory / name).exists() for name in ("state.json", "status.env", "metadata.env")):
                continue
            if len(deployments) >= MAX_DEPLOYMENTS:
                warnings.add("limit_exceeded")
                break
            try:
                item = read_deployment(directory, containers)
                if item:
                    deployments.append(item)
                    if item["metadata_error"]:
                        warnings.add("metadata_unreadable")
            except (OSError, ValueError, TypeError, KeyError):
                warnings.add("metadata_unreadable")
    except OSError:
        warnings.add("root_unavailable")
    return {"schema_version": 1, "observed_at": int(time.time()), "complete": not bool(warnings),
            "deployments": deployments, "warnings": sorted(warnings)}


def output_directory(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path.name in {"", ".", "/"}:
        raise ValueError("Output must be an absolute file path")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parent.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            if info.st_uid != 0 or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):
                raise ValueError("Output ancestors must be root-controlled")
        info = os.fstat(fd)
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("Output directory must be root-owned and not group/world writable")
        return fd
    except BaseException:
        os.close(fd)
        raise


def write_snapshot(path, report):
    body = json.dumps(report, separators=(",", ":"), allow_nan=False).encode()
    if len(body) > 2_000_000:
        raise ValueError("Snapshot too large")
    directory = output_directory(path)
    temporary = ".snapshot-" + secrets.token_hex(16)
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            os.fchown(stream.fileno(), 0, os.fstat(directory).st_gid)
            os.fchmod(stream.fileno(), 0o640)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, Path(path).name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass
        os.close(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/opt/semaphore-deployments")
    parser.add_argument("--output", required=True, help="Absolute path in a root-controlled directory")
    parser.add_argument("--docker-bin", default="/usr/bin/docker")
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("The offline exporter requires root; run the network sender as the service account instead.")
    if any(os.environ.get(k) for k in ("SEMAPORTER_URL", "SEMAPORTER_MONITOR_TOKEN", "SEMAPORTER_MONITOR_TOKEN_FILE")):
        parser.error("Do not pass network configuration or tokens to the offline exporter.")
    try:
        report = collect(args.root, docker_bin=args.docker_bin)
        write_snapshot(args.output, report)
        print(f"Snapshot written: {len(report['deployments'])} deployments; complete={report['complete']}", flush=True)
        return 0
    except Exception as exc:
        print(f"Export failed: {type(exc).__name__}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
