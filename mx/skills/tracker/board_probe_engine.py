"""What the board's probes share."""


# Whether the graph engine arrived, read off the requests that failed rather than off the page: one
# of its two imports failing is the network's answer, save an abort, which is a navigation leaving
# the page that asked and says nothing about the network. The chunks mermaid fetches while it draws
# are not the engine.
def cdn(failed):
    return not any(url.endswith(("mermaid.min.js", ".esm.min.mjs")) and why != "net::ERR_ABORTED" for url, why in failed)
