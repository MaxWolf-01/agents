# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "hypothesis", "tyro", "pyyaml", "markdown-it-py"]
# ///
"""What the turn review reads its rules and the record's shape from. Run: uv run test_turn_review.py

The seam is `turn_review`'s readers of the catalogue and the session page's rules (RULES.md), whose
output the reviewer's system prompt is built from. The oracles are the catalogue's own published
selection command and the renderer's reader of a turn record.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import session_page
import turn_review

# ---- the catalogue's chat rules ---------------------------------------------

CATALOGUE_FIXTURE = """# Tells

Prose about the tags.

## Content

- `3` `both` **A rule.** Its first line.
  Before: "indented continuation". After: "rides with its rule".

- `51` `artifact` **A rule for files only.** Dropped.

## Style

- `13` `chat` **A rule for replies.** Kept.
"""

SELECTED = """- `3` `both` **A rule.** Its first line.
  Before: "indented continuation". After: "rides with its rule".

- `13` `chat` **A rule for replies.** Kept."""


def test_the_rules_selected_are_the_ones_the_catalogue_documents() -> None:
    """The oracle is the awk command CATALOGUE.md's header publishes as its format contract, run
    on the real catalogue: a catalogue whose bullets stop matching fails here rather than turning
    every record clean."""
    catalogue = turn_review.CATALOGUE
    program = re.search(r"awk '(.+?)' CATALOGUE\.md", catalogue.read_text()).group(1)
    awk = subprocess.run(["awk", program, catalogue], capture_output=True, text=True, check=True)
    assert turn_review.chat_rules(catalogue.read_text()) == awk.stdout.rstrip("\n")


def test_selected_rule_blocks_come_whole() -> None:
    assert turn_review.chat_rules(CATALOGUE_FIXTURE) == SELECTED


RULES_FIXTURE = """# The session page

Prose before the shape.

## The turn record

The shape's prose.

```markdown
---
date: 2026-09-28
---

# A headline inside the example

## Details

The example's own section.
```

- A rule about the record.

## Another section

After the shape.
"""


def test_the_shape_runs_to_the_next_heading_past_the_example_records_own() -> None:
    shape = turn_review.record_shape(RULES_FIXTURE)
    assert shape.startswith("The shape's prose.") and shape.endswith("- A rule about the record.")
    assert "# A headline inside the example" in shape and "## Details" in shape
    assert "Prose before" not in shape and "After the shape" not in shape


def test_the_turn_record_the_rules_give_the_agent_parses(tmp_path: Path) -> None:
    """The oracle is the renderer's own reader: the example record the agent is shown is a record
    it accepts, and it uses every part a record can hold, so the rules and the parser cannot drift
    apart unnoticed."""
    shape = turn_review.record_shape(turn_review.RULES.read_text())
    example = re.search(r"```markdown\n(.*?)```", shape, re.S).group(1)
    record = tmp_path / "07.md"
    record.write_text(example)
    turn = session_page.read_turn(record)
    assert turn.headline and turn.details and turn.links and turn.answered and turn.superseded
    (question,) = turn.questions
    assert len(question.options) >= 2 and sum(o.picked for o in question.options) == 1 and question.why


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
