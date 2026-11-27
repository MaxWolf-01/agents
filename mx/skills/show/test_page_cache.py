"""Checks for page_cache's answers to the requests a page makes.

The seam is answer(): one paused request or response in, the DevTools calls that settle it out.
A stand-in for the page's DevTools session records those calls and hands over the bodies a server
would have sent, so no browser runs. The oracle is page_cache's docstring: a copy is fetched the
first time its address is asked for and answers every later load without the network; a request
with no copy goes to the network, or with the network cut off fails without trying. A redirect is
kept so its copy sends the page on the same way, and an error answer is not kept. The live
context, and the page that loads what these answers hand it, are test_render_lint.py's --cache
checks.
"""

import base64
from pathlib import Path

import pytest

from page_cache import answer

URL = "https://cdn.example/lib.js"
SCRIPT = b"window.lib = 1"


class Refused(Exception):
    """What the session raises for a request it will not act on."""


class Session:
    """A page's DevTools session: records every call, hands over `body` when asked for a response's,
    and refuses the calls named in `refusing`."""

    def __init__(self, body: bytes = SCRIPT, refusing: tuple[str, ...] = ()) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.body, self.refusing = body, refusing

    def send(self, method: str, params: dict) -> dict:
        self.calls.append((method, params))
        if method in self.refusing:
            raise Refused(method)
        if method == "Fetch.getResponseBody":
            return {"body": base64.b64encode(self.body).decode(), "base64Encoded": True}
        return {}

    def methods(self) -> list[str]:
        return [m for m, _ in self.calls]

    def fulfilled(self) -> tuple[int, dict[str, str], bytes]:
        """The status, headers and body the page was answered with."""
        [params] = [p for m, p in self.calls if m == "Fetch.fulfillRequest"]
        return (params["responseCode"], {h["name"]: h["value"] for h in params["responseHeaders"]},
                base64.b64decode(params["body"]))


def request(method: str = "GET") -> dict:
    return {"requestId": "r1", "request": {"url": URL, "method": method}}


def response(status: int, **headers: str) -> dict:
    return request() | {"responseStatusCode": status, "responseHeaders": [{"name": k, "value": v} for k, v in headers.items()]}


def load(root: Path, offline: bool = False) -> Session:
    """The page asking for URL once, in a session of its own."""
    cdp = Session()
    answer(cdp, request(), root, offline, Refused)
    return cdp


def fetch(root: Path, status: int, body: bytes = SCRIPT, **headers: str) -> Session:
    """The first load of URL: the request goes to the network, and the server answers it."""
    cdp = load(root)
    assert cdp.calls == [("Fetch.continueRequest", {"requestId": "r1", "interceptResponse": True})]
    cdp.body = body
    answer(cdp, response(status, **headers), root, False, Refused)
    return cdp


def test_a_fetched_script_answers_every_later_load_from_its_copy(tmp_path: Path) -> None:
    """The body reaches the page decoded and whole, so a header saying it is compressed, or how
    long it was on the wire, would make the page misread it."""
    first = fetch(tmp_path, 200, **{"Content-Type": "text/javascript", "Content-Encoding": "gzip", "Content-Length": "9"})
    assert first.fulfilled() == (200, {"Content-Type": "text/javascript"}, SCRIPT)
    for offline in (False, True):
        later = load(tmp_path, offline)
        assert later.methods() == ["Fetch.fulfillRequest"]
        assert later.fulfilled() == first.fulfilled()


def test_a_redirect_is_kept_and_sends_the_page_on_the_same_way(tmp_path: Path) -> None:
    first = fetch(tmp_path, 302, Location="https://cdn.example/lib.2.js")
    assert "Fetch.getResponseBody" not in first.methods(), "a redirect has no body to hand over"
    later = load(tmp_path, offline=True)
    assert later.fulfilled() == (302, {"Location": "https://cdn.example/lib.2.js"}, b"")


def test_an_error_answer_reaches_the_page_and_is_not_kept(tmp_path: Path) -> None:
    first = fetch(tmp_path, 500, b"upstream down")
    assert first.fulfilled() == (500, {}, b"upstream down")
    later = load(tmp_path, offline=True)
    assert later.calls == [("Fetch.failRequest", {"requestId": "r1", "errorReason": "InternetDisconnected"})]


def test_with_the_network_cut_off_a_request_without_its_copy_fails_without_trying(tmp_path: Path) -> None:
    cdp = load(tmp_path, offline=True)
    assert cdp.methods() == ["Fetch.failRequest"]


def test_a_response_whose_body_the_protocol_will_not_hand_over_goes_on_as_it_came(tmp_path: Path) -> None:
    cdp = Session(refusing=("Fetch.getResponseBody",))
    answer(cdp, response(200), tmp_path, False, Refused)
    assert cdp.calls[-1] == ("Fetch.continueRequest", {"requestId": "r1"})
    assert load(tmp_path, offline=True).methods() == ["Fetch.failRequest"], "nothing was kept"


@pytest.mark.parametrize("paused", [request(), response(200)], ids=["request", "response"])
def test_a_request_the_page_dropped_is_past_answering(tmp_path: Path, paused: dict) -> None:
    """Every call on it is refused, and answering it raises nothing."""
    cdp = Session(refusing=("Fetch.continueRequest", "Fetch.getResponseBody"))
    answer(cdp, paused, tmp_path, False, Refused)
    assert cdp.methods()[-1] == "Fetch.continueRequest"
