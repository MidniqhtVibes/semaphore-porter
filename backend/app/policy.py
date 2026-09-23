from __future__ import annotations

import re
from typing import Any, Iterable

from app.models import RuleType, VariableRule


class PolicyViolation(ValueError):
    def __init__(self, errors: dict[str, str]):
        super().__init__("Task-Variablen verletzen die Tenant-Policy.")
        self.errors = errors


def enforce_policy(rules: Iterable[VariableRule], submitted: dict[str, Any]) -> dict[str, Any]:
    rule_list = list(rules)
    by_name = {rule.variable_name: rule for rule in rule_list}
    errors: dict[str, str] = {}
    result: dict[str, Any] = {}

    for key in submitted:
        rule = by_name.get(key)
        if rule is None:
            errors[key] = "Diese Variable ist nicht freigegeben."
        elif rule.rule_type in {RuleType.FIXED, RuleType.HIDDEN}:
            errors[key] = "Diese Variable wird ausschließlich serverseitig gesetzt."

    for rule in rule_list:
        key = rule.variable_name
        if rule.rule_type in {RuleType.FIXED, RuleType.HIDDEN}:
            result[key] = rule.fixed_value
            continue

        supplied = key in submitted
        value = submitted.get(key, rule.default_value)
        if value is None:
            if rule.is_required:
                errors[key] = "Dieses Feld ist erforderlich."
            continue

        if rule.rule_type == RuleType.ENUM:
            allowed = rule.allowed_values or []
            if not any(value == candidate and type(value) is type(candidate) for candidate in allowed):
                errors[key] = "Der Wert ist nicht in der erlaubten Auswahlliste."
                continue
        elif rule.rule_type == RuleType.INTEGER_RANGE:
            if type(value) is not int:
                errors[key] = "Es ist eine ganze Zahl erforderlich."
                continue
            if rule.minimum is not None and value < rule.minimum:
                errors[key] = f"Der Wert muss mindestens {rule.minimum} sein."
                continue
            if rule.maximum is not None and value > rule.maximum:
                errors[key] = f"Der Wert darf höchstens {rule.maximum} sein."
                continue
        elif rule.rule_type == RuleType.STRING:
            if not isinstance(value, str):
                errors[key] = "Es ist Text erforderlich."
                continue
            if rule.max_length is not None and len(value) > rule.max_length:
                errors[key] = f"Maximal {rule.max_length} Zeichen sind erlaubt."
                continue
            if rule.regex_pattern:
                try:
                    if re.fullmatch(rule.regex_pattern, value) is None:
                        errors[key] = "Der Text entspricht nicht dem erlaubten Format."
                        continue
                except re.error:
                    errors[key] = "Die serverseitige Policy enthält ein ungültiges Textmuster."
                    continue
        elif rule.rule_type == RuleType.BOOLEAN:
            if type(value) is not bool:
                errors[key] = "Es ist ein Ja/Nein-Wert erforderlich."
                continue
        else:
            errors[key] = "Unbekannter Policy-Typ."
            continue
        result[key] = value

    if errors:
        raise PolicyViolation(errors)
    return result


def build_form_schema(rules: Iterable[VariableRule], survey: list[dict[str, Any]]) -> list[dict[str, Any]]:
    survey_by_name = {item.get("name"): item for item in survey if isinstance(item, dict) and item.get("name")}
    fields: list[dict[str, Any]] = []
    for rule in sorted(rules, key=lambda item: item.position):
        if rule.rule_type in {RuleType.FIXED, RuleType.HIDDEN}:
            continue
        source = survey_by_name.get(rule.variable_name, {})
        fields.append(
            {
                "name": rule.variable_name,
                "title": rule.title or source.get("title") or rule.variable_name,
                "help_text": rule.help_text or source.get("description") or "",
                "type": rule.rule_type.value,
                "default": rule.default_value,
                "allowed_values": rule.allowed_values,
                "minimum": rule.minimum,
                "maximum": rule.maximum,
                "max_length": rule.max_length,
                "required": rule.is_required,
            }
        )
    return fields

