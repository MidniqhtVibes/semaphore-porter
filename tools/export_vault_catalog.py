"""Export public contracts; requires PyYAML in the exporting environment only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import yaml

SEMAPORTER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEMAPORTER_ROOT / "backend"))
from app.catalog_export import export_catalog


def export(root: Path) -> dict:
    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    return export_catalog(root, revision)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack-root", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=SEMAPORTER_ROOT / "backend/app/vault_catalog.json")
    args = parser.parse_args()
    args.output.write_text(json.dumps(export(args.stack_root), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
