---
hide:
  - navigation
  - toc
---

# Public IP data for agents

Patent Client Agents is an open-source Python library and MCP server for
researching patents, trademarks, designs, copyright records, IP law, published
decisions, and official fee schedules. It exposes source-specific clients as
typed tools without hiding where a record came from.

[Try the hosted service](https://mcp.patentclient.com/){ .md-button .md-button--primary }
[Install an agent plugin](install/agent-plugins.md){ .md-button }
[Browse the source atlas](https://patentclient.com/atlas){ .md-button }

## Choose the right way to run it

| Use | Best for | What you control |
| --- | --- | --- |
| [Hosted MCP](hosted-demo.md) | A first query with no local setup | Google sign-in and a deliberately curated public surface |
| [Agent plugin](install/agent-plugins.md) | Private research in Claude Code, OpenAI Codex CLI, or Google Antigravity CLI | The same Satchel-generated package in each client; 136 tools by default, up to 234 when every gated family is configured |
| [Stdio MCP server](mcp-stdio.md) | Other MCP clients or a hand-managed local configuration | The server command, environment, and client configuration |
| [Python library](install/python.md) | Application code and source-specific integrations | The exact clients, credentials, caching, and runtime your application needs |

The hosted service is convenient, but it is not the full product surface and
should not receive confidential material. The agent plugins are the shortest
path to a private local setup in Claude Code, Codex, or Antigravity. Configure
the stdio server directly for other MCP clients or when you need to control the
command and environment yourself.

## Start from a research task

### Find and compare patent records

Use global search to identify relevant publications, then retrieve claims,
citations, families, legal events, or prosecution records from the appropriate
office source.

- [Google Patents](api/google-patents.md) for broad discovery and document data
- [USPTO Publications](api/uspto-publications.md) for U.S. full-text search
- [USPTO Applications](api/uspto-applications.md) for application records and file history
- [EPO OPS](api/epo-ops.md) for European and worldwide bibliographic, family, and legal-event data

### Reconstruct prosecution and ownership

Follow application events, office actions, cited references, recorded transfers,
and agency proceedings without treating any single database as a complete file.

- [USPTO Office Actions](api/uspto-office-actions.md)
- [USPTO Assignments](api/uspto-assignments.md)
- [USPTO Petitions](api/uspto-petitions.md)
- [USPTO TSDR](api/uspto-tsdr.md) and [Trademark Assignments](api/uspto-trademark-assignments.md)

### Research law, guidance, and proceedings

Search examiner manuals, statutes, published opinions, and public tribunal data
through clients that retain each source's native citations and identifiers.

- [MPEP](api/mpep.md), [TMEP](api/tmep.md), and [WIPO Lex](api/wipo-lex.md)
- [Federal Circuit opinions](api/cafc.md)
- [USITC EDIS, DataWeb, HTS, and IDS](api/usitc.md)
- [Japan IP High Court](api/japan-ip-high-court.md) and [China SPC IP Court](api/china-spc-ip-court.md)

## Understand coverage before you depend on it

Coverage is intentionally explicit. The
[Patent Client Index](patent-client-index/index.md) records each data product,
its status, rights, data types, access conditions, and source documentation. The
[public atlas](https://patentclient.com/atlas) adds office-level research:

- Green means a usable programmatic path exists.
- Yellow identifies a credential or paid-access condition.
- Red records a legal or technical reason a connector is not shipped.

These ratings describe access, not the completeness or legal sufficiency of an
individual research result. Verify material conclusions against the linked
official record.

## What a client provides

Each integration follows the upstream source rather than forcing every system
into one lowest-common-denominator schema. Depending on the source, a client may
provide typed models, source URLs, retrieval details, caching, rate limiting,
retry behavior, normalized errors, or local searchable corpora.

This design preserves distinctions that matter in IP research: publication and
application numbers, family relationships, office-specific status fields,
effective dates, court identifiers, and the difference between a register,
search index, bulk dataset, and published document.

## Next steps

1. [Install the shared agent plugin](install/agent-plugins.md) in Claude Code, Codex, or Antigravity.
2. For another client, [configure the local MCP server](mcp-stdio.md).
3. Find the source you need in the [Patent Client Index](patent-client-index/index.md).
4. Open its page under **API Reference** for exact methods, models, limits, and examples.

The project is developed in public on
[GitHub](https://github.com/parkerhancock/patent-client-agents) under the
Apache-2.0 license.
