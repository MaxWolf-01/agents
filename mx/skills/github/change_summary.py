#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Write the opening paragraph of a pull request from a unified diff on stdin.

A model reads the diff and nothing else, and says in one plain-English paragraph what behaviour changes and why it matters. It runs `claude -p` in an empty directory with no user settings, plugins, hooks, MCP servers, tools, slash commands or session file. Its prose rules are the rules tagged `artifact` or `both` in writing-for-humans/CATALOGUE.md, read from the plugin at run time.

The paragraph goes to stdout. When it runs past 150 words the model is asked once more. An empty diff, a failed model call, or a paragraph still past 150 words after that exits 1, with the reason, and the paragraph, on stderr.

Env: CHANGE_SUMMARY_MODEL sets the default model.

Examples:

    git diff main...HEAD | change-summary
    git show HEAD | change-summary --model sonnet
"""

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import tyro

CATALOGUE = Path(__file__).resolve().parents[1] / "writing-for-humans/CATALOGUE.md"
TARGET, STATED, CAP = 60, 100, 150  # Opus overshoots the length it is asked for by about half, so the prompt asks for less than the cap the tool enforces

INSTRUCTION = f"""You write the opening paragraph of a pull request description, from the unified diff you are given and nothing else.

The reader is a colleague who has not seen this codebase and was not there when the change was made. They read this paragraph and may stop. Tell them what changes in behaviour, for whoever uses or runs the thing, and why that matters. Give the why only as far as the diff shows it; do not invent motives. Leave out the tests and code comments that come with the change unless they are the change.

One plain-English paragraph, about {TARGET} words and never more than {STATED}. A small change gets fewer words; do not pad. Name no file paths, directory names or code identifiers unless there is no plainer way to refer to the thing. No lists, no headings, no preamble, no sign-off: output only the paragraph.

The prose rules below bind every sentence. Each names a tell of generated text and its fix.

# Rules

"""


class Failure(Exception):
    """A reason the tool has no paragraph to print."""


@dataclass
class Args:
    model: str = field(default_factory=lambda: os.environ.get("CHANGE_SUMMARY_MODEL", "opus"))
    """Model the paragraph is asked of: an alias or a full model name."""


def artifact_rules(catalogue: str) -> str:
    """The catalogue's rule blocks tagged `artifact` or `both`, whole, headings dropped."""
    kept, keep = [], False
    for line in catalogue.splitlines():
        if line.startswith("#"):
            keep = False
        if line.startswith("- `"):
            keep = line.split()[2] in ("`artifact`", "`both`")
        if keep:
            kept.append(line)
    if not any(line.strip() for line in kept):
        raise Failure(f"no rule tagged `artifact` or `both` in {CATALOGUE}")
    return "\n".join(kept).rstrip("\n")


def ask(model: str, system: str, prompt: str) -> str:
    """One bare `claude -p` call, from an empty directory so no project file is in reach."""
    with tempfile.TemporaryDirectory() as empty:
        try:
            proc = subprocess.run(
                ["claude", "-p", "--model", model, "--system-prompt", system,
                 "--setting-sources", "", "--strict-mcp-config", "--tools", "",
                 "--disable-slash-commands", "--no-session-persistence"],
                input=prompt, capture_output=True, text=True, timeout=600, cwd=empty,
                env={**os.environ, "CLAUDECODE": ""},
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise Failure(f"claude did not run: {e}") from e
    if proc.returncode != 0:
        raise Failure(f"claude exited {proc.returncode}: {(proc.stderr.strip() or proc.stdout.strip())[-500:]}")
    if not proc.stdout.strip():
        raise Failure("claude answered with no paragraph")
    return proc.stdout.strip()


def summarize(diff: str, model: str) -> str:
    """The paragraph for a diff, asked for once more when the first runs past the cap."""
    if not diff.strip():
        raise Failure("no diff on stdin")
    system = INSTRUCTION + artifact_rules(CATALOGUE.read_text())
    paragraph = ask(model, system, diff)
    words = len(paragraph.split())
    if words > CAP:
        paragraph = ask(model, system, f"{diff}\n\n---\nYour previous paragraph ran {words} words; write at most {STATED}. Write it again within the cap.")
        words = len(paragraph.split())
    if words > CAP:
        raise Failure(f"the paragraph ran {words} words after a retry, over the cap of {CAP}:\n{paragraph}")
    return paragraph


def main() -> None:
    args = tyro.cli(Args, prog="change-summary", description=__doc__)
    try:
        print(summarize(sys.stdin.buffer.read().decode(errors="replace"), args.model))
    except Failure as e:
        sys.exit(f"change-summary: {e}")


if __name__ == "__main__":
    main()
