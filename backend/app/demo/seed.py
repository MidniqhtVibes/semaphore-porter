"""Synthetic fixtures for the in-memory presentation database only."""
from __future__ import annotations

import json
import secrets
import uuid

from sqlalchemy import select

from app.config import get_settings

HOSTS = {"semaphore": "semaphore.demo.invalid", "vault": "vault.demo.invalid", "gitlab": "gitlab.demo.invalid"}
ACTORS = {"admin": "system_admin", "tenant_admin": "tenant_admin", "operator": "operator", "viewer": "viewer"}


def identifier(name):
    return uuid.uuid5(uuid.NAMESPACE_URL, "https://semaporter.demo.invalid/" + name)


def backup(name="Demo-Basis", slug="demo-basis"):
    surveys = [{"name": key, "type": "enum", "required": True, "values": [{"value": value} for value in values]}
               for key, values in {"application_id": ["azubiorga", "wordpress"], "database_type": ["postgresql", "mariadb", "mysql"], "dataset_id": ["none"]}.items()]
    surveys.append({"name": "ttl_minutes", "type": "int", "default_value": 60})
    return {"meta": {"name": name, "alert": False, "max_parallel_tasks": 2},
        "environments": [{"name": "Semaphore-Defaults", "json": json.dumps({"tenant_slug": slug, "runtime_scope_id": slug + "-apps",
            "azubiorga_registry_host":"registry.demo.invalid", "azubiorga_registry_username":"demo",
            "wordpress_registry_host":"registry-wp.demo.invalid", "wordpress_registry_username":"demo"}), "env": "{}"}],
        "keys": [{"name": "Demo SSH", "type": "ssh"}],
        "repositories": [{"name": "Demo-Stack", "git_url": "git@gitlab.demo.invalid:demo/stack.git", "git_branch": "main", "ssh_key": "Demo SSH"}],
        "inventories": [{"name": "Demo-Host", "type": "static", "inventory": "[docker_test]\ndemo ansible_host=192.0.2.10 ansible_user=deploy\n", "ssh_key": "Demo SSH"}],
        "templates": [{"name": "Deployment starten", "app": "ansible", "playbook": "playbooks/deploy-temporary-program.yml", "repository": "Demo-Stack", "inventory": "Demo-Host", "environment": "Semaphore-Defaults", "survey_vars": surveys},
                      {"name": "Check-Hosts", "app": "ansible", "playbook": "playbooks/check-hosts.yml", "repository": "Demo-Stack", "inventory": "Demo-Host", "environment": "Semaphore-Defaults", "survey_vars": []}]}


def assert_demo(db=None):
    settings = get_settings()
    if not settings.demo_mode or settings.database_url != "sqlite+pysqlite:///:memory:":
        raise RuntimeError("Demo-Operation außerhalb der isolierten Demo abgelehnt.")
    if db is not None:
        from app.database import session_context
        factory = session_context.get()
        engine = db.get_bind()
        if factory is None or engine is not factory.kw["bind"] or engine.url.get_backend_name() != "sqlite" or engine.url.query.get("mode") != "memory":
            raise RuntimeError("Demo-Operation benötigt die eigene flüchtige Demo-Datenbank.")


def initialize():
    from app.database import Base, SessionLocal
    from app.models import Role
    assert_demo()
    with SessionLocal() as db:
        assert_demo(db)
        Base.metadata.create_all(db.get_bind())
        if db.scalar(select(Role.id).limit(1)) is None:
            seed(db)
            db.commit()


def seed(db):
    from app.models import (Role, User, Group, GroupMembership, Tenant, TenantStatus, TenantMembership,
        SemaphoreProject, ProjectTemplate, SemaphoreSettings, VaultSettings, CredentialSettings,
        CredentialProfile, GitLabSettings, TaskTemplate, TaskPolicy, VariableRule, RuleType, TaskPermission,
        Preset, PresetVersion, RegistrySettings, RegistryProfile, utcnow)
    from app.bootstrap import ROLES, BUILTIN_PRESETS
    from app.security import encrypt_secret, hash_password
    from app.demo.simulator import reset_state, project_templates, private_key
    assert_demo(db)
    reset_state()
    role_rows = {code: Role(id=rid, code=code, name=name, description=description) for rid, code, name, description in ROLES}
    db.add_all(role_rows.values())
    users = {}
    password_hash = hash_password(secrets.token_urlsafe(40))
    for actor, role in ACTORS.items():
        user = User(id=identifier("user/" + actor), email=f"demo.{actor}@example.com", username="demo." + actor,
            display_name={"admin":"Demo Administrator", "tenant_admin":"Demo Tenant-Admin", "operator":"Demo Operator", "viewer":"Demo Viewer"}[actor],
            password_hash=password_hash, must_change_password=False, color="blue" if actor=="admin" else "green", tags=["Demo", role],
            position={"admin":"Plattformadministration","tenant_admin":"Anwendungsbetreuung","operator":"Deployment-Betrieb","viewer":"Qualitätssicherung"}[actor],
            department="Demo IT", location="Beispielstandort", bio="Fiktives Profil für die Semaporter-Vorführung.",
            skills=["Semaphore", "Docker"], responsibilities=["Betriebsprüfung"], profile_color="blue" if actor=="admin" else "green")
        user.roles = [role_rows[role]]
        users[actor] = user
        db.add(user)
    db.add(User(id=identifier("user/disabled"), email="demo.disabled@example.com", username="demo.disabled", display_name="Demo – deaktiviert",
                password_hash=password_hash, is_active=False, color="rose", tags=["Demo"]))
    group = Group(id=identifier("group/operators"), name="Demo Betrieb", description="Erfundenes Team für die Vorführung", color="violet", tags=["Demo", "Betrieb"],
        is_team=True, responsibilities=["Deployment-Betrieb", "Monitoring"], responsibility_notes="Gemeinsame technische Zuständigkeiten des Demo-Teams.")
    db.add(group)
    db.flush()
    db.add(GroupMembership(group_id=group.id, user_id=users["operator"].id))
    users["operator"].primary_team_id = group.id
    for project_id, name, slug in [(1,"Nordstadt","nordstadt"),(2,"Südtal","suedtal"),(3,"Internes Labor","labor")]:
        tenant = Tenant(id=identifier("tenant/"+slug), tenant_slug=slug, display_name=name, status=TenantStatus.ACTIVE,
            configuration_complete=True, application_id="azubiorga", application_ids=["azubiorga", "wordpress"],
            database_types=["postgresql", "mariadb", "mysql"], dataset_ids=["none"], description="Simulierte Demo-Daten")
        tenant.semaphore_project = SemaphoreProject(semaphore_project_id=project_id, name="Demo · "+name)
        db.add(tenant)
        for template in project_templates(project_id):
            task = TaskTemplate(id=identifier(f"task/{project_id}/{template['id']}"), semaphore_template_id=template["id"],
                name=template["name"], app="ansible", is_enabled=True, survey_schema=template["survey_vars"])
            tenant.task_templates.append(task)
            policy = TaskPolicy(name="Demo · " + task.name, is_active=True)
            if task.name == "Deployment starten":
                policy.variable_rules = [VariableRule(variable_name=k, title=title, rule_type=RuleType.ENUM, allowed_values=values, default_value=values[0], is_required=True, position=i)
                    for i,(k,title,values) in enumerate([("application_id","Anwendung",["azubiorga","wordpress"]),("database_type","Datenbank",["postgresql","mariadb","mysql"]),("dataset_id","Dataset",["none"])])]
                policy.variable_rules.append(VariableRule(variable_name="ttl_minutes", title="Laufzeit (Minuten)", rule_type=RuleType.INTEGER_RANGE, minimum=5, maximum=1440, default_value=60, position=3))
            task.policy = policy
        db.flush()
        if project_id == 1:
            db.add(TenantMembership(tenant_id=tenant.id, group_id=group.id, role_code="operator"))
            db.add(TenantMembership(tenant_id=tenant.id, user_id=users["viewer"].id, role_code="viewer"))
        if project_id == 2:
            db.add(TenantMembership(tenant_id=tenant.id, user_id=users["tenant_admin"].id, role_code="tenant_admin"))
        for task in tenant.task_templates:
            if project_id == 1:
                db.add(TaskPermission(task_template_id=task.id, group_id=group.id, can_view=True, can_start=True, can_stop=True))
                db.add(TaskPermission(task_template_id=task.id, user_id=users["viewer"].id, can_view=True, can_start=False, can_stop=False))
            if project_id == 2:
                db.add(TaskPermission(task_template_id=task.id, user_id=users["tenant_admin"].id, can_view=True, can_start=True, can_stop=True))
    db.add(ProjectTemplate(id=identifier("template/base"), name="Demo-Basis", description="Synthetische Projektvorlage für die Präsentation", source_type="upload", backup_document=backup()))
    db.add(SemaphoreSettings(id=1, base_url="https://"+HOSTS["semaphore"], encrypted_token=encrypt_secret("demo-semaphore-token"), last_test_success=True, last_tested_at=utcnow()))
    vault = {"enabled": True, "base_url": "https://"+HOSTS["vault"], "namespace": "", "kv_mount": "kv", "tenant_root": "semaphore",
        "writer_auth_mount": "semaphore-ansible", "reader_auth_mount": "semaphore-ansible", "writer_role_id": "demo-writer", "writer_secret_id": "demo-writer-secret",
        "reader_role_id": "demo-reader", "reader_secret_id": "demo-reader-secret", "registry_passwords": {"azubiorga":"demo-registry-password", "wordpress":"demo-registry-password"}}
    db.add(VaultSettings(id=1, encrypted_configuration=encrypt_secret(json.dumps(vault))))
    from app.registry_service import connection_id
    registry_reader={"base_url":"https://"+HOSTS["vault"],"namespace":"","kv_mount":"kv","auth_mount":"semaphore-ansible","role_id":"demo-reader","secret_id":"demo-reader-secret"}
    db.add(RegistrySettings(id=1, encrypted_configuration=encrypt_secret(json.dumps(registry_reader))))
    for app,host in [("azubiorga","registry.demo.invalid"),("wordpress","registry-wp.demo.invalid")]:
        db.add(RegistryProfile(id=identifier("registry/"+app),name="Demo Registry · "+app,application_id=app,host=host,username="demo",
            host_variable=app+"_registry_host",username_variable=app+"_registry_username",source="stored" if app=="azubiorga" else "vault",
            encrypted_password=encrypt_secret("demo-registry-password") if app=="azubiorga" else None,
            vault_path="automation-credentials/registries/demo-wordpress" if app=="wordpress" else None,
            vault_version=1 if app=="wordpress" else None,vault_field="registry_password" if app=="wordpress" else None,
            vault_connection_id=connection_id(registry_reader) if app=="wordpress" else None,revision="demo-registry-"+app,is_active=True))
    db.add(CredentialSettings(id=1, encrypted_configuration=encrypt_secret(json.dumps({"base_url":"https://"+HOSTS["vault"],"namespace":"","kv_mount":"kv","auth_mount":"semaphore-ansible","role_id":"demo-reader","secret_id":"demo-reader-secret"}))))
    from cryptography.hazmat.primitives import serialization
    import base64, hashlib
    public = serialization.load_ssh_private_key(private_key().encode(), password=None).public_key().public_bytes(serialization.Encoding.OpenSSH,serialization.PublicFormat.OpenSSH).decode()
    fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(base64.b64decode(public.split()[1])).digest()).decode().rstrip("=")
    for kind, login, target in [("host","deploy","192.0.2.10"),("git","git","git@gitlab.demo.invalid:demo/stack.git")]:
        db.add(CredentialProfile(id=identifier("profile/"+kind), name="Demo · "+kind, purpose=kind, login=login,
            vault_path="automation-credentials/ssh/demo-"+kind, vault_version=1, allowed_targets=[target],
            fingerprint=fingerprint, public_key=public, last_tested_at=utcnow()))
    db.add(GitLabSettings(id=1, encrypted_configuration=encrypt_secret(json.dumps({"base_url":"https://"+HOSTS["gitlab"], "project_id":7,
        "base_branch":"main", "write_enabled":True, "token":"demo-gitlab-token", "connection_id":"demo-connection",
        "project_name":"demo/stack", "web_url":"https://gitlab.demo.invalid/demo/stack", "protected":True}))))
    for name,category,values in BUILTIN_PRESETS:
        preset=Preset(name=name,category=category,description="Demo-Beispiel",is_builtin=True)
        preset.versions.append(PresetVersion(version=1,values=values))
        db.add(preset)
