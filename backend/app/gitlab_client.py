"""Project-scoped GitLab REST client. No redirects or automatic write retries."""
from __future__ import annotations

import base64
import binascii
import re
import ssl
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from app.config import get_settings

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
MAX_FILES = 400
SHA = re.compile(r"^[a-f0-9]{40,64}$")


class GitLabError(RuntimeError):
    def __init__(self, message: str, *, uncertain=False, status=None):
        super().__init__(message)
        self.uncertain, self.status = uncertain, status


def decode_file(value: str) -> bytes:
    try:
        if len(value) > (MAX_FILE_BYTES + 2) * 4 // 3 + 4:
            raise ValueError("Datei überschreitet 10 MB.")
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Ungültige oder zu große Datei (maximal 10 MB).") from exc
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Datei überschreitet 10 MB.")
    return raw


def safe_file_path(path: str) -> str:
    if (not isinstance(path, str) or len(path) > 300 or not path
            or any((segment != ".gitkeep" and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", segment))
                   or segment in {".", ".."} for segment in path.split("/"))):
        raise ValueError("Unsicherer Repository-Dateipfad.")
    return path


class GitLabClient:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.base = config["base_url"].rstrip("/") + "/api/v4/"
        self.project = f"projects/{int(config['project_id'])}"
        settings = get_settings()
        self.timeout = settings.gitlab_request_timeout_seconds
        try:
            self.verify = ssl.create_default_context(cafile=settings.gitlab_ca_bundle or None)
        except (OSError, ssl.SSLError) as exc:
            raise GitLabError("Die konfigurierte GitLab-CA konnte nicht geladen werden.") from exc

    async def request(self, method: str, path: str, *, params=None, data=None, absence_ok=False):
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=self.verify, follow_redirects=False, trust_env=False) as client:
                async with client.stream(method, self.base + path, params=params, json=data,
                        headers={"PRIVATE-TOKEN": self.config["token"], "Accept": "application/json"}) as response:
                    if absence_ok and response.status_code == 404:
                        return None
                    if response.status_code >= 300:
                        raise GitLabError(f"GitLab-Anfrage fehlgeschlagen (HTTP {response.status_code}).",
                            uncertain=method != "GET" and (response.status_code >= 500 or response.status_code in {408, 429}),
                            status=response.status_code)
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 4 * MAX_FILE_BYTES:
                            raise GitLabError("GitLab-Antwort überschreitet das Größenlimit.", uncertain=method != "GET")
                    import json
                    try:
                        return json.loads(body)
                    except ValueError as exc:
                        raise GitLabError("GitLab lieferte keine gültige JSON-Antwort.", uncertain=method != "GET") from exc
        except httpx.TransportError as exc:
            raise GitLabError("GitLab ist nicht erreichbar. Bereits gestartete Schreibvorgänge zuerst abgleichen.",
                              uncertain=method != "GET") from exc

    async def get_project(self):
        value = await self.request("GET", self.project)
        if not isinstance(value, dict) or value.get("id") != self.config["project_id"]:
            raise GitLabError("GitLab bestätigte die konfigurierte Projekt-ID nicht.")
        return value

    async def branch(self, name: str, *, absence_ok=False):
        value = await self.request("GET", f"{self.project}/repository/branches/{quote(name, safe='')}", absence_ok=absence_ok)
        if value is not None and (not isinstance(value, dict) or not SHA.fullmatch(str(value.get("commit", {}).get("id", "")))):
            raise GitLabError("GitLab lieferte keine eindeutige Branch-Revision.")
        return value

    async def pages(self, path: str, params: dict | None = None):
        rows = []
        for page in range(1, 22):
            batch = await self.request("GET", path, params={**(params or {}), "per_page": 100, "page": page})
            if not isinstance(batch, list):
                raise GitLabError("GitLab lieferte keine gültige Liste.")
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise GitLabError("GitLab-Liste ist zu groß; Projektumfang eingrenzen.")

    async def file(self, path: str, sha: str, *, absence_ok=False):
        safe_file_path(path)
        value = await self.request("GET", f"{self.project}/repository/files/{quote(path, safe='')}",
                                   params={"ref": sha}, absence_ok=absence_ok)
        if value is None:
            return None
        try:
            if value.get("encoding") != "base64" or value.get("file_path") != path:
                raise ValueError()
            # GitLab wraps base64 in line breaks. Store one canonical representation.
            raw = decode_file("".join(value["content"].splitlines()))
            return base64.b64encode(raw).decode()
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise GitLabError("Repository-Datei ist ungültig oder größer als 10 MB.") from exc

    async def snapshot(self, sha: str):
        if not SHA.fullmatch(sha):
            raise ValueError("Vollständige Commit-SHA erforderlich.")
        files, size = {}, 0
        for folder in ("programs", "database-types", "mail"):
            tree = await self.pages(f"{self.project}/repository/tree", {"path": folder, "ref": sha, "recursive": True})
            for entry in tree:
                if entry.get("type") == "tree":
                    continue
                path = safe_file_path(entry.get("path"))
                if not path.startswith(folder + "/") or entry.get("type") != "blob" or entry.get("mode") not in {"100644", "100755"}:
                    raise GitLabError("Verlinkte, fremde oder spezielle Dateien werden nicht unterstützt.")
                if len(files) >= MAX_FILES:
                    raise GitLabError("Katalog umfasst mehr als 400 Dateien.")
                content = await self.file(path, sha)
                size += len(decode_file(content))
                if size > MAX_SNAPSHOT_BYTES:
                    raise GitLabError("Katalog überschreitet 32 MB; große Datensätze separat verkleinern.")
                files[path] = content
        return files

    async def commit(self, payload):
        return await self.request("POST", f"{self.project}/repository/commits", data=payload)

    async def merge_requests(self, branch):
        return await self.pages(f"{self.project}/merge_requests", {"scope": "all", "state": "all",
            "source_branch": branch, "target_branch": self.config["base_branch"]})

    async def merge_request(self, iid):
        return await self.request("GET", f"{self.project}/merge_requests/{int(iid)}")

    async def create_merge_request(self, payload):
        return await self.request("POST", f"{self.project}/merge_requests", data=payload)

    async def pipelines(self, sha):
        return await self.pages(f"{self.project}/pipelines", {"sha": sha, "order_by": "id", "sort": "desc"})

    def web_link(self, value):
        if not isinstance(value, str):
            return None
        base, target = urlsplit(self.config["base_url"]), urlsplit(value)
        if (target.scheme == base.scheme and target.netloc == base.netloc and not target.username
                and not target.password and target.path.startswith(base.path.rstrip("/") + "/")):
            return value
        return None
