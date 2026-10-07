# Federal Circuit (CAFC)

Read-only access to opinions from the US Court of Appeals for the Federal Circuit. The CAFC hears virtually every appeal in a US patent case — plus ITC §337, government-contract, veterans, and trademark TTAB appeals. The connector wraps the court's WordPress DataTables API, classifies each opinion as patent-related via keyword scoring, and serves opinion PDFs through the shared `pca://cafc/...` download channel.

## Source

| | |
|---|---|
| Module | `patent_client_agents.cafc` |
| Client | `CAFCClient` |
| Base URL | `https://www.cafc.uscourts.gov` |
| Auth | None — WordPress nonce scraped from the opinions page on session init |
| Rate limits | Not published; client uses BaseAsyncClient SQLite cache and a desktop Chrome User-Agent (CAFC's edge blocks plain Python UAs with 403 on the AJAX endpoint) |
| Status | Active |

## Authentication

None. The client `__aenter__` step fetches `/home/case-information/opinions-orders/` and extracts the `wdtNonceFrontendServerSide_1` hidden input via regex, then feeds that nonce on every subsequent `wp-admin/admin-ajax.php` request.

## API Endpoints

| Path | Method | Coverage |
|---|---|---|
| `/home/case-information/opinions-orders/` | GET | Opinions HTML page; nonce extraction |
| `/wp-admin/admin-ajax.php?action=get_wdtable&table_id=1` | POST | DataTables search (form-encoded `draw`, `start`, `length`, `search[value]`, column filters, `wdtNonce`) |
| `/<file_path>` | GET | Opinion PDF download (absolute path returned in each row) |

## Library API

```python
from datetime import date
from patent_client_agents.cafc import CAFCClient, PatentClassifier

async with CAFCClient() as client:
    # Patent-origin opinions for the year
    opinions = await client.search_patent_opinions(date_from=date(2025, 1, 1))

    # Free-text + origin filter
    pto_ipr = await client.search(query="IPR", origins=["PTO"], max_results=50)

    # Download a specific opinion's PDF
    pdf = await client.download_pdf(opinions[0])
```

### Methods

| Method | Description |
|---|---|
| `search(query, date_from, date_to, origins, max_results)` | Search the DataTables index with free-text + date + origin filters |
| `search_patent_opinions(date_from, date_to, max_results)` | Convenience: pre-filter origins to `PTO`/`DCT`/`ITC`/`CFC` |
| `recent(days)` | Convenience: last *N* days, all origins |
| `download_pdf(opinion, output_path)` | Fetch the opinion PDF bytes; optional disk write |

## Patent classifier

`PatentClassifier.classify(case_name, text_content=None)` returns `(is_patent, confidence, matched_keywords)`. Weighs categories — strong indicators (e.g. "patent", "USPTO", "PTAB"), statute refs (`35 U.S.C. § 103`), technical terms ("infringement", "claim construction") — and filters false positives like "patient care", "patent leather". Threshold is 0.5.

## MCP Tools

| Tool | Description |
|---|---|
| `search_cafc_opinions` | Free-text search + optional `patent_only` filter |
| `search_cafc_patent_opinions` | Pre-filtered to patent-origin appeals (PTO/DCT/ITC/CFC) |
| `download_cafc_pdf` | Fetch an opinion PDF by appeal number; returns a signed `download_url` |

The `download_cafc_pdf` tool registers a `pca://cafc/opinions/{appeal_number}` download fetcher so resource-aware MCP clients (CoWork) can stream the PDF via `resources/read` instead of the HTTP `download_url`.

Exact document retrieval: pass `document_url` from a discovery row to
`download_cafc_pdf`. The URL identifies the document separately from its appeal;
ambiguous appeal-only requests fail. Each call fetches current bytes and returns
`content_sha256`, `bytes_retrieved_at`, and `source_checked_at`. Downloads are
stored under a content-addressed path so replacements do not overwrite older
returned artifacts. Compare hashes across observations to detect same-URL byte
changes; the connector does not infer legal supersession from a hash change.
