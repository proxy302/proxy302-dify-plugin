from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from proxy302_client import service
from proxy302_client.glue import run_json_tool


class GetAccountUsageTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        yield from run_json_tool(self, lambda c: service.get_account_usage(c, tool_parameters.get("days", 7)))
