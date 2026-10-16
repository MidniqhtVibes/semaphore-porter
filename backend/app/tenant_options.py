from __future__ import annotations

from typing import Any


SELECTION_FIELDS = {
    "application_id": "application_ids",
    "database_type": "database_types",
    "dataset_id": "dataset_ids",
}


def selected_options(draft: dict[str, Any], name: str) -> list[str] | None:
    """None preserves old drafts without a selection; [] is an explicit empty choice."""
    plural = SELECTION_FIELDS.get(name)
    if plural and draft.get(plural) is not None:
        return list(dict.fromkeys(draft[plural]))
    legacy = draft.get(name)
    return [legacy] if isinstance(legacy, str) and legacy else None


def allowed_options(draft: dict[str, Any], name: str, available: list[Any]) -> list[Any]:
    selected = selected_options(draft, name)
    if selected is None:
        return available
    # Selection order determines the initial value, while values retain their types.
    return [value for value in selected if value in available]
