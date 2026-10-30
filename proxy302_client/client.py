"""Thin client for the Proxy302 open API (/open_api/v3).

Every response is HTTP 200; success is envelope ``code == 0``. Only read-only GET
endpoints are used. Nothing here can buy, renew, top up or create a resource.
"""

from __future__ import annotations

import base64
import re
from typing import Any

import requests

from . import CLIENT_ID
from .errors import Proxy302Error, redact

DEFAULT_BASE_URL = "https://proxy302.com"
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 20


def build_authorization(api_key: str | None) -> str:
    key = (api_key or "").strip()
    if not key:
        raise Proxy302Error(
            "No Proxy302 API key is configured. Create one in the Proxy302 console and "
            'paste it as "<key id>:<secret>".'
        )
    if re.match(r"(?i)^basic\s+", key):
        return key
    if ":" in key:
        return "Basic " + base64.b64encode(key.encode()).decode()
    if re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", key) and len(key) >= 16:
        return "Basic " + key
    raise Proxy302Error('The Proxy302 API key must look like "<key id>:<secret>".')


def key_secrets(api_key: str | None) -> list[str]:
    """Every string form of the credential that must never be echoed."""
    key = (api_key or "").strip()
    out = [key]
    if ":" in key:
        out.extend(p for p in key.split(":") if p)
    try:
        out.append(build_authorization(key).split(" ", 1)[-1])
    except Proxy302Error:
        pass
    return [s for s in out if s]


class Proxy302Client:
    def __init__(self, api_key: str | None, base_url: str = DEFAULT_BASE_URL, session: Any = None):
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self._session = session or requests
        self.secrets = key_secrets(self.api_key)

    def redact(self, text: object) -> str:
        return redact(text, self.secrets)

    def request(self, path: str, query: dict[str, Any] | None = None) -> Any:
        authorization = build_authorization(self.api_key)
        url = f"{self.base_url}/open_api/v3/{path.lstrip('/')}"
        params = {k: v for k, v in (query or {}).items() if v is not None and v != ""}
        try:
            res = self._session.get(
                url,
                params=params,
                headers={
                    "Authorization": authorization,
                    "Accept": "application/json",
                    "User-Agent": CLIENT_ID,
                    "X-Proxy302-Client": CLIENT_ID,
                },
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                allow_redirects=False,
            )
        except requests.RequestException as e:
            raise Proxy302Error(f"Could not reach Proxy302 ({type(e).__name__}).") from None
        if res.status_code == 401:
            raise Proxy302Error("Proxy302 rejected the API key (401).", 401)
        try:
            body = res.json()
        except ValueError:
            raise Proxy302Error(f"Unexpected response from Proxy302 (HTTP {res.status_code}).") from None
        if not isinstance(body, dict):
            raise Proxy302Error(f"Unexpected response from Proxy302 (HTTP {res.status_code}).")
        code = body.get("code")
        if code != 0:
            msg = self.redact(body.get("msg") or f"Proxy302 error code {code}")
            raise Proxy302Error(msg, code if isinstance(code, int) else None)
        return body.get("data")

    # --- read-only endpoints -------------------------------------------------
    def me(self):
        return self.request("user/users/me")

    def wallet(self):
        return self.request("user/users/wallet")

    def areas(self, kind: str, pid: str | None = None, name: str | None = None):
        return self.request(f"proxy/area/{kind}", {"pid": pid, "name": name})

    def payways(self, name: str):
        return self.request(f"proxy/payway/{name}")

    def traffic_pool(self):
        return self.request("proxy/traffic/pool/remaining")

    def consume_summary(self, start_time: int, end_time: int):
        return self.request("proxy/traffic/consume/log/summary", {"start_time": start_time, "end_time": end_time})

    def tokens(self, generate: str, proxy_type: str, **query: Any):
        return self.request(f"proxy/tokens/{generate}/{proxy_type}", query)
