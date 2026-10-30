from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from proxy302_client import service
from proxy302_client.glue import run_json_tool


class GetDynamicProxyTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        p = tool_parameters
        yield from run_json_tool(
            self, lambda c: service.get_dynamic_proxy(c, p.get("country", ""), p.get("protocol", "http"), p.get("include_credentials"))
        )
