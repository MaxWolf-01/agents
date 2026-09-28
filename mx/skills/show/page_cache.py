"""Answer every remote request a Chromium context makes from a copy kept on this machine.

A copy is fetched the first time its address is asked for and kept, so every later load of the
page touches no network: a check that loads a page with a graph engine and fonts on a CDN stops
waiting on the CDN. Each copy is one file named by a hash of its address, holding a JSON line of
status and headers and then the body, and lands in place by a rename, so processes filling the
same directory at once never read half a file.

A request the directory holds no copy of goes to the network, and fails the way the network makes
it fail. MX_PAGE_CACHE_OFFLINE=1 fails it without trying, which is a run with the network cut off.

The requests are caught through the DevTools protocol on each page rather than through
Playwright's routing: a window a page opens and writes into itself makes its first requests
through the page that opened it, and Playwright's routing leaves those hanging.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import weakref
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, CDPSession, Page

# Headers that no longer describe the body: the protocol hands it over decoded and whole.
DROPPED = {"content-encoding", "content-length", "transfer-encoding"}


def default_root() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "mx" / "page-cache"


# The pages whose requests are caught already, and the contexts that catch a page opening.
CAUGHT: weakref.WeakSet = weakref.WeakSet()
WATCHED: weakref.WeakSet = weakref.WeakSet()


def serve(context: BrowserContext, root: Path) -> None:
    """Answer every http(s) request of every page in `context` from `root`: the pages open now,
    and the windows they open later. A page the caller opens is announced only once it has started
    loading, so a caller serves the context again after opening one and before loading it."""
    root.mkdir(parents=True, exist_ok=True)
    offline = os.environ.get("MX_PAGE_CACHE_OFFLINE") == "1"
    for page in context.pages:
        intercept(context, page, root, offline)
    if context not in WATCHED:
        WATCHED.add(context)
        context.on("page", lambda page: intercept(context, page, root, offline))


def intercept(context: BrowserContext, page: Page, root: Path, offline: bool) -> None:
    if page in CAUGHT:
        return
    CAUGHT.add(page)
    cdp = context.new_cdp_session(page)
    cdp.on("Fetch.requestPaused", lambda paused: answer(cdp, paused, root, offline))
    cdp.send("Fetch.enable", {"patterns": [{"urlPattern": "http*"}]})


def answer(cdp: CDPSession, paused: dict, root: Path, offline: bool) -> None:
    """One request paused on its way out, or its response on the way back in. A response whose body
    the protocol will not hand over goes on as it came; a request the page
    dropped meanwhile, by navigating away or closing, is past answering."""
    from playwright.sync_api import Error

    try:
        settle(cdp, paused, root, offline)
    except Error:
        try:
            cdp.send("Fetch.continueRequest", {"requestId": paused["requestId"]})
        except Error:
            pass


def settle(cdp: CDPSession, paused: dict, root: Path, offline: bool) -> None:
    request, rid = paused["request"], paused["requestId"]
    copy = copy_of(root, request["url"])
    if "responseStatusCode" in paused:  # the response to a GET this let through
        status = paused["responseStatusCode"]
        headers = [h for h in paused.get("responseHeaders", []) if h["name"].lower() not in DROPPED]
        if 300 <= status < 400:  # a redirect has no body, and its copy sends the page on the same way
            body = b""
        else:
            said = cdp.send("Fetch.getResponseBody", {"requestId": rid})
            body = base64.b64decode(said["body"]) if said["base64Encoded"] else said["body"].encode()
        if status == 200 or 300 <= status < 400:
            keep(copy, json.dumps({"status": status, "headers": headers}).encode() + b"\n" + body)
        fulfil(cdp, rid, status, headers, body)
    elif request["method"] == "GET" and copy.exists():
        head, _, body = copy.read_bytes().partition(b"\n")
        said = json.loads(head)
        fulfil(cdp, rid, said["status"], said["headers"], body)
    elif offline:
        cdp.send("Fetch.failRequest", {"requestId": rid, "errorReason": "InternetDisconnected"})
    else:
        cdp.send("Fetch.continueRequest", {"requestId": rid, "interceptResponse": request["method"] == "GET"})


def copy_of(root: Path, url: str) -> Path:
    """Where `root` keeps its copy of `url`."""
    return root / hashlib.sha256(url.encode()).hexdigest()


def fulfil(cdp: CDPSession, rid: str, status: int, headers: list[dict], body: bytes) -> None:
    cdp.send("Fetch.fulfillRequest", {"requestId": rid, "responseCode": status, "responseHeaders": headers,
                                      "body": base64.b64encode(body).decode()})


def keep(copy: Path, data: bytes) -> None:
    fd, scratch = tempfile.mkstemp(dir=copy.parent, prefix=f".{copy.name}.")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(scratch, copy)
