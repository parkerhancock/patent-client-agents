# Thailand DIP Data Exchange connector specification

**Status:** implemented as BYOK beta; catalogue-schema tested; live unverified
**Last verified:** 2026-08-03
**Package:** `patent_client_agents.thai_dip`
**Credential:** `DIP_DATA_EXCHANGE_TOKEN`

## 1. Scope and evidence

This connector covers seven register datasets published by Thailand's Department
of Intellectual Property through its Data Exchange service. DIP's public catalogue
provides the endpoint, HTTP method, request-body example, response field table,
version, and last-update date for each dataset.

No usable OpenAPI document is public. The conventional
`/DIP-APIDynamic/swagger/v1/swagger.json` and `/swagger/docs/v1` paths returned
HTTP 200 with `{"status":false,"message":"Invalid Api."}` on 2026-08-03. The
catalogue field tables are therefore the implementation contract.

Primary sources:

- [DIP Data Exchange catalogue](https://api.ipthailand.go.th/data-exchange/view/home.aspx)
- [DIP Data Exchange registration](https://api.ipthailand.go.th/data-exchange/Register.aspx)
- [DIP API Specification user guide](https://api.ipthailand.go.th/data-exchange/file/DIP-EDW_%E0%B8%84%E0%B8%B9%E0%B9%88%E0%B8%A1%E0%B8%B7%E0%B8%AD%E0%B8%81%E0%B8%B2%E0%B8%A3%E0%B9%83%E0%B8%8A%E0%B9%89%E0%B8%87%E0%B8%B2%E0%B8%99%20API%20Specification.pdf)
- [DIP 2026 data-disclosure notice](https://api.ipthailand.go.th/data-exchange/view/images/fileexchange/00019867.pdf)

## 2. Authentication and deployment

The connector sends `Authorization: Bearer {token}` and JSON requests. The user
must register online, send a paper request letter to DIP's ICT Center within 30
days, and wait for approval. DIP then exposes the token through the account page.

The token belongs to the approved person or organization. The connector is BYOK
only and must not be mounted on the public hosted demo with a maintainer token.
The MCP tools register only when `DIP_DATA_EXCHANGE_TOKEN` is present.

The default base URL is:

`https://api.ipthailand.go.th/DIP-APIDynamic/api/Search`

Only HTTPS is allowed outside injected test clients. Error mapping is:

- HTTP 401 or 403: `AuthenticationError`
- HTTP 429: `RateLimitError`
- other non-success status: `ApiError`
- malformed JSON or non-array response: `ApiError`

The public catalogue gives no rate limit, result cap, or pagination contract.
The client returns at most 100 records per call and reports whether the response
contained more records. It cannot provide a next cursor.

## 3. Dataset contract

All endpoints use POST and return a top-level JSON array according to DIP's own
sample code. Text fields marked as wildcard use the catalogue's `%value%` form.

| Dataset | Catalogue ID | Endpoint | Supported request fields |
|---|---:|---|---|
| Invention patents | A0019 | `PATENT_NOIP` | `patent_name` (wildcard), `app_no`, `pub_no`, `patent_no` |
| Design patents | A0005 | `PRODUCTPATENT` | `patent_name` (wildcard), `app_no`, `pub_no`, `patent_no` |
| Petty patents | A0006 | `PETTYPATENT` | `patent_name` (wildcard), `app_no`, `pub_no`, `patent_no` |
| Trademarks | A0007 | `TM` | `tr_name`, `req_no` (wildcard), `regis_no`, `expire_date` |
| Copyright notifications | A0001 | `CPR` | `work_name`, `typename`, `owner_name` (wildcard); `request_no`, `register_no` |
| Music copyright | A0002 | `CPRSONG` | `reg_songs_name`, `album_name`, `lyric_author_name`, `compose_author_name` (wildcard) |
| Geographical indications | A0003 | `GI` | `giname` (wildcard), `app_no_number` |

The normalized models expose stable identifiers and common register fields. Each
model also preserves the complete source object in `raw`. Parsing is
case-insensitive because the catalogue publishes uppercase response fields while
request fields are lowercase.

The date parser accepts the two catalogue formats: `YYYY-MM-DD` and `DD-MM-YYYY`.

## 4. MCP surface

The connector provides nine tools:

1. `search_thai_dip_patents`
2. `get_thai_dip_patent`
3. `search_thai_dip_trademarks`
4. `get_thai_dip_trademark`
5. `search_thai_dip_copyrights`
6. `get_thai_dip_copyright`
7. `search_thai_dip_songs`
8. `search_thai_dip_geographical_indications`
9. `get_thai_dip_geographical_indication`

DIP publishes search endpoints only. The four fetch tools use an exact stable-ID
search and return the first record. The music dataset has stable response IDs but
no documented identifier request field, so it has no fetch tool.

Fetch tools accept up to 50 identifiers and use concurrency five. Lean responses
exclude `raw`; `full=true` includes it. Provenance points to the exact DIP endpoint
and states that live compatibility is unverified.

## 5. Test contract

The synthetic fixtures copy DIP's published request fields, response field names,
types, and date formats. They do not contain live or personal data. Tests verify:

- Bearer authentication and exact JSON request bodies
- all seven endpoint paths and response models
- invention, design, and petty-patent routing
- exact-identifier fetch behavior
- result limits and missing-record handling
- HTTP authentication, rate-limit, and server errors
- malformed or unexpected JSON
- credential-gated MCP registration, envelopes, provenance, and lean/full output

No test claims live compatibility. A contributor with an approved account should
run a private smoke test and report schema differences. Any shared fixture must
remove tokens, personal data, protected full-text works, and confidential records.

## 6. Deferred work

- Live account validation and sanitized response-shape confirmation
- Upstream result-cap and rate-limit measurement
- Statistics endpoints A0013 and A0021 through A0031
- Unified patent endpoint A0034, which duplicates the three typed patent datasets
- Trademark GET endpoint A0015, whose public detail dialog has no field contract
- Images, patent documents, lyrics, and other potentially protected content
