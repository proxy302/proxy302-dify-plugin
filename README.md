# Proxy302 for Dify

Read-only [Proxy302](https://proxy302.com) tools for Dify workflows, chatflows and agents: check your traffic and usage, browse countries and plans, look up your residential proxies, and fetch a public web page through your own Proxy302 proxy.

- Source repository: https://github.com/proxy302/proxy302-dify-plugin
- Contact: partners@proxy302.com

> **Never spends money.** The plugin cannot buy, renew or top up anything and cannot create a proxy. It only reads your account, with one exception: `fetch_url` sends a page request through a proxy you already own, which uses your existing prepaid proxy traffic.

## Installation

1. In Dify, open **Plugins**, find **Proxy302** in the Marketplace and install it. (Self-hosted installs from a `.difypkg` file need signature verification disabled, or the package must come from the Marketplace.)
2. Open the plugin's **Authorize** dialog and paste your Proxy302 key ID and key secret.

## Credential

Two fields are required: the **key ID** and **key secret** of a Proxy302 API key.

1. Sign in to the [Proxy302 console](https://proxy302.com/) and open **API keys**.
2. Create a key (or open an existing one) and click **Copy as env vars**. This copies two lines: `PROXY302_KEY_ID` and `PROXY302_KEY_SECRET`.
3. In Dify, paste the `PROXY302_KEY_ID` value into **Key ID** and the `PROXY302_KEY_SECRET` value into **Key secret**.

When you save the credential the plugin makes a single read-only request (`GET /open_api/v3/user/users/me`) to check that the key works. The key is stored by Dify as a secret and is only ever sent to `proxy302.com` in an HTTP `Authorization: Basic` header.

## Connection requirements

The Dify plugin runtime must be able to reach `https://proxy302.com` (API) and, for `fetch_url`, the Proxy302 proxy gateway host and port that belong to your proxy (shown in `list_my_proxies`). No inbound connections are needed.

## Tools

| Tool | What it does |
|---|---|
| `get_account_usage` | Account, wallet balance (PTC), remaining prepaid traffic, per-pool balances and daily usage for the last N days (1-90). |
| `list_countries` | Countries you can target, with ids and ISO codes. Optional name filter. |
| `list_regions` | States of a country, or cities of a state (pass `country` or `state_id`). |
| `list_products` | Proxy product lines and the static IP plans (data center and residential) with plan ids. |
| `get_dynamic_proxy` | Looks up one of your **existing** rotating residential proxies for a country and protocol. Passwords are masked unless `include_credentials` is on. It never creates a proxy; if none exists it tells you to create one in the console. |
| `list_my_proxies` | Your dynamic or static proxies, billed by traffic or by IP, paged. Passwords masked by default. |
| `fetch_url` | Requests a public http(s) URL through one of your dynamic proxies (optionally by exit country or proxy id) and returns Markdown, text or raw content. |

## Usage

Each tool is a normal Dify tool node. Examples:

- **Chatflow / agent:** add the Proxy302 tools to an agent and ask "How much proxy traffic do I have left this week?" (`get_account_usage`) or "Fetch https://example.com/pricing from a US exit and summarise it" (`fetch_url` with `country` = `US`).
- **Workflow:** add a *Proxy302 / Fetch a web page through my proxy* node, set `url`, optionally `country`, `format` (`markdown`, `text`, `raw`) and `max_chars`, and use its `text` or `json.content` output downstream.
- **Find what you can target:** `list_countries` with `name` = `ger`, then `list_regions` with `country` = `Germany`.

`fetch_url` is a plain HTTP request without JavaScript rendering.

Output notes: every tool returns the same data as a JSON message and as text. `fetch_url` returns a JSON message (metadata plus `content`) and the content as text.

## `fetch_url` security boundaries

`fetch_url` is an arbitrary-URL fetch capability, so it is deliberately constrained:

- Only `http` and `https`; URLs up to 2048 characters; no whitespace or control characters.
- URLs containing credentials (`user:password@host`) are rejected.
- Literal private, loopback, link-local and other non-public IP addresses, `localhost` and `.local`, `.internal`, `.lan` style names are rejected.
- The request is made only through a Proxy302 proxy that belongs to the API key's account, never directly from the Dify host. If you have no active proxy it fails with guidance.
- Timeouts: 10 s connect, 30 s read, 45 s overall; at most 5 redirects.
- The response is streamed and cut at 5 MB before decoding; the output is truncated to `max_chars` (500 to 200000, default 20000).
- The API key and the proxy password are never put in outputs, errors or logs. Error messages are generic (for example "timed out") and are scrubbed of secrets.
- Responses are returned as data; the plugin does not execute scripts or follow `javascript:` or `file:` links.

## Privacy

See [PRIVACY.md](PRIVACY.md). In short: the plugin has no server of its own and stores nothing; it talks only to the Proxy302 API and, for `fetch_url`, to the target website through your own Proxy302 proxy.

## Development

```bash
uv venv --python 3.12 && uv pip install -r requirements.txt pytest
python -m pytest
dify plugin package .
```

Requests identify themselves with `User-Agent` and `X-Proxy302-Client` set to `proxy302-dify-plugin/<version>`.

## License

MIT. See [LICENSE](LICENSE).
