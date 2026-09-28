"""Every `claude` that a file in mx starts in print mode states what it inherits from the machine it
runs on. Run: pytest test_launches.py, or `make check`.

A launch that names no `--setting-sources` loads whatever the host has: the user's CLAUDE.md and
output style, their hooks, allowlist and plugins, and on some hosts the claude.ai connectors. So
a new launch nobody wrote a test for fails here, whatever else it does.

The launches are found by reading the files rather than running them: a Python list or tuple that
holds `claude` as its program, a shell statement (or a command in a markdown code span or fence)
that runs `claude` with a flag after it. A launch is print mode when it carries `-p` or `--print`,
or takes arguments this reading cannot see (`*args`, `"${common[@]}"`), and it states what it
inherits when it carries `--setting-sources`, in its own text or in a shell array it expands. Test
files are left out: their launches run a stub on PATH.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path

MX = Path(__file__).resolve().parent

RULE = """\
Every `claude` mx starts unattended names what it inherits from the machine it runs on with
`--setting-sources`: "" for nothing, `project` for the project's own settings and CLAUDE.md.
`--strict-mcp-config` keeps every MCP server out beside it, and the code-review reviewers' launch
(mx/skills/code-review/review) is the whole pattern. These state nothing:"""

# What a `claude` followed by one of these runs is a command of its own, never a model.
SUBCOMMANDS = {"--version", "-v", "--help", "-h", "plugin", "update", "mcp", "config", "doctor", "install"}
PRINT = {"-p", "--print"}
STATES = "--setting-sources"
WORD = re.compile(r"(?<![\w./$-])claude(?![\w.-])")
EXPANDED = re.compile(r"\$\{(\w+)\[@\]\}")


@dataclass(frozen=True)
class Launch:
    path: Path
    line: int
    states: bool  # carries --setting-sources

    def __str__(self) -> str:
        return f"  {self.path.relative_to(MX.parent) if self.path.is_relative_to(MX.parent) else self.path}:{self.line}"


def launches(path: Path) -> list[Launch]:
    """The print-mode launches of `claude` in one file."""
    try:
        text = path.read_text()
    except (UnicodeDecodeError, OSError):
        return []
    shebang = text.split("\n", 1)[0] if text.startswith("#!") else ""
    if path.suffix == ".py" or "python" in shebang:
        return python_launches(path, text)
    if path.suffix == ".md":
        return markdown_launches(path, text)
    if path.suffix == ".sh" or re.search(r"\b(ba)?sh\b", shebang):
        return shell_launches(path, text, statements(text))
    return []


def python_launches(path: Path, text: str) -> list[Launch]:
    """Lists and tuples whose program is `claude`, as a string or a module-level name bound to one."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    aliases = {target.id for node in tree.body if isinstance(node, ast.Assign)
               and isinstance(node.value, ast.Constant) and node.value.value == "claude"
               for target in node.targets if isinstance(target, ast.Name)}
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple)):
            continue
        items = node.elts
        at = next((i for i, item in enumerate(items) if (isinstance(item, ast.Constant) and item.value == "claude")
                   or (isinstance(item, ast.Name) and item.id in aliases)), None)
        if at is None:
            continue
        after = [item.value for item in items[at + 1:] if isinstance(item, ast.Constant)]
        if after[:1] and after[0] in SUBCOMMANDS:
            continue
        unseen = any(isinstance(item, ast.Starred) for item in items[at + 1:])
        if unseen or PRINT & set(after):
            found.append(Launch(path, node.lineno, STATES in after))
    return found


def statements(text: str, first: int = 1) -> list[tuple[int, str]]:
    """Shell text as (line, statement) pairs: comments dropped, a backslash-continued line and an
    open parenthesis (an array, a subshell) each joined to the lines after them."""
    found, held, start, depth = [], [], first, 0
    for n, line in enumerate(text.splitlines(), first):
        line = re.sub(r"(^|\s)#.*", "", line)
        if not held:
            start = n
        held.append(line.rstrip("\\"))
        depth = max(0, depth + line.count("(") - line.count(")"))
        if depth == 0 and not line.rstrip().endswith("\\"):
            found.append((start, " ".join(held)))
            held = []
    if held:
        found.append((start, " ".join(held)))
    return found


def shell_launches(path: Path, text: str, commands: list[tuple[int, str]], mention: bool = False) -> list[Launch]:
    """`claude` followed by a flag or an array expansion, in the given statements. The arrays a
    statement expands are read from the whole of `text`. `mention` reads a bare `claude -p` as the
    name of the mode, which is what one is in a sentence of prose."""
    arrays = {m.group(1): body for _, body in statements(text)
              if (m := re.match(r"\s*(?:local\s+)?(\w+)=\(", body))}
    found = []
    for line, body in commands:
        for m in WORD.finditer(body):
            rest = body[m.end():]
            words = [w.strip("\"'") for w in rest.split()]
            if not words or words[0] in SUBCOMMANDS or not (words[0].startswith("-") or rest.lstrip().startswith(("\"$", "$"))):
                continue
            if mention and words in (["-p"], ["--print"]):
                continue
            seen = " ".join([rest, *(arrays.get(name, "") for name in EXPANDED.findall(rest))])
            if PRINT & {w.strip("\"'") for w in seen.split()} or EXPANDED.search(rest):
                found.append(Launch(path, line, STATES in seen))
    return found


def markdown_launches(path: Path, text: str) -> list[Launch]:
    """Commands in fenced code blocks, and in inline code spans outside them."""
    fenced, prose, block, inside, start = [], [], [], False, 0
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            if inside:
                fenced.append((start, "\n".join(block)))
            inside, start, block = not inside, n + 1, []
        elif inside:
            block.append(line)
        else:
            prose += [(n, span) for span in re.findall(r"`([^`]+)`", line)]
    commands = [c for first, block in fenced for c in statements(block, first)]
    return shell_launches(path, "", commands) + shell_launches(path, "", prose, mention=True)


def mx_launches() -> list[Launch]:
    files = sorted(p for p in MX.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                   and not p.name.startswith("test_") and p.name != "conftest.py")
    return [launch for path in files for launch in launches(path)]


def test_every_claude_launch_in_mx_states_what_it_inherits() -> None:
    silent = [launch for launch in mx_launches() if not launch.states]
    assert not silent, "\n".join([RULE, *map(str, silent)])


def test_the_launches_read_include_every_one_mx_is_known_to_make() -> None:
    """The launches `unattended-launch` lists, and the fork's: a reading that finds none of them
    would pass the check above by finding nothing."""
    read = {launch.path.relative_to(MX).as_posix() for launch in mx_launches()}
    assert read >= {"skills/code-review/review", "skills/dispatch/run-worker.sh", "skills/tracker/briefing.py",
                    "skills/github/change_summary.py", "skills/writing-for-humans/chat_review.py",
                    "skills/fork/CLI.md"}, read


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def test_a_python_launch_states_what_it_inherits_only_in_its_own_list(tmp_path: Path) -> None:
    path = write(tmp_path, "ask.py", '''
import subprocess
COMMAND = "claude"
FLAGS = ["--setting-sources", ""]
subprocess.run(["claude", "-p", "--model", "opus"])
subprocess.run(["run-log", "--", "claude", "-p", "--setting-sources", "", "--strict-mcp-config"])
subprocess.run([COMMAND, *args, "--model", "opus"])
subprocess.run(["claude", "--version"])
subprocess.run(["claude", "plugin", "list", "-p"])
print(f"claude -p {x}")
''')
    assert [(l.line, l.states) for l in launches(path)] == [(5, False), (6, True), (7, False)]


def test_a_shell_launch_states_what_it_inherits_in_its_statement_or_the_arrays_it_expands(tmp_path: Path) -> None:
    path = write(tmp_path, "run.sh", '''#!/usr/bin/env bash
common=(
    -p
    --setting-sources project
)
bare=(-p --model opus)
claude "${common[@]}" --resume "$session"
claude "${bare[@]}" < "$message"
cmd=(bash run-log run --
     claude -p --model "$model"
     --effort high)
version=$(claude --version 2> /dev/null)
echo "spawn: claude update failed; $name runs on the claude this host has" >&2
# claude -p in a comment
claude --resume "$id"
''')
    assert [(l.line, l.states) for l in launches(path)] == [(7, True), (8, False), (9, False)]


def test_markdown_mentions_are_not_launches_and_its_commands_are(tmp_path: Path) -> None:
    path = write(tmp_path, "CLI.md", '''# A skill

Every `claude -p` the workflow starts goes through run-log, and `claude --resume <id>` finds it.
Ask it later with `claude -p --resume <id> '<question>'`.

```bash
tmux new-session -d -s fork "env -u CLAUDECODE \\
  claude -p --setting-sources user,project,local --resume <id> '<directive>'"
claude -p --model opus 'bare'
```
''')
    assert [(l.line, l.states) for l in launches(path)] == [(7, True), (9, False), (4, False)]
