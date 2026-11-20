# JPO Patent Information Retrieval API

October 26, 2026. `JpoClient` ([source](../packages/client/src/jpo.ts)) ports
the Python `jpo` package: all 36 endpoints of JPO's Patent Information
Retrieval API (handbook v14) for patents, designs and trademarks, and the
document-bundle parser ([source](../packages/client/src/jpo-documents.ts)).
The [MCP adapter](../packages/mcp/src/jpo.ts) serves the eleven Python JPO
tools under the same names and parameters. The curated facade doesn't route to
JPO, in Python or here.

Nothing here has run against the API from TypeScript. No JPO account is
available to this project, so the tests replay the Python connector's live
recordings of May 7, 2026.

## Credentials, token and rate limit

JPO issues each user a username and password. `JPO_API_USERNAME` and
`JPO_API_PASSWORD` (or the `username` and `password` options) are exchanged
for a bearer token by password grant at `POST /auth/token`. The token is
reused until a minute before its `expires_in`, measured on the local clock,
and refreshes are single-flight. As in Python, one token is shared by every
client in the process that uses the same origin and account. The refresh token
JPO also returns is never kept.

An HTTP 401 or 403, or a JPO status 210 (invalid token), gets one refresh and
one retry. Python retried on HTTP 401 and 403 only and reported 210 as an
authentication error.

The handbook (§3) asks for at most 10 requests a minute across the three
APIs. Every client on an origin shares one sliding window of 10 requests per
60 seconds, as Python's `process_shared` limiter did. Callers queue in order,
and a caller's abort signal ends its wait. The `rateLimit` option changes the
window, or turns it off with `false` for tests. Retries inside the shared HTTP
transport (HTTP 408, 429 and 5xx) aren't counted against the window. Daily
caps are per endpoint and enforced by JPO, which reports the remainder as
`remainAccessCount`. Each result carries it as `remaining_access_count`.

The MCP server registers the JPO tools only when a client is provided or both
environment variables are set, and requires the `jpo:read` scope over HTTP.
The public demo carries no JPO credentials, per JPO's terms.

## Library surface

Python has one method per endpoint per register. The port takes the register
as an argument, as the Python MCP tools already did:

| Python methods | TypeScript |
| --- | --- |
| `get_{patent,design,trademark}_progress`, `..._progress_simple` | `getProgress(ipType, number, { simple })` |
| `get_*_priority_info` | `getPriorityInfo(ipType, number)` |
| `get_*_applicant_by_code`, `get_*_applicant_by_name` | `getApplicantByCode(ipType, code)`, `getApplicantByName(ipType, name)` |
| `get_*_number_reference` | `getNumberReference(ipType, kind, number)` |
| `get_*_registration_info` | `getRegistrationInfo(ipType, number)` |
| `get_*_jplatpat_url` | `getJplatpatUrl(ipType, number)` |
| `get_*_application_documents`, `get_*_mailed_documents`, `get_*_refusal_notices` | `getDocumentBundle(ipType, docKind, number)`, with docKind `application`, `mailed` or `refusal` |
| `get_patent_divisional_info`, `get_patent_cited_documents`, `get_patent_pct_national_number` | `getPatentDivisionalInfo`, `getPatentCitedDocuments`, `getPatentPctNationalPhase` |
| `parse_document_bundle` | `parseJpoDocumentBundle(zip, docKind, ipType, number)` |

`getDocumentArchive` and `getDocuments` add what the Python MCP tool did
inline: they follow an oversize bundle's link and parse the archive.

Records use Python's field names (snake_case) and Python's defaults: absent
text is `""`, absent lists are `[]` and an absent parent application is
`null`. Upstream keys no model names are kept under their own names. Python
dropped them. A value of the wrong type (a list where an object belongs, for
example) is an `INVALID_RESPONSE` error rather than an empty record. Status
107, 108 and 111 are empty results: `null`, or `[]` for list endpoints.
Python's mapping of the other documented codes to errors is kept. An
undocumented code is now an error too; Python returned the response's data as
a record.

Document bundles come back as the ZIP inline (under 10 MB) or as JPO's own
link to a larger archive. `downloadOversizeBundle` fetches that link only over
HTTPS on `jpo.go.jp` or a subdomain, without JPO credentials. Python fetched
whatever URL the response named. No recording shows an oversize response, so
which host JPO uses is unverified; a link elsewhere fails with a message naming
the host.

The response cache uses Python's `jpo` cache name. JPO's recorded API
responses carry no `Cache-Control` and every request carries `Authorization`,
so under RFC 9111 nothing is stored ([cache](cache.md)).

## Evidence

[`scripts/convert-jpo-cassettes.py`](../scripts/convert-jpo-cassettes.py)
turns the 33 Python cassettes (`tests/cassettes/tests_jpo_test_live_py_*.yaml`
at the repository root) into 23 Cassetter cassettes, one per distinct request.
They cover 21 of the 36 endpoints: all 14 patent endpoints, design progress,
J-PlatPat link, application documents and refusal notices, and trademark
progress, refusal notices and mailed documents. Seven are ZIP bundles and two
are no-data responses. The Python recorder had already
replaced the username, password and tokens. The converter checks for leftover
credentials and drops the authorization header and AWS request identifiers.

[`scripts/extract-jpo-python-output.py`](../scripts/extract-jpo-python-output.py)
runs Python's models and parser on each recorded body and writes
`tests/fixtures/jpo/python-output.json`. Every JSON endpoint normalizes
exactly as Python's models do. Bundles match Python except for the
corrections below. [Client tests](../tests/jpo-client.test.ts) also cover the
token lifecycle, status mapping, malformed data, path encoding, the oversize
host rule, the rate limiter and the parser's edge cases.
[MCP tests](../tests/jpo-mcp.test.ts) run every tool through a real client
and check scope enforcement on the authenticated HTTP listener.

The other 15 are design and trademark variants of priority, applicant,
number-reference, registration and simple-progress lookups, design mailed
documents, and trademark J-PlatPat links and application documents. They
share code with the recorded patent variants, but their field sets aren't
verified against a response.

## Python bugs corrected

- A refusal notice's reasons and its cited-document list are in
  `jp:drafting-body`, which Python never read. Its `body_text` stopped at the
  conclusion, which only introduces the reasons. The port appends the drafting
  body.
- `<br/>` is a line break. Python joined text across breaks, so a drafting
  body written as one line of breaks ran its paragraphs together.
- An HTM application number such as `意願２０２１−　１９５００` became
  `２０２１−`, because the pattern stopped at the full-width space. HTM numbers
  are now the API's 10-digit form (`2021019500`).
- HTM dates stayed as era strings (`令和　４年　３月１０日`) although the field
  is documented as YYYYMMDD. Era dates are now converted (`20220310`).
- Applicant-filed HTM got no document name. It is now read from the
  `【書類名】` line.
- The progress summary looked for camelCase and status keys that Python's
  records never have. Design and trademark titles read "(no title)", and every
  status read "(unknown status)". Summaries now use the register's title
  field and add the registration number and date when there is one.

Shift-JIS is decoded with the WHATWG decoder, which is Microsoft's cp932. Six
characters, such as byte 0x817C, map differently from the strict Shift-JIS
Python tries first. They are mapped back, so text matches Python. cp932-only
characters such as ① still decode.

## Differences from Python's MCP tools

`get_jpo_documents` returns a detail envelope: `details` holds the parsed
bundle and a `document` artifact (a single-use link, or a path under stdio)
for the raw ZIP. Python returned the bundle dictionary with its own signed URL
and also exposed a `pca://jpo/documents/...` resource. That resource isn't
ported, because artifacts already deliver the archive. An empty bundle is
still `{}`.

The list tools (`get_jpo_progress`, `get_jpo_progress_simple`,
`get_jpo_registration_info`) keep Python's behavior: up to 50 numbers, blanks
dropped, five requests at a time, input order kept, and missing numbers in
`not_found`.
