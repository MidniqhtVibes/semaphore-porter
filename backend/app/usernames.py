"""Canonical portal usernames and collision-safe suggestions for existing accounts."""
import re
from collections.abc import Collection


def suggest_username(email: str, existing: Collection[str]) -> str:
    stem = re.sub(r"[^a-z0-9._-]+", "-", email.split("@", 1)[0].lower()).strip("._-")[:64]
    if len(stem) < 2:
        stem = "user"
    taken = {value.lower() for value in existing}
    candidate, number = stem, 2
    while candidate in taken:
        suffix = f"-{number}"
        candidate = stem[:64 - len(suffix)] + suffix
        number += 1
    return candidate
