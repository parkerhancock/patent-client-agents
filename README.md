# IP Tools

**Give your AI agent access to the world's patent data.**

```bash
claude plugins add github:parkerhancock/ip_tools
```

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

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
| **USPTO ODP** | Applications, prosecution history, PTAB trials & appeals, assignments, bulk data |
| **EPO OPS** | European patents, Inpadoc families, legal events, EP Register, CPC classification |
| **JPO** | Japanese patents, examination history, PCT national phase |

All sources include automatic caching, rate limiting, and retry logic.

## Install

```bash
claude plugins add github:parkerhancock/ip_tools
```

That's it. Claude Code now has access to patent data through the `ip_research` skill.

### API Keys (Optional)

Some data sources require API keys for full access:

| Variable | Source | How to Get |
|----------|--------|------------|
| `EPO_OPS_API_KEY` | EPO | [Register at EPO](https://developers.epo.org/) |
| `EPO_OPS_API_SECRET` | EPO | [Register at EPO](https://developers.epo.org/) |
| `JPO_API_USERNAME` | JPO | [Register at JPO](https://www.j-platpat.inpit.go.jp/) |
| `JPO_API_PASSWORD` | JPO | [Register at JPO](https://www.j-platpat.inpit.go.jp/) |

Google Patents and USPTO work without API keys.

## As a Python Library

IP Tools is also a standalone async Python library:

```bash
pip install ip-tools
```

```python
from ip_tools.google_patents import GooglePatentsClient

async with GooglePatentsClient() as client:
    patent = await client.fetch("US10123456B2")
    print(patent.title)
    print(patent.abstract)

    results = await client.search("machine learning neural network")
    for patent in results:
        print(f"{patent.publication_number}: {patent.title}")
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
│                   ip_tools Library                           │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│    │  USPTO   │  │   EPO    │  │  Google  │  │   JPO    │   │
│    │   ODP    │  │   OPS    │  │ Patents  │  │          │   │
│    └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Development

```bash
git clone https://github.com/parkerhancock/ip_tools.git
cd ip_tools
uv sync --group dev
uv run pytest
uv run ruff check . && uv run ruff format .
```

## Related

- [patent_client](https://github.com/parkerhancock/patent_client) - The original patent data library this project builds on

## License

Apache-2.0
