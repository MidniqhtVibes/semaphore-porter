from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx


class SemaphoreError(RuntimeError):
    def __init__(self, message: str, *, uncertain: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.uncertain = uncertain
        self.status_code = status_code


@dataclass(frozen=True)
class SemaphoreConnection:
    base_url: str
    token: str
    proxy_url: str | None = None
    timeout_seconds: float = 30


class SemaphoreClient:
    """Narrow Semaphore UI client; no generic browser-controlled proxy endpoint."""

    def __init__(self, connection: SemaphoreConnection):
        parts = urlsplit(connection.base_url.strip())
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            raise SemaphoreError("Semaphore-URL muss eine vollständige HTTP(S)-Adresse ohne Zugangsdaten sein.")
        path = parts.path.rstrip("/")
        if path.lower().endswith("/api"):
            path = path[:-4]
        self._origin = (parts.scheme, parts.hostname.lower(), parts.port or (443 if parts.scheme == "https" else 80))
        self._api_base = urlunsplit((parts.scheme, parts.netloc, path + "/api/", "", ""))
        self._token = connection.token.strip()
        if not self._token:
            raise SemaphoreError("Semaphore-Service-Token fehlt.")
        self._proxy = connection.proxy_url or None
        self._timeout = httpx.Timeout(connection.timeout_seconds)

    def _url(self, path: str) -> str:
        return urljoin(self._api_base, path.lstrip("/"))

    def _same_api_target(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = (parts.scheme, (parts.hostname or "").lower(), parts.port or (443 if parts.scheme == "https" else 80))
        api_path = urlsplit(self._api_base).path
        return origin == self._origin and parts.path.startswith(api_path)

    async def _request(self, method: str, path: str, *, payload: Any = None, expect_json: bool = True) -> Any:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "User-Agent": "SemaphoreTenantPortal/1.0",
        }
        url = self._url(path)
        try:
            async with httpx.AsyncClient(timeout=self._timeout, proxy=self._proxy, follow_redirects=False) as client:
                for _ in range(6):
                    response = await client.request(method, url, headers=headers, json=payload)
                    if response.status_code not in {301, 302, 303, 307, 308}:
                        break
                    if method != "GET":
                        raise SemaphoreError(
                            f"Semaphore antwortet auf {method} mit einer Weiterleitung; die Anfrage wird nicht wiederholt.",
                            uncertain=True,
                            status_code=response.status_code,
                        )
                    location = response.headers.get("location")
                    if not location:
                        raise SemaphoreError("Semaphore-Weiterleitung enthält kein Ziel.")
                    target = urljoin(url, location)
                    if not self._same_api_target(target):
                        raise SemaphoreError("Unsichere Semaphore-Weiterleitung auf einen anderen API-Ursprung abgelehnt.")
                    url = target
                else:
                    raise SemaphoreError("Zu viele Semaphore-Weiterleitungen.")
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            uncertain = method != "GET"
            raise SemaphoreError(
                "Semaphore ist nicht erreichbar; bei schreibenden Anfragen ist das Ergebnis unklar."
                if uncertain
                else "Semaphore ist nicht erreichbar.",
                uncertain=uncertain,
            ) from exc
        if response.status_code == 401:
            raise SemaphoreError("Semaphore lehnt den Service-Token ab (HTTP 401).", status_code=401)
        if response.status_code == 407:
            raise SemaphoreError("Der Firmenproxy verlangt eine Anmeldung (HTTP 407).", status_code=407)
        if response.status_code >= 400:
            detail = response.text[:500].strip()
            raise SemaphoreError(
                f"Semaphore-API-Fehler HTTP {response.status_code}: {detail or 'keine Fehlerbeschreibung'}",
                status_code=response.status_code,
            )
        if not expect_json:
            return response.text
        try:
            return response.json()
        except ValueError as exc:
            if response.text.lstrip().startswith("<"):
                raise SemaphoreError("Semaphore lieferte HTML statt JSON; Reverse Proxy und Server-URL prüfen.") from exc
            raise SemaphoreError("Semaphore lieferte ungültiges JSON.") from exc

    @staticmethod
    def normalize_projects(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            payload = payload.get("projects", payload.get("data"))
        result: list[dict[str, Any]] = []

        def visit(value: Any) -> None:
            if isinstance(value, list):
                for item in value:
                    visit(item)
                return
            if not isinstance(value, dict) or not isinstance(value.get("id"), int) or not str(value.get("name", "")).strip():
                raise SemaphoreError("Semaphore-Projektliste enthält einen Eintrag ohne id/name.")
            result.append({"id": value["id"], "name": str(value["name"])})

        if payload is None:
            raise SemaphoreError("Semaphore-Antwort ist keine Projektliste.")
        visit(payload)
        return result

    async def test_connection(self) -> list[dict[str, Any]]:
        return await self.list_projects()

    async def list_projects(self) -> list[dict[str, Any]]:
        return self.normalize_projects(await self._request("GET", "projects"))

    async def get_project_backup(self, project_id: int) -> dict[str, Any]:
        payload = await self._request("GET", f"project/{project_id}/backup")
        if not isinstance(payload, dict) or not isinstance(payload.get("meta"), dict):
            raise SemaphoreError("Semaphore-Projektbackup besitzt kein meta-Objekt.")
        return payload

    async def restore_project(self, backup: dict[str, Any]) -> dict[str, Any]:
        payload = await self._request("POST", "projects/restore", payload=backup)
        if not isinstance(payload, dict):
            raise SemaphoreError("Semaphore-Restore lieferte kein Projektobjekt.", uncertain=True)
        return payload

    async def list_templates(self, project_id: int) -> list[dict[str, Any]]:
        payload = await self._request("GET", f"project/{project_id}/templates?sort=name&order=asc")
        if not isinstance(payload, list):
            raise SemaphoreError("Semaphore-Task-Templates sind keine Liste.")
        return [item for item in payload if isinstance(item, dict)]

    async def start_task(self, project_id: int, template_id: int, variables: dict[str, Any]) -> dict[str, Any]:
        payload = {"template_id": template_id, "environment": json.dumps(variables, separators=(",", ":"))}
        result = await self._request("POST", f"project/{project_id}/tasks", payload=payload)
        if not isinstance(result, dict) or not isinstance(result.get("id"), int):
            raise SemaphoreError("Semaphore bestätigte den Taskstart nicht mit einer Task-ID.", uncertain=True)
        return result

    async def get_task(self, project_id: int, task_id: int) -> dict[str, Any]:
        payload = await self._request("GET", f"project/{project_id}/tasks/{task_id}")
        if not isinstance(payload, dict) or payload.get("id") != task_id:
            raise SemaphoreError("Semaphore lieferte keinen passenden Task.")
        return payload

    async def get_task_output(self, project_id: int, task_id: int) -> list[dict[str, Any]]:
        payload = await self._request("GET", f"project/{project_id}/tasks/{task_id}/output")
        if not isinstance(payload, list):
            raise SemaphoreError("Semaphore-Taskausgabe ist keine Liste.")
        return [line for line in payload if isinstance(line, dict)]

    async def list_task_history(self, project_id: int) -> list[dict[str, Any]]:
        payload = await self._request("GET", f"project/{project_id}/tasks/last")
        if not isinstance(payload, list):
            raise SemaphoreError("Semaphore-Taskhistorie ist keine Liste.")
        return [task for task in payload if isinstance(task, dict)]

    async def stop_task(self, project_id: int, task_id: int) -> None:
        await self._request("POST", f"project/{project_id}/tasks/{task_id}/stop", payload={"force": False}, expect_json=False)

