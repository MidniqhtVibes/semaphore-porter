from __future__ import annotations

import ssl
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from app.config import get_settings


class VaultError(RuntimeError):
    def __init__(self, message: str, *, uncertain: bool = False, conflict: bool = False):
        super().__init__(message)
        self.uncertain = uncertain
        self.conflict = conflict


def safe_path(value: str) -> str:
    import re
    if (not isinstance(value, str) or len(value) > 500 or not value
            or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", p) or p in {".", ".."} for p in value.split("/"))):
        raise ValueError("Vault-Mounts und Pfade benötigen gültige, durch / getrennte Segmente.")
    return value


def safe_url(value: str) -> str:
    parts = urlsplit(value)
    if (parts.scheme not in {"https", "http"} or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or parts.path not in {"", "/"}):
        raise ValueError("Vault-URL muss eine HTTP(S)-Serveradresse ohne Pfad oder Zugangsdaten sein.")
    # Validate the port as well; urlsplit otherwise defers errors.
    _ = parts.port
    return value.rstrip("/")


class VaultClient:
    """KV v2 create-only client. No redirects, automatic retries or secret reads."""
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.base = safe_url(config["base_url"]) + "/v1/"
        settings = get_settings()
        self.timeout = settings.vault_request_timeout_seconds
        try:
            self.verify = ssl.create_default_context(cafile=settings.vault_ca_bundle or None)
        except (OSError, ssl.SSLError) as exc:
            raise VaultError("Die konfigurierte Vault-CA konnte nicht geladen werden.") from exc
        self.token: str | None = None

    async def _request(self, method: str, path: str, data: Any = None, *, absence_ok: bool = False, writing: bool = False,
                       params: dict | None = None) -> Any:
        headers = {"Accept": "application/json"}
        if self.config.get("namespace"):
            headers["X-Vault-Namespace"] = self.config["namespace"]
        if self.token:
            headers["X-Vault-Token"] = self.token
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=self.verify, follow_redirects=False) as client:
                response = await client.request(method, self.base + quote(path, safe="/"), headers=headers, json=data, params=params)
        except httpx.TransportError as exc:
            raise VaultError("Vault ist nicht erreichbar; das Schreibergebnis muss gegebenenfalls geprüft werden.", uncertain=writing) from exc
        if absence_ok and response.status_code == 404:
            return None
        if response.status_code >= 300:
            # Never include a response body: Vault or reverse proxies can echo inputs.
            raise VaultError(f"Vault-Anfrage fehlgeschlagen (HTTP {response.status_code}).",
                uncertain=writing and (response.status_code >= 500 or response.status_code < 400 or response.status_code == 408),
                conflict=writing and response.status_code in {400, 409, 412})
        try:
            return response.json()
        except ValueError as exc:
            raise VaultError("Vault lieferte keine gültige JSON-Antwort.", uncertain=writing) from exc

    async def login(self) -> None:
        safe_path(self.config["writer_auth_mount"])
        result = await self._request("POST", f"auth/{self.config['writer_auth_mount']}/login", {
                "role_id": self.config["writer_role_id"], "secret_id": self.config["writer_secret_id"]})
        auth = result.get("auth") if isinstance(result, dict) else None
        token = auth.get("client_token") if isinstance(auth, dict) else None
        if not isinstance(token, str) or not token:
            raise VaultError("Vault bestätigte die AppRole-Anmeldung nicht.")
        self.token = token

    async def metadata(self, path: str) -> dict[str, Any] | None:
        result = await self._request("GET", f"{safe_path(self.config['kv_mount'])}/metadata/{safe_path(path)}", absence_ok=True)
        if result is None:
            return None
        data = result.get("data") if isinstance(result, dict) else None
        if not isinstance(data, dict) or type(data.get("current_version")) is not int or data["current_version"] < 1:
            raise VaultError("Vault-Metadaten konnten nicht zuverlässig geprüft werden.")
        return data

    async def create(self, path: str, values: dict[str, str]) -> dict[str, Any]:
        result = await self._request("POST", f"{safe_path(self.config['kv_mount'])}/data/{safe_path(path)}",
            {"options": {"cas": 0}, "data": values}, writing=True)
        data = result.get("data") if isinstance(result, dict) else None
        version = data.get("version") if isinstance(data, dict) else None
        created_time = data.get("created_time") if isinstance(data, dict) else None
        if type(version) is not int or version != 1 or not isinstance(created_time, str) or not created_time:
            raise VaultError("Vault bestätigte die Neuanlage nicht eindeutig.", uncertain=True)
        return {"version": version, "created_time": created_time}
