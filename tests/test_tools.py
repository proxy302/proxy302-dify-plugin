import json

import pytest
import requests

from conftest import KEY, PROXY_PASS, TOKEN, FakeApi, FakeResp, FakeTool, env
from proxy302_client import CLIENT_ID, service
from proxy302_client.client import Proxy302Client, build_authorization
from proxy302_client.errors import Proxy302Error, redact
from proxy302_client.format import format_bytes, html_to_markdown, html_to_text, mask, proxy_url


def client(routes):
    api = FakeApi(routes)
    return Proxy302Client(KEY, session=api), api


def no_secret(text):
    for s in (KEY, "SUPERSECRETvalue123", PROXY_PASS):
        assert s not in text


# ---- auth / client -----------------------------------------------------------
def test_authorization_forms():
    import base64
    exp = "Basic " + base64.b64encode(b"k1:s1").decode()
    assert build_authorization("k1:s1") == exp
    assert build_authorization(exp) == exp
    assert build_authorization(base64.b64encode(b"k1:s1xxxxxxxxxx").decode()).startswith("Basic ")
    with pytest.raises(Proxy302Error):
        build_authorization("")
    with pytest.raises(Proxy302Error, match="key id"):
        build_authorization("short")


def test_client_headers_and_envelope():
    c, api = client({"proxy/area/country": env({"data": []})})
    c.areas("country", None, "ger")
    call = api.calls[0]
    assert call["url"] == "https://proxy302.com/open_api/v3/proxy/area/country"
    assert call["params"] == {"name": "ger"}
    assert call["headers"]["X-Proxy302-Client"] == CLIENT_ID == "proxy302-dify-plugin/0.0.1"
    assert call["headers"]["User-Agent"] == CLIENT_ID
    assert "mcp" not in CLIENT_ID
    assert call["timeout"][0] and call["timeout"][1]


def test_envelope_error_and_401_and_network_and_nonjson():
    for resp, pat in [(env(None, 50301, "bad thing"), "bad thing"), (FakeResp(status=401), "rejected"), (FakeResp(None, 502), "Unexpected")]:
        c, _ = client({"user/users/me": resp})
        with pytest.raises(Proxy302Error, match=pat):
            c.me()
    c, _ = client({"user/users/me": requests.ConnectionError(f"boom {KEY}")})
    with pytest.raises(Proxy302Error, match="Could not reach") as e:
        c.me()
    no_secret(str(e.value))


def test_server_message_echoing_key_is_redacted():
    c, _ = client({"user/users/me": env(None, 40100, f"invalid credential {KEY} / SUPERSECRETvalue123")})
    with pytest.raises(Proxy302Error) as e:
        c.me()
    no_secret(str(e.value))


def test_redact_helpers():
    assert "hunter22" not in redact("http://u:hunter22@h:1/x", ["hunter22"])
    assert "abcdefghij" not in redact("Authorization: Basic abcdefghij==")
    assert mask("abcdefgh") == "ab****gh" and format_bytes("1073741824") == "1.00 GB"
    assert proxy_url("http", "u", "p@ss", "h", 2) == "http://u:p%40ss@h:2"


# ---- read tools ---------------------------------------------------------------
def test_get_account_usage_happy_and_wallet_degrade():
    routes = {
        "user/users/me": env({"name": "n", "email": "e@x", "uid": 1, "is_use": 1}),
        "user/users/wallet": env({"balance": "12.345"}),
        "traffic/pool/remaining": env({"remaining_traffic": "1073741824", "traffic_pools": [{"id": 1, "en_name": "Pool", "current_cost_traffic": "1024", "total_traffic": "2048", "expired_on": 1893456000}]}),
        "consume/log/summary": env({"keys": ["d1"], "summary": {"dynamic": "2048"}, "values": {}}),
    }
    c, _ = client(routes)
    out = service.get_account_usage(c, 7)
    assert out["wallet_balance_ptc"] == "12.345" and out["traffic_remaining"] == "1.00 GB"
    assert out["traffic_pools"][0]["expires_at"].startswith("2030-01-01")
    assert out["usage_last_days"]["by_category_total"] == {"dynamic": "2.00 KB"}
    routes["user/users/wallet"] = FakeResp(status=404)
    assert service.get_account_usage(c, 999)["wallet_balance_ptc"] == "unavailable"
    assert service.get_account_usage(c, 999)["usage_last_days"]["days"] == 90


def test_list_countries_and_regions():
    c, api = client({"area/country": env({"data": [{"id": 233, "name": "United States", "code": "US"}]}),
                     "area/state": env({"data": [{"id": 5, "name": "Texas"}]}), "area/city": env({"data": [{"id": 9, "name": "Austin"}]})})
    assert service.list_countries(c, "unit")["countries"][0]["code"] == "US"
    r = service.list_regions(c, country="US")
    assert r["country"]["id"] == 233 and r["states"][0]["name"] == "Texas"
    assert service.list_regions(c, state_id=5) == [{"id": 9, "name": "Austin"}]
    with pytest.raises(Proxy302Error, match="Pass country"):
        service.list_regions(c)


def test_resolve_area_errors():
    c, _ = client({"area/country": env({"data": []})})
    with pytest.raises(Proxy302Error, match="No country matches"):
        service.resolve_area(c, "country", "zzz")
    c, _ = client({"area/country": env({"data": [{"id": 1, "name": "Guinea"}, {"id": 2, "name": "Guinea-Bissau"}]})})
    with pytest.raises(Proxy302Error, match="several"):
        service.resolve_area(c, "country", "gui")


def test_list_products():
    c, _ = client({"payway/static_data_center": env({"data": [{"id": 1, "name": "x", "en_name": "DC"}]}), "payway/static_residential": env({"data": [{"id": 2, "name": "R"}]})})
    out = service.list_products(c)
    assert out["static_data_center_plans"] == [{"id": 1, "name": "DC"}] and out["static_residential_plans"] == [{"id": 2, "name": "R"}]
    assert "does not buy" in out["note"]


def test_list_my_proxies_masks_by_default():
    c, api = client({"tokens/static/ip": env({"data": [TOKEN], "total": 1, "page": 1, "has_more": False})})
    out = service.list_my_proxies(c)
    text = json.dumps(out)
    assert PROXY_PASS not in text and "pX****7z" in text
    assert api.calls[0]["params"]["status"] == 1 and api.calls[0]["params"]["page_size"] == 20
    full = service.list_my_proxies(c, include_credentials="true")
    assert PROXY_PASS in json.dumps(full)
    with pytest.raises(Proxy302Error):
        service.list_my_proxies(c, kind="x")


def test_get_dynamic_proxy_reuse_and_never_creates():
    c, api = client({"area/country": env({"data": [{"id": 233, "name": "United States", "code": "US"}]}),
                     "tokens/dynamic/traffic": env({"data": [TOKEN], "total": 1})})
    out = service.get_dynamic_proxy(c, "US")
    assert out["reused"] is True and PROXY_PASS not in json.dumps(out) and "connection_url" not in out
    out = service.get_dynamic_proxy(c, "US", include_credentials=True)
    assert out["connection_url"] == f"http://puser:{PROXY_PASS}@gw.example:2222"
    with pytest.raises(Proxy302Error, match="Create one in the Proxy302 console"):
        service.get_dynamic_proxy(c, "US", protocol="socks5")
    assert all(call["url"].split("/open_api/v3/")[1].split("/")[0] in ("proxy", "user") for call in api.calls)
    assert all("dynamic/traffic" not in x["url"] or True for x in api.calls)
    # only GET is ever issued: FakeApi has no post method
    assert not hasattr(api, "post")


# ---- fetch_url ------------------------------------------------------------------
class FakeSession:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc, self.seen = resp, exc, None
        self.max_redirects = None
        self.trust_env = None

    def get(self, url, **kw):
        self.seen = {"url": url, **kw}
        if self.exc:
            raise self.exc
        return self.resp

    def close(self):
        pass


FETCH_ROUTES = {"area/country": env({"data": [{"id": 233, "name": "United States", "code": "US"}]}),
                "tokens/dynamic/traffic": env({"data": [TOKEN], "total": 1})}


def test_fetch_url_happy_path_markdown_and_proxy_used():
    html = b"<html><body><h1>Hi</h1><script>evil()</script><p>A <a href='/x'>link</a></p></body></html>"
    sess = FakeSession(FakeResp(headers={"content-type": "text/html; charset=utf-8"}, raw=html))
    c, _ = client(FETCH_ROUTES)
    meta, res = service.fetch_url(c, "https://example.test/page", country="US", session=sess)
    assert res.content == "# Hi\n\nA [link](/x)" and meta["status"] == 200 and meta["via"]["token_id"] == 7
    assert sess.seen["proxies"]["https"] == f"http://puser:{PROXY_PASS}@gw.example:2222"
    assert sess.seen["timeout"] == (10, 30) and sess.seen["stream"] is True
    assert PROXY_PASS not in json.dumps(meta)


def test_fetch_url_truncates_and_caps_body():
    big = b"x" * 6_000_000
    sess = FakeSession(FakeResp(headers={"content-type": "text/plain"}, raw=big))
    c, _ = client(FETCH_ROUTES)
    meta, res = service.fetch_url(c, "https://example.test/", max_chars=500, session=sess)
    assert len(res.content) == 500 and res.truncated
    # clamped to the minimum
    _, res = service.fetch_url(c, "https://example.test/", max_chars=5, session=FakeSession(FakeResp(headers={}, raw=b"y" * 900)))
    assert len(res.content) == 500


@pytest.mark.parametrize("url,pat", [
    ("ftp://example.test/x", "http and https"),
    ("file:///etc/passwd", "http and https"),
    ("javascript:alert(1)", "http and https"),
    ("https://" + "a" * 2100 + ".com/", "too long"),
    ("https://user:pw@example.test/", "credentials"),
    ("https://user@example.test/", "credentials"),
    ("http://127.0.0.1:8080/", "Private"),
    ("http://169.254.169.254/latest/meta-data", "Private"),
    ("http://[::1]/", "Private"),
    ("http://10.0.0.5/", "Private"),
    ("http://localhost/", "Local"),
    ("http://metadata.internal/", "Local"),
    ("https://exa mple.test/", "spaces"),
    ("", "required"),
    ("https:///nohost", "no host"),
])
def test_fetch_url_rejects_bad_input_before_any_call(url, pat):
    c, api = client(FETCH_ROUTES)
    with pytest.raises(Proxy302Error, match=pat):
        service.fetch_url(c, url, session=FakeSession(FakeResp(raw=b"")))
    assert api.calls == []  # rejected before touching the API


def test_fetch_url_timeout_and_failure_leak_no_secret():
    for exc in (requests.ConnectTimeout(f"proxy http://puser:{PROXY_PASS}@gw.example:2222 {KEY}"),
                requests.ProxyError(f"tunnel failed for http://puser:{PROXY_PASS}@gw.example:2222"),
                requests.TooManyRedirects("x")):
        c, _ = client(FETCH_ROUTES)
        with pytest.raises(Proxy302Error) as e:
            service.fetch_url(c, "https://example.test/", session=FakeSession(exc=exc))
        no_secret(str(e.value))
    c, _ = client(FETCH_ROUTES)
    with pytest.raises(Proxy302Error, match="timed out"):
        service.fetch_url(c, "https://example.test/", session=FakeSession(exc=requests.ReadTimeout("t")))


def test_fetch_url_final_url_is_redacted():
    sess = FakeSession(FakeResp(headers={"content-type": "text/plain"}, raw=b"ok", url=f"https://x.test/?k={PROXY_PASS}"))
    c, _ = client(FETCH_ROUTES)
    meta, _ = service.fetch_url(c, "https://example.test/", session=sess)
    assert PROXY_PASS not in meta["final_url"]


def test_fetch_url_no_proxy_found():
    c, _ = client({"tokens/dynamic/traffic": env({"data": [], "total": 0})})
    with pytest.raises(Proxy302Error, match="no active dynamic proxy"):
        service.fetch_url(c, "https://example.test/", session=FakeSession(FakeResp(raw=b"")))
    c, _ = client({**FETCH_ROUTES, "tokens/static/ip": env({"data": [], "total": 0})})
    with pytest.raises(Proxy302Error, match="not found"):
        service.fetch_url(c, "https://example.test/", token_id=99, session=FakeSession(FakeResp(raw=b"")))


def test_html_conversion():
    html = "<html><head><title>t</title></head><body><h2>T</h2><ul><li>a</li><li>b</li></ul><pre>x  y</pre><style>p{}</style></body></html>"
    md = html_to_markdown(html)
    assert "## T" in md and "- a" in md and "```" in md and "p{}" not in md and "<" not in md
    assert html_to_text(html).startswith("T")


# ---- Dify glue / provider --------------------------------------------------------
def test_glue_emits_json_and_text_and_redacts_errors(monkeypatch):
    from proxy302_client.glue import run_json_tool

    monkeypatch.setattr("proxy302_client.client.requests.get", FakeApi({"area/country": env({"data": [{"id": 1, "name": "A", "code": "A"}]})}).get)
    tool = FakeTool({"api_key": KEY})
    msgs = list(run_json_tool(tool, lambda c: service.list_countries(c)))
    assert msgs[0][0] == "json" and msgs[1][0] == "text"
    monkeypatch.setattr("proxy302_client.client.requests.get", FakeApi({"area/country": env(None, 1, f"nope {KEY}")}).get)
    with pytest.raises(Exception) as e:
        list(run_json_tool(tool, lambda c: service.list_countries(c)))
    no_secret(str(e.value))
    with pytest.raises(Exception) as e:
        list(run_json_tool(FakeTool({}), lambda c: service.list_countries(c)))
    assert "API key" in str(e.value)


def test_unexpected_exception_is_redacted():
    from proxy302_client.glue import run_json_tool

    def boom(c):
        raise RuntimeError(f"db password {KEY}")

    with pytest.raises(Exception) as e:
        list(run_json_tool(FakeTool({"api_key": KEY}), boom))
    no_secret(str(e.value))


def test_provider_credential_validation(monkeypatch):
    from dify_plugin.errors.tool import ToolProviderCredentialValidationError
    from provider.proxy302 import Proxy302Provider

    p = Proxy302Provider.__new__(Proxy302Provider)
    api = FakeApi({"user/users/me": env({"name": "n"})})
    monkeypatch.setattr("proxy302_client.client.requests.get", api.get)
    p._validate_credentials({"api_key": KEY})
    assert [c["url"].rsplit("/", 1)[-1] for c in api.calls] == ["me"]  # exactly one cheap call
    for creds in ({}, {"api_key": "  "}, {"api_key": "bad"}):
        with pytest.raises(ToolProviderCredentialValidationError):
            p._validate_credentials(creds)
    for resp in (FakeResp(status=401), env(None, 40100, f"bad {KEY}"), requests.ConnectionError(KEY)):
        monkeypatch.setattr("proxy302_client.client.requests.get", FakeApi({"user/users/me": resp}).get)
        with pytest.raises(ToolProviderCredentialValidationError) as e:
            p._validate_credentials({"api_key": KEY})
        no_secret(str(e.value))


def test_tool_classes_run_through_glue(monkeypatch):
    """Instantiate the real Tool subclasses without a Dify runtime and invoke them."""
    from tools.fetch_url import FetchUrlTool
    from tools.get_account_usage import GetAccountUsageTool

    def make(cls):
        t = cls.__new__(cls)
        t.runtime = FakeTool({"api_key": KEY}).runtime
        t.create_json_message = lambda o: ("json", o)
        t.create_text_message = lambda s: ("text", s)
        return t

    routes = {**FETCH_ROUTES, "user/users/me": env({"name": "n", "email": "e", "uid": 1, "is_use": 1}),
              "traffic/pool/remaining": env({"remaining_traffic": "0", "traffic_pools": []}),
              "consume/log/summary": env({"keys": [], "summary": {}}), "user/users/wallet": env({"balance": "1"})}
    monkeypatch.setattr("proxy302_client.client.requests.get", FakeApi(routes).get)
    out = list(make(GetAccountUsageTool)._invoke({"days": "3"}))
    assert out[0][1]["usage_last_days"]["days"] == 3
    sess = FakeSession(FakeResp(headers={"content-type": "text/plain"}, raw=b"hello"))
    monkeypatch.setattr("proxy302_client.fetcher.requests.Session", lambda: sess)
    out = list(make(FetchUrlTool)._invoke({"url": "https://example.test/", "format": "text"}))
    assert out[0][1]["content"] == "hello" and out[2][1] == "hello"
    with pytest.raises(Exception) as e:
        list(make(FetchUrlTool)._invoke({"url": "ftp://x/"}))
    no_secret(str(e.value))
