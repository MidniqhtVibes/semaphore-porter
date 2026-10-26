"""Validated, versioned contracts exported from the deployment repository."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.vault_client import safe_path


class SecretField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=100)
    source: str = Field(pattern=r"^(registry|input)$")
    generate: str | None = Field(default=None, pattern=r"^(password|hex)$")
    min_length: int = Field(default=1, ge=1, le=4096)
    max_length: int = Field(default=4096, ge=1, le=4096)
    hex: bool = False
    even_length: bool = False
    forbid_whitespace: bool = False
    forbid_newlines: bool = True

    @model_validator(mode="after")
    def valid_limits(self):
        if self.min_length > self.max_length or (self.even_length and self.min_length == self.max_length and self.min_length % 2):
            raise ValueError("Secret-Längengrenzen sind widersprüchlich.")
        if self.source == "registry" and self.generate:
            raise ValueError("Registry-Credentials können nicht generiert werden.")
        return self


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: str
    fields: list[SecretField]

    @model_validator(mode="after")
    def valid_profile(self):
        safe_path(self.profile)
        if "/" in self.profile or len({f.key for f in self.fields}) != len(self.fields):
            raise ValueError("Profil benötigt ein einzelnes Segment und eindeutige Schlüssel.")
        return self


class Provider(Profile):
    provider_id: str


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    database_type: str
    provider_ids: list[str]


class Application(Profile):
    display_name: str
    database_types: dict[str, str]
    datasets: dict[str, Dataset]


class Catalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(ge=1, le=1)
    source_revision: str
    applications: dict[str, Application]
    providers: dict[str, Provider]

    @model_validator(mode="after")
    def valid_contracts(self):
        for identifier in [*self.applications, *self.providers]:
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", identifier):
                raise ValueError("Ungültige Katalog-ID.")
        for application in self.applications.values():
            for kind, provider_id in application.database_types.items():
                if kind not in self.providers or self.providers[kind].provider_id != provider_id:
                    raise ValueError("Anwendung referenziert einen unbekannten Provider.")
            for dataset in application.datasets.values():
                provider = self.providers.get(dataset.database_type)
                if not provider or dataset.database_type not in application.database_types or provider.provider_id not in dataset.provider_ids:
                    raise ValueError("Dataset passt nicht zum freigegebenen Provider.")
        return self


def load_catalog(db=None) -> Catalog:
    if db is not None:
        from app.models import CatalogActivation, CatalogSnapshot
        active = db.get(CatalogActivation, 1)
        if active and active.snapshot_id:
            return Catalog.model_validate(db.get(CatalogSnapshot, active.snapshot_id).catalog)
    return Catalog.model_validate(json.loads(Path(__file__).with_name("vault_catalog.json").read_text(encoding="utf-8")))


def validate_value(field: dict[str, Any], value: str) -> None:
    valid = isinstance(value, str) and field["min_length"] <= len(value) <= field["max_length"]
    valid = valid and not (field.get("forbid_newlines") and any(c in value for c in "\r\n"))
    valid = valid and not (field.get("forbid_whitespace") and any(c.isspace() for c in value))
    valid = valid and not (field.get("even_length") and len(value) % 2)
    valid = valid and not (field.get("hex") and not re.fullmatch(r"[a-fA-F0-9]+", value))
    if not valid:
        raise ValueError(f"{field['key']}: Wert entspricht nicht dem Secret-Vertrag ({field['min_length']}–{field['max_length']} Zeichen).")
