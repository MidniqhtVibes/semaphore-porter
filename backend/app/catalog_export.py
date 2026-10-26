"""Export declarative Vault contracts without executing repository code."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from app.vault_catalog import Catalog


def export_catalog(root: Path, source_revision: str) -> dict:
    root = root.resolve(strict=True)

    def read(relative):
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or path.stat().st_size > 2_000_000:
            raise ValueError("Manifest liegt außerhalb des Stack-Repositories oder ist zu groß.")
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("Unbekanntes Manifestformat.")
        return value

    def identifier(value):
        if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", value):
            raise ValueError("Ungültige Paket-ID.")
        return value

    result = {"schema_version": 1, "source_revision": source_revision, "applications": {}, "providers": {}}
    for kind, entry in read("database-types/catalog.yml")["database_types"].items():
        kind = identifier(kind)
        driver = read(f"database-types/{kind}/driver.yml")
        if driver["id"] != kind or driver["provider_id"] != entry["provider_id"]:
            raise ValueError("Provider-ID passt nicht zum Katalog.")
        fields = [] if kind == "none" else [{"key": driver["secrets"]["admin_password_vault_key"],
            "source": "input", "generate": "password", "min_length": driver["credential"]["min_length"],
            "max_length": driver["credential"]["max_length"]}]
        result["providers"][kind] = {"provider_id": entry["provider_id"],
            "profile": driver.get("secrets", {}).get("vault_profile") or entry["provider_id"], "fields": fields}
    for app_id, entry in read("programs/catalog.yml")["programs"].items():
        app_id = identifier(app_id)
        manifest = read(f"programs/{app_id}/program.yml")
        if manifest["id"] != app_id:
            raise ValueError("Programm-ID passt nicht zum Katalog.")
        fields = []
        for name, contract in manifest["secrets"].get("required", {}).items():
            validation = contract.get("validation", {})
            if (set(validation) - {"type", "format", "min_length", "max_length", "even_length", "forbid_whitespace"}
                    or validation.get("format") not in {None, "hex", "text"}
                    or validation.get("type") not in {None, "string"}):
                raise ValueError("Secret-Validierung wird vom Semaporter noch nicht unterstützt.")
            registry = name == manifest.get("release", {}).get("registry", {}).get("password_secret")
            fields.append({"key": contract["vault_key"], "source": "registry" if registry else "input",
                "generate": None if registry else "hex" if validation.get("format") == "hex" else "password" if name == "crypto_secret" else None,
                "min_length": validation.get("min_length", 1), "max_length": validation.get("max_length", 4096),
                "hex": validation.get("format") == "hex", "even_length": validation.get("even_length", False),
                "forbid_whitespace": validation.get("forbid_whitespace", False)})
        result["applications"][app_id] = {"display_name": entry["display_name"],
            "profile": manifest["secrets"]["vault_profile"], "fields": fields,
            "database_types": {kind: contract["provider_id"] for kind, contract in manifest["database"]["types"].items()},
            "datasets": {name: {"database_type": ds["database_type"], "provider_ids": ds["provider_ids"]}
                         for name, ds in read(f"programs/{app_id}/testdata/catalog.yml")["datasets"].items()}}
    return Catalog.model_validate(result).model_dump()
