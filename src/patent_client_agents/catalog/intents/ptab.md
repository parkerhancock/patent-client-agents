# PTAB (trials, appeals, interferences)

Unified surface over USPTO ODP's PTAB endpoints. 15 original tools
collapsed to 4 via type discriminators on search, get, and list-by-parent
shapes.

## Tribunal types

The `type` discriminator surfaces legally distinct tribunals — don't treat
them interchangeably:

- **`proceeding`** — AIA trial proceedings (IPR, PGR, CBM, DER). Identified
  by trial number like `IPR2024-00001`.
- **`trial_decision`** — decisions issued in an AIA trial. Identified by
  document identifier.
- **`trial_document`** — documents filed in an AIA trial (petitions,
  responses, orders, etc.). Identified by document identifier.
- **`appeal_decision`** — ex parte appeal decisions (Board decisions on
  examiner rejections). Legally different from AIA trials; keyed by
  application number for listing, document identifier for single lookup.
- **`interference_decision`** — pre-AIA interference decisions. Legacy
  proceedings; keyed by interference number for listing, document
  identifier for single lookup.

## MCP tools

### `search_ptab(type, query, limit, offset, full, next_cursor)`

Search any of the five types by query. Returns lean records in a list envelope;
use `full=True` for full records or `get_ptab` for selected records. Pass the
returned `next_cursor` with the same type and query to continue. The cursor
carries the next offset and page size, overriding `offset` and `limit`, with no
server-side session. `more_available=False` means the source query has ended;
the index is not a frozen snapshot. A missing or contradictory upstream count
raises a source error rather than claiming completion.

```python
# AIA trials mentioning "machine learning":
search_ptab(type="proceeding", query="machine learning")

# Ex parte appeals by a specific applicant:
search_ptab(type="appeal_decision", query="applicant:\"Anthropic PBC\"")
```

### `get_ptab(type, identifier)`

Fetch a single PTAB record by identifier.

- `type="proceeding"` → `identifier` is a trial number (`IPR2024-00001`).
- All other types → `identifier` is a document identifier from the
  corresponding `search_ptab` response.

```python
get_ptab(type="proceeding", identifier="IPR2024-00001")
get_ptab(type="trial_decision", identifier="document-id-here")
```

### `list_ptab_children(parent_type, parent_identifier, include)`

List decisions or documents attached to a parent record.

| `parent_type` | `parent_identifier` | valid `include` |
|---|---|---|
| `trial` | Trial number (`IPR2024-00001`) | `decisions`, `documents`, `both` |
| `application` | USPTO application number | `decisions` only (appeals) |
| `interference` | Interference number | `decisions` only |

```python
# All decisions + documents in an AIA trial:
list_ptab_children(parent_type="trial", parent_identifier="IPR2024-00001", include="both")

# Appeals for a specific application:
list_ptab_children(parent_type="application", parent_identifier="16123456")
```

### Bulk downloads (container-scoped)

Four tools, one per API container, each returning a zip (n=1 → raw PDF)
plus a manifest. Enumerate candidates with `list_ptab_children` /
`list_file_history` / etc., filter by `item_ids` or date range if
needed, then call the bulk tool.

| Tool | Container | Cap |
|------|-----------|-----|
| `download_ptab_trial_documents(trial_number, …)` | All party filings in one AIA trial (petitions, responses, exhibits, motions) | 100 |
| `download_ptab_trial_decisions(trial_number, …)` | All board decisions in one AIA trial (institution, scheduling orders, FWD) | 50 |
| `download_ptab_appeal_decisions(application_number, …)` | All ex parte appeal decisions for one application | 50 |
| `download_ptab_interference_decisions(interference_number, …)` | All decisions for one pre-AIA interference | 50 |

The former `download_ptab_document` (single trial document) was removed —
use `download_ptab_trial_documents(trial_number, item_ids=[document_identifier])`
to fetch one paper, or the general bulk form to grab a set.

## Python API (raw)

Source-specific methods on `UsptoOdpClient` remain for direct Python use:

```python
from patent_client_agents.uspto_odp import UsptoOdpClient

async with UsptoOdpClient() as client:
    # Search
    proceedings = await client.search_trial_proceedings(query="...")
    decisions = await client.search_trial_decisions(query="...")
    documents = await client.search_trial_documents(query="...")
    appeals = await client.search_appeal_decisions(query="...")
    interferences = await client.search_interference_decisions(query="...")

    # Lookup
    proceeding = await client.get_trial_proceeding(trial_number)
    decision = await client.get_trial_decision(document_identifier)
    # (... similar getters for appeal_decision, interference_decision, trial_document)

    # List by parent
    trial_decisions = await client.get_trial_decisions_by_trial(trial_number)
    trial_documents = await client.get_trial_documents_by_trial(trial_number)
    application_appeals = await client.get_appeal_decisions_by_number(application_number)
    interference_decisions = await client.get_interference_decisions_by_number(interference_number)
```

No library-level fusion — the MCP discriminators dispatch directly to these
client methods. Python consumers already have the granular API.
