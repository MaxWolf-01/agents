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
BROWSER_ARG = f"--mx-run={os.environ.get('MX_RUN') or os.getcwd()}"


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
                           str(html), "--scheme", scheme, "--width", str(width), f"--browser-arg={BROWSER_ARG}"],
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
