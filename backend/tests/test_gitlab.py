import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import uuid

import httpx
import pytest
import respx
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.database import SessionLocal
from app.gitlab_client import GitLabClient, GitLabError, safe_file_path
from app.gitlab_schemas import PackageCreate
from app.models import GitLabSettings, ProgramPackageDraft, ProjectTemplate, utcnow
from app.package_validation import (compose_safety, encode, generate_package, read_yaml, validate_snapshot)
from app.security import decrypt_secret
from app.vault_catalog import load_catalog

A, B = "a" * 40, "b" * 40
CONFIG = {"base_url": "https://gitlab.example", "project_id": 7, "base_branch": "main", "write_enabled": True, "token": "private-gitlab-token"}
STACK = json.loads((Path(__file__).parent / "fixtures/stack.json").read_text())


class FakeGitLab:
    def __init__(self):
        self.config = CONFIG.copy()
        self.project = "projects/7"
        self.files, self.commits, self.branches, self.mrs = {A: copy.deepcopy(STACK)}, {}, {}, []
        self.head, self.protected, self.pipeline_status = A, True, "success"
        self.commit_calls, self.mr_calls = 0, 0
        self.timeout_commit, self.timeout_mr = False, False

    async def get_project(self):
        return {"id": 7, "path_with_namespace": "team/stack", "web_url": "https://gitlab.example/team/stack",
                "http_url_to_repo": "https://gitlab.example/team/stack.git", "ssh_url_to_repo": "git@gitlab.example:team/stack.git"}

    async def branch(self, name, *, absence_ok=False):
        if name == "main":
            return {"commit": {"id": self.head}, "protected": self.protected}
        if name in self.branches:
            return {"commit": {"id": self.branches[name]}}
        if absence_ok:
            return None
        raise GitLabError("Nicht gefunden.", status=404)

    async def snapshot(self, sha):
        return copy.deepcopy(self.files[sha])

    async def request(self, method, path, **kwargs):
        assert method == "GET" and "/repository/commits/" in path
        return self.commits[path.rsplit("/", 1)[-1]]

    async def commit(self, payload):
        self.commit_calls += 1
        assert payload["force"] is False and payload["start_sha"] == A
        assert payload["branch"] not in self.branches
        result = copy.deepcopy(self.files[A])
        for action in payload["actions"]:
            assert action["file_path"].startswith("programs/")
            if action["action"] == "delete":
                del result[action["file_path"]]
            else:
                assert action["encoding"] == "base64"
                result[action["file_path"]] = action["content"]
        self.branches[payload["branch"]], self.files[B] = B, result
        self.commits[B] = {"id": B, "parent_ids": [A], "message": payload["commit_message"]}
        if self.timeout_commit:
            self.timeout_commit = False
            raise GitLabError("Timeout nach Commit.", uncertain=True)
        return {"id": B}

    async def merge_requests(self, branch):
        return [mr for mr in self.mrs if mr["source_branch"] == branch]

    async def create_merge_request(self, payload):
        self.mr_calls += 1
        mr = {**payload, "iid": 42, "state": "opened", "source_project_id": 7, "target_project_id": 7,
              "web_url": "https://gitlab.example/team/stack/-/merge_requests/42", "sha": B}
        self.mrs.append(mr)
        if self.timeout_mr:
            self.timeout_mr = False
            raise GitLabError("Timeout nach MR.", uncertain=True)
        return mr

    async def merge_request(self, iid):
        return self.mrs[0]

    async def pipelines(self, sha):
        return [{"id": 80, "sha": sha, "ref": "main", "status": self.pipeline_status,
                 "web_url": "https://gitlab.example/team/stack/-/pipelines/80"}]

    def web_link(self, value):
        return value if isinstance(value, str) and value.startswith("https://gitlab.example/") else None


@pytest.fixture
def gitlab(monkeypatch):
    fake = FakeGitLab()

    def factory(config):
        fake.config = config
        return fake
    monkeypatch.setattr("app.gitlab_service.GitLabClient", factory)
    return fake


def connect(client, headers, **changes):
    response = client.put("/api/admin/gitlab", headers=headers, json={**CONFIG, **changes})
    assert response.status_code == 200, response.text
    return response.json()


def create(client, headers, **changes):
    response = client.post("/api/admin/program-packages", headers=headers, json={
        "package_id": "demo", "name": "Demo", "image_repository": "nginx", "release": "1.27", "container_port": 80, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def validate(client, headers, draft):
    response = client.post(f"/api/admin/program-packages/{draft['id']}/validate", headers=headers, json={"version": draft["version"]})
    assert response.status_code == 200, response.text
    return response.json()


def seed_template():
    with SessionLocal() as db:
        source = ProjectTemplate(name="Base", source_type="upload", backup_document={"meta": {"name": "Base"},
            "repositories": [{"name": "Stack", "git_url": "https://gitlab.example/team/stack.git", "git_branch": "main"}],
            "templates": [{"name": "deploy", "repository": "Stack", "survey_vars": [
                {"name": name, "type": "enum", "values": [{"name": "old", "value": "old"}], "default_value": "old"}
                for name in ("application_id", "database_type", "dataset_id")]}], "environments": []})
        db.add(source)
        db.commit()
        return str(source.id)


def test_gitlab_access_is_admin_only_and_csrf_required(client, operator_headers):
    for path in ("/gitlab", "/gitlab/repository", "/gitlab/snapshots", "/program-packages"):
        assert client.get("/api/admin" + path).status_code == 403
    assert client.put("/api/admin/gitlab", json=CONFIG).status_code == 403
    assert client.put("/api/admin/gitlab", headers=operator_headers, json=CONFIG).status_code == 403


def test_configuration_encrypts_token_preserves_rotation_and_scopes_identity(client, admin_headers, gitlab):
    config = connect(client, admin_headers)
    assert config["token_present"] and "private-gitlab-token" not in json.dumps(config)
    with SessionLocal() as db:
        stored = db.get(GitLabSettings, 1).encrypted_configuration
        assert b"private-gitlab-token" not in stored
        assert json.loads(decrypt_secret(stored))["token"] == CONFIG["token"]
    rotated = connect(client, admin_headers, token="rotated")
    assert rotated["connection_id"] == config["connection_id"]
    assert connect(client, admin_headers, token=None)["connection_id"] == config["connection_id"]
    response = client.put("/api/admin/gitlab", headers=admin_headers, json={**CONFIG, "project_id": 8, "token": None})
    assert response.status_code == 422


def test_real_stack_contracts_and_generated_http_program():
    report, catalog = validate_snapshot(STACK, A)
    assert len(report["checks"]) == 8
    assert set(catalog["applications"]["wordpress"]["database_types"]) == {"mysql", "mariadb"}
    generated = generate_package(STACK, PackageCreate(package_id="demo", name="Demo", image_repository="nginx", release="1.27"))
    report, catalog = validate_snapshot({**STACK, **generated}, A)
    assert "demo" in catalog["applications"] and len(report["checks"]) == 9


def test_create_copy_edit_version_scope_and_no_network_writes(client, admin_headers, gitlab):
    connect(client, admin_headers)
    draft = create(client, admin_headers, source_id="wordpress", package_id="wp-demo", image_repository="wordpress")
    assert draft["manifest"]["secrets"]["vault_profile"] == "wp-demo"
    assert draft["manifest"]["release"]["images"]["wordpress"]["repository_key"].startswith("wp_demo_")
    draft = validate(client, admin_headers, draft)
    manifest = draft["manifest"]
    manifest["display_name"] = "Changed"
    response = client.put(f"/api/admin/program-packages/{draft['id']}", headers=admin_headers,
        json={"version": draft["version"], "files": draft["files"], "manifest": manifest})
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2 and response.json()["validation"] is None
    assert client.put(f"/api/admin/program-packages/{draft['id']}", headers=admin_headers,
        json={"version": 1, "files": draft["files"]}).status_code == 409
    forbidden = {**response.json()["files"], "database-types/mysql/driver.yml": encode("bad")}
    assert client.put(f"/api/admin/program-packages/{draft['id']}", headers=admin_headers,
        json={"version": 2, "files": forbidden}).status_code == 422
    assert gitlab.commit_calls == gitlab.mr_calls == 0


@pytest.mark.parametrize("failure", ["commit", "mr", None])
def test_publish_recovers_timeouts_without_duplicate_commit_or_mr(client, admin_headers, gitlab, failure):
    connect(client, admin_headers)
    draft = validate(client, admin_headers, create(client, admin_headers))
    gitlab.timeout_commit, gitlab.timeout_mr = failure == "commit", failure == "mr"
    path = f"/api/admin/program-packages/{draft['id']}/publish"
    body = {"version": 1, "confirm": True}
    response = client.post(path, headers=admin_headers, json=body)
    if failure:
        assert response.status_code == 502, response.text
        assert client.get(f"/api/admin/program-packages/{draft['id']}").json()["status"] == "verification_required"
        response = client.post(path, headers=admin_headers, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["merge_request_iid"] == 42 and response.json()["commit_sha"] == B
    assert client.post(path, headers=admin_headers, json=body).status_code == 200
    assert gitlab.commit_calls == gitlab.mr_calls == 1
    assert client.put(f"/api/admin/program-packages/{draft['id']}", headers=admin_headers,
        json={"version": 1, "files": draft["files"]}).status_code == 409
    assert client.request("DELETE", f"/api/admin/program-packages/{draft['id']}", headers=admin_headers,
        content=json.dumps({"version": 1})).status_code == 409


@pytest.mark.parametrize("problem", ["read_only", "head_changed", "unprotected", "lease", "unvalidated", "confirmation"])
def test_publish_blocks_unsafe_or_unreviewed_states(client, admin_headers, gitlab, problem):
    connect(client, admin_headers, write_enabled=problem != "read_only")
    draft = create(client, admin_headers)
    if problem != "unvalidated":
        draft = validate(client, admin_headers, draft)
    if problem == "head_changed": gitlab.head = "c" * 40
    if problem == "unprotected": gitlab.protected = False
    if problem == "lease":
        with SessionLocal() as db:
            db.get(ProgramPackageDraft, uuid.UUID(draft["id"])).execution_started_at = utcnow()
            db.commit()
    response = client.post(f"/api/admin/program-packages/{draft['id']}/publish", headers=admin_headers,
        json={"version": 1, "confirm": problem != "confirmation"})
    assert response.status_code in {409, 422}, response.text
    assert gitlab.commit_calls == gitlab.mr_calls == 0


def test_foreign_branch_is_never_reused(client, admin_headers, gitlab):
    connect(client, admin_headers)
    draft = validate(client, admin_headers, create(client, admin_headers))
    branch = f"semaporter/programs/demo/{uuid.UUID(draft['id']).hex}"
    gitlab.branches[branch], gitlab.commits[B] = B, {"parent_ids": [A], "message": "someone else"}
    response = client.post(f"/api/admin/program-packages/{draft['id']}/publish", headers=admin_headers, json={"version": 1, "confirm": True})
    assert response.status_code == 409 and gitlab.commit_calls == 0


def test_lost_mr_response_can_recover_after_merge_and_source_branch_deletion(client, admin_headers, gitlab):
    connect(client, admin_headers)
    draft = validate(client, admin_headers, create(client, admin_headers))
    gitlab.timeout_mr = True
    path = f"/api/admin/program-packages/{draft['id']}/publish"
    assert client.post(path, headers=admin_headers, json={"version": 1, "confirm": True}).status_code == 502
    gitlab.branches.clear()
    gitlab.mrs[0]["state"] = "merged"
    response = client.post(path, headers=admin_headers, json={"version": 1, "confirm": True})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "merged" and gitlab.commit_calls == gitlab.mr_calls == 1


@pytest.mark.parametrize("status", ["failed", "skipped", "running", "manual"])
def test_snapshot_requires_successful_exact_revision_pipeline(client, admin_headers, gitlab, status):
    connect(client, admin_headers)
    gitlab.pipeline_status = status
    response = client.post("/api/admin/gitlab/snapshots", headers=admin_headers)
    assert response.status_code == 422


def test_snapshot_activation_is_atomic_pins_template_and_supports_reviewed_rollback(client, admin_headers, gitlab):
    connect(client, admin_headers)
    template_id = seed_template()
    response = client.post("/api/admin/gitlab/snapshots", headers=admin_headers)
    assert response.status_code == 201, response.text
    snapshot = response.json()
    body = {"expected_active_id": None, "confirm_reviewed": True, "project_template_id": template_id,
            "repository_name": "Stack", "template_name": "Released"}
    path = f"/api/admin/gitlab/snapshots/{snapshot['id']}/activate"
    assert client.post(path, headers=admin_headers, json={**body, "historical": True}).status_code == 422
    activated = client.post(path, headers=admin_headers, json=body)
    assert activated.status_code == 200, activated.text
    assert client.post(path, headers=admin_headers, json=body).status_code == 409
    with SessionLocal() as db:
        source = db.get(ProjectTemplate, uuid.UUID(template_id))
        updated = db.get(ProjectTemplate, uuid.UUID(activated.json()["project_template_id"]))
        assert source.backup_document["repositories"][0]["git_branch"] == "main"
        assert updated.backup_document["repositories"][0]["git_branch"] == A
        assert updated.catalog_snapshot_id == uuid.UUID(snapshot["id"])
        assert load_catalog(db).source_revision == A
    assert client.get("/api/admin/vault/catalog").json()["source_revision"] == A
    gitlab.head, gitlab.pipeline_status = B, "failed"
    rollback = client.post(path, headers=admin_headers, json={**body, "expected_active_id": snapshot["id"], "historical": True})
    assert rollback.status_code == 200, rollback.text
    assert gitlab.commit_calls == gitlab.mr_calls == 0


@pytest.mark.parametrize("path", ["../x", "programs/a/../b", "/tmp/x", "C:/x", "programs\\x", "programs/%2e%2e/x", "programs/.git/config"])
def test_repository_paths_reject_traversal(path):
    with pytest.raises(ValueError): safe_file_path(path)


@pytest.mark.parametrize("source", ["a: 1\na: 2", "a: &a {b: *a}", "a: !!python/object/apply:os.system [echo bad]"])
def test_yaml_rejects_duplicates_cycles_and_code_tags(source):
    with pytest.raises(ValueError): read_yaml(encode(source))


@pytest.mark.parametrize("unsafe", [{"privileged": True}, {"network_mode": "host"}, {"volumes": ["/var/run/docker.sock:/var/run/docker.sock"]}, {"environment": {"PASSWORD": "literal"}}, {"build": "."}])
def test_compose_rejects_host_access_and_literal_secrets(unsafe):
    with pytest.raises(ValueError): compose_safety({"services": {"app": {"image": "nginx:1.27", **unsafe}}}, ["app"])


def test_client_errors_redact_credentials_and_never_follow_redirects():
    client = GitLabClient(CONFIG)
    with respx.mock as mock:
        route = mock.get("https://gitlab.example/api/v4/projects/7").respond(302, headers={"Location": "https://foreign.example"})
        with pytest.raises(GitLabError) as raised:
            asyncio.run(client.get_project())
        assert "private" not in str(raised.value) and route.call_count == 1
        assert client.web_link("javascript:alert(1)") is None
        assert client.web_link("https://foreign.example/x") is None
    with respx.mock as mock:
        mock.post("https://gitlab.example/api/v4/projects/7/repository/commits").respond(500, json={"token": CONFIG["token"]})
        with pytest.raises(GitLabError) as raised:
            asyncio.run(client.commit({"actions": []}))
        assert raised.value.uncertain and CONFIG["token"] not in str(raised.value)


def test_client_snapshot_preserves_bytes_and_rejects_symlinks():
    client = GitLabClient(CONFIG)
    with respx.mock as mock:
        for folder in ("programs", "database-types", "mail"):
            path = f"{folder}/tests/.gitkeep"
            mock.get(f"https://gitlab.example/api/v4/projects/7/repository/tree", params={
                "path": folder, "ref": A, "recursive": True, "per_page": 100, "page": 1}).respond(200, json=[
                    {"path": path, "mode": "100644", "type": "blob"}])
            mock.get(f"https://gitlab.example/api/v4/projects/7/repository/files/{path.replace('/', '%2F')}",
                params={"ref": A}).respond(200, json={"encoding": "base64", "file_path": path, "content": "aGVs\nbG8="})
        files = asyncio.run(client.snapshot(A))
        assert len(files) == 3 and set(files.values()) == {encode("hello")}
    with respx.mock as mock:
        mock.get("https://gitlab.example/api/v4/projects/7/repository/tree").respond(200, json=[
            {"path": "programs/demo/link", "mode": "120000", "type": "blob"}])
        with pytest.raises(GitLabError): asyncio.run(client.snapshot(A))


@pytest.mark.parametrize("mismatch", ["missing", "wrong_sha", "wrong_ref", "newer_failed"])
def test_release_gate_rejects_missing_wrong_or_outdated_pipeline(client, admin_headers, gitlab, mismatch):
    connect(client, admin_headers)

    async def pipelines(sha):
        if mismatch == "missing": return []
        rows = [{"id": 1, "sha": B if mismatch == "wrong_sha" else sha,
                 "ref": "other" if mismatch == "wrong_ref" else "main", "status": "success"}]
        if mismatch == "newer_failed": rows.append({"id": 2, "sha": sha, "ref": "main", "status": "failed"})
        return rows
    gitlab.pipelines = pipelines
    assert client.post("/api/admin/gitlab/snapshots", headers=admin_headers).status_code == 422


def test_gitlab_migration_preserves_existing_templates_and_downgrades():
    path = Path(__file__).parents[1] / "alembic/versions/20261026_0005_gitlab.py"
    spec = importlib.util.spec_from_file_location("gitlab_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    legacy = sa.Table("project_templates", metadata, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("name", sa.String()))
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(legacy.insert(), {"id": uuid.uuid4(), "name": "preserved"})
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert connection.execute(sa.text("SELECT name FROM project_templates")).scalar() == "preserved"
        assert connection.execute(sa.text("SELECT snapshot_id FROM catalog_activation WHERE id=1")).scalar() is None
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert connection.execute(sa.text("SELECT name FROM project_templates")).scalar() == "preserved"
        assert "catalog_snapshots" not in sa.inspect(connection).get_table_names()
