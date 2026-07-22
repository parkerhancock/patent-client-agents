# Office Actions Search

Single unified search across USPTO ODP office-action data, replacing four
separate tools (`search_oa_rejections`, `search_oa_citations`, `search_oa_text`,
`search_enriched_citations`).

## Why fused

All four endpoints share the same Lucene `criteria` grammar and hit the
same `OfficeActionClient`. They differ only in which result shape they
return. A `result_type` discriminator is the right shape for this.

## MCP tool

```
search_office_actions(
    criteria,
    result_type = "rejections" | "citations" | "text" | "enriched_citations",
    start=0,
    rows=25,
) -> dict
```

For a stateless watched-patent workflow, use:

```
check_citation_hits(
    patent_numbers=["US 10946800 B2", "WO-2017115695-A1"],
    since="2026-01-01",
) -> dict
```

It phrase-quotes each normalized citation identifier, filters to
examiner-cited references, and reports whether each citing application also
carries a §102 rejection. That §102 flag is application-level and does not
prove the watched patent supplied the rejection basis.

## Result types

| `result_type` | What you get | Key Lucene fields |
|---|---|---|
| `rejections` | Per-claim rejection records with indicators for 35 USC 101/102/103/112/DP, plus Alice/Bilski/Mayo/Myriad eligibility flags. | `patentApplicationNumber`, `hasRej101`, `hasRej102`, `hasRej103`, `hasRej112`, `hasRejDP`, `legalSectionCode`, `nationalClass`, `groupArtUnitNumber`, `submissionDate`, `aliceIndicator`, `allowedClaimIndicator` |
| `citations` | Prior-art references cited in office actions, with examiner/applicant cited-by flags. | `patentApplicationNumber`, `referenceIdentifier`, `parsedReferenceIdentifier`, `legalSectionCode`, `examinerCitedReferenceIndicator`, `applicantCitedExaminerReferenceIndicator`, `groupArtUnitNumber`, `techCenter` |
| `text` | Full office-action body text with structured section breakdowns. | `patentApplicationNumber`, `inventionTitle`, `submissionDate`, `legacyDocumentCodeIdentifier` (CTNF/CTFR/NOA/…), `groupArtUnitNumber`, `patentNumber`, `applicationTypeCategory` |
| `enriched_citations` | Citations enriched with inventor names, country/kind codes, passage locations, and quality summaries. | `patentApplicationNumber`, `citedDocumentIdentifier`, `publicationNumber`, `inventorNameText`, `countryCode`, `kindCode`, `officeActionCategory`, `citationCategoryCode`, `officeActionDate`, `examinerCitedReferenceIndicator`, `nplIndicator`, `groupArtUnitNumber` |

Valid fields differ per `result_type` — using a `hasRej103` criterion with
`result_type="citations"` will fail at the upstream endpoint. The MCP tool
does not pre-validate field-vs-type compatibility; upstream errors surface
as-is.

## Python API (raw)

```python
from patent_client_agents.uspto_office_actions import OfficeActionClient

async with OfficeActionClient() as client:
    rejections = await client.search_rejections("hasRej103:1 AND nationalClass:438")
    citations = await client.search_citations("patentApplicationNumber:16123456")
    text = await client.search_office_action_text("patentApplicationNumber:16123456")
    enriched = await client.search_enriched_citations("countryCode:US AND kindCode:A1")
```

Like `search_patent_assignments`, this is a parameter-fusion MCP tool with
no library-level wrapper — Python consumers call the underlying client's
four methods directly.
