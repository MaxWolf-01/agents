"""The test files a change can reach: `make test` runs these, `make test-all` runs every one.

A change is every file that differs between the working tree and its merge-base with $BASE
(default master), committed or not, untracked included. A test file reaches every file it names,
and every file those name in turn: a Python import of a module beside the importer, or a quoted
string or a word ending in a file extension that is some file's name under mx/. A name several
files share resolves to the one beside the naming file when there is one, else to all of them, so
an ambiguous name runs more tests, never fewer. A change outside mx/skills/ other than prose
(this script, the Makefile, mx/bin, mx/hooks) reaches every test.

Prints one test path per line, nothing when no test is reached.
"""

import ast
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MX = ROOT / "mx"
# A path joined in Python (`SKILL / "dispatch"`) or written in a path (`$skill/../tracker/`), and a
# word with a file suffix: the forms a file names another file in, and not the forms a plain word
# ("review", a status) takes.
JOINED = re.compile(r"""/\s*["']([\w.-]+)["']|/([\w.-]+)""")
WITH_SUFFIX = re.compile(r"\b[\w-]+\.(?:py|sh|md|json|css|html|txt)\b")


def git(*args: str) -> list[str]:
    done = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True)
    return [line for line in done.stdout.splitlines() if line]


def changed(base: str) -> set[Path]:
    fork = git("merge-base", "HEAD", base)[0]
    names = git("diff", "--name-only", fork) + git("ls-files", "--others", "--exclude-standard")
    return {ROOT / name for name in names}


def named_in(path: Path) -> set[str]:
    """The names a file uses for other files: path segments, words with a file suffix, and for
    Python the modules it imports."""
    text = path.read_text(errors="replace")
    names = {a or b for a, b in JOINED.findall(text)} | set(WITH_SUFFIX.findall(text))
    if path.suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return names
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {alias.name.split(".")[0] + ".py" for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0] + ".py")
    return names


def reach(test: Path, by_name: dict[str, list[Path]]) -> set[Path]:
    """The test file, its directory's conftest, and every file they name, followed through code but
    not through prose: a skill's markdown names half the tree without depending on any of it. Other
    test files are never reached; each is its own start."""
    seen, todo = {test}, [test]
    conftest = test.parent / "conftest.py"
    if conftest.exists():
        seen.add(conftest)
        todo.append(conftest)
    while todo:
        at = todo.pop()
        for name in named_in(at):
            found = [f for f in by_name.get(name, []) if not f.name.startswith("test_")]
            beside = [f for f in found if f.parent == at.parent]
            for f in beside or found:
                if f not in seen:
                    seen.add(f)
                    if f.suffix != ".md":
                        todo.append(f)
    return seen


def reaches_every_test(path: Path) -> bool:
    """What runs the tests or wraps what they test: the Makefile, this script, and mx/ outside its
    skills (the bin wrappers, the hooks, the plugin manifest)."""
    return (path == ROOT / "Makefile" or path.is_relative_to(ROOT / "tools")
            or (path.is_relative_to(MX) and not path.is_relative_to(MX / "skills")))


def main() -> None:
    changes = changed(os.environ.get("BASE", "master"))
    tests = sorted(MX.rglob("test_*.py"))
    if any(reaches_every_test(c) for c in changes):
        hit = tests
    else:
        by_name: dict[str, list[Path]] = defaultdict(list)
        for f in MX.rglob("*"):
            if f.is_file() and "__pycache__" not in f.parts:
                by_name[f.name].append(f)
        hit = [t for t in tests if reach(t, by_name) & changes]
    for t in hit:
        print(t.relative_to(ROOT))


if __name__ == "__main__":
    main()
