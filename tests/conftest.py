import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

KEY = "kid_9f3a:SUPERSECRETvalue123"
PROXY_PASS = "pXy-PASSWORD-77z"


class FakeResp:
    def __init__(self, body=None, status=200, headers=None, raw=None, url="https://example.test/page", encoding="utf-8"):
        self.status_code = status
        self._body = body
        self.raw = raw
        self.headers = headers or {}
        self.url = url
        self.encoding = encoding
        self.closed = False

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body

    def iter_content(self, chunk_size=65536):
        data = self.raw or b""
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

    def close(self):
        self.closed = True


def env(data, code=0, msg="success"):
    return FakeResp({"code": code, "msg": msg, "data": data})


class FakeApi:
    """Routes by path suffix; records calls."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None, allow_redirects=None):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        path = url.split("/open_api/v3/")[1]
        for suffix, resp in self.routes.items():
            if path.endswith(suffix):
                if isinstance(resp, Exception):
                    raise resp
                return resp() if callable(resp) else resp
        return env(None, 404, "no such route")


TOKEN = {"token_id": 7, "username": "puser", "passwd": PROXY_PASS, "host": "gw.example", "port": 2222,
         "proxy_area": "United States - - ", "network": "http", "status": 1, "generate": "dynamic", "proxy_type": "traffic"}


@pytest.fixture
def key():
    return KEY


class FakeTool:
    """Stands in for dify_plugin.Tool in glue tests."""

    def __init__(self, creds):
        class RT:
            credentials = creds

        self.runtime = RT()

    def create_json_message(self, obj):
        return ("json", obj)

    def create_text_message(self, text):
        return ("text", text)
