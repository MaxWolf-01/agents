from typing import NamedTuple


class Ticket(NamedTuple):
    title: str
    status: str
    priority: int


TICKETS = [
    Ticket("fix login", "open", 2),
    Ticket("add export", "claimed", 1),
    Ticket("rename flag", "open", 3),
    Ticket("docs pass", "review", 2),
]
