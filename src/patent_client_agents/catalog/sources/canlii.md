# CanLII

Read-only Canadian case-law and legislation API. Covers federal + provincial courts, tribunals, statutes, regulations, and a citator (citing + cited cases / legislation). The IP-relevant slice includes the Federal Court, Federal Court of Appeal, and Supreme Court of Canada (patent and trademark infringement / validity rulings), the Trade-marks Opposition Board (TMOB), the Commissioner of Patents — Patent Appeal Board, plus the Patent Act, Trademarks Act, Industrial Design Act, Copyright Act, and PBR Act with point-in-time entry-into-force / repeal markers.

## Source

| | |
|---|---|
| Module | `patent_client_agents.canlii` |
| Client | `CanLIIClient` |
| Base URL | `https://api.canlii.org/v1` |
| Auth | `CANLII_API_KEY` |
| Rate limits | Not published numerically; high-volume scraping discouraged; keys revocable |
| Status | Active |

## Authentication

Free API key by request via the [CanLII feedback form](https://www.canlii.org/en/feedback/feedback.html). Provide a brief description of intended use. Set `CANLII_API_KEY` in the environment, or pass `api_key=...` to `CanLIIClient`. The MCP tools are env-gated: they only register when `CANLII_API_KEY` is present (matches the JPO pattern).

## Rate Limits

CanLII does not publish numeric rate limits. The terms warn against high-volume scraping and reserve the right to revoke keys. Plan for low single-digit RPS on production usage and back off aggressively on any throttling response. Responses larger than 10 MB return a `TOO_LONG` envelope that surfaces as `ApiError(413)`; for legislation with long text, page through `content` parts.

## API Endpoints

| Path | Method | Coverage |
|---|---|---|
| `/v1/caseBrowse/{lang}/` | GET | List court / tribunal databases |
| `/v1/caseBrowse/{lang}/{databaseId}/` | GET | Browse cases in a database (offset + date filters) |
| `/v1/caseBrowse/{lang}/{databaseId}/{caseId}/` | GET | Case metadata |
| `/v1/caseCitator/en/{databaseId}/{caseId}/citedCases` | GET | Cases this one cites |
| `/v1/caseCitator/en/{databaseId}/{caseId}/citingCases` | GET | Cases that cite this one |
| `/v1/caseCitator/en/{databaseId}/{caseId}/citedLegislations` | GET | Legislation this case cites |
| `/v1/legislationBrowse/{lang}/` | GET | List legislation databases |
| `/v1/legislationBrowse/{lang}/{databaseId}/` | GET | Browse statutes / regulations in a database |
| `/v1/legislationBrowse/{lang}/{databaseId}/{legislationId}/` | GET | Legislation metadata |

The citator is English-only; everything else accepts `en` or `fr`.

## Library API

```python
from patent_client_agents.canlii import (
    BrowseCasesInput,
    CanLIIClient,
    GetCaseInput,
    browse_cases,
    get_case,
)

# Last 20 TMOB decisions
cases = await browse_cases(BrowseCasesInput(database_id="tmob-comc", result_count=20))

# Federal Court IP cases filed after 2024-01-01
recent_fct = await browse_cases(
    BrowseCasesInput(database_id="fct", result_count=100, published_after="2024-01-01")
)

# Detailed view
case = await get_case(GetCaseInput(database_id="fct", case_id="2024fc12345"))

# Patent Act
from patent_client_agents.canlii import GetLegislationInput, get_legislation
act = await get_legislation(
    GetLegislationInput(database_id="cas", legislation_id="rsc-1985-c-p-4")
)
```

### Methods

| Method | Description |
|---|---|
| `list_case_databases()` | All court / tribunal databases |
| `browse_cases(database_id, ...)` | Paginated case list with `publishedBefore/After`, `modifiedBefore/After`, `changedBefore/After`, `decisionDateBefore/After` filters |
| `get_case(database_id, case_id)` | Case metadata: title, citation, docket, decision date, keywords, canonical URL |
| `get_cited_cases(database_id, case_id)` | Citator: cases this one cites |
| `get_citing_cases(database_id, case_id)` | Citator: cases that cite this one |
| `get_cited_legislations(database_id, case_id)` | Citator: legislation cited |
| `list_legislation_databases()` | Statutes / regulations / annual-statutes databases |
| `browse_legislation(database_id)` | List statutes / regulations within a database |
| `get_legislation(database_id, legislation_id)` | Legislation metadata: title, citation, type, dates, repealed flag, parts |

## MCP Tools

| Tool | Description |
|---|---|
| `list_canlii_case_databases` | List courts / tribunals |
| `search_canlii_cases` | Filter-driven case listing (date / language windows) |
| `get_canlii_case` | Case metadata |
| `get_canlii_cited_cases` | Cases cited by `case_id` |
| `get_canlii_citing_cases` | Cases citing `case_id` |
| `get_canlii_cited_legislations` | Legislation cited by `case_id` |
| `list_canlii_legislation_databases` | List statute / regulation databases |
| `search_canlii_legislation` | List statutes within a database |
| `get_canlii_legislation` | Statute / regulation metadata |

All tools env-gate on `CANLII_API_KEY` — they are absent from `tool/list` on deployments that don't carry the key.

## Related Docs

- Survey: [research/connectors/cipo.md](../../../../research/connectors/cipo.md) (CanLII was the standout finding in the CIPO survey)
