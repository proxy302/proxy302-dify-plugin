"""Glue between the Dify runtime and the service layer."""

from __future__ import annotations

import json
from collections.abc import Callable, Generator
from typing import Any

from dify_plugin.entities.tool import ToolInvokeMessage

from .client import Proxy302Client, api_key_from_credentials
from .errors import Proxy302Error


def client_from(tool: Any) -> Proxy302Client:
    creds = getattr(tool.runtime, "credentials", None) or {}
    try:
        return Proxy302Client(api_key_from_credentials(creds))
    except Proxy302Error:
        return Proxy302Client(None)  # the first request raises the "no key configured" message


def run_json_tool(tool: Any, fn: Callable[[Proxy302Client], Any]) -> Generator[ToolInvokeMessage, None, None]:
    """Run ``fn`` and emit a JSON message plus the same JSON as text. Errors are raised with safe text only."""
    client = client_from(tool)
    try:
        data = fn(client)
    except Proxy302Error as e:
        raise Exception(client.redact(e)) from None
    except Exception as e:  # never let an unexpected exception text carry a secret
        raise Exception(f"Unexpected error ({type(e).__name__}). {client.redact(e)}") from None
    payload = data if isinstance(data, dict) else {"result": data}
    yield tool.create_json_message(payload)
    yield tool.create_text_message(json.dumps(data, indent=2, ensure_ascii=False, default=str))
