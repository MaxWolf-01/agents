"""A toy board: prints tickets by priority. The grid's example change, after."""

from tickets import TICKETS

for t in sorted(TICKETS, key=lambda t: t.priority):
    print(f"P{t.priority}  {t.title:<12} {t.status}")
