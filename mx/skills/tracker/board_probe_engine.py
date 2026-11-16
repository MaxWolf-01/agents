"""What the board's probes share."""


# Whether the graph engine arrived, read off the requests that failed rather than off the page: its
# file failing is the network's answer, save an abort, which is a navigation leaving the page that
# asked and says nothing about the network.
def cdn(failed):
    return not any(url.endswith("/pele.global.js") and why != "net::ERR_ABORTED" for url, why in failed)
