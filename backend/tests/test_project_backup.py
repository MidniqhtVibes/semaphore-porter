from copy import deepcopy

from app.project_backup import prepare_backup, survey_catalog, validate_backup


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
    tenant_group = next(item for item in result["environments"] if item["name"].startswith("Tenant-kunde-a"))
    assert '"host_port":0' in tenant_group["json"]
    assert validate_backup(result)[0] == []


def test_survey_catalog_uses_only_actual_values():
    assert survey_catalog(SOURCE) == {"dataset_id": ["none", "smoke-v1"]}

