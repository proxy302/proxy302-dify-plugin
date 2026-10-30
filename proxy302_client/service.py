"""Tool logic, independent of the Dify runtime so it can be unit-tested with mocked HTTP."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from .client import Proxy302Client
from .errors import Proxy302Error
from .fetcher import FetchResult, ProxyEndpoint, clamp_chars, fetch_through_proxy
from .format import format_bytes, mask, proxy_url


def _iso(ts: Any) -> str | None:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def as_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        n = int(float(value)) if value not in (None, "") else default
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def resolve_area(client: Proxy302Client, kind: str, text: str, pid: str | None = None) -> dict[str, Any]:
    text = (text or "").strip()
    if text.isdigit():
        return {"id": int(text), "name": text}
    rows = (client.areas(kind, pid, text) or {}).get("data", [])
    q = text.lower()
    exact = [r for r in rows if str(r.get("name", "")).lower() == q or str(r.get("code") or "").lower() == q]
    pick = exact if len(exact) == 1 else rows if len(rows) == 1 else []
    if len(pick) == 1:
        return pick[0]
    if not rows:
        raise Proxy302Error(f'No {kind} matches "{text}". Use list_countries / list_regions to see valid names.')
    names = ", ".join(f"{r.get('name')} (id {r.get('id')})" for r in rows[:10])
    raise Proxy302Error(f'"{text}" matches several {kind}s: {names}. Pass the exact name or id.')


def _endpoint(row: dict[str, Any]) -> ProxyEndpoint | None:
    if not (row.get("username") and row.get("passwd") and row.get("host") and row.get("port")):
        return None
    return ProxyEndpoint(str(row["host"]), int(row["port"]), str(row["username"]), str(row["passwd"]))


def describe_token(row: dict[str, Any], include_credentials: bool) -> dict[str, Any]:
    ep = _endpoint(row)
    out: dict[str, Any] = {
        "token_id": row.get("token_id", row.get("id")),
        "kind": f"{row.get('generate') or ''}/{row.get('proxy_type') or ''}",
        "area": row.get("proxy_area") or "any",
        "protocol": row.get("network") or "http",
        "status": row.get("status"),
        "connection_state": row.get("connection_state"),
        "expires_at": _iso(row.get("expired_on")) if row.get("expired_on") else None,
        "host": row.get("host"),
        "port": row.get("port"),
        "username": row.get("username"),
        "password": row.get("passwd") if include_credentials else mask(row.get("passwd")),
    }
    if row.get("traffic_usage") is not None:
        out["traffic_used"] = format_bytes(row["traffic_usage"])
    if include_credentials and ep:
        out["connection_url"] = proxy_url(row.get("network") or "http", ep.username, ep.password, ep.host, ep.port)
    return out


def _country_of(row: dict[str, Any]) -> str:
    return str(row.get("proxy_area") or "").split(" - ")[0].strip().lower()


def _usable(row: dict[str, Any]) -> bool:
    return row.get("status") in (1, 5)


def get_account_usage(client: Proxy302Client, days: Any = 7) -> dict[str, Any]:
    days = as_int(days, 7, 1, 90)
    end = int(time.time())
    me = client.me() or {}
    pool = client.traffic_pool() or {}
    usage = client.consume_summary(end - days * 86400, end) or {}
    try:
        wallet = client.wallet()
    except Proxy302Error:
        wallet = None  # older servers lack the endpoint: degrade instead of failing
    return {
        "account": {"name": me.get("name"), "email": me.get("email"), "uid": me.get("uid"), "active": me.get("is_use") == 1},
        "wallet_balance_ptc": wallet.get("balance") if wallet else "unavailable",
        "traffic_remaining": format_bytes(pool.get("remaining_traffic")),
        "traffic_pools": [
            {
                "id": p.get("id"),
                "name": p.get("en_name") or p.get("name"),
                "used": format_bytes(p.get("current_cost_traffic")),
                "total": format_bytes(p.get("total_traffic")),
                "expires_at": _iso(p.get("expired_on")) if p.get("expired_on") else "never",
            }
            for p in pool.get("traffic_pools", [])
        ],
        "usage_last_days": {
            "days": days,
            "by_category_total": {k: format_bytes(v) for k, v in (usage.get("summary") or {}).items()},
            "day_keys": usage.get("keys", []),
        },
    }


def list_countries(client: Proxy302Client, name: str | None = None) -> dict[str, Any]:
    rows = (client.areas("country", None, (name or "").strip()[:100] or None) or {}).get("data", [])
    return {"count": len(rows), "countries": [{"id": r.get("id"), "name": r.get("name"), "code": r.get("code")} for r in rows]}


def list_regions(client: Proxy302Client, country: str | None = None, state_id: Any = None, name: str | None = None) -> Any:
    name = (name or "").strip()[:100] or None
    if state_id not in (None, "", 0, "0"):
        sid = as_int(state_id, 0, 1, 10**12)
        return (client.areas("city", str(sid), name) or {}).get("data", [])
    if not country or not country.strip():
        raise Proxy302Error("Pass country (to list states) or state_id (to list cities).")
    c = resolve_area(client, "country", country)
    return {"country": c, "states": (client.areas("state", str(c["id"]), name) or {}).get("data", [])}


def list_products(client: Proxy302Client) -> dict[str, Any]:
    dc = (client.payways("static_data_center") or {}).get("data", [])
    res = (client.payways("static_residential") or {}).get("data", [])
    return {
        "dynamic_residential": {
            "billing": "per GB of traffic",
            "lines": {"premium": "higher-quality line", "budget": "lower-cost line"},
            "targeting": "country (state/city on supported lines)",
            "tool": "get_dynamic_proxy",
        },
        "static_data_center_plans": [{"id": p.get("id"), "name": p.get("en_name") or p.get("name")} for p in dc],
        "static_residential_plans": [{"id": p.get("id"), "name": p.get("en_name") or p.get("name")} for p in res],
        "note": "This plugin does not buy, renew or top up. Do that in the Proxy302 console.",
    }


def get_dynamic_proxy(client: Proxy302Client, country: str, protocol: str = "http", include_credentials: Any = False) -> dict[str, Any]:
    """Reuse-only: never creates a credential (the MCP's create_if_missing path is deliberately omitted)."""
    protocol = (protocol or "http").lower()
    if protocol not in ("http", "socks5"):
        raise Proxy302Error("protocol must be http or socks5.")
    if not country or not str(country).strip():
        raise Proxy302Error("country is required.")
    c = resolve_area(client, "country", str(country))
    rows = (client.tokens("dynamic", "traffic", page_size=200) or {}).get("data", [])
    want = str(c.get("name", "")).lower()
    hit = next((r for r in rows if _usable(r) and _country_of(r) == want and (r.get("network") or "http") == protocol and _endpoint(r)), None)
    if not hit:
        raise Proxy302Error(
            f"No existing {protocol} dynamic proxy for {c.get('name')} on this account. "
            "Create one in the Proxy302 console (creating is free; traffic is billed per GB on use), then call this tool again."
        )
    return {"reused": True, **describe_token(hit, as_bool(include_credentials))}


def list_my_proxies(
    client: Proxy302Client, kind: str = "static", billing: str = "ip", page_size: Any = 20, page: Any = 1,
    active_only: Any = True, include_credentials: Any = False,
) -> dict[str, Any]:
    kind, billing = (kind or "static").lower(), (billing or "ip").lower()
    if kind not in ("dynamic", "static"):
        raise Proxy302Error("kind must be dynamic or static.")
    if billing not in ("ip", "traffic"):
        raise Proxy302Error("billing must be ip or traffic.")
    q: dict[str, Any] = {"page": as_int(page, 1, 1, 10**6), "page_size": as_int(page_size, 20, 1, 100)}
    if as_bool(active_only, True):
        q["status"] = 1
    r = client.tokens(kind, billing, **q) or {}
    creds = as_bool(include_credentials)
    return {"total": r.get("total"), "page": r.get("page"), "has_more": r.get("has_more"),
            "proxies": [describe_token(row, creds) for row in r.get("data", [])]}


def pick_proxy(client: Proxy302Client, country: str | None, token_id: Any) -> dict[str, Any]:
    rows = [r for r in (client.tokens("dynamic", "traffic", page_size=200) or {}).get("data", [])
            if _usable(r) and (r.get("network") or "http") != "socks5" and _endpoint(r)]
    if token_id not in (None, ""):
        row = next((r for r in rows if str(r.get("token_id", r.get("id"))) == str(token_id)), None)
        if not row:
            statics = [r for r in (client.tokens("static", "ip", page_size=200) or {}).get("data", []) if _usable(r) and _endpoint(r)]
            row = next((r for r in statics if str(r.get("token_id", r.get("id"))) == str(token_id)), None)
        if not row:
            raise Proxy302Error(f"Proxy {token_id} not found, inactive or not an HTTP proxy.")
        return row
    if country and country.strip():
        c = resolve_area(client, "country", country)
        row = next((r for r in rows if _country_of(r) == str(c.get("name", "")).lower()), None)
        if not row:
            raise Proxy302Error(f"You have no active HTTP dynamic proxy for {c.get('name')}. Create one in the Proxy302 console first.")
        return row
    if not rows:
        raise Proxy302Error("You have no active dynamic proxy yet. Create one in the Proxy302 console first.")
    return rows[0]


def fetch_url(
    client: Proxy302Client, url: str, country: str | None = None, token_id: Any = None, fmt: str = "markdown",
    max_chars: Any = None, session: Any = None,
) -> tuple[dict[str, Any], FetchResult]:
    from .fetcher import validate_url

    validate_url(url)  # reject bad input before any API call
    row = pick_proxy(client, country, token_id)
    ep = _endpoint(row)
    assert ep is not None
    result = fetch_through_proxy(url, ep, fmt or "markdown", clamp_chars(max_chars), session=session, extra_secrets=tuple(client.secrets))
    meta = {
        "via": {"token_id": row.get("token_id", row.get("id")), "area": row.get("proxy_area") or "any"},
        "status": result.status, "final_url": result.final_url, "content_type": result.content_type, "truncated": result.truncated,
    }
    return meta, result
