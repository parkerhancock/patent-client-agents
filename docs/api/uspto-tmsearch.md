# USPTO Trademark Search (TESS)

Read-only access to USPTO's Trademark Electronic Search System (TESS) at `tmsearch.uspto.gov`. Searches the live trademark register over wordmark, owner, goods/services description, design code, and registration metadata. The connector wraps the TESS Elasticsearch backend.

## Auth

USPTO TESS sits behind AWS WAF. The WAF binds a `aws-waf-token` cookie to the User-Agent that solved the challenge.js puzzle. The token lasts ~4 days. Two ways to obtain one:

1. **`pip install 'patent-client-agents[tmsearch]'`** — adds Playwright + curl_cffi. The first request mints a token via headless Chromium and caches it. After that, all requests use curl_cffi with no browser.
2. **Bring your own** — set `PCA_WAF_TOKEN_JSON` to a JSON payload `{"token": "...", "expires": <unix_ts>, "acquired": "..."}` (Secret Manager / Vault style), or point `PCA_WAF_TOKEN_PATH` at an on-disk JSON file with the same shape.

Legacy env vars `LAW_TOOLS_WAF_TOKEN_JSON` and `WAF_TOKEN_PATH` are still honored for one release.

Default cache path: `~/.cache/patent_client_agents/waf_token.json`. The legacy `~/.law-tools/waf_token.json` is also read as a fallback for users on the old default.

If neither a cached token nor Playwright is available, `TmsearchClient.__aenter__` raises `ConfigurationError` with a message pointing at both options.

## Install

```bash
# Default install — works if you BYO a WAF token via env or cache
pip install patent-client-agents

# Power install — adds Playwright + curl_cffi so the client mints tokens itself
pip install 'patent-client-agents[tmsearch]'
playwright install chromium   # one-time browser bootstrap
```

## Quick Start

```python
from patent_client_agents.uspto_tmsearch import TmsearchClient

async with TmsearchClient() as client:
    # Wordmark search
    results = await client.search_wordmark("APPLE", live_only=True)
    for tm in results.results:
        print(tm.serial_number, tm.wordmark, tm.primary_owner)

    # By serial / registration
    detail = await client.get_by_serial("97123456")
    detail = await client.get_by_registration("1234567")

    # Multi-criteria
    apple_in_cls9 = await client.search(
        wordmark="APPLE",
        live_only=True,
        size=100,
    )

    # Auto-paginate
    all_apple = await client.search_all(
        wordmark="APPLE",
        max_results=1000,
        batch_size=500,
    )
```

## Functions

| Method | Description |
|---|---|
| `search(wordmark, owner, goods_services, serial_number, registration_number, live_only, status, size, from_)` | Unified search (≥1 criterion); `status="live"`/`"dead"`/`"all"` |
| `search_wordmark(wordmark, live_only, size, from_)` | Wordmark text search |
| `search_owner(owner_name, live_only, size, from_)` | Owner-name search |
| `search_goods_services(terms, live_only, size, from_)` | Goods/services description search |
| `get_by_serial(serial_number)` | Single-record lookup |
| `get_by_registration(registration_number)` | Single-record lookup |
| `search_all(wordmark, owner, live_only, batch_size, max_results)` | Auto-paginated wordmark or owner search |

## Response Shape

`TrademarkSearchResult` carries the canonical fields:

- `serial_number`, `registration_number`, `wordmark`, `status_live`
- `owner_name` (list), `primary_owner` (property), `attorney`
- `filed_date`, `registration_date`, `abandon_date`, `cancel_date`
- `goods_and_services`, `drawing_code` + description
- `current_basis`, `international_class`, `us_class`
- `design_code` + description, `mark_description`, `disclaimer`
- `assignment_recorded`
- Properties: `is_live`, `is_registered`

`TrademarkSearchResponse` adds `total`, `query_time_ms`, and `count`.

## Token refresh on the deploy server

The production infrastructure runs a separate Cloud Run Job (`patent_mcp_deploy.waf_refresh`) every four hours. It mints a fresh `aws-waf-token` through Playwright and writes a new Secret Manager secret version. A new MCP service instance reads that secret through `PCA_WAF_TOKEN_JSON`; the in-process token-refresh path remains the fallback when an environment-supplied token is rejected mid-request.

The public `mcp.patentclient.com` facade does not advertise `search_trademarks`. The refresh job maintains the credential path for controlled deployments, but it does not change the public-demo visibility rule.

## Stability Notes

- The WAF challenge mechanism is the fragile bit. If AWS changes the challenge.js algorithm or USPTO swaps WAF providers, Playwright would need to follow.
- AWS WAF binds the token to the request's User-Agent and TLS fingerprint. The client sends a canonical Chrome 120 UA and uses curl_cffi's `chrome120` TLS impersonation. Changing either without re-minting will get a 403.
- TESS doesn't publish API docs; the field schema can shift on USPTO upgrades. The model coerces comma-separated strings to lists and handles missing fields gracefully.

## MCP Tool Surface

| Tool | Description |
|---|---|
| `search_trademarks` | Unified search by wordmark / owner / goods+services; supports auto-pagination |
| `get_trademark` | Single-record lookup by serial or registration number |

These tools share PCA's trademarks sub-server with TSDR (`get_trademark_status`, `get_trademark_documents`, `batch_trademark_status`, `get_trademark_last_update`), TMEP (`search_tmep`, `get_tmep_section`), and Trademark Assignments (`search_trademark_assignments`).
