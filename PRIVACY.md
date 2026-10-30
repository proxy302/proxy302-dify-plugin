# Privacy Policy: Proxy302 plugin for Dify

_Last updated: 2026-10-31 (plugin version 0.0.1)_

This plugin lets Dify apps call the [Proxy302](https://proxy302.com) API with the user's own Proxy302 API key. The plugin has no backend of its own, runs only inside the user's Dify plugin runtime, and does not collect, store or log user data for the plugin author.

## What data the plugin handles

| Data | Where it comes from | Where it goes | Stored by the plugin? |
|---|---|---|---|
| Proxy302 API key (`key id:secret`) | Entered by the user as a Dify credential | Sent only to `https://proxy302.com` in an `Authorization: Basic` header | No. Stored by Dify as a secret credential. |
| Tool parameters (country, state id, page, days, proxy id, ...) | Workflow, agent or user | Sent to the Proxy302 API as query parameters | No |
| Account data returned by Proxy302 (name, email, wallet balance, traffic usage, proxy list) | Proxy302 API | Returned to the Dify app as tool output. The email address and proxy host, port and username can appear in output. | No |
| Proxy passwords | Proxy302 API | Masked in output by default. Returned in full only if the user turns on `include_credentials`; that output then lives wherever Dify keeps workflow logs. | No |
| `fetch_url`: the requested URL and its response | Workflow, agent or user supplies the URL | The URL is requested from the target website **through the user's own Proxy302 proxy gateway**, so the target website and the Proxy302 gateway can see the request. The page content is returned to the Dify app as tool output. | No |

## Third parties

- **Proxy302** (`proxy302.com`), operated by the Proxy302 service, receives the API key and request parameters. Its own privacy policy and terms apply to the account and the proxy service: https://proxy302.com/privacy/
- **Target websites** contacted by `fetch_url` receive an ordinary HTTP request from a Proxy302 exit IP. Do not put personal data or secrets into the URL.

No analytics, telemetry or advertising services are used. No data is sent to the plugin author or to any third party other than the two above.

## Logging and retention

The plugin does not write its own logs and keeps no files or caches between calls. Requests carry the client identifier `proxy302-dify-plugin/<version>` so that Proxy302 can recognise traffic from this plugin. Dify itself and Proxy302 may log requests under their own policies. Error messages shown by the plugin are scrubbed so that the API key and proxy passwords are not included.

## Sensitive data

The plugin does not intentionally process health, financial-card, biometric, children's or similar sensitive data. Account email and wallet balance are returned to the user's own Dify app only.

## Contact

partners@proxy302.com
