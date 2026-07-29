"""Downloading an image the user pasted a link to.

The server opens the socket, so every hop is checked against the rules below first:
public http(s) addresses only, no redirect chains longer than MAX_REDIRECTS, a hard
byte ceiling and a short timeout.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request

MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 10.0
USER_AGENT = "Kolektor image import"
_REDIRECT_CODES = {301, 302, 303, 307, 308}


class FetchError(Exception):
    """Carries a message that is safe to hand back to the user."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        return None


def check_url(url: str) -> None:
    """Raise FetchError unless the URL points at a public http(s) address."""
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        raise FetchError("only http and https links are supported")
    if not parts.hostname:
        raise FetchError("the link has no host name")

    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        raise FetchError("the link has an invalid port") from None

    try:
        infos = socket.getaddrinfo(parts.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise FetchError("the host name could not be resolved") from None

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global or address.is_multicast:
            raise FetchError("links to private or local addresses are refused")


def fetch_image(url: str, max_bytes: int) -> bytes:
    current = url.strip()
    for _ in range(MAX_REDIRECTS + 1):
        check_url(current)
        request = urllib.request.Request(  # noqa: S310 - scheme and address checked above
            current,
            headers={"User-Agent": USER_AGENT, "Accept": "image/*"},
        )
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                data = response.read(max_bytes + 1)
        except urllib.error.HTTPError as err:
            location = err.headers.get("Location") if err.code in _REDIRECT_CODES else None
            if not location:
                raise FetchError(f"the other server answered {err.code}") from None
            current = urllib.parse.urljoin(current, location)
            continue
        except (urllib.error.URLError, OSError, ValueError):
            raise FetchError("the image could not be downloaded") from None

        if not data:
            raise FetchError("the link returned an empty file")
        if len(data) > max_bytes:
            raise FetchError("the image is larger than the upload limit")
        return data

    raise FetchError("too many redirects")
