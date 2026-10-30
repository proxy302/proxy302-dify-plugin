"""Error type and secret redaction. Nothing user-visible may contain a credential."""

from __future__ import annotations

import re
from collections.abc import Iterable


class Proxy302Error(Exception):
    """A failure whose message is safe to show to the user and the LLM."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


_URL_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s@]*@")
_BASIC = re.compile(r"(?i)\bBasic\s+[A-Za-z0-9+/=._-]{6,}")


def redact(text: object, secrets: Iterable[str] = ()) -> str:
    """Remove known secrets, URL userinfo and Basic tokens from ``text``."""
    out = str(text)
    for s in sorted({x for x in secrets if x and len(x) >= 3}, key=len, reverse=True):
        out = out.replace(s, "***")
    out = _URL_USERINFO.sub(r"\1***@", out)
    out = _BASIC.sub("Basic ***", out)
    return out
