"""Checks for the Struktogramm renderer and its layout checker. Run: make test, and make
test-full-path for the ones that open a browser.

The checker's oracle is the notation itself (../SKILL.md, and check_layout.py's --help for the
band shapes): no point of the diagram belongs to no block, two blocks share one line, nothing
reaches past the outer rectangle, no band line crosses a text, no word is split across lines, and
a band's lines run where the notation draws them. The original
renderer's output, as it came from claude.ai, breaks every one of those, and the checker has to
name each fault on it (fixtures/), on the blocks where it shows. The renderer is then held to the
same checker on every example, on every construct nested in every other, and embedded in a host
page, in both colour schemes; and its HTML holds every text it was given, each branch's body in
its label's column.

Without a browser or Playwright the checker cannot measure, and says the layout is unverified
rather than passing it; the renderer itself needs nothing past Python's standard library.
"""

import json
import os
import subprocess
import sys
from html import escape
from pathlib import Path

import pytest

from struktogramm import fragment, main, page

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
    missing = [t for t in texts_in(json.loads(example.read_text())) if escape(t) not in done.stdout]
    assert missing == []


def test_the_renderer_writes_its_page_to_the_file_o_names(tmp_path: Path) -> None:
    """SKILL.md step 2 renders with `-o out.html`, the file the layout check then reads."""
    example = HERE.parent / "examples" / "troubleshooting.json"
    out = tmp_path / "out.html"
    done = stdlib_python(str(HERE / "struktogramm.py"), str(example), "-o", str(out))
    assert done.returncode == 0, done.stderr
    html = out.read_text()
    assert [t for t in texts_in(json.loads(example.read_text())) if escape(t) not in html] == []


def test_the_command_writes_the_page_to_the_file_o_names_instead_of_to_stdout(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """`-o`'s --help: "write here instead of to stdout", so the agent that renders reads a line, not
    the page. On the example holding an inputs block, exits and parallel tracks that name what they use."""
    example = HERE.parent / "examples" / "batch-download.json"
    out = tmp_path / "out.html"
    monkeypatch.setattr(sys, "argv", ["struktogramm.py", str(example), "-o", str(out)])
    assert main() == 0
    assert capsys.readouterr().out == ""
    html = out.read_text()
    assert html.lstrip().lower().startswith("<!doctype html")
    assert [t for t in texts_in(json.loads(example.read_text())) if escape(t) not in html] == []


def test_the_command_prints_the_fragment_to_embed(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """SKILL.md's Rendering: `--fragment` prints `<style>` and the diagram, which a host page embeds
    as it is. On the example holding a call and a parallel block."""
    example = HERE.parent / "examples" / "roast-dinner-parallel.json"
    monkeypatch.setattr(sys, "argv", ["struktogramm.py", str(example), "--fragment"])
    assert main() == 0
    printed = capsys.readouterr().out
    assert "<style" in printed and "<html" not in printed.lower() and "<body" not in printed.lower()
    assert [t for t in texts_in(json.loads(example.read_text())) if escape(t) not in printed] == []


def test_the_command_refuses_a_node_list_with_a_misspelt_type_and_writes_no_page(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SKILL.md step 2 as the agent runs it, on a node list it wrote with a typo: the refusal names
    the type, and no page is left for the layout check to read."""
    diagram = tmp_path / "diagram.json"
    diagram.write_text(json.dumps([{"type": "stmt", "text": "Preheat"}, {"type": "whiel", "cond": "x", "body": []}]))
    out = tmp_path / "out.html"
    monkeypatch.setattr(sys, "argv", ["struktogramm.py", str(diagram), "-o", str(out)])
    with pytest.raises(ValueError, match="'whiel'"):
        main()
    assert not out.exists()


def texts_in(nodes: list) -> list[str]:
    """Every text a node list asks the diagram to show."""
    found = []
    for n in nodes:
        found += [n[k] for k in ("text", "sub", "cond", "cap", "join", "time", "title") if k in n]
        found += n.get("items", [])
        for arm in [n.get("yes"), n.get("no"), *n.get("branches", [])]:
            if arm:
                found += [arm["label"]] if "label" in arm else []
                found += texts_in(arm.get("body", []))
        found += texts_in(n.get("body", []))
        for track in n.get("tracks", []):
            found += [track["uses"]] if isinstance(track, dict) and "uses" in track else []
            found += texts_in(track["body"] if isinstance(track, dict) else track)
    return found


def test_each_branch_body_is_drawn_under_its_own_label() -> None:
    html = fragment([
        {"type": "if", "cond": "c", "yes": {"label": "LABEL-YES", "body": [{"type": "stmt", "text": "BODY-YES"}]},
         "no": {"label": "LABEL-NO", "body": [{"type": "stmt", "text": "BODY-NO"}]}},
        {"type": "case", "cond": "k", "branches": [
            {"label": f"LABEL-{i}", "body": [{"type": "stmt", "text": f"BODY-{i}"}]} for i in range(3)]},
    ])
    # Columns are laid out left to right in the order the markup holds them.
    order = lambda *words: [html.index(w) for w in words] == sorted(html.index(w) for w in words)
    assert order("LABEL-YES", "LABEL-NO", "BODY-YES", "BODY-NO")
    assert order("LABEL-0", "LABEL-1", "LABEL-2", "BODY-0", "BODY-1", "BODY-2")


def test_a_node_of_no_known_type_is_refused_naming_it() -> None:
    """A misspelt type in the node list the agent wrote, nested where it is easy to miss."""
    with pytest.raises(ValueError, match="'whiel'"):
        fragment([{"type": "if", "cond": "c", "yes": {"body": [{"type": "whiel", "cond": "x", "body": []}]}}])


def test_checker_without_playwright_says_the_layout_is_unverified(tmp_path: Path) -> None:
    page = tmp_path / "diagram.html"
    page.write_text((FIXTURES / "original-roast-dinner-parallel.html").read_text())
    done = stdlib_python(str(HERE / "check_layout.py"), str(page))
    assert done.returncode == 2
    assert "UNVERIFIED" in done.stderr
    assert "PASS" not in done.stdout


def test_preview_without_a_browser_still_writes_the_page_and_says_the_layout_is_unseen(tmp_path: Path) -> None:
    """preview.py's docstring: needs a Chromium binary, and without one still writes the HTML and
    says the layout is unseen. Its PATH here holds no browser."""
    if Path("/opt/google/chrome/chrome").exists():
        pytest.skip("this host has a Chrome at the path preview.py tries first, whatever PATH holds")
    example = HERE.parent / "examples" / "troubleshooting.json"
    (tmp_path / "bin").mkdir()
    done = subprocess.run([sys.executable, str(HERE / "preview.py"), str(example)], cwd=tmp_path, capture_output=True,
                          text=True, timeout=60, env={**os.environ, "PATH": str(tmp_path / "bin")})
    assert done.returncode == 0, done.stderr
    assert "unseen" in done.stderr
    html = (tmp_path / "preview.html").read_text()
    assert [t for t in texts_in(json.loads(example.read_text())) if escape(t) not in html] == []
    assert not (tmp_path / "preview.png").exists()


def preview_with(tmp_path: Path, chromium: str, *args: str) -> subprocess.CompletedProcess:
    """preview.py run on an example with a `chromium` on PATH that runs `chromium`, a shell script,
    in place of the browser; its arguments are left in `argv` beside it."""
    if Path("/opt/google/chrome/chrome").exists():
        pytest.skip("this host has a Chrome at the path preview.py tries first, whatever PATH holds")
    (tmp_path / "bin").mkdir()
    stub = tmp_path / "bin" / "chromium"
    stub.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "{tmp_path / "argv"}"\n{chromium}\n')
    stub.chmod(0o755)
    example = HERE.parent / "examples" / "troubleshooting.json"
    return subprocess.run([sys.executable, str(HERE / "preview.py"), str(example), *args], cwd=tmp_path, capture_output=True,
                          text=True, timeout=60, env={**os.environ, "PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin"})


# Chromium writes the picture to the file its --screenshot= names.
SCREENSHOTS = 'for arg; do case "$arg" in --screenshot=*) printf png > "${arg#--screenshot=}";; esac; done'


@pytest.mark.parametrize("scheme, dark", [("light", False), ("dark", True)])
def test_preview_says_where_the_picture_is_to_look_at(tmp_path: Path, scheme: str, dark: bool) -> None:
    """SKILL.md step 3: the agent renders a picture with preview.py and looks at it, so the PNG's
    path is what it prints. `--scheme dark` shows the page dark, which Chromium's
    --force-dark-mode does (what the page's prefers-color-scheme reads)."""
    done = preview_with(tmp_path, SCREENSHOTS, "--scheme", scheme)
    assert done.returncode == 0, done.stderr
    png = tmp_path / "preview.png"
    assert str(png) in done.stdout and png.read_text() == "png"
    assert ("--force-dark-mode" in (tmp_path / "argv").read_text().splitlines()) == dark


def test_a_browser_that_takes_no_picture_fails_the_preview_saying_why(tmp_path: Path) -> None:
    """With no picture there is nothing to look at: the preview exits 1 with the browser's own words."""
    done = preview_with(tmp_path, 'echo "Missing X server to draw on" >&2')
    assert done.returncode == 1
    assert "Missing X server to draw on" in done.stderr
    assert "png:" not in done.stdout and not (tmp_path / "preview.png").exists()


def faults_of(html: Path, scheme: str = "light", width: int = 680) -> list[str]:
    """The checker's FAIL lines on a page, run as a caller runs it, with Playwright installed."""
    done = subprocess.run(["uv", "run", "--quiet", "--with", "playwright", "python", str(HERE / "check_layout.py"),
                           str(html), "--scheme", scheme, "--width", str(width)],
                          capture_output=True, text=True, timeout=180)
    assert done.returncode in (0, 1), done.stderr
    return [line.removeprefix("FAIL ") for line in done.stdout.splitlines() if line.startswith("FAIL ")]


# Each fault a faulty render shows, by the start of the line the checker names it in. Which
# column of a branch comes out shorter depends on the fonts and the width, so the roast dinner is
# also measured at 900px, where its potato track is the short one.
FAULTY_RENDERS = {
    ("original-troubleshooting", 680): [
        "dead-space: ",  # a stretched block whose inside does not stretch with it; the fonts decide which block
        'doubled-border: left of div.fork "Does any other device',
        'overflow: div. "all normal"',  # the case's label row, past the outer right border
        'text-crossed: a line runs through "Does any other device',
        'text-crossed: a line runs through "router status lights"',
        'text-crossed: a line runs through "yes"',
        'text-crossed: a line runs through "no"',
        'band-shape: div.cond "router status lights"',
        'band-shape: div.cond "Fixed?',
    ],
    ("original-roast-dinner-parallel", 680): [
        'doubled-border: left of div.par "in parallel',
        'text-crossed: a line runs through "Oven free?"',
        'band-shape: div.cond "Oven free?',
    ],
    ("original-roast-dinner-parallel", 900): [
        'dead-space: div.fork "Oven free?',  # a stretched branch whose columns do not stretch with it
    ],
    # The message loop as this renderer drew it before it sized the diagram by its longest words:
    # at 680px its narrowest columns split words.
    ("split-words-message-loop", 680): [
        'broken-word: "checksu/m"',
        'broken-word: "incre/ment"',
    ],
}


@pytest.mark.full_path
@pytest.mark.parametrize("fixture,width", sorted(FAULTY_RENDERS))
def test_checker_names_every_fault_of_a_faulty_render(fixture: str, width: int) -> None:
    found = faults_of(FIXTURES / f"{fixture}.html", width=width)
    missing = [fault for fault in FAULTY_RENDERS[fixture, width] if not any(f.startswith(fault) for f in found)]
    assert missing == [], "\n".join(found)


def page_of(nodes: list, tmp_path: Path, name: str) -> Path:
    out = tmp_path / f"{name}.html"
    out.write_text(page(nodes))
    return out


@pytest.mark.full_path
@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_every_example_passes_the_checker(example: Path, scheme: str, tmp_path: Path) -> None:
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
    return {"type": "par", "cap": "in parallel", "join": "wait for both",
            "tracks": [{"uses": "the one oven", "body": [inner]}, [TALL]]}


INNER = {
    "stmt": {"type": "stmt", "text": "A statement"},
    "call": {"type": "call", "text": "A call", "sub": "its own diagram"},
    "exit": {"type": "exit", "text": "leave the loop"},
    "return": {"type": "exit", "kind": "return", "text": "the result"},
    "raise": {"type": "exit", "kind": "raise", "text": "TimeoutError", "time": "after 30 s"},
    "inputs": {"type": "inputs", "title": "ingredients", "items": ["2 eggs", "100 g flour", "a pinch of salt"]},
    "timed": {"type": "stmt", "text": "Simmer", "sub": "lid on", "time": "20 min"},
    "pre": {"type": "loop", "cond": "while inner", "time": "5 min", "body": [{"type": "stmt", "text": "step"}]},
    "post": {"type": "loop", "kind": "post", "cond": "until inner", "body": [{"type": "stmt", "text": "step"}]},
    "if": {"type": "if", "cond": "Inner?", "time": "1 s", "yes": {"body": [{"type": "stmt", "text": "do"}]}, "no": {"body": []}},
    "case": {"type": "case", "cond": "inner case", "branches": [{"label": "a", "body": []}, {"label": "b", "body": []}]},
    "par": {"type": "par", "tracks": [[{"type": "stmt", "text": "left"}], [{"type": "stmt", "text": "right"}]]},
}


@pytest.mark.full_path
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_construct_nested_in_every_other_passes_the_checker(scheme: str, tmp_path: Path) -> None:
    nodes = [holding(outer, inner) for outer in ("pre", "post", "if", "case", "par") for inner in INNER.values()]
    assert faults_of(page_of(nodes, tmp_path, "nested"), scheme, width=900) == []


@pytest.mark.full_path
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_fragment_embedded_in_a_themed_host_page_passes_the_checker(scheme: str, tmp_path: Path) -> None:
    nodes = json.loads((HERE.parent / "examples" / "troubleshooting.json").read_text())
    host = tmp_path / "host.html"
    host.write_text("<!doctype html><meta charset=utf-8><style>body { margin: 40px; background: #f3ead8; font: 16px Georgia, serif;"
                    " --text-primary: #3b2a1a; --text-secondary: #7a6650; --border-strong: #8a7a60; }</style>"
                    f"<body><h1>A host page</h1>{fragment(nodes)}</body>")
    assert faults_of(host, scheme) == []
