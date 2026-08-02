<!--
Canonical template for an office synopsis. Copy this file to
research/{multilateral,regional,national}/<id>.md and fill in.

Naming convention:
  multilateral/  → wipo-<system>.md
  regional/      → <office-shortname>.md      (e.g. epo.md, euipo.md, upc.md)
  national/      → <iso2>-<office>.md         (e.g. us-uspto.md, jp-jpo.md)

Target length: 150-200 lines. If you find yourself going longer, push
the detail into a wave file under research/waves/<date>-<subject>/
and link from this synopsis.

Every claim of fact must have a primary-source URL. Last-verified date
on every section that could go stale.
-->

# {Office Name} ({ISO code or system code})

**Layer:** multilateral | regional | national
**Jurisdiction:** {ISO 3166 alpha-2 / WIPO ST.3 code}
**Issuing body:** {full official name}
**Rights administered:** patent / utility_model / trademark / design / copyright / plant_variety / gi / trade_secret
**Working languages:** {primary, others}
**Connector status:** active | partial | planned | blocked | skipped
**Last verified:** YYYY-MM-DD
**Manifest entry:** [`coverage/sources.yaml` `XX/YY/ZZ`](../../coverage/sources.yaml) — *or "not yet listed" if planned/blocked/skipped*

**Detail surveys:**
- [`connectors/<office>.md`](../connectors/<office>.md) — *2026-05 detail survey, if present*
- [`waves/<date>-<subject>/<office>.md`](../waves/<date>-<subject>/<office>.md) — *latest grounded research*

**Higher layers covering this office transitively:**
- e.g. EPO INPADOC (patents biblio/family/legal-events for ~50 offices)
- e.g. WIPO Madrid (international TMs designating this country)

---

## §1 Mission

One paragraph on what this office does and its role in the IP system.
Why agents care about it. What unique role it plays in the layered
structure.

## §2 What's unique here

Bullets — fields/data types available ONLY from this office (not
covered by any higher layer at the same fidelity). This drives §5
(connector strategy).

- e.g. Full prosecution file wrappers
- e.g. Real-time legal-status (vs. INPADOC's lag)
- e.g. National-language full text
- e.g. National-only TM filings (no Madrid IR)

### Substitution gate

| Candidate data | Best existing substitute | Material fidelity gap | Build decision |
|---|---|---|---|
| {data type} | {EPO OPS / WIPO / EUIPO / Google Patents / corpus} | {specific missing field, freshness, or authority} | build / skip |

Do not queue a connector unless this table identifies a material gap.

## §3 Programmatic surfaces

For each surface (REST API, bulk feed, SFTP, HTML scrape, SOAP, Atom,
etc.), one block:

### {Surface name}

| Field | Value |
|---|---|
| Endpoint | `https://...` |
| Auth | none / API key / OAuth2 / username+password / paper contract / paid |
| Format | JSON / XML / Atom / PDF |
| Rate limit | published throttle if any |
| ToS posture | permissive / per-user only / proxy-prohibited / paid-only |
| Verdict (zero-infra proxy) | 🟢 green / 🟡 yellow / 🔴 red |
| Primary source | [hyperlink](https://...) |

One sentence explaining why the verdict is what it is.

### {Next surface, if any}

(repeat)

## §4 Fees

**Policy: link only.** Reproducing fee amounts is *not our job* — fees
drift, and the only authoritative figure is whatever the official
schedule says *today*. Document what categories of fees exist (in their
local currency) and where the authoritative source lives. Don't paste
tables, percentages, or specific effective dates.

{Office name} publishes a fee schedule (in {LOCAL_CURRENCY}) covering
{high-level categories that exist — e.g. filing, search, examination,
grant, opposition, appeal, renewal}.

- **Official schedule:** [primary URL](https://...)
- **Statutory basis:** [law / regulation URL](https://...) *(if separate)*
- **Rate adjustment notices:** [official journal / gazette URL](https://...) *(if separate)*

Notable discount programs *(name + one-line eligibility — no specific
amounts or dates)*:

- **Rule N.NN** — {who qualifies}
- ...

## §5 Connector strategy

### What we cover today

- e.g. `patent_client_agents.uspto_odp` — patent applications, PTAB, petitions
- e.g. Nothing — currently statutes only (`<package>`)

### What we should add (if anything)

If queued: cross-reference [`BACKLOG.md`](../BACKLOG.md) entry rank and rationale.
State which substitution-gate gap the connector closes.

### What we should NOT add

If we've decided to skip: cite the blocker (higher-layer coverage, ToS,
contract restriction, no API, etc.). This is the *strategic memory* —
why future-us shouldn't waste time re-evaluating.

### Next steps

Concrete — "research X", "design BYOK config", "wait for partner-API announcement", etc.

## §6 Open questions

- Bullets, each linkable
- Each should be answerable with a defined next action

## §7 References

Primary sources only — no third-party blogs, no Wikipedia, no Stack Overflow.

- [Official API docs](https://...)
- [Terms of service](https://...)
- [Fee schedule](https://...)
- [Registration / signup portal](https://...)
- [Related detail surveys](../connectors/<office>.md)

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| YYYY-MM-DD | Initial synopsis | Distilled from `connectors/<office>.md` + `waves/<date>/<office>.md` |
