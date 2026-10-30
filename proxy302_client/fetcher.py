"""fetch_url: request a public web page through one of the user's own Proxy302 proxies.

Security boundary (reviewed as an "arbitrary URL fetch" capability):
* http/https only, URL length capped, no credentials in the URL, no literal
  private/loopback/link-local IPs and no localhost-style names;
* the request leaves through the user's Proxy302 proxy, never directly from the host;
* connect/read timeouts plus an overall deadline, at most 5 redirects;
* the body is streamed and cut at 5 MB before decoding;
* the proxy password and API key never appear in outputs or error text.
"""

from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

import requests

from . import CLIENT_ID
from .errors import Proxy302Error, redact
from .format import html_to_markdown, html_to_text, truncate

MAX_URL_LENGTH = 2048
MAX_BODY_BYTES = 5_000_000
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30
OVERALL_DEADLINE = 45
MAX_REDIRECTS = 5
MIN_CHARS, MAX_CHARS, DEFAULT_CHARS = 500, 200_000, 20_000
_BLOCKED_NAMES = ("localhost", ".localhost", ".local", ".internal", ".lan", ".home.arpa")


@dataclass
class ProxyEndpoint:
    host: str
    port: int
    username: str
    password: str


@dataclass
class FetchResult:
    status: int
    final_url: str
    content_type: str
    truncated: bool
    content: str


def validate_url(raw: object) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise Proxy302Error("A URL is required.")
    url = raw.strip()
    if len(url) > MAX_URL_LENGTH:
        raise Proxy302Error(f"The URL is too long (limit {MAX_URL_LENGTH} characters).")
    if any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise Proxy302Error("The URL must not contain spaces or control characters.")
    try:
        parts = urlsplit(url)
        host = parts.hostname
        parts.port  # noqa: B018 - raises ValueError on a bad port
    except ValueError:
        raise Proxy302Error("Not a valid URL.") from None
    if parts.scheme.lower() not in ("http", "https"):
        raise Proxy302Error("Only http and https URLs can be fetched.")
    if parts.username is not None or parts.password is not None or "@" in (parts.netloc or ""):
        raise Proxy302Error("URLs containing credentials (user:password@host) are not allowed.")
    if not host:
        raise Proxy302Error("The URL has no host.")
    h = host.lower().rstrip(".")
    if h == "localhost" or h.endswith(_BLOCKED_NAMES):
        raise Proxy302Error("Local and internal host names cannot be fetched.")
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        ip = None
    if ip is not None and not ip.is_global:
        raise Proxy302Error("Private, loopback and link-local addresses cannot be fetched.")
    return url


def clamp_chars(value: object) -> int:
    try:
        n = int(value) if value not in (None, "") else DEFAULT_CHARS
    except (TypeError, ValueError):
        n = DEFAULT_CHARS
    return max(MIN_CHARS, min(MAX_CHARS, n))


def fetch_through_proxy(
    raw_url: str,
    proxy: ProxyEndpoint,
    fmt: str = "markdown",
    max_chars: int = DEFAULT_CHARS,
    session: requests.Session | None = None,
    extra_secrets: tuple[str, ...] = (),
) -> FetchResult:
    url = validate_url(raw_url)
    if fmt not in ("markdown", "text", "raw"):
        raise Proxy302Error("format must be markdown, text or raw.")
    max_chars = clamp_chars(max_chars)
    secrets = (proxy.password, proxy.username, *extra_secrets)
    proxy_uri = f"http://{quote(proxy.username, safe='')}:{quote(proxy.password, safe='')}@{proxy.host}:{proxy.port}"
    sess = session or requests.Session()
    sess.max_redirects = MAX_REDIRECTS
    sess.trust_env = False
    started = time.monotonic()
    res = None
    try:
        res = sess.get(
            url,
            proxies={"http": proxy_uri, "https": proxy_uri},
            headers={
                "User-Agent": f"Mozilla/5.0 (compatible; {CLIENT_ID}; +https://proxy302.com)",
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,text/plain;q=0.8,*/*;q=0.5",
                "Accept-Language": "en-US,en;q=0.8",
            },
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            stream=True,
            allow_redirects=True,
        )
        chunks: list[bytes] = []
        size = 0
        for chunk in res.iter_content(chunk_size=65536):
            if not chunk:
                continue
            chunks.append(chunk)
            size += len(chunk)
            if size >= MAX_BODY_BYTES:
                break
            if time.monotonic() - started > OVERALL_DEADLINE:
                raise Proxy302Error("The page took too long to download.")
        body = b"".join(chunks)[:MAX_BODY_BYTES]
        content_type = res.headers.get("content-type", "")
        charset = res.encoding if res.encoding and "charset" in content_type.lower() else "utf-8"
        try:
            text = body.decode(charset, errors="replace")
        except LookupError:
            text = body.decode("utf-8", errors="replace")
        lowered = text[:200].lstrip().lower()
        is_html = "html" in content_type.lower() or "xml" in content_type.lower() or lowered.startswith(("<!doctype", "<html"))
        if fmt == "raw" or not is_html:
            converted = text
        elif fmt == "text":
            converted = html_to_text(text)
        else:
            converted = html_to_markdown(text)
        out, truncated = truncate(converted, max_chars)
        return FetchResult(res.status_code, redact(res.url or url, secrets), content_type, truncated, out)
    except Proxy302Error:
        raise
    except requests.Timeout as e:
        raise Proxy302Error(f"Request through the proxy timed out ({type(e).__name__}).") from None
    except requests.TooManyRedirects:
        raise Proxy302Error(f"Too many redirects (limit {MAX_REDIRECTS}).") from None
    except requests.RequestException as e:
        raise Proxy302Error(f"Request through the proxy failed ({type(e).__name__}).") from None
    finally:
        if res is not None:
            res.close()
        if session is None:
            sess.close()
