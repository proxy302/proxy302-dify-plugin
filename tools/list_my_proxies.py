from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from proxy302_client import service
from proxy302_client.glue import run_json_tool


class ListMyProxiesTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        p = tool_parameters
        yield from run_json_tool(
            self,
            lambda c: service.list_my_proxies(
                c, p.get("kind", "static"), p.get("billing", "ip"), p.get("page_size", 20), p.get("page", 1),
                p.get("active_only", True), p.get("include_credentials"),
            ),
        )
