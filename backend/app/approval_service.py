"""Optional, parameter-bound, single-use task approvals. No remote task is started here."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import smtplib
import ssl
import uuid
from datetime import timezone
from email.message import EmailMessage
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import select

from app.audit import sanitize
from app.config import get_settings
from app.models import SemaphoreSettings, TaskApproval, TaskTemplate, Tenant, User, utcnow
from app.security import decrypt_secret, user_has_role

LEVELS = {"low": 0, "medium": 1, "high": 2}


def aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def notifications_available():
    config = get_settings()
    url = urlsplit(config.approval_portal_url or "")
    return bool(not config.demo_mode and config.approval_smtp_host and config.approval_smtp_from
        and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", config.approval_smtp_from)
        and config.approval_smtp_security in {"starttls", "tls"} and url.scheme == "https"
        and url.hostname and not url.username and not url.query and not url.fragment)


def validate_config(db, config):
    if not config.get("enabled"):
        return
    try:
        approver = db.get(User, uuid.UUID(str(config.get("approver_id"))))
    except (ValueError, TypeError):
        approver = None
    if not approver or not approver.is_active:
        raise HTTPException(422, "Einen aktiven Portalbenutzer als Vorgesetzten auswählen.")
    if config.get("threshold") not in LEVELS:
        raise HTTPException(422, "Eine gültige Genehmigungsgrenze auswählen.")
    if config.get("notify_by_email") and not notifications_available():
        raise HTTPException(422, "Optionale Genehmigungsmails sind im Backend noch nicht eingerichtet.")


def required(tenant, template):
    config = tenant.approval_config or {}
    if not config.get("enabled"):
        return False
    policy = template.policy
    if not policy or policy.cost_class not in LEVELS or policy.effort_class not in LEVELS:
        raise HTTPException(409, "Kosten- und Aufwandsklasse dieses Tasks zuerst administrativ einstufen.")
    threshold = config.get("threshold")
    if threshold not in LEVELS:
        raise HTTPException(409, "Die Genehmigungsgrenze ist ungültig. Administration kontaktieren.")
    return max(LEVELS[policy.cost_class], LEVELS[policy.effort_class]) >= LEVELS[threshold]


def validate_creation(db, draft, prepared):
    config = draft.get("approval_config") or {}
    validate_config(db, config)
    if config.get("enabled"):
        classifications = draft.get("task_classifications") or {}
        names = set(draft.get("task_template_names") or [])
        for task in prepared.get("templates", []):
            if task.get("name") in names:
                entry = classifications.get(task["name"], {})
                if entry.get("cost_class") not in LEVELS or entry.get("effort_class") not in LEVELS:
                    raise HTTPException(422, f"Kosten und Aufwand für Task „{task['name']}“ zuerst einstufen.")


def context_digest(db, tenant, template, variables):
    settings = db.get(SemaphoreSettings, 1)
    policy = template.policy
    document = {"tenant": str(tenant.id), "config": tenant.approval_config, "template": str(template.id),
        "project": tenant.semaphore_project.semaphore_project_id, "remote_template": template.semaphore_template_id,
        "semaphore_url": settings.base_url if settings else None, "survey": template.survey_schema,
        "policy": {"id": str(policy.id), "version": policy.version, "active": policy.is_active,
            "cost": policy.cost_class, "effort": policy.effort_class,
            "rules": [{key: getattr(rule, key) for key in ("variable_name", "rule_type", "fixed_value",
                "default_value", "allowed_values", "minimum", "maximum", "regex_pattern", "max_length", "is_required", "position")}
                for rule in policy.variable_rules]}, "variables": variables}
    return hashlib.sha256(json.dumps(document, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def visible_status(row):
    if row.status in {"pending", "approved"} and aware(row.expires_at) <= utcnow():
        return "expired"
    return row.status


def get_visible(db, approval_id, user):
    row = db.get(TaskApproval, approval_id)
    if not row or (user.id not in {row.requester_id, row.approver_id} and not user_has_role(user, "system_admin")):
        raise HTTPException(404, "Genehmigungsanfrage nicht gefunden.")
    return row


def public_request(db, row, user):
    tenant, task = db.get(Tenant, row.tenant_id), db.get(TaskTemplate, row.task_template_id)
    requester, approver = db.get(User, row.requester_id), db.get(User, row.approver_id)
    document = json.loads(decrypt_secret(row.encrypted_variables))
    # Never expose fixed/hidden values or raw submitted unknown parameters.
    allowed = {rule.variable_name for rule in task.policy.variable_rules
               if str(getattr(rule.rule_type, "value", rule.rule_type)) not in {"hidden", "fixed"}} if task.policy else set()
    variables = sanitize({key: value for key, value in document["validated"].items() if key in allowed})
    status = visible_status(row)
    return {"id": str(row.id), "tenant_id": str(row.tenant_id), "tenant": tenant.display_name,
        "task_id": str(row.task_template_id), "task": task.name, "requester": requester.display_name,
        "approver": approver.display_name, "status": status, "reason": row.reason,
        "decision_note": row.decision_note, "variables": variables,
        "cost_class": document["cost_class"], "effort_class": document["effort_class"],
        "notification_status": row.notification_status, "created_at": row.created_at, "expires_at": row.expires_at,
        "decided_at": row.decided_at, "run_id": str(row.run_id) if row.run_id else None,
        "can_decide": user.id == row.approver_id and user.id != row.requester_id and status == "pending",
        "can_start": user.id == row.requester_id and status == "approved",
        "can_cancel": user.id == row.requester_id and status in {"pending", "approved"},
        "can_resolve": user_has_role(user, "system_admin") and status in {"executing", "uncertain"}
            and row.execution_started_at is not None and (utcnow()-aware(row.execution_started_at)).total_seconds() >= 900}


async def notify(db, row, *, decision=False):
    tenant = db.get(Tenant, row.tenant_id)
    if not (tenant.approval_config or {}).get("notify_by_email"):
        return
    if not notifications_available():
        row.notification_status = "unavailable"
        db.commit()
        return
    config = get_settings()
    recipient = db.get(User, row.requester_id if decision else row.approver_id).email
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", recipient):
        row.notification_status = "failed"
        db.commit()
        return
    message = EmailMessage()
    message["From"], message["To"] = config.approval_smtp_from, recipient
    message["Subject"] = "Semaporter: Entscheidung zur Task-Anfrage" if decision else "Semaporter: Task-Anfrage wartet auf Genehmigung"
    message.set_content("Eine Task-Anfrage in Semaporter wurde aktualisiert.\n"
        "Bitte angemeldet in Semaporter prüfen:\n"
        f"{config.approval_portal_url.rstrip('/')}/portal/genehmigungen?anfrage={row.id}\n"
        "Diese Nachricht genehmigt und startet keinen Task.")
    def deliver():
        context = ssl.create_default_context()
        if config.approval_smtp_security == "tls":
            smtp = smtplib.SMTP_SSL(config.approval_smtp_host, config.approval_smtp_port, timeout=10, context=context)
        else:
            smtp = smtplib.SMTP(config.approval_smtp_host, config.approval_smtp_port, timeout=10)
        with smtp:
            if config.approval_smtp_security == "starttls":
                smtp.starttls(context=context)
            if config.approval_smtp_username:
                smtp.login(config.approval_smtp_username, config.approval_smtp_password.get_secret_value() if config.approval_smtp_password else "")
            smtp.send_message(message)
    try:
        await asyncio.to_thread(deliver)
        row.notification_status = "sent"
    except Exception:
        # Approval remains available in the portal; never log SMTP credentials.
        row.notification_status = "failed"
    db.commit()
