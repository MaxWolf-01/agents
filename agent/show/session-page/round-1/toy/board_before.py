"""A toy board: prints tickets grouped by status. The grid's example change, before."""

from itertools import groupby
from tickets import TICKETS


def status_of(t):
    return t.status


for status, group in groupby(sorted(TICKETS, key=status_of), key=status_of):
    print(status)
    for t in group:
        print(f"  {t.title}")
