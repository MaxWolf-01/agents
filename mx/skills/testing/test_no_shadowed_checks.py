"""No test file in this repo defines one name twice.

Python rebinds a duplicated `def`, so the earlier one is never collected and the suite stays green
without it. Three of the board's checks were lost that way when a review round appended its
corrected versions above the originals instead of replacing them, and the copies that ran were the
ones the review had replaced. Collection cannot see this, since only one of each name reaches it;
the source can.
"""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def test_no_test_file_defines_one_name_twice() -> None:
    twice = []
    for path in sorted(REPO.glob("mx/**/test_*.py")) + sorted(REPO.glob("mx/**/conftest.py")):
        body = ast.parse(path.read_text()).body
        seen: set[str] = set()
        for node in body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if node.name in seen:
                    twice.append(f"{path.relative_to(REPO)}:{node.lineno}: {node.name}")
                seen.add(node.name)
    assert not twice, "shadowed by a later definition of the same name, so never collected:\n" + "\n".join(twice)
