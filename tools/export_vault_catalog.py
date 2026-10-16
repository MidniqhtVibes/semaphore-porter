"""Export public contracts; requires PyYAML in the exporting environment only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import yaml

PORTER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORTER_ROOT / "backend"))
from app.vault_catalog import Catalog


def export(root: Path) -> dict:
    root = root.resolve(strict=True)

    def read(relative: str) -> dict:
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or path.stat().st_size > 2_000_000:
            raise ValueError("Manifest liegt außerhalb des Stack-Repositories oder ist zu groß.")
        result = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(result, dict) or result.get("schema_version") != 1:
            raise ValueError(f"Unbekanntes Manifestformat: {relative}")
        return result

    def identifier(value: str) -> str:
        import re
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", value):
            raise ValueError("Ungültige Paket-ID.")
        return value

    result = {"schema_version": 1, "source_revision": subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(), "applications": {}, "providers": {}}
    for kind, entry in read("database-types/catalog.yml")["database_types"].items():
        kind = identifier(kind)
        driver = read(f"database-types/{kind}/driver.yml")
        if driver["id"] != kind or driver["provider_id"] != entry["provider_id"]:
            raise ValueError("Provider-ID passt nicht zum Katalog.")
        fields = []
        if kind != "none":
            fields = [{"key": driver["secrets"]["admin_password_vault_key"], "source": "input",
                "generate": "password", "min_length": driver["credential"]["min_length"],
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
            unknown = set(validation) - {"type", "format", "min_length", "max_length", "even_length", "forbid_whitespace"}
            if unknown or validation.get("format") not in {None, "hex"} or validation.get("type") not in {None, "string"}:
                raise ValueError("Secret-Validierung muss zuerst im Porter unterstützt werden.")
            key = contract["vault_key"]
            registry_key = manifest.get("release", {}).get("registry", {}).get("password_secret")
            is_registry = name == registry_key
            fields.append({"key": key, "source": "registry" if is_registry else "input",
                "generate": None if is_registry else "hex" if validation.get("format") == "hex" else "password" if name == "crypto_secret" else None,
                "min_length": validation.get("min_length", 1), "max_length": validation.get("max_length", 4096),
                "hex": validation.get("format") == "hex", "even_length": validation.get("even_length", False),
                "forbid_whitespace": validation.get("forbid_whitespace", False)})
        result["applications"][app_id] = {"display_name": entry["display_name"],
            "profile": manifest["secrets"]["vault_profile"], "fields": fields,
            "database_types": {kind: contract["provider_id"] for kind, contract in manifest["database"]["types"].items()},
            "datasets": {name: {"database_type": ds["database_type"], "provider_ids": ds["provider_ids"]}
                for name, ds in read(f"programs/{app_id}/testdata/catalog.yml")["datasets"].items()}}
    return Catalog.model_validate(result).model_dump()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack-root", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=PORTER_ROOT / "backend/app/vault_catalog.json")
    args = parser.parse_args()
    args.output.write_text(json.dumps(export(args.stack_root), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
