# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest"]
# ///
"""Checks for the chat reviewer's two readings. Run: uv run test_chat_review.py

The seams are the scope selection (catalogue text in, the chat-scoped rule blocks out) and the
answer parse (a model's answer in, hits out). The oracle for the selection is the awk command
CATALOGUE.md's header publishes as its format contract: this test runs that command and demands
the same bytes, so the header and the script cannot drift apart, and a catalogue whose bullets
stop matching fails here rather than turning every reply clean. The answer parse is held to the
hook's fail-open rule: drop what cannot be formatted, raise only where the caller still catches.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from chat_review import CATALOGUE, chat_rules, hits_from

FIXTURE = """# Tells

Prose about the tags.

## Content

- `3` `both` **A rule.** Its first line.
  Before: "indented continuation". After: "rides with its rule".

- `51` `artifact` **A rule for files only.** Dropped.

## Style

- `13` `chat` **A rule for replies.** Kept.
"""


def awk_selection() -> str:
    """The header's own command, run on the real catalogue."""
    program = re.search(r"awk '(.+?)' CATALOGUE\.md", CATALOGUE.read_text()).group(1)
    run = subprocess.run(["awk", program, CATALOGUE], capture_output=True, text=True, check=True)
    return run.stdout.rstrip("\n")


def test_selection_is_the_one_the_catalogue_documents() -> None:
    assert chat_rules(CATALOGUE.read_text()) == awk_selection()


def test_selected_blocks_come_whole() -> None:
    assert chat_rules(FIXTURE).splitlines() == [
        "- `3` `both` **A rule.** Its first line.",
        '  Before: "indented continuation". After: "rides with its rule".',
        "",
        "- `13` `chat` **A rule for replies.** Kept.",
    ]


def test_a_catalogue_with_no_chat_rules_raises() -> None:
    with pytest.raises(RuntimeError):
        chat_rules(FIXTURE.replace("`both`", "`artifact`").replace("`chat`", "`artifact`"))


def test_hits_are_read_out_of_surrounding_prose() -> None:
    hit = {"rule": "13", "quote": "a dash", "fix": "a period"}
    assert hits_from('Here you go: {"hits": [%s]}' % str(hit).replace("'", '"')) == [hit]
    assert hits_from('{"hits": []}') == []


def test_hits_shaped_unlike_a_hit_are_dropped() -> None:
    assert hits_from('{"hits": ["Great question!"]}') == []
    assert hits_from('{"hits": 5}') == []


def test_an_answer_with_no_json_raises() -> None:
    with pytest.raises(RuntimeError):
        hits_from("The message reads well.")
