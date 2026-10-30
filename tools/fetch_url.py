import json
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from proxy302_client import service
from proxy302_client.errors import Proxy302Error
from proxy302_client.glue import client_from


class FetchUrlTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        p = tool_parameters
        client = client_from(self)
        try:
            meta, result = service.fetch_url(
                client, p.get("url", ""), p.get("country"), p.get("token_id"), p.get("format", "markdown"), p.get("max_chars"),
            )
        except Proxy302Error as e:
            raise Exception(client.redact(e)) from None
        except Exception as e:
            raise Exception(f"Unexpected error ({type(e).__name__}).") from None
        yield self.create_json_message({**meta, "content": result.content})
        yield self.create_text_message(json.dumps(meta, ensure_ascii=False))
        yield self.create_text_message(result.content)
