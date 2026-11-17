"""Checks for `tools/validate.sh`: the seam is its command line, the way an agent runs it. A full-path
check, since its first run installs Pele from npm."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

VALIDATE = Path(__file__).parent / "tools" / "validate.sh"


def validate(tmp_path: Path, source: str, *out: Path) -> subprocess.CompletedProcess:
    diagram = tmp_path / "diagram.mmd"
    diagram.write_text(source)
    # the install goes under the check's own directory, never this machine's cache
    env = {**os.environ, "XDG_CACHE_HOME": str(tmp_path / "cache")}
    return subprocess.run(["bash", str(VALIDATE), str(diagram), *map(str, out)],
                          capture_output=True, text=True, env=env, timeout=300)


@pytest.mark.full_path
def test_a_diagram_pele_draws_passes_and_one_it_cannot_parse_fails_at_its_line_and_column(tmp_path: Path) -> None:
    if not shutil.which("npm"):
        pytest.skip("no npm to install Pele with")
    svg = tmp_path / "diagram.svg"
    drawn = validate(tmp_path, "flowchart LR\n  A[Draft] --> B[Done]\n", svg)
    assert drawn.returncode == 0, drawn.stdout + drawn.stderr
    assert 'class="pele pele-flowchart"' in svg.read_text()
    # an unclosed bracket on line 2, which a parser reports where the next one opens
    broken = validate(tmp_path, "flowchart LR\n  A[Draft --> B[Done]\n")
    assert broken.returncode == 1
    assert "diagram.mmd:2:16:" in broken.stderr, broken.stderr
