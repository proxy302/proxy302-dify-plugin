"""Output shaping shared by the tools (mirrors the Proxy302 MCP server's formatting)."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import quote


def format_bytes(value: object) -> str:
    try:
        n = float(value if value is not None else 0)
    except (TypeError, ValueError):
        return str(value)
    if n != n or n in (float("inf"), float("-inf")):
        return str(value)
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.0f} {units[i]}" if i == 0 else f"{n:.2f} {units[i]}"


def mask(secret: str | None) -> str:
    if not secret:
        return ""
    return "********"


def proxy_url(protocol: str, user: str, password: str, host: str, port: int) -> str:
    scheme = "socks5" if protocol == "socks5" else "http"
    return f"{scheme}://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"


def truncate(text: str, limit: int) -> tuple[str, bool]:
    return (text[:limit], True) if len(text) > limit else (text, False)


_SKIP = {"script", "style", "noscript", "iframe", "svg", "template", "head"}


class _MarkdownParser(HTMLParser):
    """Small HTML to Markdown converter (headings, links, lists, code, emphasis)."""

    def __init__(self, text_only: bool) -> None:
        super().__init__(convert_charrefs=True)
        self.text_only = text_only
        self.out: list[str] = []
        self.skip = 0
        self.href: list[str | None] = []
        self.lists: list[str] = []
        self.in_pre = 0

    def _w(self, s: str) -> None:
        self.out.append(s)

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        a = dict(attrs)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._w("\n\n" + ("" if self.text_only else "#" * int(tag[1]) + " "))
        elif tag in {"p", "div", "section", "article", "tr", "table", "blockquote", "header", "footer", "main"}:
            self._w("\n\n" if tag in {"p", "blockquote", "table"} else "\n")
        elif tag == "br":
            self._w("\n")
        elif tag in {"ul", "ol"}:
            self.lists.append(tag)
            self._w("\n")
        elif tag == "li":
            self._w("\n" + ("  " * max(len(self.lists) - 1, 0)) + ("- " if not self.lists or self.lists[-1] == "ul" else "1. "))
        elif tag == "pre":
            self.in_pre += 1
            self._w("\n\n" if self.text_only else "\n\n```\n")
        elif tag == "code" and not self.in_pre and not self.text_only:
            self._w("`")
        elif tag in {"strong", "b"} and not self.text_only:
            self._w("**")
        elif tag in {"em", "i"} and not self.text_only:
            self._w("*")
        elif tag == "a":
            self.href.append(a.get("href"))
            if not self.text_only:
                self._w("[")
        elif tag == "img" and not self.text_only and a.get("alt"):
            self._w(f"![{a.get('alt')}]({a.get('src') or ''})")
        elif tag in {"td", "th"}:
            self._w(" ")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self.skip = max(self.skip - 1, 0)
            return
        if self.skip:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote"}:
            self._w("\n\n")
        elif tag in {"ul", "ol"}:
            if self.lists:
                self.lists.pop()
            self._w("\n")
        elif tag == "pre":
            self.in_pre = max(self.in_pre - 1, 0)
            self._w("\n\n" if self.text_only else "\n```\n\n")
        elif tag == "code" and not self.in_pre and not self.text_only:
            self._w("`")
        elif tag in {"strong", "b"} and not self.text_only:
            self._w("**")
        elif tag in {"em", "i"} and not self.text_only:
            self._w("*")
        elif tag == "a":
            href = self.href.pop() if self.href else None
            if not self.text_only:
                self._w(f"]({href})" if href else "]")

    def handle_data(self, data):
        if self.skip:
            return
        self._w(data if self.in_pre else re.sub(r"\s+", " ", data))


def _convert(html: str, text_only: bool) -> str:
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    m = re.search(r"<body[^>]*>(.*)</body>", html, flags=re.S | re.I)
    p = _MarkdownParser(text_only)
    p.feed(m.group(1) if m else html)
    p.close()
    text = "".join(p.out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text) if text_only else text
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def html_to_markdown(html: str) -> str:
    return _convert(html, text_only=False)


def html_to_text(html: str) -> str:
    return _convert(html, text_only=True)
