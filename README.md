# IP Tools

**Give your AI agent access to the world's patent data.**

[![CI](https://github.com/parkerhancock/patent-client-agents/actions/workflows/ci.yml/badge.svg)](https://github.com/parkerhancock/patent-client-agents/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/parkerhancock/patent-client-agents/branch/main/graph/badge.svg)](https://codecov.io/gh/parkerhancock/patent-client-agents)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

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

See [docs/installation.md](docs/installation.md) for all seven install modes.

---

## What You Can Do

Ask Claude to research patents in natural language:

> "Find Tesla's recent battery patents and summarize the key innovations"

> "What's the prosecution history for US Patent 11,234,567?"

> "Compare Apple and Samsung's patent portfolios in mobile display technology"

> "Track the legal status of EP3456789 across all designated states"

IP Tools connects Claude Code to USPTO, EPO, JPO, and Google Patents, giving your agent the ability to search, analyze, and report on intellectual property worldwide.

## Coverage

| Source | What You Get |
|--------|--------------|
| **Google Patents** | Global search, full-text, citations, PDFs, families |
| **USPTO ODP** | Applications, prosecution history, PTAB trials & appeals, petitions, bulk data |
| **USPTO Publications** | Patent Public Search (PPUBS) full-text search and document retrieval |
| **USPTO Assignments** | Patent ownership transfers and reel/frame lookups |
| **USPTO Office Actions** | Rejection analytics, cited references, full-text OA retrieval |
| **EPO OPS** | European patents, Inpadoc families, legal events, EP Register |
| **JPO** | Japanese patents, examination history, PCT national phase |
| **MPEP** | Manual of Patent Examining Procedure search and section lookup |
| **CPC** | Classification hierarchy lookup, search, and CPC/IPC mapping |

All sources include automatic caching (hishel + SQLite with WAL), rate limiting,
and retry logic via `law_tools_core`.

## Install

For Claude Code users — run these inside a Claude Code session:

```
/plugin marketplace add parkerhancock/patent-client-agents
/plugin install patent-client-agents@patent-client-agents
/reload-plugins
```

Three slash commands (not shell). You get all 63 patent MCP tools
exposed to the agent. Prereq: [uv](https://docs.astral.sh/uv/) on
PATH — the MCP server runs under `uvx` so you don't `pip install`
anything yourself.

**Seven install modes are documented in [docs/installation.md](docs/installation.md)**
— Python library, Python+MCP runtime, Claude Code plugin, dev symlink, stdio
MCP, Cowork remote MCP, and generic remote MCP. Pick the one that matches
how you'll use it.

### API keys

| Variable | Source | Required | How to get |
|----------|--------|----------|------------|
| `USPTO_ODP_API_KEY` | USPTO ODP | Most USPTO tools | [developer.uspto.gov](https://developer.uspto.gov/) (free) |
| `EPO_OPS_API_KEY`, `EPO_OPS_API_SECRET` | EPO OPS | All EPO tools | [developers.epo.org](https://developers.epo.org/) (free) |
| `JPO_API_USERNAME`, `JPO_API_PASSWORD` | JPO | JPO tools only | [j-platpat.inpit.go.jp](https://www.j-platpat.inpit.go.jp/) |

**No API key needed:** Google Patents, USPTO Publications (PPUBS), USPTO
Assignments, MPEP, CPC.

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
│                    IP Tools MCP Server                       │
│              (Natural language → API calls)                  │
├─────────────────────────────────────────────────────────────┤
│                   patent_client_agents Library                           │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│    │  USPTO   │  │   EPO    │  │  Google  │  │   JPO    │   │
│    │   ODP    │  │   OPS    │  │ Patents  │  │          │   │
│    └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Development

```bash
git clone https://github.com/parkerhancock/patent-client-agents.git
cd patent_client_agents
uv sync --group dev
uv run pytest                       # 767 tests, replays VCR cassettes
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
