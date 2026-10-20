"""Clean-install import smoke (ROADMAP P2.15): import every app module.

Run: PYTHONPATH=. uv run python scripts/check_imports.py
A dependency used by an import but missing from pyproject.toml fails here
in CI's clean environment, where nothing is installed by accident. Pure
imports: no network, no DB rows, no keychain reads. It imports no other
check, so it keeps the one-check-per-process rule.
"""

import importlib
import os
import pkgutil
import tempfile
from pathlib import Path

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "imports_test.db")

import app  # noqa: E402

failed: list[tuple[str, Exception]] = []
count = 0
for module in pkgutil.walk_packages(app.__path__, prefix="app."):
    count += 1
    try:
        importlib.import_module(module.name)
    except Exception as exc:  # noqa: BLE001 - report the failure, keep walking
        failed.append((module.name, exc))

for name, exc in failed:
    print(f"IMPORT FAILED: {name}: {exc}")
assert not failed, f"{len(failed)} of {count} app modules failed to import"
print(f"import smoke OK ({count} modules)")
