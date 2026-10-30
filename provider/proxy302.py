from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from proxy302_client.client import Proxy302Client
from proxy302_client.errors import Proxy302Error


class Proxy302Provider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        """One cheap read-only call (GET user/users/me). It spends nothing and creates nothing."""
        api_key = str(credentials.get("api_key") or "").strip()
        if not api_key:
            raise ToolProviderCredentialValidationError(
                'A Proxy302 API key is required, in the form "<key id>:<secret>". Create one in the Proxy302 console.'
            )
        client = Proxy302Client(api_key)
        try:
            client.me()
        except Proxy302Error as e:
            raise ToolProviderCredentialValidationError(client.redact(e)) from None
        except Exception as e:
            raise ToolProviderCredentialValidationError(f"Could not verify the API key ({type(e).__name__}).") from None
