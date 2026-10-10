"""Every module the scripts under mx import by its bare name names one file. Run: pytest
test_module_names.py, or `make check`.

The scripts import each other by bare name, across skills too (the board reads the session page,
which reads the tracker), and `pytest.ini` puts every directory a check imports from on the path of
one test process. So two scripts of one name shadow each other, at runtime and in a run: whichever
directory comes first on the path wins for every importer. Test files and conftests are imported by
their path, so their names may repeat, but they sit in those same directories and are the files no
check imports by name.
"""

import ast
from collections import defaultdict
from pathlib import Path

MX = Path(__file__).resolve().parent


def test_no_two_scripts_under_mx_share_a_name() -> None:
    by_name = defaultdict(list)
    for path in MX.rglob("*.py"):
        if path.name != "conftest.py" and not path.name.startswith("test_"):
            by_name[path.stem].append(path.relative_to(MX))
    assert {name: paths for name, paths in by_name.items() if len(paths) > 1} == {}


def imported_by_name(path: Path) -> list[str]:
    return [name for node in ast.walk(ast.parse(path.read_text()))
            for name in ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module] if isinstance(node, ast.ImportFrom) else [])]


def test_no_check_imports_a_conftest_by_name() -> None:
    assert [path.relative_to(MX) for path in MX.rglob("*.py") if "conftest" in imported_by_name(path)] == []


def test_no_check_imports_another_check() -> None:
    """Importing a test module collects its checks with the importer's; what two share lives in a
    module of its own beside them."""
    importers = {path.relative_to(MX): checks for path in MX.rglob("*.py")
                 if (checks := [name for name in imported_by_name(path) if name and name.startswith("test_")])}
    assert importers == {}
