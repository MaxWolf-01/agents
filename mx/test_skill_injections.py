"""Every `!` line in an mx skill runs a command its own `allowed-tools` approves. Run: pytest
test_skill_injections.py.

Outside auto mode, Claude Code aborts a skill's invocation when one of its `!` commands is not
allowed by a permission rule, and a skill's `allowed-tools` is the only rule it carries with it.
`${CLAUDE_SKILL_DIR}` stays unexpanded on both sides: Claude Code substitutes it in the line and in
the rule alike.

What this cannot see: a model-invoked skill that has any `allowed-tools` at all makes the Skill
call itself ask for permission, and in `claude -p` in the default mode that ask is refused before
a `!` line runs.
"""

import re
from pathlib import Path

import yaml

SKILLS = Path(__file__).resolve().parent / "skills"
INJECTION = re.compile(r"^!`(.+)`\s*$", re.M)
BASH_RULE = re.compile(r"Bash\(([^)]*)\)")
OPERATORS = re.compile(r"\|\||&&|;|\|")


def frontmatter_and_body(path: Path) -> tuple[dict, str]:
    _, front, body = path.read_text().split("---\n", 2)
    return yaml.safe_load(front) or {}, body


def bash_rules(allowed_tools: str | list | None) -> list[str]:
    text = " ".join(allowed_tools) if isinstance(allowed_tools, list) else allowed_tools or ""
    return BASH_RULE.findall(text)


def covers(rule: str, command: str) -> bool:
    """Claude Code's Bash rule matching: exact, `prefix *` (a word boundary), or legacy `prefix:*`."""
    for wildcard in (" *", ":*"):
        if rule.endswith(wildcard):
            prefix = rule.removesuffix(wildcard)
            return command == prefix or command.startswith(prefix + " ")
    return command == rule


def approved(command: str, rules: list[str]) -> bool:
    """A compound command is checked one part at a time, as Claude Code checks it."""
    return all(any(covers(r, part.strip()) for r in rules) for part in OPERATORS.split(command))


def test_the_matcher_reads_rules_as_claude_code_does():
    assert covers("git commit *", "git commit -m x")
    assert covers("git commit *", "git commit")
    assert not covers("git commit *", "git commitx")
    assert covers("ccx:*", "ccx list")
    assert not covers("job --help", "job --help --all")
    assert not approved('job --help || echo "missing"', ["job --help"])
    assert approved('job --help || echo "missing"', ["job --help", "echo *"])


def test_every_injected_command_is_in_its_skills_allowed_tools():
    injections = {}
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        front, body = frontmatter_and_body(path)
        rules = bash_rules(front.get("allowed-tools"))
        for command in INJECTION.findall(body):
            injections[(path.parent.name, command)] = approved(command, rules)
    assert injections, "no skill has a `!` line: the pattern no longer finds them"
    unapproved = [f"  {skill}: {command}" for (skill, command), ok in injections.items() if not ok]
    assert not unapproved, "these `!` commands fall outside their skill's allowed-tools:\n" + "\n".join(unapproved)
