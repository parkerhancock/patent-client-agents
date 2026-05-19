# EPO European Patent Office (EP) — regional

**Layer:** regional
**Jurisdiction:** EP (38 EPC contracting states); designations cover EU + EEA + Switzerland + UK + Turkey + Norway + Iceland + others
**Issuing body:** European Patent Organisation / European Patent Office (Munich, The Hague, Berlin, Vienna)
**Rights administered:** patent (granted via European Patent Convention); operates INPADOC + DOCDB aggregators
**Working languages:** English, French, German (official EPO languages)
**Connector status:** **active** (mature)
**Last verified:** 2026-05-16
**Manifest entries:**
- [`EP/EPO/OPS`](../../coverage/sources.yaml) — `patent_client_agents.epo_ops`
- [`EP/EPO/CPC`](../../coverage/sources.yaml) — `patent_client_agents.cpc`
- [`EP/EPC/Statute`](../../coverage/sources.yaml) — substantive law
- [`EP/EPO/Guidelines`](../../coverage/sources.yaml) — examination guidelines (substantive law)
- [`EP/EPO/CaseLaw`](../../coverage/sources.yaml) — Boards of Appeal case law (substantive law)
- [`UP/EPO/UPGuidelines`](../../coverage/sources.yaml) — Unitary Patent Guidelines

**Detail surveys:**
- [`connectors/upc.md`](../connectors/upc.md) — UPC + EPO UP helpers (668 lines)
- Pre-existing knowledge in [`COVERAGE_STRATEGY.md`](../COVERAGE_STRATEGY.md) §2 (regional layer) — INPADOC carries biblio for ~100 offices, legal events for ~50

**Sibling layers carrying overlapping data:**
- **National offices** for direct-filed patents in EPC states; EPO doesn't fully substitute for national prosecution.
- **WIPO PATENTSCOPE** for PCT applications before national-phase entry.
- **UPC** ([`upc.md`](upc.md)) for litigation under the Unitary Patent system.

---

## §1 Mission

EPO is the **single highest-leverage office in our registered-IP catalog**.
It issues European patents (granting protection across 38 EPC contracting
states via national validation), administers the Unitary Patent system
(currently ~17 EU states), and — most importantly for our coverage
strategy — operates INPADOC + DOCDB, the worldwide patent bibliographic
aggregators. Through EPO Open Patent Services (OPS), one connector
gives us biblio + family data for ~100 national patent offices
worldwide, substituting for many national patent register connectors at
once.

For agents needing patent biblio, family, or legal events for nearly any
jurisdiction outside Russia/some Asian gaps, EPO OPS is the first stop.

## §2 What's unique here
- **EP-filed and EP-granted patents** — applications and grants under the European Patent Convention.
- **INPADOC family data** — DOCDB simple families + INPADOC extended families across ~100 contributing offices.
- **INPADOC legal events** — legal-status events for ~50 contributing offices (subset of DOCDB coverage).
- **EP full-text** for the ~30 collections EPO has full-text rights to.
- **EPO Boards of Appeal case law** (substantive law layer).
- **EPO examination Guidelines** (substantive law).
- **Unitary Patent register** — UP-specific status, opt-out registry.

## §3 Programmatic surfaces

### EPO Open Patent Services (OPS) v3.2

| Field | Value |
|---|---|
| Endpoint | `https://ops.epo.org/3.2/rest-services/` |
| Auth | OAuth2 client credentials (consumer key + secret) |
| Format | XML (EPO ST.36-derived schemas); JSON variant available on some endpoints |
| Rate limit | Free tier: ~4 GB/week soft limit; commercial tier: higher |
| ToS posture | Permissive for proxy-shaped use; the standard agreement permits programmatic access |
| Verdict (zero-infra proxy) | 🟢 **Green** — already operational in our connector |
| Primary sources | [EPO OPS service](https://www.epo.org/en/searching-for-patents/data/web-services/ops) · [Developer registration](https://www.epo.org/en/searching-for-patents/data/web-services/ops/registration) |

### EPO Espacenet INPADOC legal status

Same OPS endpoint, separate operation. Legal-events coverage scope:
**~50 contributing offices** (per [Espacenet INPADOC legal-status help](https://worldwide.espacenet.com/help?locale=en_EP&method=handleHelpTopic&topic=legalstatusqh)).

### EPO Bulk Data (Open Patent Services bulk)

Separate bulk product; not what we use for the live connector. Bulk
delivery via FTP.

### CPC classification

| Field | Value |
|---|---|
| Endpoint | EPO OPS classification helpers |
| Auth | Same OPS credentials |
| Verdict | 🟢 Green — operational via [`patent_client_agents.cpc`](../../src/patent_client_agents/cpc/) |

## §4 Fees

EPO publishes a fee schedule covering filing, search, designation,
examination, grant, opposition, appeal, and renewal (years 3–20), plus
separate Unitary Patent renewal fees decided by the Select Committee.
Rate adjustments are issued by Administrative Council decision (look
for `CA/D` references) and published in the EPO Official Journal.

- **Official schedule:** [EPO Schedule of Fees](https://www.epo.org/en/legal/fees) — authoritative; updated periodically.
- **Statutory basis:** [Rules relating to Fees, EPC Implementing Regulations](https://www.epo.org/en/legal/epc/2020/r-fees.html).
- **Rate adjustment notices:** [EPO Official Journal](https://www.epo.org/en/legal/official-journal).

Discount programs:

- **Rule 7a EPC micro-entity** — for individual applicants under defined size thresholds; stackable with Rule 6.
- **Rule 6 language reduction** — for natural persons / SMEs / universities / non-profits filing in a non-official EPO language.


## §5 Connector strategy

### What we cover today

- [`patent_client_agents.epo_ops`](../../src/patent_client_agents/epo_ops/) — search, biblio, family, full-text (where available), legal events. Manifest `EP/EPO/OPS`.
- [`patent_client_agents.cpc`](../../src/patent_client_agents/cpc/) — CPC classification lookups. Manifest `EP/EPO/CPC`.
- [`patent_client_agents.epc`](../../src/patent_client_agents/epc/) (if present) + EPO Guidelines + Boards of Appeal case law — substantive law layer.
- UP helpers (Unitary Patent status, opt-out registry) — recipes on existing OPS, see [`connectors/upc.md`](../connectors/upc.md).

### What we should improve

- **§5.9 envelope sweep on EPO tools** — completed 2026-05-18 ✅. All `search_epo`/`get_epo_*`/`get_epo_cql_help` tools on the envelope, with list-accept on the four single-record gets (biblio/family/fulltext/legal_events) and cross-refs.
- **Per-jurisdiction recipe helpers** — `get_de_biblio(de_application_number)`, `get_cn_biblio(...)`, `get_kr_biblio(...)` etc. — wraps OPS jurisdiction-specific search patterns. Documented as "Tier 1 Rank 12" in BACKLOG.

### What we should NOT add

- **EPO Bulk Data** — bulk-shaped; doesn't fit our zero-infra constraint and OPS already gives us live access.

### Next steps

1. Ship per-jurisdiction recipe helpers (especially CN — see [BACKLOG Tier 1 Rank 12 `cn_via_epo_ops`](../BACKLOG.md)) to make INPADOC's transitive coverage discoverable for agents.
2. Update fee-aware tooling once we expose fees via MCP — EPO 2026-04-01 schedule is now effective; old fee logic with 2024 figures will misquote.

## §6 Open questions

- **Free-tier rate limit hard numbers** — published policy mentions ~4 GB/week soft limit; needs verification for production planning.
- **UP renewal fee future trajectory** — UP fees are decided by the Select Committee, not the Administrative Council; CA/D 9/25 didn't touch them. Decision rhythm differs from EPC fees.

## §7 References

Primary sources only.

**OPS:**
- [EPO Open Patent Services](https://www.epo.org/en/searching-for-patents/data/web-services/ops)
- [OPS developer registration](https://www.epo.org/en/searching-for-patents/data/web-services/ops/registration)
- [Espacenet INPADOC legal-status help](https://worldwide.espacenet.com/help?locale=en_EP&method=handleHelpTopic&topic=legalstatusqh)

**Fees:**
- [Schedule of Fees](https://www.epo.org/en/legal/fees)
- [Rules relating to Fees](https://www.epo.org/en/legal/epc/2020/r-fees.html)
- [CA/D 9/25 decision (2026-04-01 effective)](https://www.epo.org/en/legal/official-journal)

**EPC text + supplementary publications:**
- [European Patent Convention (consolidated)](https://www.epo.org/en/legal/epc)
- [EPO Official Journal](https://www.epo.org/en/legal/official-journal)

**UP / UPC linkage:**
- [Unitary Patent system](https://www.epo.org/en/applying/european/unitary)
- [`connectors/upc.md`](../connectors/upc.md) for UPC + EPO UP helpers

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-16 | Initial synopsis. Flagged §5.9 envelope sweep as pending. | — |
| 2026-05-18 | §5.9 envelope sweep on EPO tools complete; next step is per-jurisdiction recipe helpers (CN/DE/KR via INPADOC). | — |
