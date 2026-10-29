#!/usr/bin/env python3
"""Unprivileged snapshot sender. No Docker, metadata scanning or subprocesses.

Run separately from semaporter-exporter.py. Only a root-owned JSON snapshot
and a scoped monitoring token are needed. Both scripts use only the stdlib.
"""
from __future__ import annotations

import argparse
import grp
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BODY = 2_000_000
MAX_AGE = 90
TEXT_FIELDS = {"application_id", "application_name", "release_id", "tenant_slug", "runtime_scope_id",
               "database_type", "provider_id", "database_mode", "dataset_id", "source_git_commit"}
TIME_FIELDS = {"created_at", "ready_at", "expires_at"}
COUNT_FIELDS = {"container_count", "running_count", "unhealthy_count", "starting_count"}
FIELDS = TEXT_FIELDS | TIME_FIELDS | COUNT_FIELDS | {"deployment_id", "url", "host_port", "lifecycle_status", "metadata_error"}
WARNINGS = {"root_unavailable", "metadata_unreadable", "docker_unavailable", "limit_exceeded"}


def trusted_parent(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path.name in {"", ".", "/"}:
        raise ValueError("Snapshot must be an absolute file path")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parent.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            if info.st_uid != 0 or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):
                raise ValueError("Snapshot ancestors must be root-controlled")
        if os.fstat(fd).st_mode & 0o022:
            raise ValueError("Snapshot directory is writable by another account")
        return fd
    except BaseException:
        os.close(fd)
        raise


def safe_url(value, *, base=False, allow_http=False):
    if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 33 for c in value):
        raise ValueError("Invalid URL")
    parts = urlsplit(value)
    port = parts.port
    if (parts.scheme not in ({"http", "https"} if allow_http or not base else {"https"}) or not parts.hostname
            or parts.username is not None or parts.password is not None or parts.query or parts.fragment
            or (base and parts.path not in {"", "/"}) or (port is not None and not 1 <= port <= 65535)):
        raise ValueError("Invalid URL")
    return value


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def validate_snapshot(report, now=None):
    now = time.time() if now is None else now
    if (not isinstance(report, dict) or set(report) != {"schema_version", "observed_at", "complete", "deployments", "warnings"}
            or type(report["schema_version"]) is not int or report["schema_version"] != 1
            or type(report["complete"]) is not bool or not integer(report["observed_at"], 1, 32_503_680_000)
            or not now - MAX_AGE <= report["observed_at"] <= now + 60):
        raise ValueError("Invalid or stale snapshot; wait for the offline exporter")
    warnings, rows = report["warnings"], report["deployments"]
    if (not isinstance(warnings, list) or len(warnings) > 4 or any(not isinstance(w, str) or w not in WARNINGS for w in warnings)
            or (report["complete"] and warnings) or not isinstance(rows, list) or len(rows) > 1000):
        raise ValueError("Invalid snapshot structure")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError("Unknown or missing deployment fields")
        identifier = row["deployment_id"]
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", identifier) or identifier in seen:
            raise ValueError("Invalid or duplicate deployment ID")
        seen.add(identifier)
        for key in TEXT_FIELDS:
            if not isinstance(row[key], str) or len(row[key]) > 200 or any(ord(c) < 32 for c in row[key]):
                raise ValueError("Invalid metadata text")
        if row["url"]:
            safe_url(row["url"])
        elif row["url"] != "":
            raise ValueError("Invalid URL")
        for key in TIME_FIELDS | COUNT_FIELDS | {"host_port"}:
            low, high = (1, 65535) if key == "host_port" else (0, 10000) if key in COUNT_FIELDS else (1 if key == "expires_at" else 0, 32_503_680_000)
            if row[key] is not None and not integer(row[key], low, high):
                raise ValueError("Invalid numeric metadata")
        if row["lifecycle_status"] not in ("preparing", "running", "cleanup_pending", "unknown") or type(row["metadata_error"]) is not bool:
            raise ValueError("Invalid lifecycle state")
        counts = [row[k] for k in COUNT_FIELDS]
        if (any(c is None for c in counts) and not all(c is None for c in counts)) or (row["container_count"] is not None
                and (row["running_count"] > row["container_count"] or row["unhealthy_count"] + row["starting_count"] > row["running_count"])):
            raise ValueError("Invalid container counts")
    return report


def read_snapshot(path):
    directory = trusted_parent(path)
    try:
        fd = os.open(Path(path).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o027 or info.st_nlink != 1 or info.st_size > MAX_BODY:
            raise ValueError("Snapshot must be a protected root-owned regular file (0640)")
        body = stream.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise ValueError("Snapshot too large")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    return validate_snapshot(json.loads(body, object_pairs_hook=unique_object))


def service_account():
    if os.geteuid() == 0:
        raise ValueError("Run the network sender as the restricted service account, never as root")
    try:
        docker_group = grp.getgrnam("docker").gr_gid
    except KeyError:
        docker_group = None
    if docker_group in {*os.getgroups(), os.getegid()} or os.access("/var/run/docker.sock", os.W_OK):
        raise ValueError("The sender account must not have Docker access")


def read_token():
    path = os.environ.get("SEMAPORTER_MONITOR_TOKEN_FILE")
    if not path or os.environ.get("SEMAPORTER_MONITOR_TOKEN"):
        raise ValueError("Use SEMAPORTER_MONITOR_TOKEN_FILE; do not put the token in the environment")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid not in {0, os.geteuid()} or info.st_mode & 0o077
                or info.st_nlink != 1 or info.st_size > 201):
            raise ValueError("Token must be a private regular credential file (0400/0600)")
        value = stream.read(202).decode("ascii").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{30,200}", value):
        raise ValueError("Invalid collector token")
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send(url, token, report):
    body = json.dumps(report, separators=(",", ":"), allow_nan=False).encode()
    if len(body) > MAX_BODY:
        raise ValueError("Snapshot too large")
    request = Request(url.rstrip("/") + "/api/monitoring/report", body,
                      {"Authorization": "Bearer " + token, "Content-Type": "application/json"}, method="POST")
    try:
        with build_opener(NoRedirect()).open(request, timeout=10) as response:
            if response.status != 204:
                raise ValueError("Unexpected response")
    except HTTPError as exc:
        if exc.code != 409:
            raise
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, help="Root-owned JSON snapshot from the offline exporter")
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--allow-http", action="store_true", help="Explicitly allow an unencrypted internal test connection")
    args = parser.parse_args()
    try:
        if args.interval < 10:
            raise ValueError("Interval must be at least 10 seconds")
        service_account()
        url = safe_url(os.environ.get("SEMAPORTER_URL", ""), base=True, allow_http=args.allow_http)
        token = read_token()
    except (OSError, ValueError):
        parser.error("Use a non-root account without Docker access, a private token file, a valid HTTPS URL and interval >= 10.")
    last_sent = None
    while True:
        try:
            report = read_snapshot(args.snapshot)
            if report["observed_at"] != last_sent:
                accepted = send(url, token, report)
                last_sent = report["observed_at"]
                print(f"Snapshot {'accepted' if accepted else 'already received or superseded'}: {len(report['deployments'])} deployments; complete={report['complete']}", flush=True)
            else:
                print("Waiting for a new offline snapshot", flush=True)
        except Exception as exc:
            code = getattr(exc, "code", None)
            print(f"Collector report failed: {type(exc).__name__}" + (f" HTTP {code}" if code else ""), file=sys.stderr, flush=True)
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
