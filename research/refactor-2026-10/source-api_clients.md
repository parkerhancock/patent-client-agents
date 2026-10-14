# Live API client connectors: refactoring primitives

Read-only analysis of `src/patent_client_agents/` (patent-client-agents) against
`tools/mcp-data-core/src/mcp_data_core/` (BaseAsyncClient, oauth2, resilience,
exceptions, cache). No repo files were edited. Paths below are relative to
`src/patent_client_agents/` unless noted.

Slice analysed (27 packages, 23,824 lines of Python): uspto_odp, uspto_applications,
uspto_assignments, uspto_petitions, uspto_bulkdata, uspto_office_actions, epo_ops,
cpc, jpo, kipo_kipris, tipo_opdata, inpi_pi, ipi_swissreg, oepm_spain,
iponz_new_zealand, thai_dip, ip_australia_common/patents/trademarks/designs/bulk,
euipo_designs, euipo_trademarks, canlii, ilpo_tm, inpi_br_bulk, dpma_register.

## Summary

Every client in the slice subclasses `BaseAsyncClient`; none build a raw
`httpx.AsyncClient`. But eight of them subclass it only for construction and
`close()`, then call `self._client.get/post/request` directly with their own
status-to-exception mapping (and, for five of them, no retry at all). The
biggest wins are (a) one-shot `api.py` wrappers that are pure boilerplate,
(b) closing the gaps in `BaseAsyncClient` that force those bypasses, (c) shared
auth/rate-limit state that survives the "new client per call" pattern, and
(d) four near-duplicate families (CKAN trio, IP Australia trio, EUIPO pair,
ODP PTAB/petitions resources).

Estimated total reduction: about 3,900 lines (16% of the slice), about 4,350
if the `UsptoOdpClient` facade is also converted. Ranked table:

| # | Primitive | Lands in | Est. lines removed |
|---|-----------|----------|-------------------:|
| 10 | `one_shot()` typed wrapper factory (+ drop deprecated `client=`) | mcp-data-core or `patent_client_agents/_api.py` | ~1,400 |
| 11 | ODP declarative resource spec (search/get/by-number/download) | `uspto_odp/clients/base.py` | ~550 (+~450 facade, optional) |
| 6 | `ApiModel` base + `LenientDate` / `EmptyStrNone` / `CoerceList` annotated types | mcp-data-core `models.py` | ~360 |
| 7 | `CkanCatalogClient` + shared CKAN models | `patent_client_agents/_ckan.py` | ~270 |
| 8 | `IpAustraliaSearchClient` base | `ip_australia_common` | ~250 |
| 13 | Package `__init__` re-export from `api.__all__` | each package | ~250 |
| 3 | `TokenAuth` (pluggable grant, shared token cache) | mcp-data-core `oauth2.py` | ~170 |
| 1 | `BaseAsyncClient` transport hooks (abs URL, auth retry, extensions, cache policy, error label) | mcp-data-core `base_client.py` | ~165 |
| 5 | Lenient XML helpers module | mcp-data-core `xml.py` | ~130 |
| 2 | `env_credential()` / `resolve_environment()` / `require_https()` | mcp-data-core `config.py` | ~110 |
| 9 | `EuipoClientBase` + shared EUIPO models | `euipo_common` | ~95 |
| 4 | Process-wide `SlidingWindowLimiter` registry | mcp-data-core `resilience.py` | ~75 |
| 12 | `iter_offset_pages()` helper | mcp-data-core | ~20 |

Numbers are arithmetic from current file/line counts (method shown in each
section); treat them as plus/minus 25%.

### Bugs and behavioural gaps found during the survey (worth fixing regardless)

1. **CKAN `download_resource` builds a broken URL.** `ip_australia_bulk/client.py:84-95`,
   `ilpo_tm/client.py:79-91`, `inpi_br_bulk/client.py:91-104` pass an absolute
   resource URL to `self._request`, and `BaseAsyncClient._build_url` blindly
   prefixes `base_url`. Verified:
   `IpAustraliaBulkClient().download_resource("https://data.gov.au/data/x/iprapid.zip")`
   requests `https://data.gov.auhttps//data.gov.au/data/x/iprapid.zip`. The
   tests (`tests/ip_australia_bulk/test_client.py:104-118` and the ilpo/inpi_br
   twins) only assert `str(url).endswith("/iprapid.zip")`, so they pass. Three
   other clients already override `_build_url` for exactly this
   (`uspto_odp/clients/base.py:222`, `epo_ops/client.py:242`, plus out-of-slice
   `prv_se/client.py:158`, `prh_fi/client.py:363`). Fix belongs in
   `BaseAsyncClient._build_url` (primitive 1).
2. **Rate limiters and token caches are per instance, but callers create one
   instance per call.** JPO's `RateLimiter` (`jpo/client.py:176`) and INPI's
   `_SlidingWindowThrottle` (`inpi_pi/client.py:163`) enforce 10 req/min only
   within one client. Every `api.py` one-shot function and every MCP tool
   (`mcp/tools/jpo.py` has 14 `async with JpoClient()` sites, `mcp/tools/inpi_pi.py` 4)
   constructs a fresh client, so the limit is never shared. Same for tokens:
   JPO `TokenManager`, Swissreg `_fetch_token`, INPI login (XSRF bootstrap +
   login = 2 extra requests per call, which themselves count against INPI's
   10/min), and the `OAuth2ClientCredentialsAuth` instances built by EUIPO and
   IP Australia all mint a new token per call. EPO alone fixed this with a
   module global (`epo_ops/client.py:676 _get_shared_auth`). Primitives 3 and 4.
3. **Five connectors have no retry and no file logging on errors.** iponz
   (`iponz_new_zealand/client.py:344`), swissreg (`ipi_swissreg/client.py:416`),
   oepm (`oepm_spain/client.py:307`), thai_dip (`thai_dip/client.py:249`),
   dpma_register (`dpma_register/client.py:217`) call `self._client` once and
   map status codes by hand; transient 5xx and transport errors surface
   immediately and never reach `logger.error` in `_raise_for_status`.
4. **`UsptoOdpClient` facade opens six cached httpx clients per instance.**
   `uspto_odp/client.py:90-125` constructs Applications/BulkData/Petitions/
   PtabTrials/PtabAppeals/PtabInterferences clients, each of which runs
   `build_cached_http_client` (own connection pool + own hishel SQLite handle
   on the same `uspto_odp` cache DB). `mcp/tools/uspto.py` opens a facade in
   21 places, i.e. six pools per tool call. Fix: build one transport and pass
   it as `client=` to the sub-clients (the facade already supports `client=`
   for tests).
5. Minor: `epo_ops/api.py` and `cpc/api.py` deprecation text says
   "Use 'async with EpoOpsClient() as client:'", but `EpoOpsClient.__init__`
   requires `api_key`/`api_secret` (no env fallback; that lives in
   `client_from_env`).

---

## 1. BaseAsyncClient transport hooks

**Owns:** URL building, retry, status-to-exception mapping and logging for
every request, including connectors that need per-request auth headers,
throttling, cookies, or non-default hishel policy.

**Gaps that force bypasses today**

| Gap in `BaseAsyncClient` | Who works around it | Where |
|---|---|---|
| `_build_url` does not pass absolute URLs through | uspto_odp, epo_ops override; CKAN trio broken | `uspto_odp/clients/base.py:222-226`, `epo_ops/client.py:242-246` |
| `__init__` cannot forward `base_url=`/`policy=` to `build_cached_http_client` | epo_ops skips `super().__init__` and sets `_owns_client`, `_max_retries`, `_timeout`, `_client`, `_cache_manager` by hand | `epo_ops/client.py:209-240` |
| `_request` has no `extensions=` (force_cache) | epo_ops `download_pdf` calls `self._client.request` | `epo_ops/client.py:648-656` |
| No pre-request hook (throttle, bearer injection, cookies) or "on 401 refresh once then retry" | jpo, inpi_pi override `_request` with an incompatible signature (`# ty: ignore[invalid-method-override]`) and reimplement retry loop | `jpo/client.py:294-370`, `inpi_pi/client.py:329-385` |
| No per-client retry tuning (they use `max_attempts=3, max_wait=10`) | jpo, kipo, inpi run their own `default_retryer` loop | `jpo/client.py:323`, `kipo_kipris/client.py:172`, `inpi_pi/client.py:354` |
| Error messages are generic; connectors want "IPONZ ..." labels | iponz, swissreg, oepm, thai, dpma, kipo hand-map 401/403/404/429/!ok | lines listed in bug 3 above, plus `kipo_kipris/client.py:155-187` |
| Retry-After parsing is private to `_raise_for_status` | iponz and swissreg each define a `_rate_limit()` staticmethod | `iponz_new_zealand/client.py:331-342`, `ipi_swissreg/client.py:403-414` |

**Proposed shape (backward compatible; law-tools has 21 subclasses of
`BaseAsyncClient`, so defaults must not change):**

```python
class BaseAsyncClient:
    ERROR_LABEL: ClassVar[str] = ""            # prefixes typed-error messages
    RETRY: ClassVar[dict] = {}                 # e.g. {"max_attempts": 3, "max_wait": 10}
    HTTP_CLIENT_KWARGS: ClassVar[dict] = {}    # e.g. {"policy": hishel.SpecificationPolicy()}

    def _build_url(self, path): return path if path.startswith(("http://", "https://")) else ...
    async def _prepare(self, request_kwargs) -> None: ...   # hook: throttle, headers, cookies
    async def _on_auth_failure(self) -> bool: return False  # hook: invalidate token, return True to retry once
    async def _request(..., extensions=None, cookies=None)  # forward to httpx
    async def _request_bytes / _request_xml(parser)          # thin helpers over _request
```

**What stays source-specific:** JPO's body-level status codes (`_check_result`,
`jpo/client.py:376+`), EPO's 403 quota decoding (`_build_forbidden_error`, already
cleanly layered on `_raise_for_status`), KIPRIS `resultCode` envelope errors,
CanLII `TOO_LONG`, Thai DIP list-vs-dict body check, Swissreg/DPMA in-XML error nodes.

**Line estimate:** removable hand-rolled transport per connector: iponz 22,
swissreg 35, oepm 17, thai 12, dpma 9, kipo 18, inpi 30, jpo 45, epo 18 = 206;
minus ~40 added to the base = **~165 net**.

**Risks / divergences**
- Tests assert specific messages: `raises_match` counts are iponz 8, oepm 7,
  swissreg 6, thai 6, dpma 4, kipo 11, inpi 6, jpo 10. `ERROR_LABEL` must
  preserve those strings or tests need updating.
- Swissreg, iponz, oepm set `use_cache=False` deliberately (oepm puts
  credentials in the SOAP body; swissreg POSTs XML). Keep it.
- Adding retry to POST endpoints (swissreg, oepm SOAP, thai) assumes idempotent
  lookups; all three are read-only searches, but say so explicitly.
- `_raise_for_status` maps 401/403 to `AuthenticationError`; EPO maps 403 to
  `OpsForbiddenError(RateLimitError)`. Keep EPO's override.
- `RateLimitError` is retried by `is_retryable_error`; JPO maps body status
  303/DAILY_LIMIT to `RateLimitError` after the transport returns, so those are
  not retried today. Moving them into the transport would change behaviour.

**Test coverage:** mcp-data-core has `test_resilience.py`, `test_oauth2.py`,
`test_auth.py` but no `test_base_client.py` (base client is exercised only via
consumers; `tests/test_core.py` in patent-client-agents). Consumers: MockTransport
suites for iponz/swissreg/oepm/thai/dpma/kipo/inpi; VCR cassettes for jpo (33)
and uspto_odp (24). EPO request path has no cassettes (tests patch the client).
Add a dedicated `test_base_client.py` in mcp-data-core first.

## 2. Credential and environment resolution

**Owns:** "arg or env var, else `ConfigurationError` with signup hint",
production/sandbox host selection, HTTPS enforcement for BYOK secrets.

**Today (all hand-written, 17 sites):** `uspto_odp/clients/base.py:208`,
`epo_ops/client.py:683-692` (with legacy env aliases), `jpo/client.py:256-264`,
`kipo_kipris/client.py:120-143` (key + base URL + HTTPS), `tipo_opdata/client.py:150-155`,
`inpi_pi/client.py:248-257`, `ipi_swissreg/client.py:332-345` (+TOTP + HTTPS),
`oepm_spain/client.py:289-298`, `iponz_new_zealand/client.py:297-319` (key + env + HTTPS + optional token),
`thai_dip/client.py:225-233`, `dpma_register/client.py:195-204`,
`ip_australia_common/__init__.py:41-89`, `euipo_trademarks/client.py:73-107`,
`euipo_designs/client.py:63-97`, `canlii/client.py:54-58`. HTTPS checks are
duplicated in six clients, always guarded by `client is None`.

**Proposed:**
```python
key = env_credential(api_key, "KIPO_KIPRIS_API_KEY", aliases=(), signup=_SIGNUP_URL, label="KIPRIS Plus")
env = resolve_environment(environment, "EUIPO_ENV")            # "production" | "sandbox"
base = pick(env, prod=_PROD_BASE_URL, sandbox=_SANDBOX_BASE_URL, override=base_url)
require_https(base, label="KIPRIS Plus", skip=client is not None)
```
A declarative `CREDENTIALS: ClassVar` on the client could also feed a single
"which connectors are configured" status function for the MCP server.

**Line estimate:** ~208 current lines across the 17 sites shrink to ~45;
primitive ~50: **~110 net**.

**Stays specific:** EPO's legacy `EPO_API_KEY` alias, Swissreg TOTP, IPONZ
optional bearer, EUIPO's `X-IBM-Client-Id` header derived from the client id.

**Risks:** error message wording is asserted in constructor tests (e.g.
`tests/euipo_trademarks/test_client.py:49-70`, kipo, tipo). KIPRIS has two
required env vars (key and base URL); keep both errors.

**Coverage:** good; nearly every connector has constructor tests with
`monkeypatch.setenv/delenv`.

## 3. `TokenAuth`: pluggable grant + shared token cache

**Owns:** acquiring, caching, expiring, and refreshing bearer tokens as an
`httpx.Auth`, with an asyncio lock, a configurable "token rejected" predicate,
and a process-wide cache keyed by `(token_url, client_id/username)` so short-lived
client instances reuse tokens.

**Today, five separate implementations:**
| Implementation | Grant | Lines | Notes |
|---|---|---|---|
| `mcp_data_core.oauth2.OAuth2ClientCredentialsAuth` | client_credentials (Basic or body) | 171 | used by IP Australia (`ip_australia_common/__init__.py:84`), EUIPO (`euipo_trademarks/client.py:101`, `euipo_designs/client.py:91`); per-instance cache; sync `auth_flow` with no lock |
| `epo_ops/client.py:114-200 OpsAuth` | client_credentials, Basic header without "Basic " prefix, `issued_at` ms + `expires_in` | ~90 | async lock, 400 `invalid_access_token` also counts as rejection, 429/5xx on token -> `RetryableAuthenticationError`; module-global sharing at :676 |
| `jpo/client.py:88-173 TokenManager` | password grant (Keycloak) | ~85 | not an `httpx.Auth`; called from `_raw_request`; 60 s buffer; invalidated on 401/403 |
| `ipi_swissreg/client.py:357-401` + retry in `_post_xml` | password grant + refresh_token, TOTP | ~60 | `time.monotonic`, 30 s buffer, inline 401 retry |
| `inpi_pi/session.py` (283) + `client.py:281-327` | XSRF cookie bootstrap -> login -> refresh -> relogin | ~330 | cookies + `X-XSRF-TOKEN` header; not OAuth |

**Proposed:** generalise `OAuth2ClientCredentialsAuth` into
`TokenAuth(grant: TokenGrant, *, rejected=lambda r: r.status_code == 401,
cache_key=..., shared=True)` with grants `ClientCredentials(basic|body|raw_basic)`,
`PasswordGrant(username, password, extra={"totp": ...}, use_refresh=True)`, and a
`parse_expiry` hook (EPO's `issued_at`). Implement both `auth_flow` and
`async_auth_flow` with a lock. INPI keeps `session.py` but plugs in via
primitive 1's `_prepare`/`_on_auth_failure` hooks rather than its own `_request`.

**Line estimate:** EPO ~70, JPO ~70, Swissreg ~50, INPI client-side ~40
(session.py stays) = 230 removed; ~60 added to the primitive: **~170 net**.
Bigger value is behavioural: one token per process instead of one per call
for JPO, Swissreg, EUIPO, IP Australia (and INPI if its session is cached the
same way).

**Risks:** process-wide token caches must be keyed by credentials (EPO already
compares key/secret) and must not leak across tenants in the hosted demo
(`mcp.patentclient.com`), where BYOK connectors are disabled per memory notes;
confirm before sharing. EPO's raw Basic header quirk and 400-as-401 must be
preserved. JPO's token endpoint is on the same host and is cached through
hishel; tokens carry `no-store`, keep that assumption documented.

**Coverage:** `mcp-data-core/tests/test_oauth2.py`; EPO auth tests in
`tests/epo_ops/test_client.py`; JPO VCR cassettes include token calls (conftest
scrubs `access_token`); Swissreg/INPI MockTransport token tests. EUIPO and
IP Australia have no request-path tests (constructor only) so the shared cache
change there is unprotected.

## 4. Process-wide sliding-window rate limiter

**Owns:** `acquire()` against a named bucket (e.g. `"jpo"`, `"inpi"`) shared
across client instances in the process, with injectable clock.

**Today:** `jpo/client.py:176-212 RateLimiter` (~37 lines, `time.time`) and
`inpi_pi/client.py:163-202 _SlidingWindowThrottle` (~40 lines, injectable
`time.monotonic` clock). Same algorithm. Both per-instance (bug 2).

**Proposed:** `SlidingWindowLimiter.for_key("jpo", max_requests=10, window=60)`
in `mcp_data_core.resilience`, plugged in via the `_prepare` hook.

**Line estimate:** ~77 removed, ~6 call-site lines: **~75 net** (minus the
shared implementation if it lives in mcp-data-core).

**Risks:** sharing the bucket changes latency for concurrent MCP calls (they
will now actually wait). Multi-worker Cloud Run deployments still won't share
state; document as per-process.

**Coverage:** `tests/inpi_pi` has clock-injected throttle tests; JPO has a
`TestRateLimiting` cassette. Keep the injectable clock.

## 5. Lenient XML helpers

**Owns:** namespace-stripping, normalised-key leaf indexing, alias lookup,
element-to-dict for `raw` payloads, and "parse or raise ApiError(label)".

**Today (copy-pasted, byte-identical bodies):**
| Helper | swissreg | iponz | dpma | oepm |
|---|---|---|---|---|
| `_local` | 61 | 45 | 34 | 55 |
| `_key` | 65 | 49 | 38 | – |
| `_element_to_value` | 69 | 53 | 42 | 59 |
| `_leaves` | 87 | 75 | 60 | – |
| `_first` | 98 | 87 | 70 | – |
| `_many` | 106 | 94 | – | – |
| `_raw` | 113 | 71 | inline | – |
| `_parse_xml` | 259 | 131 | 100 | `_parse_response` 153 |

(line numbers in each `client.py`). symilar reports 44 lines swissreg+iponz,
21 dpma+swissreg. Related but semantically different: INPI
`_strip_namespace`/`_xml_to_dict` (`inpi_pi/client.py:428-460`, empty leaf ->
`None`, no `_attributes`) and KIPRIS `_element_to_dict` (`kipo_kipris/client.py:548`,
flat items only).

**Proposed:** `mcp_data_core.xml` (stdlib ElementTree; repo guidance prefers
lxml for new HTML parsing, but these are XML API payloads already on ET) with
`local_name`, `norm_key`, `element_to_value(empty=""|None, attributes=True)`,
`Leaves` (with `.first(*aliases)` / `.many(*aliases)`), `parse_xml(bytes, label, error_check=None)`.

**Line estimate:** ~175 duplicated helper lines + ~24 in `_parse_xml` variants;
shared module ~70: **~130 net**.

**Stays specific:** record extractors (`_patent`, `_trademark`, `_spc`, ...),
error-node detection (`dpma_register/client.py:89`, `ipi_swissreg/client.py:303`,
IPONZ `TransactionError`), SOAP envelope building in oepm.

**Risks:** the INPI/KIPRIS variants differ on empty-leaf semantics; do not fold
them without a flag. These four connectors are fixture-only (no live account),
so behaviour drift would not be caught by real data.

**Coverage:** MockTransport + schema-derived fixtures for all four
(`tests/ipi_swissreg` 565 lines, `tests/iponz_new_zealand` 499, `tests/dpma_register` 447,
`tests/oepm_spain` 375).

## 6. Model conventions: `ApiModel` + annotated coercion types

**Owns:** default `model_config`, camelCase aliasing, and reusable before-validators.

**Today**
- **Lenient date parsers (8 copies):** `ipi_swissreg/models.py:11 parse_ipi_date`,
  `iponz_new_zealand/models.py:11 parse_iponz_date` (identical to ipi),
  `oepm_spain/models.py:11`, `dpma_register/models.py:16`, `thai_dip/models.py:11`,
  `tipo_opdata/models.py:~40`, `kipo_kipris/models.py:~95`, `inpi_pi/models.py:~100`
  (kipo and inpi identical, including the `"00000000"` sentinel). ~156 lines.
  They differ only in accepted formats (`%Y-%m-%d`, `%Y%m%d`, `%d/%m/%Y`,
  `%d-%m-%Y`, `%Y/%m/%d`) and sentinels (`"00000000"`, `"0/0/0"`).
- **Validator boilerplate:** 39 `@field_validator(..., mode="before")` methods
  whose body is one call to the above or `_empty_str_to_none`/`_coerce_to_list`
  (oepm 4, dpma 2, thai 5, tipo 8, kipo 6, inpi 6, swissreg 4, iponz 4). ~156 lines.
  `_empty_str_to_none` duplicated in kipo and inpi (and copyright, out of slice).
- **Aliases:** 410 explicit `Field(alias="camelCase")` whose alias equals
  `to_camel(field_name)` (jpo 146, office_actions 68, kipo 37, euipo 52,
  canlii 24, assignments 18, ip_australia 40, ...). tipo_opdata's 173 aliases and
  inpi's 32 are not camel-derivable. symilar: inpi+kipo models 24 lines.
- `model_config` declared 120+ times; common variants are
  `ConfigDict(populate_by_name=True, extra="allow")` (IP Australia `_BASE_CONFIG`,
  EUIPO, CanLII) and `extra="ignore"` (KIPRIS).

**Proposed** (mcp-data-core `models.py`):
```python
LenientDate = Annotated[date | None, BeforeValidator(lenient_date(formats=(...), sentinels=(...)))]
EmptyStrNone = Annotated[str | None, BeforeValidator(empty_to_none)]
CoerceList = Annotated[list[T], BeforeValidator(as_list)]
class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow", alias_generator=to_camel)
```

**Line estimate:** date parsers ~156 -> ~10 per-package format tuples; validators
~156 -> 0 (type annotations replace them); camel aliases: only multi-line
`Field(...)` calls shrink (~107 lines; single-line ones just get shorter).
Primitive ~60. **~360 net.**

**Risks:** `alias_generator` changes `model_dump(by_alias=True)` output for any
field whose current alias is not camel (assignments 3, office_actions 4, jpo 5
exceptions) so those keep explicit aliases. `extra="allow"` vs `"ignore"` is a
deliberate per-source choice (KIPRIS comments call `ignore` critical), so the
base must not force it. Date formats are order-sensitive (`%d/%m/%Y` vs
`%m/%d/%Y`); keep per-source format tuples.

**Coverage:** model tests exist for tipo (`tests/tipo_opdata`, 1,538 lines),
kipo (1,719), inpi (2,118), euipo (`test_models.py`), jpo (3,343, VCR), office
actions (720). The four XML BYOK connectors have date-parsing tests in their
fixture suites.

## 7. `CkanCatalogClient` (ip_australia_bulk, ilpo_tm, inpi_br_bulk)

**Owns:** `package_show` fetch, `success=False` -> `ApiError`, `result` unwrap,
resource download, and the `BulkDataset`/`BulkResource` models.

**Today:** three near-identical clients: `ip_australia_bulk/client.py` (98),
`ilpo_tm/client.py` (94), `inpi_br_bulk/client.py` (107), differing only in
host, package path prefix (`/data/api/3/...` on data.gov.au), default dataset id,
User-Agent, error wording. Models: `ip_australia_bulk/models.py` (63),
`inpi_br_bulk/models.py` (69), `ilpo_tm/models.py` (59); symilar 23 and 9 lines.
MCP tool layers also duplicate (`mcp/tools/ilpo.py` vs `inpi_br_bulk.py`,
`ip_australia_bulk.py`; out of this slice).

**Proposed:**
```python
class IpAustraliaBulkClient(CkanCatalogClient):
    DEFAULT_BASE_URL = "https://data.gov.au"
    PACKAGE_PATH = "/data/api/3/action/package_show"
    DEFAULT_DATASET_ID = "iprapid"
    CACHE_NAME = "ip_australia_bulk"
```

**Line estimate:** clients 299 -> 3 x ~25 + base ~50 = 125 (save ~175); models
191 -> shared ~50 + 3 x ~15 docstring subclasses = 95 (save ~95). **~270.**

**Risks:** `ilpo_tm` dataset model has extra fields; keep it a subclass. Fixes
bug 1 if the base downloads through an absolute-URL-aware `_build_url`.

**Coverage:** each has a 274-278 line MockTransport test file with identical
structure; tighten the download assertion to the full URL.

## 8. `IpAustraliaSearchClient` (patents, trademarks, designs)

**Owns:** environment/auth wiring (already in `ip_australia_common`), the
`POST /search/quick` payload builder (query, filters, `changedSinceDate`,
sort, `extra`), and `GET /{kind}/{id}` detail fetch.

**Today:** `ip_australia_patents/client.py` (149), `ip_australia_trademarks/client.py`
(147), `ip_australia_designs/client.py` (142). `diff` shows only API path, cache
name, models, one extra filter (`quick_search_type` on trademarks), and
docstrings differ. symilar 20+18+16 lines.

**Proposed:** base class with `API_PATH`, `DETAIL_SEGMENT`, `SEARCH_RESULT_MODEL`,
`RECORD_MODEL`, `EXTRA_FILTERS: tuple[str, ...]`; subclasses ~25 lines each.

**Line estimate:** 438 -> base ~110 + 3 x ~25 = 185: **~250.** Models (223 lines)
keep per-right fields; `_BASE_CONFIG` folds into primitive 6.

**Risks:** per-right method names (`get_patent`, `get_trademark`, `get_design`)
are public; keep thin named wrappers. Production access is gated, so live
coverage is thin.

**Coverage:** ~330-360 line MockTransport suites per right, structurally identical.

## 9. `EuipoClientBase` (trademarks, designs)

**Owns:** `EUIPO_ENV` resolution, prod/sandbox base and token URLs,
`EUIPO_CLIENT_ID`/`SECRET` resolution, OAuth with `scope="uid"` and
credentials-in-body, `X-IBM-Client-Id` header, page-size validation (10..100),
and a `_get_bytes(path, context)` helper for media endpoints.

**Today:** `euipo_trademarks/client.py:52-121` and `euipo_designs/client.py:45-112`
(symilar 56 lines). Trademarks has five byte getters (`get_image`,
`get_image_thumbnail`, `get_sound`, `get_video`, `get_model`; 8 lines each).
Shared `Person`, `Publication`, `Status` models.

**Line estimate:** constructor ~55 + media ~25 + shared models ~20 minus base
~5 net-new: **~95.**

**Risks:** two different API products with independent versioning (sandbox
v1.1.0 vs prod v1.0.0 for trademarks); keep models separate except the shared
leaf types. **Coverage gap:** neither package has request-path tests; the
suites only cover constructor/env/validation. Add MockTransport tests before
refactoring.

## 10. `one_shot()`: typed module-level wrappers (and removing `client=`)

**Owns:** "open a client, call one method, close it" for the public functional
API, with full static typing via `ParamSpec`/`Concatenate`:

```python
def one_shot(factory: Callable[[], C], method: Callable[Concatenate[C, P], Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    @functools.wraps(method)
    async def run(*args: P.args, **kwargs: P.kwargs) -> T:
        async with factory() as client:
            return await method(client, *args, **kwargs)
    return run

get_dpma_patent = one_shot(DpmaRegisterClient, DpmaRegisterClient.get_patent)
```

**Today:** 17 `api.py` files, 3,374 lines, 161 functions, almost all of the form
"build kwargs, `async with Client() as c: return await c.method(**kwargs)`".
Sizes: epo_ops 530, jpo 526, uspto_applications 491, tipo 285, cpc 212, kipo 203,
canlii 200, uspto_petitions 157, euipo_trademarks 150, uspto_bulkdata 130,
inpi_pi 127, euipo_designs 109, thai 81, ipi_swissreg 62, iponz 48, dpma 42, oepm 21.

Within the repo almost nothing calls them: MCP tools use the client classes
directly (e.g. 14 `async with JpoClient()` in `mcp/tools/jpo.py`, 21
`UsptoOdpClient` in `mcp/tools/uspto.py`). Importers of `*.api` outside the
packages: canlii 3, kipo 3, euipo_trademarks 1, inpi_pi 1, tipo 1, and the
swissreg/iponz/thai/dpma MCP tools. So the layer is mostly public-library
surface for PyPI users.

**Deprecated `client=` path:** `uspto_applications/api.py` (15 sites),
`uspto_petitions/api.py` (3), `uspto_bulkdata/api.py` (2), `epo_ops/api.py` (17),
`cpc/api.py` (5) each carry `_warn_client_deprecated()` plus an
`if client is not None:` branch, "will be removed in v1.0". Same helper is
copied into out-of-slice `epc`, `epo_*_guidelines`, `google_patents`, `mpep`,
`ukipo_mopp`, `uspto_publications`. Tests rely on it as the injection seam:
`client=` appears in `tests/uspto_applications/test_api.py` (4),
`tests/epo_ops/test_api.py` (8), `tests/cpc/test_api.py` (5),
`tests/uspto_bulkdata/test_api.py` (2), `tests/uspto_petitions/test_api.py` (3).

**Line estimate:** at ~10 lines saved per function for the 161 functions, minus
JPO (credentials forwarded per function), EPO/CPC (`client_from_env` with
shared auth), CanLII/EUIPO (Pydantic `*Input` models stay; wrapper becomes
`one_shot_input(...)`), conservatively **~1,400** including ~250 for removing
the deprecated `client=` branches.

**Stays specific:** the Pydantic `*Input` models in canlii/euipo (they carry
field descriptions), argument renames (`q` -> `query` in uspto_applications),
composite helpers that call two methods (e.g. `fetch_family_details`).

**Risks:** this is a public API of a published wheel; dropping `client=` is a
breaking change already announced for v1.0. Generated wrappers lose
hand-written docstrings unless `functools.wraps` copies the method's (it does).
Tests that inject `client=` need a monkeypatch of the client class or a
`factory=` parameter on `one_shot`. Combine with primitive 3/4 or the per-call
client keeps defeating token and rate-limit caching.

**Coverage:** `tests/*/test_api.py` exist for uspto_applications (75 lines),
uspto_petitions, uspto_bulkdata (57), epo_ops, cpc, mpep; JPO has VCR
`TestConvenienceFunctionsLive` cassettes for two one-shot functions. Most BYOK
`api.py` modules have no direct tests.

## 11. ODP declarative resource spec

**Owns:** the four operations every ODP "dataset" exposes: POST search with
`SearchPayload`, GET by document id with the "wrap bare record in its
`*DataBag`" fixup, GET-by-number, and `/search/download` with
`_normalize_download_bag`, each mapping 404 to an empty bag.

**Today:** `uspto_odp/clients/ptab_trials.py` (526; three resources:
proceedings, decisions, documents), `ptab_appeals.py` (172),
`ptab_interferences.py` (174), `petitions.py` (173). `diff ptab_appeals.py
ptab_interferences.py` differs only in path segment, bag key, model, and
docstring nouns (symilar 21+12, plus petitions+interferences 10). The
`SearchPayload.model_validate({...}).model_dump_pruned()` block appears 5 times,
`_search_with_payload` 14 times, the bag-wrap fixup 10 times.

**Proposed:**
```python
APPEALS = OdpResource(search="/api/v1/patent/appeals/decisions/search",
                      get="/api/v1/patent/appeals/decisions/{id}",
                      by_number="/api/v1/patent/appeals/{number}/decisions",
                      bag="patentAppealDataBag", model=PtabAppealResponse)
class PtabAppealsClient(UsptoOdpBaseClient):
    search = APPEALS.search_method(); get_decision = APPEALS.get_method(); ...
```

**Line estimate:** 1,045 -> ~450: **~550.** Optional: the `UsptoOdpClient`
facade (`uspto_odp/client.py`, 685 lines, 34 pure delegations) could use the
same `ParamSpec` trick as primitive 10 (`search_applications =
delegate("_applications", ApplicationsClient.search)`), about **~450** more, and
should share one transport across its six sub-clients (bug 4).
`uspto_office_actions/client.py` reuses `UsptoOdpBaseClient` already; its
`_search_dataset` is a different (form-encoded Solr) shape and stays.

**Risks:** public method names and docstrings on each client; MCP tools call
these methods by name. ODP endpoints have drifted before (release 3.6 removed
fields; download endpoints use flat keys, see `_normalize_download_bag`
docstring), so per-resource overrides must remain possible.

**Coverage:** strong: 24 VCR cassettes for uspto_odp, `tests/uspto_odp/test_ptab.py`,
`test_ptab_envelope.py`, `test_base.py` (3,014 lines total).

## 12. `iter_offset_pages()`

**Owns:** "call fetch(page/offset), yield rows, stop on short page or max_pages".

**Today:** `kipo_kipris/client.py:~270-310 paginate` (page number) and
`tipo_opdata/client.py:225-258 paginate` (skip/top). `uspto_assignments/client.py:182-236`
is too bespoke (client-side conveyance filter, `backendPagination` flag,
10k cap) to fold in. Most connectors return one page and let the MCP layer
page via cursors.

**Line estimate:** **~20.** Low priority; only worth doing alongside 1.

**Coverage:** tipo has 2 VCR cassettes; kipo MockTransport pagination tests.

## 13. Package `__init__` re-exports

**Today:** `__init__.py` files re-list everything `api.py` already lists in
`__all__` (symilar: jpo 37+19, uspto_applications 27, euipo_trademarks 27,
euipo_designs 24, canlii 21+14+10, cpc 18, epo_ops 16, tipo 15). Sizes: jpo 157,
epo_ops 87, canlii 86, uspto_applications 69, euipo_trademarks 64,
euipo_designs 58, tipo 54.

**Proposed:** `from .api import *  # noqa: F403` plus `__all__ = [*api.__all__, ...]`,
or let primitive 10 generate both.

**Line estimate:** **~250.** **Risk:** ruff F403/F405 and IDE discoverability;
some `__init__` files also export model types not in `api.__all__`.

---

## Not recommended as primitives

- **Application/patent number normalisation.** Only three trivial helpers
  exist (`uspto_odp/clients/base.py:228`, `epo_ops/client.py:281` plus the US
  pre-grant conversion at :286, `iponz_new_zealand/client.py:273`), each
  jurisdiction-specific. Leave them; a cross-office normaliser would belong in
  `unified.py`, not the clients.
- **`LIST_ACCEPT_CAP = 50`** is defined in six clients and consumed only by
  MCP tools; that belongs to the MCP-tools slice.
- **`resources.py` usage docs** (15-22 lines each) are prose, not code.
- **JSON vs XML split:** JSON connectors (ODP, CanLII, EUIPO, IP Australia,
  TIPO, Thai DIP, JPO) already go through `_request_json`; XML connectors
  differ enough in envelope/error conventions (KIPRIS header, Swissreg core
  namespace, DPMA fault, IPONZ TransactionError, OEPM SOAP, EPO lxml with
  namespaces in `epo_ops/parsing.py`) that only primitive 5's leaf helpers are
  shared.

## Suggested order

1. mcp-data-core: absolute-URL `_build_url` (fixes CKAN bug), `extensions`/
   `cookies` passthrough, `HTTP_CLIENT_KWARGS`, `ERROR_LABEL`, `RETRY`, hooks;
   add `test_base_client.py`. Release, then bump the pin
   (`pyproject.toml` has `mcp-data-core>=0.11.3`; mind the PyPI propagation lag).
2. Move iponz/swissreg/oepm/thai/dpma/kipo onto `_request` (primitive 1) and
   the XML helpers (5).
3. `TokenAuth` + shared limiter (3, 4), migrating EPO, JPO, Swissreg, INPI.
4. Family collapses: CKAN (7), IP Australia (8), EUIPO (9, after adding
   request-path tests), ODP resources (11) and facade transport sharing.
5. Models (6), then `one_shot` + `client=` removal + `__init__` cleanup (10, 13)
   as the v1.0 breaking change.
