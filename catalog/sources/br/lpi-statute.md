---
id: BR/LPI/Statute
name: Lei da Propriedade Industrial (LPI / Lei 9.279/1996)
jurisdictions:
- BR
institution: República Federativa do Brasil (Presidência da República)
source_type: legal_corpus
official_url: https://www.planalto.gov.br/ccivil_03/leis/l9279.htm
last_verified: 2026-05-16
source_status: active
category: substantive_law
rights:
- patent
- trademark
- design
- gi
access:
  availability: public
  audience: public
  formats:
  - unknown
  automation_posture: permitted
capabilities:
  guidelines: none
  case_law: none
  statutes: partial
  treaties: none
  full_text_search: partial
  citation_lookup: unknown
  point_in_time: unknown
connector:
  status: shipped
  module: patent_client_agents.inpi_br_statutes
  blockers: []
coverage:
  atlas_standalone_reason: independent_legal_authority
  order: 38
  wipo_st3_code: BR
  data_types:
  - statutes
  access:
    method: mcp_passthrough
    auth: none
  status: active
  category: substantive_law
  transport: mcp_local
  update_strategy: scheduled_recrawl
  update_cadence: irregular
  last_synced: 2026-05-16
  corpus_version: unknown — needs verification
  notes: 'Brazil''s unified IP code — patents (Title I), designs (Title II),

    trade marks (Title III), GIs (Title IV), trade secrets / unfair

    competition (Title V, Art. 195), and criminal sanctions. Bundles

    both PT (authoritative — Planalto) and EN (WIPO Lex translation)

    text per Article. Cadence is irregular because the LPI is amended

    by occasional federal laws (no published schedule).

    '
---

# Lei da Propriedade Industrial (LPI / Lei 9.279/1996)

## What this source contains

República Federativa do Brasil (Presidência da República) publishes this data product for patent, trademark, design, gi. The compatibility
manifest declares the following covered data types: statutes.

## Scope limitations

This record preserves the former coverage-manifest claim at data-product
granularity. A `partial` capability means that the legacy manifest asserted the
data type, not that the source is comprehensive for the jurisdiction.

Legacy coverage notes:

Brazil's unified IP code — patents (Title I), designs (Title II),
trade marks (Title III), GIs (Title IV), trade secrets / unfair
competition (Title V, Art. 195), and criminal sanctions. Bundles
both PT (authoritative — Planalto) and EN (WIPO Lex translation)
text per Article. Cadence is irregular because the LPI is amended
by occasional federal laws (no published schedule).

## Access and connector assessment

The declared access method is `mcp_passthrough` with
authentication `none`. Consult the official source
and connector implementation before increasing request volume or changing the
automation posture.

## Connector coverage

The compatibility connector module is `patent_client_agents.inpi_br_statutes`. The catalog describes the
upstream product; the package API documentation describes callable behavior.

## Known gaps

Capabilities not positively identified in frontmatter remain `none` or
`unknown`. This migration does not infer completeness, historical depth,
language coverage, or update latency beyond the preserved manifest fields.

## Evidence

- [Official source](https://www.planalto.gov.br/ccivil_03/leis/l9279.htm)
