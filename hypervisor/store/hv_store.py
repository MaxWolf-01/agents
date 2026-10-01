#!/usr/bin/env python3
"""The hypervisor's log and view.

  hv_store.py --dir DIR init                 create the store at DIR, or leave the one there as it is
  hv_store.py --dir DIR append               log the text on stdin as one entry, stamped with the current minute
  hv_store.py --dir DIR view [--budget N]    a header line, then at most N view lines (256 by default)
  hv_store.py --dir DIR zoom LO-HI           a block's two halves as view lines, leaving out a half not logged yet
  hv_store.py --dir DIR recall REGEX         the entries that match
  hv_store.py --dir DIR raw ID               the whole text of entry ID
  hv_store.py --dir DIR due                  the compressions ready to write, one LO-HI per line
  hv_store.py --dir DIR compress LO-HI       write the text on stdin as the compression of block LO-HI

`append` takes any text: any length, any number of lines. Entries are numbered from 0 in the order
they were appended. A block LO-HI is an aligned power-of-two range of entries, inclusive at both
ends, as in OptMem (github.com/VictorTaelin/OptMem). A view line starts with its start time, to the
minute in one token, then names what it covers, `#ID` for one entry or `#LO-HI` for a block:

  2026-10-01T14:07 #16-31 <the block's compression>
"""

import sys


def main(argv: list[str]) -> int:
    """Run one command: its output goes to stdout, and the exit status is returned. The property
    checks call this in-process, many times in one process, so nothing may carry over between calls."""
    raise NotImplementedError("hypervisor-store builds the store")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
