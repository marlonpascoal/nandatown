# SPDX-License-Identifier: Apache-2.0
"""Detect scenario config knobs that no code consumes.

Every key under ``task.config`` or ``failures`` in a scenario YAML is a promise
to the experimenter: set it, and behaviour changes. When no code reads the key,
the promise is silently broken. The run still succeeds, the trace is byte
identical, and the experimenter records a variable as tested that never varied.

That is the worst failure mode for a testing framework, because it manufactures
clean-looking null results.

Usage::

    python scripts/check_orphan_knobs.py            # report only
    python scripts/check_orphan_knobs.py --strict   # exit 1 if orphans found
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import cast

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_DIR = REPO_ROOT / "scenarios"
PACKAGES_DIR = REPO_ROOT / "packages"

# Keys that configure the harness itself rather than a task, so the loader
# consumes them structurally and a name-based search would not see it.
STRUCTURAL_KEYS = frozenset({"type", "config"})


def collect_declared_knobs(scenario_dir: Path) -> dict[str, set[str]]:
    """Map each declared knob to the scenario stems that declare it."""
    declared: dict[str, set[str]] = defaultdict(set)

    for path in sorted(scenario_dir.glob("*.yaml")):
        loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            continue
        doc = cast("dict[str, object]", loaded)

        task = doc.get("task")
        if isinstance(task, dict):
            config = cast("dict[str, object]", task).get("config")
            if isinstance(config, dict):
                for key in cast("dict[str, object]", config):
                    if key not in STRUCTURAL_KEYS:
                        declared[key].add(path.stem)

        failures = doc.get("failures")
        if isinstance(failures, dict):
            for key in cast("dict[str, object]", failures):
                declared[key].add(path.stem)

    return dict(declared)


def load_source(packages_dir: Path) -> str:
    """Concatenate every Python source file under packages/."""
    return "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(packages_dir.glob("**/*.py"))
    )


def has_consumer(knob: str, source: str) -> bool:
    """True when some code reads the knob by name.

    Matches the two access patterns the codebase uses: dictionary lookup
    (``task_config.get("rounds")``) and attribute access on the parsed
    failure config (``failures.message_drop``).
    """
    escaped = re.escape(knob)
    pattern = rf'get\(\s*["\']{escaped}["\']|\.{escaped}\b'
    return re.search(pattern, source) is not None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when an orphan knob is found",
    )
    args = parser.parse_args()

    declared = collect_declared_knobs(SCENARIO_DIR)
    source = load_source(PACKAGES_DIR)

    orphans = {
        knob: scenarios
        for knob, scenarios in sorted(declared.items())
        if not has_consumer(knob, source)
    }

    print(f"Declared knobs across {SCENARIO_DIR.name}/*.yaml : {len(declared)}")
    print(f"With a consumer in packages/               : {len(declared) - len(orphans)}")
    print(f"Orphaned (declared, never read)            : {len(orphans)}")

    if orphans:
        print()
        for knob, scenarios in orphans.items():
            names = ", ".join(sorted(scenarios))
            print(f"  {knob:<24} declared in: {names}")

    if orphans and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
