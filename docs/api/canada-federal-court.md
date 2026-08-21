# Canada Federal Court case files

Read-only access to the official [Federal Court Court Files](https://www-u.fct-cf.gc.ca/en/court-files-and-decisions/court-files) service. This is live case-file and recorded-docket data, not CanLII's published-decision collection.

No API key is required. The connector uses the same public JSON requests as the Court's own search page and keeps a short cache because docket entries change.

```python
from patent_client_agents.canada_federal_court import CanadaFederalCourtClient

async with CanadaFederalCourtClient() as client:
    cases = await client.search_party_cases("Pfizer", patent_only=True)
    docket = await client.list_docket_entries(cases.cases[0].court_number)
```

The MCP surface provides:

- `search_canada_federal_court_patent_cases` — party/corporation search across both sides, with patent-nature filtering and optional docket-status assessment
- `get_canada_federal_court_case` — exact file metadata, parties and public counsel, IP references, and related cases
- `list_canada_federal_court_docket_entries` — recorded entries newest first, including public document links when the Court permits download

## Status limitation

The Court's search response does not contain an authoritative pending, closed, or disposed field. The connector reports only `likely_pending`, `likely_closed`, or `unknown`, based on explicit language in recent recorded entries. Every such result is marked `inferred`; `unknown` must not be read as “no pending litigation.”

The Court also does not reliably assign plaintiff/defendant roles to every named party in the public JSON. The connector returns the official style of cause and party list without inventing roles.
