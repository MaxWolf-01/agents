"""The pilot's replay (agent/prototypes/optmem-replay/), rerun through the command line: its entries
imported, the due compressions answered from the ones Sonnet wrote for it, and the view compared with
the one the pilot rendered. The pilot's output is not in the repo; HV_PILOT_OUT points at a copy."""

import json
import os
import random
import re
from pathlib import Path

import pytest
from test_store import run

PILOT = Path(os.environ.get("HV_PILOT_OUT", "/var/tmp/optmem-replay/out"))

pytestmark = pytest.mark.skipif(
    not all((PILOT / f).exists() for f in ("entries.txt", "naps.jsonl", "view.txt")), reason=f"no pilot output at {PILOT}; set HV_PILOT_OUT"
)


def test_the_pilots_entries_give_the_pilots_view_with_every_line_stamped(tmp_path: Path) -> None:
    store = tmp_path / "store"
    run(store, "init")
    code, _, err = run(store, "import", stdin=(PILOT / "entries.txt").read_text())
    assert code == 0, err
    naps = {"%d-%d" % tuple(n["block"]): n["line"] for n in map(json.loads, (PILOT / "naps.jsonl").read_text().splitlines())}
    # Each round in a shuffled order, as forks finish, so blocks are held before they reach the tree.
    rnd = random.Random(1371)
    while blocks := run(store, "due")[1].split():
        for block in rnd.sample(blocks, len(blocks)):
            # The pilot's clip let two compressions run to 515 bytes, which the store refuses as a
            # fork's would be; neither block is one its view shows.
            if run(store, "compress", block, stdin=naps[block])[0] != 0:
                assert run(store, "compress", block, stdin=naps[block].encode()[:512].decode(errors="ignore"))[0] == 0
    code, out, err = run(store, "view")
    assert code == 0, err
    lines = out.removesuffix("\n").split("\n")[1:]
    assert len(lines) == 256
    ours = [re.fullmatch(r"(\d{4}-\d{2}-\d{2})T\d{2}:\d{2} #(\d+(?:-\d+)?) (.*)", line) for line in lines]
    assert all(ours), "a view line that does not start with its start time"
    pilot = [re.fullmatch(r"#(\S+) (\S+) (.*)", line) for line in (PILOT / "view.txt").read_text().splitlines()]
    # The pilot gives a block its first and last date, `A..B`; the store its first entry's minute.
    assert [(m[1], m[2].split("..")[0], m[3]) for m in pilot] == [(m[2], m[1], m[3]) for m in ours]
