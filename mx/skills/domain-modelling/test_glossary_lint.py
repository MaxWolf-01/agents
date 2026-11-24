# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "tyro"]
# ///
"""Checks for glossary_lint. Run: uv run test_glossary_lint.py

The seam is `check`: a glossary file in, findings out. The oracle is GLOSSARY-FORMAT.md's own
example entries, which must pass, and entries built to break exactly one rule each. The command
itself, `glossary-lint` on PATH, is run once for what its callers read: code-review reports its
findings as violations, and domain-modelling writes an entry once it passes.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from glossary_lint import check

HERE = Path(__file__).parent
COMMAND = HERE.resolve().parents[1] / "bin" / "glossary-lint"


def kinds(tmp_path: Path, text: str) -> list[tuple[str, str]]:
    p = tmp_path / "GLOSSARY.md"
    p.write_text(text)
    return [(f.term, f.kind) for f in check(p, 40, 2)]


def test_the_format_examples_pass(tmp_path):
    example = re.search(r"```md\n(# \{Context Name\}.*?)```", (HERE / "GLOSSARY-FORMAT.md").read_text(), re.S)
    assert example
    assert kinds(tmp_path, example.group(1)) == []


def test_each_rule_fires_on_its_own(tmp_path):
    text = """## Language

**Long**:
{long}

**Chatty**:
One. Two. Three.

**Coded**:
The record in `HB_ImportBatch`, keyed by import_batch_id.

**Clean**:
A tight definition, e.g. this one. It has two sentences.
_Avoid_: a `backticked` word here is fine
_In code_: `HB_Clean`, clean_table
""".format(long=" ".join(["word"] * 41) + ".")
    assert kinds(tmp_path, text) == [("Long", "words"), ("Chatty", "sentences"), ("Coded", "code")]


def test_a_definition_ends_at_the_blank_line(tmp_path):
    text = "**Term**:\nOne sentence.\n\nA paragraph of prose after the glossary. Two. Three. `code`.\n"
    assert kinds(tmp_path, text) == []


def test_the_command_fails_on_a_finding_naming_its_file_line_and_term_and_passes_a_clean_glossary(tmp_path):
    (tmp_path / "GLOSSARY.md").write_text("## Language\n\n**Clean**:\nA tight one.\n\n**Chatty**:\nOne. Two. Three.\n")
    done = subprocess.run([str(COMMAND)], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert done.returncode == 1, done.stderr
    [finding] = done.stdout.splitlines()
    assert finding.startswith("GLOSSARY.md:6:") and "Chatty" in finding and "sentences" in finding
    (tmp_path / "GLOSSARY.md").write_text("## Language\n\n**Clean**:\nA tight one.\n")
    done = subprocess.run([str(COMMAND)], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert (done.returncode, done.stdout) == (0, ""), done.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
