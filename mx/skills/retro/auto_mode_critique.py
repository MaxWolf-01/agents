#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro"]
# ///
"""Check the auto mode entries a workflow retro proposes with `claude auto-mode critique`, and write
what the critique found beside them.

It reads `deep/auto-mode.json` in the run directory, the proposed entries in the shape a settings
file's `autoMode` takes (`allow`, `environment`, `soft_deny` and `hard_deny`, each a list of
entries), and writes `deep/critique.md`. The critique judges the rules of the profile it runs
under, and fails on a rule set as long as max's (cut off halfway, or "No critique was
generated"), so it runs under a throwaway profile whose settings hold the shipped defaults and the
proposed entries alone, logged in as the profile `CLAUDE_CONFIG_DIR` names. A critique that could
not run, or printed none, is written as that, and the script exits 1.

Examples:

    auto_mode_critique.py ~/.local/share/retro/agents/runs/2026-10-21
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import tyro

SECTIONS = ("allow", "environment", "soft_deny", "hard_deny")
PROPOSED = Path("deep/auto-mode.json")
CRITIQUE = Path("deep/critique.md")
TIMEOUT = 600  # seconds; a critique of a few entries takes about 30
NO_CRITIQUE = "No critique was generated"


def critique(run: Path) -> bool:
    """Write `deep/critique.md` for the entries in `deep/auto-mode.json`; whether the critique ran
    and said something, or there was nothing to check."""
    try:
        proposed = json.loads((run / PROPOSED).read_text()) if (run / PROPOSED).is_file() else {}
    except json.JSONDecodeError as e:
        return failed(run, f"{PROPOSED} is no JSON: {e}")
    if not isinstance(proposed, dict) or (unknown := set(proposed) - set(SECTIONS)):
        return failed(run, f"{PROPOSED} holds {sorted(unknown) if isinstance(proposed, dict) else type(proposed).__name__}, "
                           f"where autoMode takes {', '.join(SECTIONS)}")
    entries = {section: proposed[section] for section in SECTIONS if proposed.get(section)}
    if not entries:
        return written(run, "No auto mode entries were proposed.", True)
    with tempfile.TemporaryDirectory(prefix="auto-mode-critique-") as profile:
        credentials = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / ".credentials.json"
        if credentials.is_file():
            (Path(profile) / credentials.name).symlink_to(credentials)
        settings = {"autoMode": {section: ["$defaults", *rules] for section, rules in entries.items()}}
        (Path(profile) / "settings.json").write_text(json.dumps(settings, indent=1))
        try:
            done = subprocess.run(["claude", "auto-mode", "critique"], capture_output=True, text=True, timeout=TIMEOUT,
                                  stdin=subprocess.DEVNULL, cwd=profile, env={**os.environ, "CLAUDE_CONFIG_DIR": profile})
        except (OSError, subprocess.TimeoutExpired) as e:
            return failed(run, f"claude auto-mode critique failed: {e}")
    if done.returncode != 0:
        return failed(run, f"claude auto-mode critique exited {done.returncode}: {done.stderr.strip()}")
    text = "\n".join(line for line in done.stdout.splitlines() if not line.startswith("Analyzing your auto mode rules")).strip()
    if not text or NO_CRITIQUE in text:
        return failed(run, f"claude auto-mode critique printed no critique: {text or 'nothing'}")
    return written(run, text, True)


def failed(run: Path, why: str) -> bool:
    return written(run, f"No critique: {why}", False)


def written(run: Path, body: str, ok: bool) -> bool:
    (run / CRITIQUE).parent.mkdir(parents=True, exist_ok=True)
    (run / CRITIQUE).write_text(f"# The critique of {PROPOSED}\n\n{body}\n")
    return ok


@dataclass
class Args:
    run: tyro.conf.Positional[Path]
    """The retro run's directory, which holds `deep/auto-mode.json`."""


if __name__ == "__main__":
    args = tyro.cli(Args, description=__doc__)
    ok = critique(args.run.resolve())
    print((args.run / CRITIQUE).read_text())
    sys.exit(0 if ok else 1)
