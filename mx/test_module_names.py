"""Every module the checks under mx import by its bare name names one file. Run: pytest
test_module_names.py.

A skill's checks put their own directory on the import path, and a run collects several skills'
checks into one process, so two files of one name shadow each other: whichever directory went on
the path first wins for every importer. `conftest.py` is the name every skill shares, and pytest
loads each by its path, so it is the one file no check imports by name.
"""

import ast
from collections import defaultdict
from pathlib import Path

MX = Path(__file__).resolve().parent


def test_no_two_modules_under_mx_share_a_name() -> None:
    by_name = defaultdict(list)
    for path in MX.rglob("*.py"):
        if path.name != "conftest.py":
            by_name[path.stem].append(path.relative_to(MX))
    assert {name: paths for name, paths in by_name.items() if len(paths) > 1} == {}


def test_no_check_imports_a_conftest_by_name() -> None:
    importers = []
    for path in MX.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) else []
            if "conftest" in names:
                importers.append(path.relative_to(MX))
    assert importers == []
