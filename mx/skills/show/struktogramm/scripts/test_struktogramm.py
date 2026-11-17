"""Checks for the Struktogramm renderer and its layout checker. Run: make test, and make
test-full-path for the ones that open a browser.

The checker's oracle is the notation itself (references/notation.md): no point of the diagram
belongs to no block, two blocks share one line, nothing reaches past the outer rectangle, no band
line crosses a text, and a band's lines run where the notation draws them. The original
renderer's output, as it came from claude.ai, breaks every one of those, and the checker has to
name each fault on it (fixtures/). The renderer is then held to the same checker on every example
and on every construct nested in every other, in both colour schemes.

Without a browser or Playwright the checker cannot measure, and says the layout is unverified
rather than passing it; the renderer itself needs nothing past Python's standard library.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
EXAMPLES = sorted((HERE.parent / "examples").glob("*.json"))


def stdlib_python(*args: str) -> subprocess.CompletedProcess:
    """The script run by a Python that imports nothing past its standard library (-S drops site-packages)."""
    return subprocess.run([sys.executable, "-I", "-S", *args], capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_renderer_draws_each_example_on_the_standard_library_alone(example: Path) -> None:
    done = stdlib_python(str(HERE / "struktogramm.py"), str(example))
    assert done.returncode == 0, done.stderr
    assert '<div class="ns">' in done.stdout


def test_checker_without_playwright_says_the_layout_is_unverified(tmp_path: Path) -> None:
    page = tmp_path / "diagram.html"
    page.write_text((FIXTURES / "original-roast-dinner-parallel.html").read_text())
    done = stdlib_python(str(HERE / "check_layout.py"), str(page))
    assert done.returncode == 2
    assert "UNVERIFIED" in done.stderr
    assert "PASS" not in done.stdout


def faults_of(html: Path, scheme: str = "light", width: int = 680) -> list[str]:
    """The checker's FAIL lines on a page, run as a caller runs it, with Playwright installed."""
    done = subprocess.run(["uv", "run", "--quiet", "--with", "playwright", "python", str(HERE / "check_layout.py"),
                           str(html), "--scheme", scheme, "--width", str(width)],
                          capture_output=True, text=True, timeout=180)
    assert done.returncode in (0, 1), done.stderr
    return [line.removeprefix("FAIL ") for line in done.stdout.splitlines() if line.startswith("FAIL ")]


ORIGINAL_FAULTS = {
    # Finding 1: a stretched loop whose body does not stretch with it.
    "original-troubleshooting": ["dead-space", "doubled-border", "overflow", "text-crossed",
                                 "band-shape: div.cond \"router status lights\"", "band-shape: div.cond \"Fixed?"],
    "original-roast-dinner-parallel": ["doubled-border", "overflow", "text-crossed",
                                       "band-shape: div.cond \"Oven free?"],
}


@pytest.mark.full_path
@pytest.mark.parametrize("fixture", sorted(ORIGINAL_FAULTS))
def test_checker_names_every_fault_of_the_original_render(fixture: str) -> None:
    found = faults_of(FIXTURES / f"{fixture}.html")
    missing = [kind for kind in ORIGINAL_FAULTS[fixture] if not any(f.startswith(kind) for f in found)]
    assert missing == [], "\n".join(found)


def page_of(nodes: list, tmp_path: Path, name: str) -> Path:
    from struktogramm import page

    out = tmp_path / f"{name}.html"
    out.write_text(page(nodes))
    return out


@pytest.mark.full_path
@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_every_example_passes_the_checker(example: Path, scheme: str, tmp_path: Path) -> None:
    import json

    assert faults_of(page_of(json.loads(example.read_text()), tmp_path, example.stem), scheme) == []


TALL = {"type": "stmt", "text": "A sibling three lines tall", "sub": "so the block beside it has to stretch to its height"}


def holding(outer: str, inner: dict) -> dict:
    """The construct `outer` with `inner` inside it, beside a taller sibling where it has columns."""
    if outer in ("pre", "post"):
        return {"type": "loop", "kind": outer, "cond": f"{outer}-tested loop", "body": [inner]}
    if outer == "if":
        return {"type": "if", "cond": "Branch?", "yes": {"body": [inner]}, "no": {"body": [TALL]}}
    if outer == "case":
        return {"type": "case", "cond": "case of", "branches": [
            {"label": "one", "body": [inner]}, {"label": "two", "body": [TALL]}, {"label": "three", "body": []}]}
    return {"type": "par", "cap": "in parallel", "join": "wait for both", "tracks": [[inner], [TALL]]}


INNER = {
    "stmt": {"type": "stmt", "text": "A statement"},
    "call": {"type": "call", "text": "A call", "sub": "its own diagram"},
    "exit": {"type": "exit", "text": "leave the loop"},
    "pre": {"type": "loop", "cond": "while inner", "body": [{"type": "stmt", "text": "step"}]},
    "post": {"type": "loop", "kind": "post", "cond": "until inner", "body": [{"type": "stmt", "text": "step"}]},
    "if": {"type": "if", "cond": "Inner?", "yes": {"body": [{"type": "stmt", "text": "do"}]}, "no": {"body": []}},
    "case": {"type": "case", "cond": "inner case", "branches": [{"label": "a", "body": []}, {"label": "b", "body": []}]},
    "par": {"type": "par", "tracks": [[{"type": "stmt", "text": "left"}], [{"type": "stmt", "text": "right"}]]},
}


@pytest.mark.full_path
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_construct_nested_in_every_other_passes_the_checker(scheme: str, tmp_path: Path) -> None:
    nodes = [holding(outer, inner) for outer in ("pre", "post", "if", "case", "par") for inner in INNER.values()]
    assert faults_of(page_of(nodes, tmp_path, "nested"), scheme, width=900) == []
