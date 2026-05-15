# JPO (Japan Patent Office)

Patent, design, and trademark prosecution data from the Japan Patent
Office Patent Information Retrieval API. Covers application progress,
registration, priority claims, divisional family, applicant lookup,
J-PlatPat permalinks, citations, PCT national-phase numbers, and the
file-history document bundles for all three IP types.

> The agent-facing reference for working JPO tools lives in the skill —
> [`skills/ip_research/references/jpo.md`](../../skills/ip_research/references/jpo.md).
> This catalog page is the **library / connector** reference: client API
> shape, deployment surface, status-code semantics, and quirks. When the
> two disagree, **the live code is the truth** — file an issue.

## Source

| | |
|---|---|
| Module | `patent_client_agents.jpo` |
| Client | `JpoClient` |
| Base URL | `https://ip-data.jpo.go.jp` (API path prefix `/api`) |
| Auth | `JPO_API_USERNAME` + `JPO_API_PASSWORD` (OAuth2 password grant against `https://ip-data.jpo.go.jp/auth/token`) |
| Rate limit | 10 requests / 60 s sliding window (handbook v14 §3) — enforced in-process |
| Daily caps | Per endpoint, server-side — see [Daily quotas](#daily-quotas) |
| Status | **Active, env-gated.** 12 MCP tools register only when `JPO_API_USERNAME` and `JPO_API_PASSWORD` are both set. Active on private deploys with the secrets (e.g. law-tools); intentionally absent on the hosted public server `mcp.patentclient.com` per JPO TOS. See [Deployment posture](#deployment-posture). |

## Authentication

Register at <https://www.jpo.go.jp/e/system/laws/koho/internet/api-patent_info.html>.
Corporate users get higher daily caps than individual users (handbook v14
Article 3§2: corporate users may also request 2× their default cap with
"rational reasons", and "Information Providers" up to 5× the document-
download caps). After approval JPO emails you a username + password.

The client posts those credentials as an OAuth2 password grant to
`/auth/token` and gets back a JWT bearer token plus refresh token.
`JpoClient` caches the JWT and refreshes when expired (it does not use
the refresh token — re-authenticating with the password grant is cheap
and avoids storing refresh tokens at rest). On status `210` (invalid
token) the client invalidates and retries once.

## Deployment posture

The 12 JPO MCP tools and the `jpo/documents` download fetcher
auto-register **only** when both `JPO_API_USERNAME` and
`JPO_API_PASSWORD` are set in the server's environment. The gate is
implemented at decorator-evaluation time via
`law_tools_core.mcp.conditional_tool` and the parallel
`register_source_if_configured` helper — the Python functions remain
importable for direct use, but `mcp.tool(...)` is never called on
unconfigured deployments, so JPO tools never appear in `tool/list`.
The download fetcher is gated symmetrically as defense in depth.

| Deployment | JPO secrets? | JPO tools advertised? |
|---|---|---|
| `mcp.patentclient.com` (public) | No (per JPO TOS) | No |
| Private Cloud Run deploy with secrets mounted | Yes (Cloud Run secret_env_map) | Yes |
| Local stdio plugin | Yes if user has them in env | Yes if both set |

**JPO TOS notes.** JPO requires individual or corporate registration
for API access. The hosted public deploy intentionally cannot proxy
those credentials to anonymous Google-OAuth'd callers — surfacing JPO
tools on a public server would push every call through one shared
account, violate the per-user attribution requirements, and exhaust
the daily caps in seconds.

**Enabling JPO on a private deploy.** Mount both secrets via the
deployment's secret manager (Cloud Run + Terraform `secret_env_map`,
docker-compose env file, etc.). Restart the process — the gate is
evaluated at module import, not on every call. Verify with a
`tool/list` request that `get_jpo_*` tools now appear; verify the
download path with a parsed `get_jpo_documents` call (the signed URL
should resolve to bytes, not 404).

**Local development.** Put the credentials in `~/.claude/secrets.env`
(or any file you `source` before running the server / tests) so the
JPO surface is live in your dev environment without hardcoding
secrets in the repo.

## Daily quotas

Daily caps are per-endpoint and reset at 00:00 JST. From handbook v14
Tables 1-3:

| Endpoint family | Patent | Design | Trademark |
|---|---:|---:|---:|
| `app_progress` (full status) | 400 | 400 | 400 |
| `app_progress_simple` | 400 | 400 | 400 |
| `divisional_app_info` | 30 | — | — |
| `priority_right_app_info` | 30 | 30 | 30 |
| `applicant_attorney` (by-name) | 200 | 200 | 200 |
| `applicant_attorney_cd` (by-code) | 200 | 200 | 200 |
| `case_number_reference` | 50 | 50 | 50 |
| `app_doc_cont_*` (each document endpoint) | **100** | **100** | **100** |
| `cite_doc_info` | 100 | — | — |
| `registration_info` | 50 | 50 | 50 |
| `jpp_fixed_address` (J-PlatPat URL) | 200 | 200 | 200 |
| `pct_national_phase_application_number` | 100 | — | — |

Each successful response carries a `remainAccessCount` field in the
`result` envelope (parsed onto `ApiResult` but not surfaced on the
domain models). When the daily cap is hit the API returns status `203`,
which `JpoClient` raises as `RateLimitError`.

## Endpoint inventory (wired up)

The library implements every Patent / Design / Trademark API in
handbook v14 Tables 1-3 (36 endpoints — see `JpoClient`). The MCP
surface exposes the agent-relevant subset; OPD APIs (Table 4) are not
shipped because EPO OPS already provides cross-jurisdiction family data.

```
Patent:    /api/patent/v1/{endpoint}/{number}
Design:    /api/design/v1/{endpoint}/{number}
Trademark: /api/trademark/v1/{endpoint}/{number}
```

`endpoint` is one of:

- `app_progress` / `app_progress_simple` — full + simplified status
- `divisional_app_info` (patent only) — divisional family
- `priority_right_app_info` — Paris + domestic priority claims
- `applicant_attorney` / `applicant_attorney_cd` — applicant by exact name / by code
- `case_number_reference/{kind}/{number}` — number cross-reference (kind = `application` / `publication` / `registration`)
- `app_doc_cont_opinion_amendment` — applicant-filed docs (opinions, amendments)
- `app_doc_cont_refusal_reason_decision` — JPO-mailed docs (rejections + decisions)
- `app_doc_cont_refusal_reason` — refusal-only subset of mailed
- `cite_doc_info` (patent only) — patent + non-patent citations
- `registration_info` — granted-rights record
- `jpp_fixed_address` — J-PlatPat permalink
- `pct_national_phase_application_number/{kind}/{number}` (patent only)

## Library API

```python
from patent_client_agents.jpo import JpoClient

async with JpoClient() as client:
    progress = await client.get_patent_progress("2020123456")
    cited = await client.get_patent_cited_documents("2020123456")
```

Per-IP-type methods on `JpoClient` follow the pattern
`get_{patent|design|trademark}_{action}` — e.g.
`get_design_progress`, `get_trademark_registration_info`. Library
callers stay on the per-IP-type surface; the `ip_type` dispatch is
**MCP-surface only**.

### Method groups

| Method | Returns | Description |
|---|---|---|
| `get_{ip}_progress(app_number)` | `*ProgressData \| None` | Full status (title, applicants, dates, priorities, family, file-wrapper inventory) |
| `get_{ip}_progress_simple(app_number)` | `*ProgressData \| None` | Simplified status (no priority/family) |
| `get_patent_divisional_info(app_number)` | `DivisionalAppInfoData \| None` | Patent-only — parent + descendants |
| `get_{ip}_priority_info(app_number)` | `list[PriorityInfo]` | Paris + domestic priority claims |
| `get_{ip}_applicant_by_code(code)` | `str \| None` | 9-digit code → single name |
| `get_{ip}_applicant_by_name(name)` | `list[ApplicantAttorney]` | Exact-match name → codes |
| `get_{ip}_number_reference(kind, n)` | `NumberReference \| None` | Cross-ref between application / publication / registration |
| `get_{ip}_application_documents(app_number)` | `DocumentBundleResult` | Applicant-filed bundle (ZIP) |
| `get_{ip}_mailed_documents(app_number)` | `DocumentBundleResult` | JPO-mailed bundle (rejections + decisions) |
| `get_{ip}_refusal_notices(app_number)` | `DocumentBundleResult` | Refusal-only subset (ZIP) |
| `get_patent_cited_documents(app_number)` | `CitedDocumentsData \| None` | Patent + non-patent citations |
| `get_{ip}_registration_info(app_number)` | `RegistrationInfo \| None` | Granted-rights record |
| `get_{ip}_jplatpat_url(app_number)` | `str \| None` | J-PlatPat permalink |
| `get_patent_pct_national_number(kind, n)` | `PctNationalPhaseData \| None` | PCT → JP national-phase lookup |

`DocumentBundleResult` carries either `zip_bytes` (inline; bundles
under ~10 MB) or `download_url` (oversize redirect to a JPO-hosted
ZIP). The MCP layer resolves the redirect transparently.

## MCP tools

Twelve MCP tools — all in
[`src/patent_client_agents/mcp/tools/international.py`](../../mcp/tools/international.py).
Cross-IP-type tools take an `ip_type: Literal["patent", "design", "trademark"]`
argument that defaults to `"patent"`. Patent-only tools have no
`ip_type` arg.

| Tool | Args | Daily quota tier | Description |
|---|---|---|---|
| `get_jpo_progress` | `application_number`, `ip_type` | 400 | Full prosecution status. `{}` on 107/111. |
| `get_jpo_progress_simple` | `application_number`, `ip_type` | 400 | Simplified status (no priority/family). |
| `get_jpo_priority_info` | `application_number`, `ip_type` | 30 | Paris + domestic priorities → `{"results": [...]}`. |
| `get_jpo_registration_info` | `application_number`, `ip_type` | 50 | Granted-rights record. `{}` if not registered. |
| `get_jpo_number_reference` | `number`, `kind`, `ip_type` | 50 | Cross-reference. `kind = "application"\|"publication"\|"registration"`. |
| `get_jpo_jplatpat_url` | `application_number`, `ip_type` | 200 | Returns `{"url": ...}` or `{}`. |
| `get_jpo_applicant` | `applicant`, `ip_type` | 200 | Auto-detects code (9-digit numeric) vs exact name. Code → `{"name": ...}`; name → `{"results": [...]}`. **Exact match** required for name lookup. |
| `get_jpo_documents` | `application_number`, `doc_kind`, `ip_type`, `parse=True` | 100 | Parsed file-history bundle + signed `download_url`. `doc_kind = "application"\|"mailed"\|"refusal"`. With `parse=False` returns just the bundle metadata + signed download URL (no parsing). |
| `get_jpo_patent_divisional_info` | `application_number` | 30 | Patent-only — divisional family. |
| `get_jpo_patent_cited_documents` | `application_number` | 100 | Patent-only — patent + non-patent citations. |
| `get_jpo_pct_national_phase_number` | `number`, `kind` | 100 | Patent-only. `kind = "international_application"\|"international_publication"`. |

Convention summary:

- `ip_type` defaults to `"patent"`; `doc_kind` defaults to `"mailed"`
  (the most useful prosecution slice).
- `kind` on `get_jpo_number_reference` is a descriptive string —
  `"application"` / `"publication"` / `"registration"` — **not** the
  numeric `NumberType` codes used in `bibliographyInformation` rows.
- `kind` on `get_jpo_pct_national_phase_number` is
  `"international_application"` (use with PCT/JP-style numbers) or
  `"international_publication"` (use with WO-style numbers).
- All tools return `dict`. List-shaped results are wrapped as
  `{"results": [...]}`.
- All tools return `{}` for "no data" (status 107/108/111).

## Document bundles

Patents ship JPO-flavoured **XML** files; designs and trademarks ship
**HTM** (handbook v14 §2(1) — the file extension is ip-type-driven, not
doc-kind-driven). Both formats are **Shift-JIS encoded** (cp932 fallback
on the rare characters strict Shift-JIS rejects). The
`parse_document_bundle` helper decodes both transparently; if you walk
the ZIP yourself, decode with `raw.decode("shift_jis")` — UTF-8 will
raise on the first kana.

When the archive exceeds ~10 MB the JPO API returns JSON with a
`URL` field pointing to a JPO-hosted ZIP. **The URL field is uppercase**
(the OpenAPI spec shows lowercase, which is wrong). The
`get_jpo_documents` MCP tool resolves the redirect in-process so the
agent always gets bytes — we never hand off "go fetch this other URL".

### Parsed entry shape

`DocumentEntry` (see `models_documents.py`) — uniform across all nine
(ip_type × doc_kind) combinations:

```
filename             — path inside the ZIP
ip_type              — patent / design / trademark
doc_kind             — application / mailed / refusal
document_code        — JPO 4-digit code (e.g. A153 for opinion)
document_name        — Japanese name (e.g. 拒絶理由通知書)
document_variant     — root XML element, or "htm" for HTM payloads
application_number   — echoed
legal_date           — drafting date (YYYYMMDD for XML; wareki string for HTM)
drafter_name         — examiner (mailed docs only)
articles             — statutes cited
applicant_names      — applicant + agent names (applicant-filed only)
dispatch_number      — JPO dispatch ID being responded to
body_text            — concatenated body text
parse_error          — set when XML/HTM parsing failed
```

Non-XML / non-HTM files (drawings, sequence listings, etc.) are listed
in `DocumentBundle.binary_attachments` by filename only. Their bytes
remain in the original ZIP and can be reached via the bundle's
`download_url`.

### `parse=False` opt-out

`get_jpo_documents` accepts an optional `parse: bool = True` argument:

- **`parse=True`** (default) — unchanged behaviour: parse the bundle
  and return entries inline.
- **`parse=False`** — skip parsing entirely. Response shape:
  `{"application_number", "ip_type", "doc_kind", "entries": [],
  "binary_attachments": [], "download_url", "filename",
  "content_type", "size_bytes", "expires_at"}`. Useful when handing
  the URL to a human reviewer or to a separate processing pipeline.

Empty bundles (status 107/108) return `{}` regardless of the `parse`
value — no leaked download URL when there are no documents.

## Status codes

The API returns a `result.statusCode` on every JSON response. Mapping:

| Code | Meaning | Client behaviour |
|---|---|---|
| 100 | Success | Returns parsed model |
| **107** | No data for query | Returns `None` / `[]` / `{}` |
| **108** | No document body | Returns empty bundle |
| **111** | Number out of scope | Returns `None` / `[]` / `{}` |
| 203 | Daily limit exceeded | Raises `RateLimitError` |
| 204 | Bad parameter | Raises `ApiError` |
| 208 | Invalid characters in parameter | Raises `ApiError` |
| 210 | Invalid token | Auto-refreshes once; raises `AuthenticationError` on persistence |
| 212 | Invalid auth credentials | Raises `AuthenticationError` |
| 301 | URL not found | Raises `NotFoundError` |
| 302 | Timeout | Raises `ApiError` |
| 303 | Concentrated access | Raises `RateLimitError` (transient — back off + retry) |
| 400 | Invalid request | Raises `ApiError` |
| 999 | Unexpected server error | Raises `ApiError` |

HTTP-level errors propagate as vanilla httpx exceptions, except 429
which becomes `RateLimitError`.

## Quirks worth knowing

- **The OpenAPI spec is unreliable.** `resources/jpo/jpo_api_openapi.json`
  describes objects where the API actually returns arrays
  (`patentDoc` / `nonPatentDoc` in `cite_doc_info`), uses incorrect
  status-code keys, and has the J-PlatPat URL field name wrong (see
  next bullet). The library models track the **live API**, not the
  spec — when they disagree the live API wins.
- **`jpp_fixed_address` returns `URL` (uppercase)**, not `jplatpatUrl`
  as the OpenAPI spec claims. Same for the oversize-bundle redirect.
- **`applicant_attorney/{name}` requires an exact match.** Searching
  for `"トヨタ"` returns status 107; you need the full registered name
  e.g. `"トヨタ自動車株式会社"`.
- **`applicant_attorney_cd` returns a single name** (a `string` keyed
  on `applicantAttorneyName`), not a list — the OpenAPI spec implies a
  list.
- **`case_number_reference` returns a single object**, not a list.
- **`case_number_reference` and `pct_national_phase_application_number`
  use descriptive `kind` strings**, not the numeric `NumberType` codes
  (which are for the `numberType` field *inside* `bibliographyInformation`
  rows).
- **Document bundles are only available for filings after January
  2019.** Patent applications filed from July 2003 forward have other
  metadata (status, biblio); design/trademark applications from
  January 2001 forward; but the actual document files (the
  `app_doc_cont_*` endpoints) only cover items received or created
  after January 2019, matching J-PlatPat's search scope.
- **JPO accumulated data updates daily.** A notice mailed today
  appears in the API tomorrow.
- **Document XML/HTM is Shift-JIS, not UTF-8.** Decode every payload
  explicitly. The handbook's "XML Tag Structures" reference is the
  source of truth for the patent XML schema (it ships as a separate
  per-DTD document set, not in `jpo_api_handbook_v14_e.md`).
- Each JPO ID is **single-tenant** — handbook §3 forbids sharing IDs
  across people or holding multiple IDs. Hosted deployments (the
  `mcp.patentclient.com` server) use a single corporate ID; agents
  share that quota.

## Live usage example

End-to-end: applicant-name lookup → number cross-reference → progress
→ document bundle.

```python
from patent_client_agents.jpo import JpoClient

async with JpoClient() as client:
    # 1. Resolve the applicant code from an exact corporate name.
    matches = await client.get_patent_applicant_by_name(
        "トヨタ自動車株式会社"
    )
    applicant_code = matches[0].applicant_attorney_cd  # "000003207"

    # 2. Cross-reference a publication number to its application number.
    ref = await client.get_patent_number_reference(
        "publication", "2021090037"
    )
    application_number = ref.application_number  # "2020123456"

    # 3. Pull full prosecution status.
    progress = await client.get_patent_progress(application_number)
    print(progress.invention_title, progress.filing_date)

    # 4. Fetch the parsed mailed-documents bundle (refusal notices +
    #    decisions). Empty when nothing has been mailed yet.
    raw = await client.get_patent_mailed_documents(application_number)
    if raw.zip_bytes or raw.download_url:
        from patent_client_agents.jpo import parse_document_bundle
        bundle = parse_document_bundle(
            raw.zip_bytes,  # parse_document_bundle handles None gracefully
            doc_kind="mailed",
            ip_type="patent",
            application_number=application_number,
        )
        for entry in bundle.entries:
            print(entry.document_name, entry.legal_date, entry.drafter_name)
```

The same flow runs from MCP via `get_jpo_applicant` (name branch) →
`get_jpo_number_reference` → `get_jpo_progress` → `get_jpo_documents`,
with `ip_type` parameters defaulting to `"patent"`. For designs or
trademarks, swap in `ip_type="design"` / `ip_type="trademark"`
everywhere.
