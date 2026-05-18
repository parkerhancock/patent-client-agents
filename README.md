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

The fastest path — nothing to install. Point any MCP-speaking client
(Claude Code, OpenAI Codex CLI, Google Gemini CLI, Cursor, Windsurf,
Cline, Zed, Continue.dev, VS Code Copilot Chat, JetBrains AI, Claude
Desktop, ChatGPT Apps, Replit Agent, CoWork, …) at the public demo at
**[mcp.patentclient.com](https://mcp.patentclient.com)**:

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "url": "https://mcp.patentclient.com/mcp"
    }
  }
}
```

Most clients also expose a "custom connector" / "add MCP server" UI
that takes just the URL `https://mcp.patentclient.com/mcp` — no tokens
to paste. On first connect you'll be sent to Google sign-in; approve
and you're in. Any verified Google account works. Usage is
rate-limited per account (100 MB/day, 20 MB/minute).

This is a public demo — don't send confidential material through it.
See the [Terms of Use](https://mcp.patentclient.com/terms).

## Or install locally

`patent-client-agents` is an MCP server, so it works with **any
MCP-speaking client** — Claude Code, OpenAI Codex CLI, Google Gemini
CLI, Cursor, Windsurf, Cline, Zed, Continue.dev, VS Code Copilot Chat,
JetBrains AI Assistant, Claude Desktop, ChatGPT (remote URL), and
Replit Agent (remote URL). Three install paths cover everything:

### Path A — Claude Code plugin (one-liner)

```
/plugin marketplace add parkerhancock/patent-client-agents
/plugin install patent-client-agents@patent-client-agents
/reload-plugins
```

### Path B — Any other MCP client

```bash
pip install 'patent-client-agents[mcp]'
```

This puts `patent-client-agents-mcp` on PATH. Point your client's MCP
config at it:

<details>
<summary><strong>OpenAI Codex CLI</strong> — <code>~/.codex/config.toml</code></summary>

```toml
[mcp_servers.patent-client-agents]
command = "patent-client-agents-mcp"
env = { USPTO_ODP_API_KEY = "…" }
```

Or use the CLI: `codex mcp add patent-client-agents --env USPTO_ODP_API_KEY=… -- patent-client-agents-mcp`.
</details>

<details>
<summary><strong>Google Gemini CLI</strong> — <code>~/.gemini/settings.json</code></summary>

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "command": "patent-client-agents-mcp",
      "env": { "USPTO_ODP_API_KEY": "$USPTO_ODP_API_KEY" }
    }
  }
}
```

Gemini interpolates `$VAR` / `${VAR}` from the parent shell (note: `.env`
files in the project root are *not* loaded — variables must be in the
actual environment).
</details>

<details>
<summary><strong>Cursor / Windsurf / Cline / Claude Desktop / JetBrains AI</strong> — same JSON shape</summary>

All five use the same `mcpServers` schema; only the config file path differs:

| Client | Config file |
|---|---|
| Cursor | `~/.cursor/mcp.json` (or project-level `.cursor/mcp.json`) |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` (uses `serverUrl` instead of `url` for remote) |
| Cline | extension UI → "Configure MCP Servers" |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS), `%APPDATA%\Claude\claude_desktop_config.json` (Windows) |
| JetBrains AI Assistant | Settings → Tools → AI Assistant → MCP → Add |

```json
{
  "mcpServers": {
    "patent-client-agents": {
      "command": "patent-client-agents-mcp",
      "env": { "USPTO_ODP_API_KEY": "…" }
    }
  }
}
```
</details>

<details>
<summary><strong>VS Code Copilot Chat (Agent mode)</strong> — <code>.vscode/mcp.json</code></summary>

VS Code uses `servers` (not `mcpServers`) and requires a `type` field:

```json
{
  "servers": {
    "patent-client-agents": {
      "type": "stdio",
      "command": "patent-client-agents-mcp",
      "env": { "USPTO_ODP_API_KEY": "${input:uspto-odp-key}" }
    }
  },
  "inputs": [
    { "id": "uspto-odp-key", "type": "promptString", "description": "USPTO ODP API key", "password": true }
  ]
}
```

Tools only appear in Copilot's **Agent mode**, not in Ask or Edit.
</details>

<details>
<summary><strong>Zed</strong> — <code>~/.config/zed/settings.json</code></summary>

Zed calls them "context servers":

```json
{
  "context_servers": {
    "patent-client-agents": {
      "source": "custom",
      "command": "patent-client-agents-mcp",
      "env": { "USPTO_ODP_API_KEY": "…" }
    }
  }
}
```
</details>

<details>
<summary><strong>Continue.dev</strong> — <code>~/.continue/config.yaml</code></summary>

YAML, with `${{ secrets.NAME }}` for secret references:

```yaml
mcpServers:
  - name: patent-client-agents
    command: patent-client-agents-mcp
    env:
      USPTO_ODP_API_KEY: ${{ secrets.USPTO_ODP_API_KEY }}
```
</details>

<details>
<summary><strong>ChatGPT Apps / Replit Agent</strong> (remote URL only)</summary>

These clients are cloud-hosted and can't spawn local subprocesses. Either
point them at the hosted demo via their UI:

```
https://mcp.patentclient.com/mcp
```

…or self-host `patent-client-agents-mcp` behind an HTTPS endpoint. For
ChatGPT: Settings → Connectors → enable Developer mode → Create. For
Replit: Integrations → MCP Servers for Replit Agent → Add MCP server.
</details>

### Path C — Python library

```bash
pip install patent-client-agents
```

Direct async use from your own Python — no MCP runtime needed.

See [docs.patentclient.com/installation](https://docs.patentclient.com/installation/)
for the full per-client reference, remote-MCP setup, and corpus-build steps.

---

## What You Can Do

Ask your agent to research patents and trademarks in natural language:

> "Find [Company]'s recent battery patents and summarize the key innovations"

> "What's the prosecution history for US Patent 11,234,567?"

> "Compare [Company A] and [Company B]'s patent portfolios in mobile display technology"

> "Track the legal status of EP3456789 across all designated states"

> "What's the current status of trademark serial 97123456, and who filed it?"

> "Search the TMEP for guidance on Section 2(d) likelihood-of-confusion refusals"

`patent-client-agents` connects your MCP-speaking agent to USPTO (patents, trademark search via TESS, and trademark prosecution), EPO, EUIPO (EU trademarks and designs), Google Patents, and JPO — plus the Federal Circuit, US International Trade Commission (Section 337), the US Copyright Office, and the Unified Patent Court (decisions feed + statutes corpus) for the litigation and adjacent-IP slice. JPO, CanLII, and EUIPO MCP tools register on the local stdio server and the Claude Code plugin only when their credentials are set in the environment; the hosted demo at `mcp.patentclient.com` does not carry those credentials, so those tool families don't appear there.

## Coverage

| Source | What You Get |
|--------|--------------|
| **Google Patents** | Global search, full-text, citations, PDFs, families |
| **USPTO ODP** | Applications, prosecution history, PTAB trials & appeals, petitions, bulk data |
| **USPTO Publications** | Patent Public Search (PPUBS) full-text search and document retrieval |
| **USPTO Assignments** | Patent ownership transfers and reel/frame lookups |
| **USPTO Office Actions** | Rejection analytics, cited references, full-text OA retrieval |
| **USPTO TSDR** | Trademark Status & Document Retrieval — status, docs, mark images |
| **USPTO Trademark Search (TESS)** | Live trademark register — search by wordmark, owner, goods/services — *requires the `[tmsearch]` extra (Playwright + curl_cffi) or a bring-your-own WAF token via `PCA_WAF_TOKEN_*`* |
| **USPTO Trademark Assignments** | Trademark ownership transfers (Assignment Center) |
| **EPO OPS** | European patents, Inpadoc families, legal events, EP Register |
| **IP Australia** | Australian patents, trade marks, and registered designs from IP Australia's OAuth 2.0 search APIs, plus the weekly IP RAPID bulk catalog on data.gov.au (CC-BY 4.0) — *live-search MCP tools register when `IPAUSTRALIA_CLIENT_ID` + `IPAUSTRALIA_CLIENT_SECRET` are set; bulk catalog is public, no auth* |
| **JPO** | Japanese patents, examination history, PCT national phase — *MCP tools register when `JPO_API_USERNAME` + `JPO_API_PASSWORD` are set; not exposed by the hosted demo* |
| **KIPO Korea** | Korean patents and utility models, trademarks, and designs via the KIPRIS Plus REST API operated by KIPI on behalf of KIPO. Free-text + structured search on each register, single-number fetch with list-accept (capped at 50). *9 MCP tools register when `KIPO_KIPRIS_API_KEY` is set; BYOK per KIPRIS Plus ToS §11 — per-user keys only, no shared-key proxy permitted; not exposed by the hosted demo* |
| **IPO India** | The four core Indian IP Acts (Patents Act 1970 with §3(d), §25, §84; Designs Act 2000; Trade Marks Act 1999; Copyright Act 1957) + Patent Rules 2003 (incl. 2024 amendments), plus the IPO India Manual of Patent Practice & Procedure (MPPP v3.0, 2019). Citation forms: `Section 3(d) Patents Act`, `Rule 71 Patent Rules`, `MPPP Chapter 04.05.01`. *Runs against local SQLite/FTS5 snapshots built by `patent-client-agents-build-ipo-in-statutes-corpus` and `patent-client-agents-build-ipo-in-mppp-corpus`* |
| **DPMA Germany** | The six core German IP statutes — Patentgesetz (PatG), Markengesetz (MarkenG), Gebrauchsmustergesetz (GebrMG), Designgesetz (DesignG), Urheberrechtsgesetz (UrhG), and Geschäftsgeheimnisgesetz (GeschGehG) — bundled into one searchable corpus. Citation forms: `§ 1 PatG`, `§ 139 PatG`, `§ 14 MarkenG`, `§ 5 GeschGehG`. *Runs against a local SQLite/FTS5 snapshot built by `patent-client-agents-build-dpma-statutes-corpus`* |
| **Légifrance IP** | The French intellectual-property statutes — Code de la propriété intellectuelle (CPI: patents L.611, trade marks L.711, designs L.511, copyright L.111) plus the Code de commerce L.151 trade-secret regime — bundled into one searchable corpus. Citation forms: `L. 611-10 CPI`, `Art. L. 611-10 CPI`, `L611-10 CPI`, `L. 151-1 Code de commerce`. *Runs against a local SQLite/FTS5 snapshot built by `patent-client-agents-build-legifrance-ip-corpus`* |
| **Taiwan Trade Secrets** | The Taiwan Trade Secrets Act (營業秘密法) in the official English translation published by law.moj.gov.tw/Eng — Articles 1, 2, 3, 10, 11, 13, and 13-1 (legislative purpose, trade-secret definition, employee-derived ownership, acts of misappropriation, injunction + damages, treble damages, criminal liability). Citation forms: `Art. 2 Trade Secrets Act`, `Section 13 Trade Secrets Act`, `Art. 13-1`, bare numeric `13` / `13-1`. *Runs against a local SQLite/FTS5 snapshot built by `patent-client-agents-build-tw-trade-secrets-corpus`* |
| **MPEP** | Manual of Patent Examining Procedure search and section lookup — *runs against a local SQLite/FTS5 snapshot built by `patent-client-agents-build-mpep-corpus`; see docs/installation.md* |
| **TMEP** | Trademark Manual of Examining Procedure search and section lookup — *runs against a local SQLite/FTS5 snapshot built by `patent-client-agents-build-tmep-corpus`; see docs/installation.md* |
| **CPC** | Classification hierarchy lookup, search, and CPC/IPC mapping |
| **CanLII** | Canadian courts, tribunals, and IP statutes — Federal Court / FCA / Supreme Court IP rulings, Trade-marks Opposition Board, Patent Appeal Board, Patent Act, Trademarks Act with point-in-time queries — *MCP tools register when `CANLII_API_KEY` is set; not exposed by the hosted demo* |
| **WIPO Lex** | Global IP statute / treaty / judgment database curated by WIPO — ~50k legal documents across ~200 jurisdictions, six UN languages. v0.9 scope: legislation collection (search + detail with PDF links) |
| **EUIPO** | EU Trade Marks (~2.3M EUTMs since 1996) + Registered Community Designs (~1.5M RCDs since 2003). RSQL search, full prosecution records, multilingual goods-and-services / product indications, sandbox toggle — *MCP tools register when `EUIPO_CLIENT_ID` + `EUIPO_CLIENT_SECRET` are set; not exposed by the hosted demo* |
| **Federal Circuit (CAFC)** | Every patent appeal in the US is appealable to the Federal Circuit. Search opinions by date / origin (PTO, DCT, ITC, CFC), classify as patent vs. non-patent, download opinion PDFs |
| **USITC** | EDIS (Section 337 patent enforcement investigations + dockets + attachments), DataWeb (US trade statistics), HTS (Harmonized Tariff Schedule), IDS (IP investigation index) — *EDIS and DataWeb need free user-minted tokens; HTS and IDS are public* |
| **US Copyright Office** | Copyright registrations (post‑1978 + digitized card catalog) and recorded documents (transfers, assignments, licenses) via the Public Records System — *public, no auth* |
| **UPC (Unified Patent Court)** | Decisions-and-orders feed (CFI + CoA + Central / Local / Regional Divisions, with canonical case IDs and PDF/A URLs) plus a corpus-backed view of the UPC Agreement, consolidated Rules of Procedure, and Table of Court Fees in EN/FR/DE — *public, no auth; statutes run against a local SQLite/FTS5 snapshot built by `patent-client-agents-build-upc-statutes-corpus`* |
| **EPO Statutes & Case Law** | The five canonical EPO legal corpora: **EPC** (180 Articles + 176 Implementing Regulations), **Guidelines for Examination** (~1,800 sections), **PCT-EPO Guidelines** (~750 sections — applies when the EPO acts as ISA/IPEA), **Unitary Patent Guidelines** (~140 sections — UP opt-in, fees, renewals), and **Case Law of the Boards of Appeal** "white book" (~2,600 sections). Each corpus accepts native citation forms (`Art. 54`, `R. 71`, `G-II, 3.1`, `I.A.1`, dotted `1.2.1`). All five run against local SQLite/FTS5 snapshots built by `patent-client-agents-build-{epc,guidelines,pct-guidelines,up-guidelines,caselaw}-corpus`. |

All sources include automatic caching (hishel + SQLite with WAL), rate limiting,
and retry logic via `law_tools_core`.

## API keys

86 patent + IP MCP tools are exposed by default, plus additional
families that register when their credentials are present: +12 JPO,
+9 CanLII, +4 EUIPO.

| Variable | Source | Required | How to get |
|----------|--------|----------|------------|
| `USPTO_ODP_API_KEY` | USPTO ODP | Most USPTO patent tools | [developer.uspto.gov](https://developer.uspto.gov/) (free) |
| `USPTO_TSDR_API_KEY` | USPTO TSDR | All TSDR trademark tools | [account.uspto.gov/api-manager/](https://account.uspto.gov/api-manager/) (free MyUSPTO account) |
| `EPO_OPS_API_KEY`, `EPO_OPS_API_SECRET` | EPO OPS | All EPO tools | [developers.epo.org](https://developers.epo.org/) (free) |
| `JPO_API_USERNAME`, `JPO_API_PASSWORD` | JPO | All JPO library + MCP tools (env-gated on the stdio server / plugin; not set on the hosted demo) | [j-platpat.inpit.go.jp](https://www.j-platpat.inpit.go.jp/) |
| `CANLII_API_KEY` | CanLII | All CanLII library + MCP tools (env-gated on the stdio server / plugin; not set on the hosted demo) | [canlii.org/en/feedback/feedback.html](https://www.canlii.org/en/feedback/feedback.html) (free, by request) |
| `EUIPO_CLIENT_ID`, `EUIPO_CLIENT_SECRET` | EUIPO | All EUIPO library + MCP tools (env-gated; not set on the hosted demo). Set `EUIPO_ENV=sandbox` to use the open sandbox environment instead of production. | [dev.euipo.europa.eu](https://dev.euipo.europa.eu/) (sandbox auto-approves; production requires ID-document review) |
| `USITC_EDIS_TOKEN` | USITC EDIS | EDIS document/attachment downloads (also rejected for *public* docs without a token); investigation+document search itself works without one | [edis.usitc.gov](https://edis.usitc.gov) → API Token Generator (free, Login.gov account). JWT, ~2 wk lifetime |
| `USITC_DATAWEB_TOKEN` | USITC DataWeb | `run_dataweb_report` only | [dataweb.usitc.gov](https://dataweb.usitc.gov) account page (free) |
| `PCA_WAF_TOKEN_PATH` *or* `PCA_WAF_TOKEN_JSON` | USPTO TESS | Trademark search via TESS — bring-your-own WAF token *or* install `[tmsearch]` extra to mint via Playwright | See [USPTO Trademark Search docs](https://docs.patentclient.com/api/uspto-tmsearch/) |

**No API key needed:** Google Patents, USPTO Publications (PPUBS), USPTO
Assignments, USPTO Trademark Assignments, MPEP, TMEP, CPC, WIPO Lex,
Federal Circuit (CAFC), USITC HTS, USITC IDS, US Copyright Office.

### `tmsearch` extra (Playwright + curl_cffi)

USPTO TESS sits behind AWS WAF. To mint the WAF token in-process, install
the optional extra and bootstrap Chromium once:

```bash
pip install 'patent-client-agents[tmsearch]'
playwright install chromium
```

On headless server deployments where Playwright isn't installed, set
`PCA_WAF_TOKEN_JSON` to a token JSON payload (Secret Manager mount) or
`PCA_WAF_TOKEN_PATH` to a path on disk — the client will reuse the
cached token until it expires (~4 days).

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
┌──────────────────────────────────────────────────────────────────────┐
│     Any MCP-speaking agent — Claude Code, Codex CLI, Gemini CLI,     │
│     Cursor, Windsurf, Cline, Zed, Continue, Copilot Chat, JetBrains, │
│     Claude Desktop, ChatGPT (remote), Replit Agent (remote)          │
├──────────────────────────────────────────────────────────────────────┤
│                   patent-client-agents MCP Server                     │
│                  (Natural language → API calls)                       │
├──────────────────────────────────────────────────────────────────────┤
│                  patent_client_agents Python library                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────┐ ┌────────┐ │
│  │  USPTO  │ │  USPTO  │ │   EPO   │ │ Google  │ │ JPO* │ │ EUIPO* │ │
│  │ patents │ │  marks  │ │   OPS   │ │ Patents │ │      │ │  marks │ │
│  │ ODP+    │ │TSDR+TM  │ │  + CPC  │ │  +MPEP  │ │      │ │ + RCDs │ │
│  │ PPUBS   │ │assigns  │ │         │ │  +TMEP  │ │      │ │        │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └──────┘ └────────┘ │
│       + CanLII* (case law) + WIPO Lex (global IP statutes)            │
└──────────────────────────────────────────────────────────────────────┘
* MCP tools register only when the corresponding credentials are set
  on the server (JPO_API_*, CANLII_API_KEY, EUIPO_CLIENT_ID/SECRET);
  the hosted demo does not carry these credentials.
```

## Development

```bash
git clone https://github.com/parkerhancock/patent-client-agents.git
cd patent-client-agents
uv sync --group dev
uv run pytest                       # 1,117 tests, replays VCR cassettes
uv run ruff check . && uv run ruff format .
```

Tests use [vcrpy](https://vcrpy.readthedocs.io) to replay recorded HTTP interactions
without hitting live APIs. Record modes:
```bash
uv run pytest --vcr-record=once     # Record missing cassettes
uv run pytest --vcr-record=all      # Re-record everything
uv run pytest --run-live-uspto      # Skip VCR, hit live USPTO
uv run pytest --run-live-jpo        # Skip VCR, hit live JPO
uv run pytest --run-live-euipo      # Skip VCR, hit live EUIPO (sandbox or prod)
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
