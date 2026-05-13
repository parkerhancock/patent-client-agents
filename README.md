<p align="center">
  <img src="docs/_static/patent_client_agents_logo.png" alt="patent-client-agents" width="600">
</p>

**Give your AI agent access to the world's patent and trademark data.**

[![CI](https://github.com/parkerhancock/patent-client-agents/actions/workflows/ci.yml/badge.svg)](https://github.com/parkerhancock/patent-client-agents/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-docs.patentclient.com-008cc8.svg)](https://docs.patentclient.com/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

**Full documentation: [docs.patentclient.com](https://docs.patentclient.com/)**

## Use the hosted demo

The fastest path — nothing to install. Point your MCP-speaking client
at the public demo at **[mcp.patentclient.com](https://mcp.patentclient.com)**:

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "url": "https://mcp.patentclient.com/mcp"
    }
  }
}
```

Or add a custom connector in CoWork / Claude Desktop with just the URL
`https://mcp.patentclient.com/mcp` — no tokens to paste. On first
connect you'll be sent to Google sign-in; approve and you're in. Any
verified Google account works. Usage is rate-limited per account
(100 MB/day, 20 MB/minute).

This is a public demo — don't send confidential material through it.
See the [Terms of Use](https://mcp.patentclient.com/terms).

## Or install locally (Claude Code plugin)

```
/plugin marketplace add parkerhancock/patent-client-agents
/plugin install patent-client-agents@patent-client-agents
/reload-plugins
```

See [docs.patentclient.com/installation](https://docs.patentclient.com/installation/) for all seven install modes.

---

## What You Can Do

Ask Claude to research patents and trademarks in natural language:

> "Find [Company]'s recent battery patents and summarize the key innovations"

> "What's the prosecution history for US Patent 11,234,567?"

> "Compare [Company A] and [Company B]'s patent portfolios in mobile display technology"

> "Track the legal status of EP3456789 across all designated states"

> "What's the current status of trademark serial 97123456, and who filed it?"

> "Search the TMEP for guidance on Section 2(d) likelihood-of-confusion refusals"

`patent-client-agents` connects Claude Code to USPTO (patents and trademarks), EPO, Google Patents, and JPO, giving your agent the ability to search, analyze, and report on intellectual property worldwide. JPO MCP tools register on the local stdio server and the Claude Code plugin when `JPO_API_USERNAME` and `JPO_API_PASSWORD` are set; the hosted demo at `mcp.patentclient.com` does not carry JPO credentials, so JPO tools don't appear there.

## Coverage

| Source | What You Get |
|--------|--------------|
| **Google Patents** | Global search, full-text, citations, PDFs, families |
| **USPTO ODP** | Applications, prosecution history, PTAB trials & appeals, petitions, bulk data |
| **USPTO Publications** | Patent Public Search (PPUBS) full-text search and document retrieval |
| **USPTO Assignments** | Patent ownership transfers and reel/frame lookups |
| **USPTO Office Actions** | Rejection analytics, cited references, full-text OA retrieval |
| **USPTO TSDR** | Trademark Status & Document Retrieval — status, docs, mark images |
| **USPTO Trademark Assignments** | Trademark ownership transfers (Assignment Center) |
| **EPO OPS** | European patents, Inpadoc families, legal events, EP Register |
| **JPO** | Japanese patents, examination history, PCT national phase — *MCP tools register when `JPO_API_USERNAME` + `JPO_API_PASSWORD` are set; not exposed by the hosted demo* |
| **MPEP** | Manual of Patent Examining Procedure search and section lookup — *runs against a local SQLite/FTS5 snapshot built by `patent-client-agents-build-mpep-corpus`; see docs/installation.md* |
| **TMEP** | Trademark Manual of Examining Procedure search and section lookup — *runs against a local SQLite/FTS5 snapshot built by `patent-client-agents-build-tmep-corpus`; see docs/installation.md* |
| **CPC** | Classification hierarchy lookup, search, and CPC/IPC mapping |
| **CanLII** | Canadian courts, tribunals, and IP statutes — Federal Court / FCA / Supreme Court IP rulings, Trade-marks Opposition Board, Patent Appeal Board, Patent Act, Trademarks Act with point-in-time queries — *MCP tools register when `CANLII_API_KEY` is set; not exposed by the hosted demo* |
| **WIPO Lex** | Global IP statute / treaty / judgment database curated by WIPO — ~50k legal documents across ~200 jurisdictions, six UN languages. v0.9 scope: legislation collection (search + detail with PDF links) |

All sources include automatic caching (hishel + SQLite with WAL), rate limiting,
and retry logic via `law_tools_core`.

## Install

For Claude Code users — run these inside a Claude Code session:

```
/plugin marketplace add parkerhancock/patent-client-agents
/plugin install patent-client-agents@patent-client-agents
/reload-plugins
```

Three slash commands (not shell). You get 51 patent + IP MCP tools
exposed to the agent by default (63 with JPO credentials in the
environment; 60 / 72 with `CANLII_API_KEY` also set). Prereq:
[uv](https://docs.astral.sh/uv/) on PATH — the MCP server runs under
`uvx` so you don't `pip install` anything yourself.

**Seven install modes are documented at [docs.patentclient.com/installation](https://docs.patentclient.com/installation/)**
— Python library, Python+MCP runtime, Claude Code plugin, dev symlink, stdio
MCP, Cowork remote MCP, and generic remote MCP. Pick the one that matches
how you'll use it.

### API keys

| Variable | Source | Required | How to get |
|----------|--------|----------|------------|
| `USPTO_ODP_API_KEY` | USPTO ODP | Most USPTO patent tools | [developer.uspto.gov](https://developer.uspto.gov/) (free) |
| `USPTO_TSDR_API_KEY` | USPTO TSDR | All TSDR trademark tools | [account.uspto.gov/api-manager/](https://account.uspto.gov/api-manager/) (free MyUSPTO account) |
| `EPO_OPS_API_KEY`, `EPO_OPS_API_SECRET` | EPO OPS | All EPO tools | [developers.epo.org](https://developers.epo.org/) (free) |
| `JPO_API_USERNAME`, `JPO_API_PASSWORD` | JPO | All JPO library + MCP tools (env-gated on the stdio server / plugin; not set on the hosted demo) | [j-platpat.inpit.go.jp](https://www.j-platpat.inpit.go.jp/) |
| `CANLII_API_KEY` | CanLII | All CanLII library + MCP tools (env-gated on the stdio server / plugin; not set on the hosted demo) | [canlii.org/en/feedback/feedback.html](https://www.canlii.org/en/feedback/feedback.html) (free, by request) |

**No API key needed:** Google Patents, USPTO Publications (PPUBS), USPTO
Assignments, USPTO Trademark Assignments, MPEP, TMEP, CPC, WIPO Lex.

## Quickstart — Python library

```bash
pip install patent-client-agents
```

```python
from patent_client_agents.google_patents import GooglePatentsClient

async with GooglePatentsClient() as client:
    patent = await client.get_patent_data("US10123456B2")
    print(patent.title)
    print(patent.abstract)

    results = await client.search_patents(keywords=["machine learning neural network"])
    for r in results.results:
        print(f"{r.publication_number}: {r.title}")
```

## Detailed Coverage

<details>
<summary><strong>Google Patents</strong></summary>

| Feature | Description |
|---------|-------------|
| Patent lookup | Fetch by publication number |
| Full-text search | Keyword, assignee, inventor search |
| Claims & description | Full-text content |
| Citations | Forward and backward citations |
| Patent families | Related applications |
| PDF download | Full document PDFs |

</details>

<details>
<summary><strong>USPTO Open Data Portal</strong></summary>

| Feature | Description |
|---------|-------------|
| **Applications** | |
| Application search | Search by number, date, status |
| Application details | Bibliographic data, status |
| Continuity data | Parent/child relationships |
| Foreign priority | Priority claims |
| Assignments | Ownership records |
| Attorneys | Attorney/agent of record |
| Transactions | Office action history |
| Adjustments | PTA/PTE data |
| **PTAB Trials** | |
| IPR/PGR/CBM search | Search inter partes reviews |
| Trial details | Party info, status, decisions |
| Trial documents | Petitions, responses, decisions |
| **PTAB Appeals** | |
| Appeal search | Ex parte appeals |
| Appeal details | Status, decisions |
| **Bulk Data** | |
| Bulk downloads | XML/JSON data packages |
| Full-text grants | Weekly patent grants |
| Full-text applications | Weekly applications |

</details>

<details>
<summary><strong>USPTO Assignments</strong></summary>

| Feature | Description |
|---------|-------------|
| Assignment search | Search by reel/frame, patent |
| Assignment details | Parties, conveyance type |
| Property lookup | Patents in assignment |

</details>

<details>
<summary><strong>USPTO TSDR (Trademark Status & Document Retrieval)</strong></summary>

| Feature | Description |
|---------|-------------|
| Status lookup | Mark text, filing/registration dates, current status |
| Prosecution documents | Office actions, responses, registration certificate |
| Mark images | Drawing JPGs by serial number |
| Batch status | Check many serial numbers in one call |
| Last-update timestamp | When the case record was last modified |

Requires `USPTO_TSDR_API_KEY`. Peak hours (5am–10pm ET): 60 req/min
general, 4 req/min PDF/ZIP. Off-peak doubles those limits.

</details>

<details>
<summary><strong>USPTO Trademark Assignments</strong></summary>

| Feature | Description |
|---------|-------------|
| Search by assignee | Company/person acquiring rights |
| Search by assignor | Company/person transferring rights |
| Search by serial / registration | Chain of title for a mark |
| Search by reel/frame | Direct recordation lookup |
| Pagination | `search_all` iterates the full result set |

No API key required.

</details>

<details>
<summary><strong>TMEP (Trademark Manual of Examining Procedure)</strong></summary>

| Feature | Description |
|---------|-------------|
| Section lookup | Get any TMEP section by number (e.g. `1207.01(a)`) |
| Full-text search | Keyword search with relevance ranking |
| Version listing | Snapshot label for the loaded corpus |

No API key required, but requires a one-time corpus build —
`patent-client-agents-build-tmep-corpus --output ~/.cache/patent_client_agents/tmep.db`
— before the first call. MPEP has the matching
`patent-client-agents-build-mpep-corpus` CLI. Cloud deployments point
`TMEP_CORPUS_PATH` / `MPEP_CORPUS_PATH` at any path. See
[docs/installation.md](docs/installation.md#mpep--tmep-corpus-setup).

</details>

<details>
<summary><strong>EPO OPS</strong></summary>

| Feature | Description |
|---------|-------------|
| **Published Data (Inpadoc)** | |
| Patent search | CQL query search |
| Family search | Search grouped by family |
| Bibliographic data | Titles, abstracts, parties |
| Claims | Full claim text |
| Description | Full description text |
| Legal events | Status changes, fees |
| Patent families | INPADOC family members |
| PDF download | Full document PDFs |
| Number conversion | Format conversion |
| **EP Register** | |
| Register search | Search EP applications |
| Register biblio | Detailed EP data |
| Procedural steps | Prosecution history |
| Register events | EPO Bulletin events |
| Designated states | Validation countries |
| Opposition data | Opposition proceedings |
| Unitary Patent | UPP status and states |
| **Classification** | |
| CPC lookup | Classification hierarchy |
| CPC search | Keyword search |
| CPC mapping | CPC/IPC/ECLA conversion |

</details>

<details>
<summary><strong>JPO (Japan Patent Office)</strong></summary>

> **JPO MCP tools are env-gated.** The local stdio MCP server and the
> Claude Code plugin register 12 JPO MCP tools (plus the
> `pca://jpo/documents/...` resource template) when `JPO_API_USERNAME`
> and `JPO_API_PASSWORD` are set in the server's env. The hosted demo
> at `mcp.patentclient.com` does not carry JPO credentials, so JPO
> tools don't appear there. The Python library's `JpoClient` works
> the same way — credentials are read from env on first use.

| Feature | Description |
|---------|-------------|
| Patent progress | Application status |
| Examination history | Office actions |
| Documents | Filed documents |
| Citations | Cited prior art |
| Family info | Divisionals, priorities |
| Registration | Grant details |
| PCT national phase | JP national entry lookup |
| Design/trademark | Similar methods available |

</details>

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Claude Code Agent                        │
├─────────────────────────────────────────────────────────────┤
│               patent-client-agents MCP Server                │
│              (Natural language → API calls)                  │
├─────────────────────────────────────────────────────────────┤
│              patent_client_agents Python library             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │
│  │  USPTO  │ │  USPTO  │ │   EPO   │ │ Google  │ │  JPO*  │ │
│  │ patents │ │  marks  │ │   OPS   │ │ Patents │ │        │ │
│  │ ODP+    │ │TSDR+TM  │ │  + CPC  │ │  +MPEP  │ │        │ │
│  │ PPUBS   │ │assigns  │ │         │ │  +TMEP  │ │        │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └────────┘ │
└─────────────────────────────────────────────────────────────┘
* JPO MCP tools register when JPO_API_USERNAME + JPO_API_PASSWORD are set
  on the server; the hosted demo does not carry these credentials.
```

## Development

```bash
git clone https://github.com/parkerhancock/patent-client-agents.git
cd patent-client-agents
uv sync --group dev
uv run pytest                       # 1,056 tests, replays VCR cassettes
uv run ruff check . && uv run ruff format .
```

Tests use [vcrpy](https://vcrpy.readthedocs.io) to replay recorded HTTP interactions
without hitting live APIs. Record modes:
```bash
uv run pytest --vcr-record=once     # Record missing cassettes
uv run pytest --vcr-record=all      # Re-record everything
uv run pytest --run-live-uspto      # Skip VCR, hit live USPTO
uv run pytest --run-live-jpo        # Skip VCR, hit live JPO
```

API errors follow a log-first pattern — concise messages with a path to
`~/.cache/patent_client_agents/patent_client_agents.log` for full stacktraces.

The shared HTTP scaffolding (`BaseAsyncClient`, cache, exceptions, retry,
logging) ships as the `law_tools_core` package inside this same wheel —
other libraries in the same family import it directly.

## Related

- [patent_client](https://github.com/parkerhancock/patent_client) - The original patent data library this project builds on

## License

Apache-2.0
