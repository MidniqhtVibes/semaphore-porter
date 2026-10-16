from copy import deepcopy

import json
import pytest

from app.project_backup import prepare_backup, survey_catalog, validate_backup
from app.project_backup import BackupValidationError


SOURCE = {
    "meta": {"name": "Vorlage"},
    "templates": [
        {
            "name": "deploy-timed-demo",
            "repository": "Git",
            "inventory": "Local",
            "environment": "Defaults",
            "survey_vars": [
                {"name": "tenant_slug", "title": "Tenant", "default_value": "old", "values": []},
                {"name": "dataset_id", "type": "enum", "default_value": "none", "values": [{"name": "Ohne", "value": "none"}, {"name": "Smoke", "value": "smoke-v1"}]},
            ],
        }
    ],
    "environments": [{"name": "Defaults", "json": "{}", "env": "{}"}],
    "repositories": [{"name": "Git", "git_url": "https://git.invalid/repo", "git_branch": "main"}],
    "inventories": [{"name": "Local", "inventory": "inventory.ini", "type": "file"}],
    "keys": [],
    "schedules": [{"name": "nightly"}],
    "integrations": [{"name": "webhook"}],
}


def test_preparation_keeps_source_immutable_and_removes_automatic_triggers():
    original = deepcopy(SOURCE)
    result = prepare_backup(
        SOURCE,
        {
            "project_name": "AzubiOrga – Kunde A",
            "tenant_slug": "kunde-a",
            "runtime_scope_id": "scope-a",
            "application_id": "azubiorga",
            "dataset_id": "smoke-v1",
            "task_template_names": ["deploy-timed-demo"],
            "environment_names": ["Defaults"],
            "preset_values": [{"name": "Deployment", "values": {"host_port": 0}}],
        },
    )
    assert SOURCE == original
    assert result["meta"]["name"] == "AzubiOrga – Kunde A"
    assert result["schedules"] == [] and result["integrations"] == []
    tenant_group = next(item for item in result["environments"] if item["name"] == "Semaphore-Defaults")
    assert '"host_port":0' in tenant_group["json"]
    assert result["templates"][0]["environments"] == ["Defaults", "Semaphore-Defaults"]
    assert validate_backup(result)[0] == []


def test_defaults_replace_copied_identity_and_preserve_other_values():
    import json
    source = deepcopy(SOURCE)
    source["environments"] = [{"name": "Semaphore-Defaults", "json": json.dumps({"tenant_slug": "old", "runtime_scope_id": "old", "custom": 42}), "env": "{}"}]
    source["templates"][0]["environment"] = "Semaphore-Defaults"
    source["templates"][0]["survey_vars"].append({"name": "runtime_scope_id"})
    result = prepare_backup(source, {"project_name": "New", "tenant_slug": "new-a", "runtime_scope_id": "new-scope"})
    assert json.loads(result["environments"][0]["json"]) == {"tenant_slug": "new-a", "runtime_scope_id": "new-scope", "custom": 42}
    assert not {"tenant_slug", "runtime_scope_id"}.intersection(x["name"] for x in result["templates"][0]["survey_vars"])
    assert source["templates"][0]["survey_vars"][0]["name"] == "tenant_slug"


def test_empty_group_selection_removes_source_groups_and_credentials():
    source = deepcopy(SOURCE)
    source["environments"][0]["json"] = '{"vault_approle_secret_id":"do-not-copy"}'
    result = prepare_backup(source, {"project_name": "New", "tenant_slug": "new-a", "runtime_scope_id": "new-scope", "environment_names": []})
    assert [x["name"] for x in result["environments"]] == ["Semaphore-Defaults"]
    assert "do-not-copy" not in str(result)


def test_copy_requires_explicit_scope_and_tasks():
    import pytest
    from app.project_backup import BackupValidationError
    with pytest.raises(BackupValidationError, match="runtime_scope_id"):
        prepare_backup(SOURCE, {"project_name": "New", "tenant_slug": "new-a"})
    with pytest.raises(BackupValidationError, match="Task Template"):
        prepare_backup(SOURCE, {"project_name": "New", "tenant_slug": "new-a", "runtime_scope_id": "scope-a", "task_template_names": []})


def test_vault_paths_survive_copy_but_bootstrap_credentials_do_not():
    import json
    source = deepcopy(SOURCE)
    source["environments"][0]["json"] = json.dumps({"vault_tenant_secret_root": "semaphore/tenants", "vault_provider_secret_paths": {"postgresql-v1": "tenant/providers/pg"}, "vault_approle_role_id": "old-role", "nested": {"password": "old-password", "public": "keep"}})
    source["environments"][0]["secrets"] = [{"name": "ANSIBLE_HASHI_VAULT_SECRET_ID", "secret": "old-secret"}]
    result = prepare_backup(source, {"project_name": "New", "tenant_slug": "new-a", "runtime_scope_id": "scope-a"})
    values = json.loads(result["environments"][0]["json"])
    assert values["vault_tenant_secret_root"] == "semaphore/tenants"
    assert values["vault_provider_secret_paths"]["postgresql-v1"] == "tenant/providers/pg"
    assert "old-role" not in str(result) and "old-secret" not in str(result) and "old-password" not in str(result)


def test_initial_policy_matches_stack_and_keeps_identity_outside_survey():
    from app.routers.admin import _default_policy_rules
    survey = [{"name": "tenant_slug"}, {"name": "runtime_scope_id"}, {"name": "ttl_minutes"}, {"name": "existing_environment_policy", "values": [{"value": "always_new"}, {"value": "reuse_only"}]}, {"name": "application_release_id"}, {"name": "send_deployment_mail"}, {"name": "mail_user"}]
    rules = {rule["variable_name"]: rule for rule in _default_policy_rules(survey, {})}
    assert "tenant_slug" not in rules and "runtime_scope_id" not in rules
    assert rules["ttl_minutes"]["minimum"] == 5 and rules["ttl_minutes"]["maximum"] == 1440
    assert rules["existing_environment_policy"]["allowed_values"] == ["always_new", "reuse_only"]
    assert rules["send_deployment_mail"]["default_value"] is False


def test_survey_catalog_uses_only_actual_values():
    assert survey_catalog(SOURCE) == {"dataset_id": ["none", "smoke-v1"]}


def test_multiple_options_filter_surveys_and_keep_scalar_defaults():
    source = deepcopy(SOURCE)
    source["templates"][0]["survey_vars"] += [
        {"name": name, "values": [{"value": value} for value in values]}
        for name, values in {"application_id": ["azubiorga", "wordpress", "other"], "database_type": ["postgresql", "mariadb", "mysql"]}.items()
    ]
    draft = {"project_name": "New", "tenant_slug": "new-a", "runtime_scope_id": "scope-a", "application_ids": ["wordpress", "azubiorga"], "database_types": ["mariadb", "postgresql"], "dataset_ids": ["smoke-v1", "none"]}
    prepared = prepare_backup(source, draft)
    variables = json.loads(next(group["json"] for group in prepared["environments"] if group["name"] == "Semaphore-Defaults"))
    assert variables["application_id"] == "wordpress"
    assert variables["database_type"] == "mariadb"
    assert variables["dataset_id"] == "smoke-v1"
    assert not any(isinstance(variables[name], list) for name in ("application_id", "database_type", "dataset_id"))
    catalog = survey_catalog(prepared)
    assert catalog["application_id"] == ["azubiorga", "wordpress"]
    assert catalog["database_type"] == ["postgresql", "mariadb"]
    assert source["templates"][0]["survey_vars"][-1]["values"][-1]["value"] == "mysql"
    from app.routers.admin import _default_policy_rules
    rules = {rule["variable_name"]: rule for rule in _default_policy_rules(source["templates"][0]["survey_vars"], draft)}
    assert rules["application_id"]["allowed_values"] == ["wordpress", "azubiorga"]
    assert rules["dataset_id"]["default_value"] == "smoke-v1"


@pytest.mark.parametrize("selection", [[], ["not-in-source"]])
def test_explicit_empty_or_unknown_choices_fail_closed(selection):
    with pytest.raises(BackupValidationError, match="dataset_id"):
        prepare_backup(SOURCE, {"project_name": "New", "tenant_slug": "new-a", "runtime_scope_id": "scope-a", "dataset_ids": selection})


def test_each_task_keeps_a_supported_default_for_its_subset():
    source = deepcopy(SOURCE)
    source["templates"].append({**deepcopy(source["templates"][0]), "name": "second", "survey_vars": [{"name": "dataset_id", "values": [{"value": "other-data"}]}]})
    prepared = prepare_backup(source, {"project_name": "New", "tenant_slug": "new-a", "runtime_scope_id": "scope-a", "dataset_ids": ["smoke-v1", "other-data"]})
    assert prepared["templates"][1]["survey_vars"][0]["default_value"] == "other-data"
    with pytest.raises(BackupValidationError, match="second"):
        prepare_backup(source, {"project_name": "New", "tenant_slug": "new-a", "runtime_scope_id": "scope-a", "dataset_ids": ["smoke-v1"]})

