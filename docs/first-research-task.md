# Complete your first research task

Use one source-backed lookup to confirm that Patent Client Agents is connected
and returning live data. This task works with the Claude Code, OpenAI Codex,
and Google Antigravity plugins, a hand-configured local MCP server, and the
public hosted service. It needs no upstream API key or local corpus.

## Ask the same question in any client

Start a new agent session after installation, then paste this prompt:

> Use Patent Client Agents to retrieve a compact bibliographic record for US
> patent 10,000,000. Report its title, filing date, publication date, current
> assignee, and the source URL returned by the tool. Do not rely on model
> memory.

The agent should call `get_patent`. Its exact arguments differ by deployment,
so let the client use the tool schema it received instead of copying a raw
tool call from another server:

| Deployment | Public source selected by the current server |
| --- | --- |
| Local plugin or stdio MCP | Google Patents |
| Public hosted service | USPTO Patent Public Search (PPUBS) |

## Confirm the result

A successful response includes these facts:

| Field | Expected value |
| --- | --- |
| Title | Coherent LADAR using intra-pixel quadrature detection |
| Filing date | 2015-03-10 |
| Publication date | 2018-06-19 |
| Current assignee | Raytheon Co. or Raytheon Company |

It should also include provenance pointing to the record on
[Google Patents](https://patents.google.com/patent/US10000000B2) or the
USPTO PPUBS record selected by the hosted service. The source URL matters: it
shows that the answer came from the connected research tool rather than the
model's memory.

## If it does not work

- If `get_patent` is unavailable, reopen the client and confirm that
  `patent-client-agents` appears in its MCP tool list. Claude Code, Codex, and
  Antigravity each expose that list through `/mcp`.
- A local plugin's first call can take about 30 seconds while `uvx` downloads
  the pinned Python environment. Later calls reuse the cache.
- If Google Patents rate-limits a local call, wait and retry. The hosted
  service uses PPUBS for this US bibliographic lookup.
- The hosted service requires Google sign-in and applies the limits in the
  [hosted service guide](hosted-demo.md#usage-limits).

Once this result matches, continue to the [Patent Client Index](patent-client-index/index.md)
to choose a source for real research.
