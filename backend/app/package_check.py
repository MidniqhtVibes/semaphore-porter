"""CLI for the same trusted contracts used by the portal and GitLab CI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.gitlab_client import MAX_FILE_BYTES, SHA
from app.package_validation import encode, validate_snapshot


def check_directory(root: Path, revision: str):
    if not SHA.fullmatch(revision):
        raise ValueError("Eine vollständige Commit-SHA angeben.")
    root = root.resolve(strict=True)
    files = {}
    for folder in ("programs", "database-types", "mail"):
        for path in (root / folder).rglob("*"):
            if path.is_symlink():
                raise ValueError("Verlinkte Dateien und Ordner werden nicht unterstützt.")
            if path.is_file():
                if path.stat().st_size > MAX_FILE_BYTES:
                    raise ValueError("Datei überschreitet 10 MB.")
                files[path.relative_to(root).as_posix()] = encode(path.read_bytes())
    return validate_snapshot(files, revision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    try:
        report, catalog = check_directory(args.root, args.revision)
        print(json.dumps({"report": report, "catalog": catalog}, ensure_ascii=False))
    except Exception as exc:
        # Do not dump file contents, exception arguments or repository-supplied secrets to CI.
        parser.exit(1, f"Paketprüfung fehlgeschlagen ({type(exc).__name__}). Details in der Portal-Vertragsprüfung prüfen.\n")


if __name__ == "__main__":
    main()
