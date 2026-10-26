#!/usr/bin/env python3
"""Compile a trusted, secret-free deployment plan from repository catalogs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, NoReturn

import yaml


ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
SHORT_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")
ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
VARIABLE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,127}$")
PROVIDER_RE = re.compile(r"^[a-z][a-z0-9-]{0,62}-v[1-9][0-9]*$")
SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
POLICIES = {"always_new", "reuse_or_create", "reuse_only"}
MODES = {
    "always_new": "deployment_local",
    "reuse_or_create": "shared_runtime",
    "reuse_only": "shared_runtime",
}
READINESS_TYPES = {
    "published_tcp",
    "compose_services",
    "service_tcp",
    "datastore_login",
    "http",
}


class PlanError(RuntimeError):
    """A safe validation error without secret-bearing context."""


def abort(message: str) -> NoReturn:
    raise PlanError(message)


def expect_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        abort(f"{context} muss ein Mapping sein.")
    return value


def expect_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        abort(f"{context} muss eine Liste sein.")
    return value


def require_keys(
    value: dict[str, Any],
    required: set[str],
    allowed: set[str],
    context: str,
) -> None:
    missing = required.difference(value)
    unknown = set(value).difference(allowed)
    if missing:
        abort(f"{context}: Pflichtfelder fehlen: {', '.join(sorted(missing))}.")
    if unknown:
        abort(
            f"{context}: unbekannte Felder: {', '.join(sorted(unknown))}."
        )


def validate_id(value: Any, context: str, pattern: re.Pattern[str] = ID_RE) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        abort(f"{context} ist keine sichere technische ID.")
    return value


def validate_environment_name(value: Any, context: str) -> str:
    if not isinstance(value, str) or ENV_RE.fullmatch(value) is None:
        abort(f"{context} ist kein sicherer Environment-Schlüssel.")
    return value


def validate_variable_name(value: Any, context: str) -> str:
    if not isinstance(value, str) or VARIABLE_RE.fullmatch(value) is None:
        abort(f"{context} ist kein sicherer Ansible-Variablenname.")
    return value


def validate_display_name(value: Any, context: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        abort(f"{context} ist kein gültiger Anzeigename.")
    if any(ord(character) < 32 for character in value):
        abort(f"{context} enthält Steuerzeichen.")
    return value


def validate_description(value: Any, context: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 1024:
        abort(f"{context} ist keine gültige Beschreibung.")
    if any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"}
        for character in value
    ):
        abort(f"{context} enthält unzulässige Steuerzeichen.")
    return value


def safe_relative_path(value: Any, context: str) -> PurePosixPath:
    """Validate repository paths independently of the controller platform."""

    if not isinstance(value, str) or not value or len(value) > 255:
        abort(f"{context} enthält keinen gültigen relativen Pfad.")
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or "\\" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        abort(f"{context} enthält einen unsicheren Pfad.")
    return posix_path


def is_regular_file_without_links(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISREG(metadata.st_mode)
        and not path.is_symlink()
        and metadata.st_nlink == 1
    )


def load_yaml(path: Path, context: str) -> dict[str, Any]:
    if not is_regular_file_without_links(path):
        abort(f"{context} fehlt, ist kein reguläres File oder ist verlinkt.")
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        abort(f"{context} konnte nicht sicher gelesen werden: {error}.")
    return expect_mapping(document, context)


def resolve_directory(root: Path, name: str, context: str) -> Path:
    candidate = root / name
    try:
        metadata = candidate.lstat()
        resolved = candidate.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
    except OSError as error:
        abort(f"{context} konnte nicht sicher aufgelöst werden: {error}.")
    if not stat.S_ISDIR(metadata.st_mode) or candidate.is_symlink():
        abort(f"{context} ist kein echtes Verzeichnis.")
    if resolved.parent != resolved_root:
        abort(f"{context} liegt außerhalb der erlaubten Wurzel.")
    return resolved


def resolve_file(root: Path, relative: Any, context: str) -> Path:
    safe_path = safe_relative_path(relative, context)
    relative_path = Path(*safe_path.parts)
    try:
        resolved_root = root.resolve(strict=True)
        candidate = root / relative_path
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        abort(f"{context} konnte nicht sicher aufgelöst werden: {error}.")
    if resolved_root not in resolved.parents:
        abort(f"{context} liegt außerhalb des erlaubten Ordners.")
    current = root
    for part in relative_path.parts:
        current = current / part
        try:
            if current.is_symlink():
                abort(f"{context} darf keine Symlinks enthalten.")
        except OSError as error:
            abort(f"{context} konnte nicht sicher geprüft werden: {error}.")
    if not is_regular_file_without_links(resolved):
        abort(f"{context} ist kein unverlinktes reguläres File.")
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_catalog_entry(entry: Any, context: str) -> dict[str, Any]:
    result = expect_mapping(entry, context)
    require_keys(result, {"display_name"}, {"display_name", "provider_id"}, context)
    validate_display_name(result["display_name"], f"{context}.display_name")
    if "provider_id" in result:
        provider_id = result["provider_id"]
        if not isinstance(provider_id, str) or PROVIDER_RE.fullmatch(provider_id) is None:
            abort(f"{context}.provider_id ist ungültig.")
    return result


def validate_program_manifest(
    manifest: dict[str, Any],
    application_id: str,
    database_type: str,
    policy: str,
    mode: str,
) -> dict[str, Any]:
    require_keys(
        manifest,
        {
            "schema_version",
            "id",
            "display_name",
            "profile_version",
            "release",
            "database",
            "application",
            "endpoint",
            "runtime",
            "datasets",
            "readiness",
            "secrets",
        },
        {
            "schema_version",
            "id",
            "display_name",
            "profile_version",
            "release",
            "database",
            "application",
            "endpoint",
            "runtime",
            "datasets",
            "readiness",
            "secrets",
        },
        "Programmmanifest",
    )
    if manifest["schema_version"] != 1 or manifest["profile_version"] != 1:
        abort("Programmmanifest-Version wird nicht unterstützt.")
    if manifest["id"] != application_id:
        abort("Programmmanifest-ID stimmt nicht mit der Auswahl überein.")
    validate_display_name(manifest["display_name"], "Programmmanifest.display_name")

    release = expect_mapping(manifest["release"], "release")
    require_keys(
        release,
        {"default", "primary_image", "images"},
        {"default", "primary_image", "registry", "images"},
        "release",
    )
    validate_id(release["primary_image"], "release.primary_image", SHORT_ID_RE)
    raw_registry = release.get("registry")
    if raw_registry is None:
        registry = {
            "login": False,
            "prefix_variable": None,
            "username_variable": None,
            "password_secret": None,
        }
    else:
        registry = expect_mapping(raw_registry, "release.registry")
        require_keys(
            registry,
            {"login", "prefix_variable", "username_variable", "password_secret"},
            {"login", "prefix_variable", "username_variable", "password_secret"},
            "release.registry",
        )
    # Downstream tasks always consume the same canonical, null-safe shape.
    release["registry"] = registry
    if not isinstance(registry["login"], bool):
        abort("release.registry.login muss boolesch sein.")
    for key in {"prefix_variable", "username_variable"}:
        if registry[key] is not None:
            validate_variable_name(registry[key], f"release.registry.{key}")
    if registry["password_secret"] is not None:
        validate_id(
            registry["password_secret"],
            "release.registry.password_secret",
            SHORT_ID_RE,
        )
    if registry["login"] and (
        registry["prefix_variable"] is None
        or registry["username_variable"] is None
        or registry["password_secret"] is None
    ):
        abort("Registry-Login benoetigt Prefix, Benutzer und Passwortsecret.")
    if not isinstance(release["default"], str) or not re.fullmatch(
        r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}", release["default"]
    ):
        abort("release.default ist ungültig.")
    images = expect_mapping(release["images"], "release.images")
    if not images or release["primary_image"] not in images:
        abort("release.images enthält kein gültiges Primary-Image.")
    for image_id, raw_image in images.items():
        validate_id(image_id, f"Image-ID {image_id}", SHORT_ID_RE)
        image = expect_mapping(raw_image, f"release.images.{image_id}")
        require_keys(
            image,
            {
                "repository_key",
                "tag_input",
                "repository_environment",
                "tag_environment",
            },
            {
                "repository_key",
                "tag_input",
                "repository_environment",
                "tag_environment",
            },
            f"release.images.{image_id}",
        )
        validate_variable_name(
            image["repository_key"],
            f"release.images.{image_id}.repository_key",
        )
        validate_variable_name(
            image["tag_input"], f"release.images.{image_id}.tag_input"
        )
        validate_environment_name(
            image["repository_environment"],
            f"release.images.{image_id}.repository_environment",
        )
        validate_environment_name(
            image["tag_environment"],
            f"release.images.{image_id}.tag_environment",
        )

    database = expect_mapping(manifest["database"], "database")
    require_keys(
        database,
        {"default_type", "types"},
        {"default_type", "types"},
        "database",
    )
    validate_id(database["default_type"], "database.default_type")
    database_types = expect_mapping(database["types"], "database.types")
    if database["default_type"] not in database_types:
        abort("database.default_type ist nicht in database.types deklariert.")
    if database_type not in database_types:
        abort("Das Testprogramm unterstützt den gewählten Datenbanktyp nicht.")
    profile = expect_mapping(
        database_types[database_type], f"database.types.{database_type}"
    )
    require_keys(
        profile,
        {
            "provider_id",
            "allowed_policies",
            "compose",
            "configuration_files",
            "connection_mapping",
        },
        {
            "provider_id",
            "allowed_policies",
            "compose",
            "configuration_files",
            "connection_mapping",
        },
        f"database.types.{database_type}",
    )
    if not isinstance(profile["provider_id"], str) or PROVIDER_RE.fullmatch(
        profile["provider_id"]
    ) is None:
        abort("Provider-ID im Programmmanifest ist ungültig.")
    allowed_policies = expect_list(
        profile["allowed_policies"], "database.allowed_policies"
    )
    if (
        not allowed_policies
        or any(
            not isinstance(item, str) or item not in POLICIES
            for item in allowed_policies
        )
        or len(set(allowed_policies)) != len(allowed_policies)
    ):
        abort("database.allowed_policies ist ungültig.")
    if policy not in allowed_policies:
        abort("Das Testprogramm unterstützt die gewählte Datenbank-Policy nicht.")

    compose = expect_mapping(profile["compose"], "database.compose")
    allowed_compose_modes = {"none", "deployment_local", "shared_runtime"}
    if mode not in compose or set(compose).difference(allowed_compose_modes):
        abort("database.compose bildet den ausgewaehlten Modus nicht sicher ab.")
    for compose_mode, relative in compose.items():
        if not isinstance(relative, str) or not relative:
            abort(f"database.compose.{compose_mode} ist ungültig.")

    configuration_files = expect_list(
        profile["configuration_files"], "database.configuration_files"
    )
    configuration_destinations: set[str] = set()
    reserved_runtime_paths = {
        "compose.yml",
        "status.env",
        "metadata.env",
        "state.json",
        "testdata",
        ".docker-auth",
        "compose-start.log",
    }
    for index, raw_configuration in enumerate(configuration_files):
        configuration = expect_mapping(
            raw_configuration, f"configuration_files[{index}]"
        )
        require_keys(
            configuration,
            {"source", "destination", "mode"},
            {"source", "destination", "mode"},
            f"configuration_files[{index}]",
        )
        if (
            not isinstance(configuration["destination"], str)
            or re.fullmatch(
                r"[a-zA-Z0-9][a-zA-Z0-9._/-]{0,127}",
                configuration["destination"],
            )
            is None
            or ".." in Path(configuration["destination"]).parts
            or Path(configuration["destination"]).is_absolute()
        ):
            abort(f"configuration_files[{index}].destination ist unsicher.")
        destination_parts = PurePosixPath(configuration["destination"]).parts
        if (
            configuration["destination"] in configuration_destinations
            or destination_parts[0] in reserved_runtime_paths
        ):
            abort(
                f"configuration_files[{index}].destination kollidiert mit "
                "einem Lifecycle-Pfad oder einem anderen Konfigurationsziel."
            )
        configuration_destinations.add(configuration["destination"])
        if not isinstance(configuration["mode"], str) or re.fullmatch(
            r"0[0-7]{3}", configuration["mode"]
        ) is None:
            abort(f"configuration_files[{index}].mode ist ungültig.")

    connection_mapping = expect_mapping(
        profile["connection_mapping"], "database.connection_mapping"
    )
    connection_fields = {
        "host",
        "port",
        "namespace",
        "principal",
        "password",
        "image",
        "container",
        "network",
        "admin_principal",
        "admin_password",
    }
    if database_type == "none":
        require_keys(
            connection_mapping,
            set(),
            set(),
            "database.connection_mapping",
        )
    else:
        require_keys(
            connection_mapping,
            connection_fields,
            connection_fields,
            "database.connection_mapping",
        )
    for field, environment_name in connection_mapping.items():
        validate_environment_name(
            environment_name, f"database.connection_mapping.{field}"
        )

    application = expect_mapping(manifest["application"], "application")
    require_keys(
        application,
        {"primary_service", "expected_services"},
        {"primary_service", "expected_services"},
        "application",
    )
    validate_id(
        application["primary_service"],
        "application.primary_service",
        SHORT_ID_RE,
    )
    expected_services = expect_mapping(
        application["expected_services"], "application.expected_services"
    )
    allowed_service_modes = {"none", "deployment_local", "shared_runtime"}
    if mode not in expected_services or set(expected_services).difference(
        allowed_service_modes
    ):
        abort("application.expected_services bildet den Modus nicht sicher ab.")
    for service_mode, services in expected_services.items():
        service_list = expect_list(services, f"expected_services.{service_mode}")
        if not service_list:
            abort(f"expected_services.{service_mode} ist leer.")
        for service in service_list:
            validate_id(service, f"Service {service}", SHORT_ID_RE)
        if len(set(service_list)) != len(service_list):
            abort(f"expected_services.{service_mode} enthält Duplikate.")

    endpoint = expect_mapping(manifest["endpoint"], "endpoint")
    require_keys(
        endpoint,
        {
            "scheme",
            "service",
            "container_port",
            "bind_address_environment",
            "host_port_environment",
        },
        {
            "scheme",
            "service",
            "container_port",
            "bind_address_environment",
            "host_port_environment",
        },
        "endpoint",
    )
    if endpoint["scheme"] not in {"http", "https"}:
        abort("endpoint.scheme wird nicht unterstützt.")
    validate_id(endpoint["service"], "endpoint.service", SHORT_ID_RE)
    if not isinstance(endpoint["container_port"], int) or not (
        1 <= endpoint["container_port"] <= 65535
    ):
        abort("endpoint.container_port ist ungültig.")
    validate_environment_name(
        endpoint["bind_address_environment"],
        "endpoint.bind_address_environment",
    )
    validate_environment_name(
        endpoint["host_port_environment"],
        "endpoint.host_port_environment",
    )

    runtime = expect_mapping(manifest["runtime"], "runtime")
    require_keys(
        runtime,
        {"lifecycle_environment", "input_environment"},
        {"lifecycle_environment", "input_environment"},
        "runtime",
    )
    lifecycle_environment = expect_mapping(
        runtime["lifecycle_environment"], "runtime.lifecycle_environment"
    )
    require_keys(
        lifecycle_environment,
        {
            "application_id",
            "tenant_slug",
            "runtime_scope_id",
            "dataset_id",
            "base_url",
        },
        {
            "application_id",
            "tenant_slug",
            "runtime_scope_id",
            "dataset_id",
            "base_url",
        },
        "runtime.lifecycle_environment",
    )
    for field, environment_name in lifecycle_environment.items():
        validate_environment_name(
            environment_name, f"runtime.lifecycle_environment.{field}"
        )
    input_environment = expect_mapping(
        runtime["input_environment"], "runtime.input_environment"
    )
    for environment_name, raw_input in input_environment.items():
        validate_environment_name(
            environment_name, f"runtime.input_environment.{environment_name}"
        )
        input_definition = expect_mapping(
            raw_input, f"runtime.input_environment.{environment_name}"
        )
        require_keys(
            input_definition,
            {"variable"},
            {"variable", "required", "default"},
            f"runtime.input_environment.{environment_name}",
        )
        validate_variable_name(
            input_definition["variable"],
            f"runtime.input_environment.{environment_name}.variable",
        )
        if "required" in input_definition and not isinstance(
            input_definition["required"], bool
        ):
            abort(
                f"runtime.input_environment.{environment_name}.required "
                "muss boolesch sein."
            )

    datasets = expect_mapping(manifest["datasets"], "datasets")
    require_keys(
        datasets,
        {"catalog", "optional"},
        {"catalog", "optional"},
        "datasets",
    )
    if not isinstance(datasets["optional"], bool):
        abort("datasets.optional muss boolesch sein.")

    readiness = expect_list(manifest["readiness"], "readiness")
    if not readiness:
        abort("readiness darf nicht leer sein.")
    for index, raw_check in enumerate(readiness):
        check = expect_mapping(raw_check, f"readiness[{index}]")
        check_type = check.get("type")
        if not isinstance(check_type, str) or check_type not in READINESS_TYPES:
            abort(f"readiness[{index}].type wird nicht unterstützt.")
        allowed = {
            "type",
            "endpoint",
            "service",
            "port",
            "binding",
            "path",
            "optional",
            "accepted_statuses",
        }
        unknown = set(check).difference(allowed)
        if unknown:
            abort(f"readiness[{index}] enthält unbekannte Felder.")
        required_by_type = {
            "published_tcp": {"type", "endpoint"},
            "compose_services": {"type"},
            "service_tcp": {"type", "service", "port"},
            "datastore_login": {"type", "binding"},
            "http": {"type", "endpoint"},
        }
        missing = required_by_type[check_type].difference(check)
        if missing:
            abort(f"readiness[{index}] fehlen typspezifische Pflichtfelder.")
        if "endpoint" in check and check["endpoint"] != "primary":
            abort(f"readiness[{index}].endpoint ist unbekannt.")
        if "binding" in check and check["binding"] != "primary":
            abort(f"readiness[{index}].binding ist unbekannt.")
        if check_type == "datastore_login" and mode == "none":
            abort("Ein datenbankloses Profil darf kein Datastore-Login pruefen.")
        if "service" in check:
            validate_id(
                check["service"],
                f"readiness[{index}].service",
                SHORT_ID_RE,
            )
        if "port" in check and (
            not isinstance(check["port"], int) or not 1 <= check["port"] <= 65535
        ):
            abort(f"readiness[{index}].port ist ungültig.")
        if "optional" in check and not isinstance(check["optional"], bool):
            abort(f"readiness[{index}].optional muss boolesch sein.")
        if "path" in check and (
            not isinstance(check["path"], str)
            or re.fullmatch(
                r"/[a-zA-Z0-9._~!$&'()*+,;=:@%/-]{0,255}",
                check["path"],
            )
            is None
            or ".." in PurePosixPath(check["path"]).parts
        ):
            abort(f"readiness[{index}].path ist ungueltig.")
        if "accepted_statuses" in check:
            accepted_statuses = expect_list(
                check["accepted_statuses"],
                f"readiness[{index}].accepted_statuses",
            )
            if (
                not accepted_statuses
                or any(
                    not isinstance(status_code, int)
                    or isinstance(status_code, bool)
                    or not 100 <= status_code <= 599
                    for status_code in accepted_statuses
                )
                or len(accepted_statuses) != len(set(accepted_statuses))
            ):
                abort(f"readiness[{index}].accepted_statuses ist ungueltig.")

    secrets = expect_mapping(manifest["secrets"], "secrets")
    require_keys(
        secrets,
        {"vault_profile", "required"},
        {"vault_profile", "required"},
        "secrets",
    )
    validate_id(secrets["vault_profile"], "secrets.vault_profile")
    required_secrets = expect_mapping(secrets["required"], "secrets.required")
    for logical_name, raw_secret in required_secrets.items():
        validate_id(logical_name, f"Secret {logical_name}", SHORT_ID_RE)
        secret = expect_mapping(raw_secret, f"secrets.required.{logical_name}")
        require_keys(
            secret,
            {"vault_key"},
            {"vault_key", "environment", "validation"},
            f"secrets.required.{logical_name}",
        )
        validate_variable_name(
            secret["vault_key"],
            f"secrets.required.{logical_name}.vault_key",
        )
        if "environment" in secret:
            validate_environment_name(
                secret["environment"],
                f"secrets.required.{logical_name}.environment",
            )
        if "validation" in secret:
            context = f"secrets.required.{logical_name}.validation"
            rules = expect_mapping(secret["validation"], context)
            require_keys(
                rules,
                {"type"},
                {"type", "format", "min_length", "max_length",
                 "even_length", "forbid_whitespace"},
                context,
            )
            if rules["type"] != "string":
                abort(f"{context}.type muss string sein.")
            if "format" in rules and rules["format"] not in ("text", "hex"):
                abort(f"{context}.format muss text oder hex sein.")
            for name in ("min_length", "max_length"):
                if name in rules and (
                    not isinstance(rules[name], int)
                    or isinstance(rules[name], bool)
                    or rules[name] < 1
                ):
                    abort(f"{context}.{name} muss eine positive Ganzzahl sein.")
            if rules.get("min_length", 1) > rules.get("max_length", float("inf")):
                abort(f"{context}: min_length ist groesser als max_length.")
            for name in ("even_length", "forbid_whitespace"):
                if name in rules and not isinstance(rules[name], bool):
                    abort(f"{context}.{name} muss ein Boolean sein.")
    if (
        registry["password_secret"] is not None
        and registry["password_secret"] not in required_secrets
    ):
        abort("release.registry.password_secret fehlt in secrets.required.")

    return profile


def validate_driver(
    driver: dict[str, Any],
    database_type: str,
    provider_id: str,
    mode: str,
) -> None:
    require_keys(
        driver,
        {
            "schema_version",
            "id",
            "provider_id",
            "protocol_version",
            "capabilities",
            "engine",
            "secrets",
            "datasets",
            "pool",
            "identifier",
            "credential",
        },
        {
            "schema_version",
            "id",
            "provider_id",
            "protocol_version",
            "capabilities",
            "engine",
            "secrets",
            "datasets",
            "pool",
            "identifier",
            "credential",
        },
        "Datenbankdriver",
    )
    if driver["schema_version"] != 1 or driver["protocol_version"] != 1:
        abort("Datenbankdriver-Version wird nicht unterstützt.")
    if driver["id"] != database_type or driver["provider_id"] != provider_id:
        abort("Datenbankdriver stimmt nicht mit der Auswahl überein.")

    capabilities = expect_mapping(driver["capabilities"], "capabilities")
    required_capabilities = {
        "binding_required",
        "deployment_local",
        "shared_runtime",
        "namespace_per_deployment",
        "principal_per_deployment",
        "ephemeral_import_principal",
        "formats",
    }
    require_keys(
        capabilities,
        required_capabilities,
        required_capabilities,
        "capabilities",
    )
    for capability in required_capabilities.difference({"formats"}):
        if not isinstance(capabilities[capability], bool):
            abort(f"capabilities.{capability} muss boolesch sein.")
    if mode != "none" and not capabilities[mode]:
        abort("Der Datenbankdriver unterstützt den gewählten Modus nicht.")
    formats = expect_list(capabilities["formats"], "capabilities.formats")
    if not formats and capabilities["binding_required"]:
        abort("capabilities.formats ist leer.")
    if formats and not capabilities["binding_required"]:
        abort("Ein datenbankloser Provider darf keine Formate anbieten.")
    for dataset_format in formats:
        validate_id(dataset_format, f"Datasetformat {dataset_format}", SHORT_ID_RE)
    if len(set(formats)) != len(formats):
        abort("capabilities.formats enthält Duplikate.")

    engine = expect_mapping(driver["engine"], "engine")
    require_keys(
        engine,
        {
            "family",
            "supported_majors",
            "default_major",
            "image_variable",
            "default_image",
            "admin_principal_variable",
            "default_admin_principal",
            "namespace_prefix_variable",
            "default_port",
            "local_compose_service",
            "client_command",
        },
        {
            "family",
            "supported_majors",
            "default_major",
            "image_variable",
            "default_image",
            "admin_principal_variable",
            "default_admin_principal",
            "namespace_prefix_variable",
            "default_port",
            "local_compose_service",
            "client_command",
        },
        "engine",
    )
    validate_id(engine["family"], "engine.family")
    majors = expect_list(engine["supported_majors"], "engine.supported_majors")
    if (
        any(
            not isinstance(item, int) or isinstance(item, bool) or item < 1
            for item in majors
        )
        or len(set(majors)) != len(majors)
        or (
            engine["default_major"] is not None
            and engine["default_major"] not in majors
        )
        or (not majors and engine["default_major"] is not None)
    ):
        abort("engine.supported_majors/default_major ist ungültig.")
    for key in {
        "image_variable",
        "admin_principal_variable",
        "namespace_prefix_variable",
    }:
        if engine[key] is not None:
            validate_variable_name(engine[key], f"engine.{key}")
    default_admin_principal = engine["default_admin_principal"]
    if default_admin_principal is not None and (
        not isinstance(default_admin_principal, str)
        or not default_admin_principal
    ):
        abort("engine.default_admin_principal ist ungueltig.")
    if engine["default_image"] is not None and (
        not isinstance(engine["default_image"], str)
        or re.fullmatch(r"[a-zA-Z0-9._/@:-]{1,255}", engine["default_image"])
        is None
    ):
        abort("engine.default_image ist ungültig.")
    if engine["default_port"] is not None and (
        not isinstance(engine["default_port"], int)
        or not 1 <= engine["default_port"] <= 65535
    ):
        abort("engine.default_port ist ungültig.")

    for key in {"local_compose_service", "client_command"}:
        if engine[key] is not None:
            validate_id(engine[key], f"engine.{key}", SHORT_ID_RE)

    driver_secrets = expect_mapping(driver["secrets"], "driver.secrets")
    require_keys(
        driver_secrets,
        {"admin_password_vault_key", "vault_profile"},
        {"admin_password_vault_key", "vault_profile"},
        "driver.secrets",
    )
    if driver_secrets["admin_password_vault_key"] is not None:
        validate_variable_name(
            driver_secrets["admin_password_vault_key"],
            "driver.secrets.admin_password_vault_key",
        )
    if driver_secrets["vault_profile"] is not None:
        validate_id(
            driver_secrets["vault_profile"],
            "driver.secrets.vault_profile",
        )
    if (driver_secrets["admin_password_vault_key"] is None) != (
        driver_secrets["vault_profile"] is None
    ):
        abort("Provider-Adminsecret und Vault-Profil muessen gemeinsam gesetzt sein.")

    dataset_contract = expect_mapping(driver["datasets"], "driver.datasets")
    require_keys(
        dataset_contract,
        {"validators"},
        {"validators"},
        "driver.datasets",
    )
    validators = expect_mapping(
        dataset_contract["validators"], "driver.datasets.validators"
    )
    if set(validators) != set(formats):
        abort("Für jedes Driver-Datasetformat muss ein Validatorvertrag existieren.")
    for dataset_format, validator in validators.items():
        if validator is not None:
            safe_relative_path(
                validator,
                f"driver.datasets.validators.{dataset_format}",
            )

    pool = expect_mapping(driver["pool"], "driver.pool")
    require_keys(
        pool,
        {"default_sharing_scope", "storage_schema", "shared_runtime_compose"},
        {"default_sharing_scope", "storage_schema", "shared_runtime_compose"},
        "pool",
    )
    if pool["default_sharing_scope"] not in {
        None,
        "runtime_scope_application",
    }:
        abort("pool.default_sharing_scope wird nicht unterstützt.")
    if pool["storage_schema"] is not None:
        validate_id(pool["storage_schema"], "pool.storage_schema")
    if pool["shared_runtime_compose"] is not None:
        safe_relative_path(
            pool["shared_runtime_compose"], "pool.shared_runtime_compose"
        )

    identifier = expect_mapping(driver["identifier"], "identifier")
    require_keys(
        identifier,
        {
            "max_namespace_length",
            "max_principal_length",
            "allowed_pattern",
        },
        {
            "max_namespace_length",
            "max_principal_length",
            "allowed_pattern",
        },
        "identifier",
    )
    for key in {"max_namespace_length", "max_principal_length"}:
        if identifier[key] is not None and (
            not isinstance(identifier[key], int)
            or not 20 <= identifier[key] <= 255
        ):
            abort(f"identifier.{key} ist ungültig.")
    allowed_pattern = identifier["allowed_pattern"]
    if allowed_pattern is not None and (
        not isinstance(allowed_pattern, str)
        or len(allowed_pattern) > 256
        or not allowed_pattern.startswith("^")
        or not allowed_pattern.endswith("$")
    ):
        abort("identifier.allowed_pattern muss ein kurzer, verankerter Regex sein.")
    try:
        re.compile(allowed_pattern or "^$")
    except (TypeError, re.error):
        abort("identifier.allowed_pattern ist ungültig.")
    if capabilities["binding_required"]:
        if default_admin_principal is None:
            abort("Ein Datenbankdriver braucht einen Default-Adminprincipal.")
        if (
            re.fullmatch(allowed_pattern, default_admin_principal) is None
            or len(default_admin_principal) > identifier["max_principal_length"]
        ):
            abort("engine.default_admin_principal verletzt die Identifierregeln.")
    elif default_admin_principal is not None:
        abort("Ein datenbankloser Provider darf keinen Adminprincipal besitzen.")

    credential = expect_mapping(driver["credential"], "credential")
    require_keys(
        credential,
        {"min_length", "max_length"},
        {"min_length", "max_length"},
        "credential",
    )
    if (
        not isinstance(credential["min_length"], int)
        or isinstance(credential["min_length"], bool)
        or not isinstance(credential["max_length"], int)
        or isinstance(credential["max_length"], bool)
        or credential["min_length"] < 0
        or credential["max_length"] < credential["min_length"]
        or credential["max_length"] > 4096
    ):
        abort("credential.min_length/max_length ist ungueltig.")


def compile_plan(arguments: argparse.Namespace) -> dict[str, Any]:
    application_id = validate_id(arguments.application_id, "application_id")
    database_type = validate_id(arguments.database_type, "database_type")
    dataset_id = validate_id(arguments.dataset_id, "dataset_id")
    if arguments.policy not in POLICIES:
        abort("existing_environment_policy ist ungültig.")
    mode = "none" if database_type == "none" else MODES[arguments.policy]

    root = Path(arguments.root)
    try:
        root = root.resolve(strict=True)
    except OSError as error:
        abort(f"Repository-Wurzel konnte nicht aufgelöst werden: {error}.")

    programs_root = root / "programs"
    database_types_root = root / "database-types"
    program_catalog = load_yaml(programs_root / "catalog.yml", "Programmkatalog")
    database_catalog = load_yaml(
        database_types_root / "catalog.yml", "Datenbankkatalog"
    )
    require_keys(
        program_catalog,
        {"schema_version", "programs"},
        {"schema_version", "programs"},
        "Programmkatalog",
    )
    require_keys(
        database_catalog,
        {"schema_version", "database_types"},
        {"schema_version", "database_types"},
        "Datenbankkatalog",
    )
    if (
        program_catalog["schema_version"] != 1
        or database_catalog["schema_version"] != 1
    ):
        abort("Katalogversion wird nicht unterstützt.")
    programs = expect_mapping(program_catalog["programs"], "programs")
    database_types = expect_mapping(
        database_catalog["database_types"], "database_types"
    )
    if application_id not in programs:
        abort("application_id ist nicht im Programmkatalog freigegeben.")
    if database_type not in database_types:
        abort("database_type ist nicht im Datenbankkatalog freigegeben.")
    program_catalog_entry = validate_catalog_entry(
        programs[application_id], f"programs.{application_id}"
    )
    database_catalog_entry = validate_catalog_entry(
        database_types[database_type], f"database_types.{database_type}"
    )
    if "provider_id" not in database_catalog_entry:
        abort("Datenbankkatalogeintrag enthält keine Provider-ID.")

    program_root = resolve_directory(
        programs_root, application_id, "Testprogrammordner"
    )
    driver_root = resolve_directory(
        database_types_root, database_type, "Datenbankdriverordner"
    )
    manifest_path = program_root / "program.yml"
    driver_path = driver_root / "driver.yml"
    manifest = load_yaml(manifest_path, "Programmmanifest")
    driver = load_yaml(driver_path, "Datenbankdriver")
    database_profile = validate_program_manifest(
        manifest, application_id, database_type, arguments.policy, mode
    )
    provider_id = database_profile["provider_id"]
    if program_catalog_entry["display_name"] != manifest["display_name"]:
        abort("Anzeigename in Programmkatalog und Programmmanifest weicht ab.")
    if database_catalog_entry["provider_id"] != provider_id:
        abort("Provider-ID in Datenbankkatalog und Programmmanifest weicht ab.")
    validate_driver(driver, database_type, provider_id, mode)

    runtime_plan: dict[str, Any] = {
        "compose_source": "",
        "compose_sha256": "none",
        "compatibility_id": "none",
        "sharing_scope": "none",
    }
    if mode == "shared_runtime":
        runtime_relative = driver["pool"]["shared_runtime_compose"]
        if runtime_relative is None:
            abort("Shared-Runtime besitzt keine deklarierte Compose-Datei.")
        runtime_path = resolve_file(
            driver_root,
            runtime_relative,
            "Shared-Runtime-Compose-Datei",
        )
        runtime_sha256 = sha256_file(runtime_path)
        runtime_plan = {
            "compose_source": str(runtime_path),
            "compose_sha256": runtime_sha256,
            "compatibility_id": "runtime-v1-" + hashlib.sha256(
                json.dumps(
                    {
                        "provider_id": provider_id,
                        "driver_sha256": sha256_file(driver_path),
                        "compose_sha256": runtime_sha256,
                        "storage_schema": driver["pool"]["storage_schema"],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "sharing_scope": driver["pool"]["default_sharing_scope"],
        }

    compose_relative = database_profile["compose"][mode]
    compose_path = resolve_file(
        program_root, compose_relative, "Compose-Datei"
    )
    materialized_files: list[dict[str, Any]] = []
    compatibility_files: list[dict[str, str]] = [
        {
            "path": str(manifest_path.relative_to(root)).replace("\\", "/"),
            "sha256": sha256_file(manifest_path),
        },
        {
            "path": str(driver_path.relative_to(root)).replace("\\", "/"),
            "sha256": sha256_file(driver_path),
        },
        {
            "path": str(compose_path.relative_to(root)).replace("\\", "/"),
            "sha256": sha256_file(compose_path),
        },
    ]
    for index, configuration in enumerate(
        database_profile["configuration_files"]
    ):
        source_path = resolve_file(
            program_root,
            configuration["source"],
            f"Konfigurationsdatei {index}",
        )
        materialized_files.append(
            {
                "source": str(source_path),
                "destination": configuration["destination"],
                "mode": configuration["mode"],
            }
        )
        compatibility_files.append(
            {
                "path": str(source_path.relative_to(root)).replace("\\", "/"),
                "sha256": sha256_file(source_path),
            }
        )

    notification_root = resolve_directory(root, "mail", "Zentrales Mailpaket")
    notification_manifest_path = resolve_file(
        notification_root,
        "notification.yml",
        "Zentrales Mailmanifest",
    )
    notification = load_yaml(
        notification_manifest_path,
        "Zentrales Mailmanifest",
    )
    require_keys(
        notification,
        {"schema_version", "enabled_input", "subject", "logo", "template"},
        {"schema_version", "enabled_input", "subject", "logo", "template"},
        "Zentrales Mailmanifest",
    )
    if notification["schema_version"] != 1:
        abort("Zentrale Mailmanifest-Version wird nicht unterstuetzt.")
    validate_variable_name(
        notification["enabled_input"],
        "Zentrales Mailmanifest.enabled_input",
    )
    validate_display_name(
        notification["subject"],
        "Zentrales Mailmanifest.subject",
    )
    logo_path = resolve_file(
        notification_root,
        notification["logo"],
        "Zentrales Benachrichtigungslogo",
    )
    if logo_path.suffix.lower() != ".png":
        abort("Das zentrale Benachrichtigungslogo muss eine PNG-Datei sein.")
    template_path = resolve_file(
        notification_root,
        notification["template"],
        "Zentrales Benachrichtigungstemplate",
    )
    notification_plan = {
        "enabled_input": notification["enabled_input"],
        "subject": notification["subject"],
        "logo": str(logo_path),
        "template": str(template_path),
    }
    for notification_file in (
        notification_manifest_path,
        logo_path,
        template_path,
    ):
        compatibility_files.append(
            {
                "path": str(notification_file.relative_to(root)).replace(
                    "\\", "/"
                ),
                "sha256": sha256_file(notification_file),
            }
        )

    driver_formats = set(driver["capabilities"]["formats"])
    dataset_plan: dict[str, Any] = {
        "id": "none",
        "format": "none",
        "file": "",
        "sha256": "none",
        "validator": "",
    }
    dataset_catalog_path = resolve_file(
        program_root, manifest["datasets"]["catalog"], "Datasetkatalog"
    )
    dataset_catalog = load_yaml(dataset_catalog_path, "Datasetkatalog")
    require_keys(
        dataset_catalog,
        {"schema_version", "datasets"},
        {"schema_version", "datasets"},
        "Datasetkatalog",
    )
    if dataset_catalog["schema_version"] != 1:
        abort("Datasetkatalog-Version wird nicht unterstützt.")
    datasets = expect_mapping(dataset_catalog["datasets"], "datasets")
    if dataset_id == "none":
        if not manifest["datasets"]["optional"]:
            abort("Für dieses Testprogramm muss ein Dataset gewählt werden.")
    else:
        if dataset_id not in datasets:
            abort("dataset_id ist für das gewählte Testprogramm nicht freigegeben.")
        selected_dataset = expect_mapping(
            datasets[dataset_id], f"datasets.{dataset_id}"
        )
        require_keys(
            selected_dataset,
            {
                "description",
                "format",
                "database_type",
                "provider_ids",
                "file",
                "sha256",
                "contains_schema",
                "engine_major",
                "compatible_image_tags",
            },
            {
                "description",
                "format",
                "database_type",
                "provider_ids",
                "file",
                "sha256",
                "contains_schema",
                "engine_major",
                "compatible_image_tags",
            },
            f"datasets.{dataset_id}",
        )
        if selected_dataset["database_type"] != database_type:
            abort("Dataset und Datenbanktyp sind nicht kompatibel.")
        validate_description(selected_dataset["description"], "dataset.description")
        provider_ids = expect_list(
            selected_dataset["provider_ids"], "dataset.provider_ids"
        )
        if (
            not provider_ids
            or any(
                not isinstance(item, str) or PROVIDER_RE.fullmatch(item) is None
                for item in provider_ids
            )
            or len(provider_ids) != len(set(provider_ids))
        ):
            abort("dataset.provider_ids ist ungültig.")
        if provider_id not in provider_ids:
            abort("Dataset und Datenbankprovider sind nicht kompatibel.")
        dataset_format = validate_id(
            selected_dataset["format"], "dataset.format", SHORT_ID_RE
        )
        if dataset_format not in driver_formats:
            abort("Datasetformat wird vom Datenbankdriver nicht unterstützt.")
        if not isinstance(selected_dataset["contains_schema"], bool) or not (
            selected_dataset["contains_schema"]
        ):
            abort("Dataset muss das benötigte Schema enthalten.")
        if (
            not isinstance(selected_dataset["engine_major"], int)
            or isinstance(selected_dataset["engine_major"], bool)
            or selected_dataset["engine_major"]
            not in driver["engine"]["supported_majors"]
            or selected_dataset["engine_major"] != driver["engine"]["default_major"]
        ):
            abort("Dataset und Engine-Major sind nicht kompatibel.")
        compatible_image_tags = expect_list(
            selected_dataset["compatible_image_tags"],
            "dataset.compatible_image_tags",
        )
        if any(
            not isinstance(item, str)
            or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}", item) is None
            for item in compatible_image_tags
        ) or len(compatible_image_tags) != len(set(compatible_image_tags)):
            abort("dataset.compatible_image_tags ist ungültig.")
        if not isinstance(selected_dataset["sha256"], str) or SHA256_RE.fullmatch(
            selected_dataset["sha256"]
        ) is None:
            abort("Dataset-SHA-256 ist ungültig.")
        dataset_relative = selected_dataset["file"]
        if not isinstance(dataset_relative, str) or Path(dataset_relative).name != (
            dataset_relative
        ):
            abort("Dataset-Dateiname ist ungültig.")
        dataset_path = resolve_file(
            dataset_catalog_path.parent,
            dataset_relative,
            "Datasetdatei",
        )
        if dataset_path.stat().st_size > arguments.max_dataset_bytes:
            abort("Dataset überschreitet die erlaubte Maximalgröße.")
        actual_sha256 = sha256_file(dataset_path)
        if actual_sha256 != selected_dataset["sha256"].lower():
            abort("Dataset-SHA-256 stimmt nicht mit dem Katalog überein.")
        validator_relative = driver["datasets"]["validators"][dataset_format]
        validator_path = ""
        if validator_relative is not None:
            validator_path = str(
                resolve_file(
                    driver_root,
                    validator_relative,
                    "Datasetvalidator",
                )
            )
        dataset_plan = {
            "id": dataset_id,
            "format": dataset_format,
            "file": str(dataset_path),
            "sha256": actual_sha256,
            "validator": validator_path,
            "contains_schema": selected_dataset["contains_schema"],
            "engine_major": selected_dataset["engine_major"],
            "compatible_image_tags": compatible_image_tags,
        }
        compatibility_files.append(
            {
                "path": str(dataset_catalog_path.relative_to(root)).replace(
                    "\\", "/"
                ),
                "sha256": sha256_file(dataset_catalog_path),
            }
        )

    compatibility_payload = {
        "application_id": application_id,
        "profile_version": manifest["profile_version"],
        "database_type": database_type,
        "provider_id": provider_id,
        "mode": mode,
        "files": compatibility_files,
    }
    compatibility_id = "compat-v2-" + hashlib.sha256(
        json.dumps(
            compatibility_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return {
        "plan_version": 1,
        "application": {
            "id": application_id,
            "display_name": manifest["display_name"],
            "profile_version": manifest["profile_version"],
            "root": str(program_root),
            "primary_service": manifest["application"]["primary_service"],
            "expected_services": manifest["application"]["expected_services"][
                mode
            ],
            "release": manifest["release"],
            "compatibility_id": compatibility_id,
        },
        "database": {
            "type": database_type,
            "provider_id": provider_id,
            "policy": arguments.policy,
            "mode": mode,
            "profile": database_profile,
            "driver": driver,
            "runtime": runtime_plan,
        },
        "compose": {
            "source": str(compose_path),
            "configuration_files": materialized_files,
        },
        "endpoint": manifest["endpoint"],
        "runtime": manifest["runtime"],
        "readiness": manifest["readiness"],
        "secrets": manifest["secrets"],
        "dataset": dataset_plan,
        "notification": notification_plan,
        "compatibility_files": compatibility_files,
    }


