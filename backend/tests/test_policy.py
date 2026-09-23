import uuid

import pytest

from app.models import RuleType, VariableRule
from app.policy import PolicyViolation, enforce_policy


def rule(name: str, kind: RuleType, **kwargs):
    return VariableRule(id=uuid.uuid4(), policy_id=uuid.uuid4(), variable_name=name, title=name, rule_type=kind, **kwargs)


def test_all_policy_types_are_enforced_server_side():
    rules = [
        rule("tenant_slug", RuleType.FIXED, fixed_value="kunde-a"),
        rule("application_id", RuleType.HIDDEN, fixed_value="azubiorga"),
        rule("dataset_id", RuleType.ENUM, allowed_values=["none", "smoke-v1"], default_value="none"),
        rule("ttl_minutes", RuleType.INTEGER_RANGE, minimum=15, maximum=180, default_value=60),
        rule("label", RuleType.STRING, regex_pattern=r"[a-z-]+", max_length=20, default_value="test"),
        rule("debug", RuleType.BOOLEAN, default_value=False),
    ]
    result = enforce_policy(rules, {"dataset_id": "smoke-v1", "ttl_minutes": 90, "label": "demo-a", "debug": True})
    assert result == {
        "tenant_slug": "kunde-a",
        "application_id": "azubiorga",
        "dataset_id": "smoke-v1",
        "ttl_minutes": 90,
        "label": "demo-a",
        "debug": True,
    }


@pytest.mark.parametrize(
    "payload,key",
    [
        ({"tenant_slug": "kunde-b"}, "tenant_slug"),
        ({"unexpected": "x"}, "unexpected"),
        ({"dataset_id": "private-dump"}, "dataset_id"),
        ({"ttl_minutes": 181}, "ttl_minutes"),
        ({"ttl_minutes": True}, "ttl_minutes"),
        ({"debug": "true"}, "debug"),
    ],
)
def test_policy_rejects_manipulated_values(payload, key):
    rules = [
        rule("tenant_slug", RuleType.FIXED, fixed_value="kunde-a"),
        rule("dataset_id", RuleType.ENUM, allowed_values=["none"]),
        rule("ttl_minutes", RuleType.INTEGER_RANGE, minimum=15, maximum=180, default_value=60),
        rule("debug", RuleType.BOOLEAN, default_value=False),
    ]
    with pytest.raises(PolicyViolation) as error:
        enforce_policy(rules, payload)
    assert key in error.value.errors

