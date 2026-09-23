# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""No test file in this repo defines one name twice. Run: uv run test_no_shadowed_checks.py

Python rebinds a duplicated `def`, so the earlier one is never collected and the suite stays green
without it. Three of the board's checks were lost that way when a review round appended its
corrected versions above the originals instead of replacing them, and the copies that ran were the
ones the review had replaced. Collection cannot see this, since only one of each name reaches it;
the source can.
"""

import ast
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
DEFINES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def test_no_test_file_defines_one_name_twice() -> None:
    checked, twice = 0, []
    for path in sorted(REPO.glob("mx/**/test_*.py")) + sorted(REPO.glob("mx/**/conftest.py")):
        checked += 1
        seen: set[str] = set()
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, DEFINES):
                if node.name in seen:
                    twice.append(f"{path.relative_to(REPO)}:{node.lineno}: {node.name}")
                seen.add(node.name)
    assert checked >= 8, f"{checked} test files found under mx/, which is fewer than this repo has"
    assert not twice, "shadowed by a later definition of the same name, so never collected:\n" + "\n".join(twice)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
