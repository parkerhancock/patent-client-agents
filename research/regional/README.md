# Regional IP offices

Multi-state offices where a single filing grants protection across a defined
region. Sits between the multilateral layer and national offices.

## Synopses in this folder

| Office | Region | Rights | Synopsis |
|---|---|---|---|
| **EPO** | 38 EPC states + PCT national-phase | Patents + INPADOC backbone | [epo.md](epo.md) |
| **EUIPO** | 27 EU states | EU Trade Marks (EUTM) + Registered EU Designs (REUD, ex-RCD) + TMview / DesignView federations | [euipo.md](euipo.md) |
| **UPC** | ~17 EU states for Unitary Patents | UP decisions, UP Court decisions | [upc.md](upc.md) |
| **EAPO** | Eurasian (8 states) | Patents | [eapo.md](eapo.md) — *not yet written; see [connectors/](../connectors/) and BACKLOG* |
| **ARIPO** | African regional (22 states, 5 protocols) | Patents + UMs + designs + TMs + plant varieties + copyright (Kampala 2024) | [waves/2026-05-18-africa-wave/aripo.md](../waves/2026-05-18-africa-wave/aripo.md) — 🔴 red_no_api; patents covered transitively via EPO OPS country code `AP` |
| **OAPI** | Francophone African (17 unitary states) | Patents + UMs + designs + TMs + GIs + copyright + plant varieties (Bangui Annexes I-X) | [waves/2026-05-18-africa-wave/oapi.md](../waves/2026-05-18-africa-wave/oapi.md) — 🔴 red_no_api (bare-IP HTTP register, no TLS); patents covered transitively via EPO OPS country code `OA` |
| **GCC Patent Office** | Gulf (6 states) | Patents (legacy register only) | [gcc-patent.md](gcc-patent.md) — *closed for new applications since 2021-01-06* |

## Layer-level note

EPO is the **single highest-leverage office in the registered-IP catalog** because INPADOC
gives biblio + family + legal-events coverage for ~100 patent offices worldwide,
substituting for national patent register connectors at many jurisdictions. EUIPO is
the only registered-IP office for EU-level marks and designs.

National-level rights still require national connectors — regional offices do **not**
substitute for national TM/design coverage outside the EU level. EUIPO's TMview is a
search frontend over national TM registers, not a unified register.

For details see [`../COVERAGE_STRATEGY.md`](../COVERAGE_STRATEGY.md) §3 and §6.
