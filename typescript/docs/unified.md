# Fused claims and PDF helpers

October 22, 2026. [`unified.ts`](../packages/client/src/unified.ts) ports the
public helpers of Python `unified.py` into the client package, so library
users get the cross-source claims and PDF cascades without going through MCP.
The curated facade's `get_patent(view='claims')` and
`download_document(source='patent_pdf')` call these functions and carry no
cascade of their own.

## API

The client package has no global clients, so each helper takes the clients
it cascades over as its first argument. Each source is typed as a `Pick` of
the methods the cascade calls, so a configured client or a stand-in object
both fit. EPO OPS is optional everywhere; without it the cascade ends one
step early and the not-found message says so.

| Function | Python | Sources, in order |
| --- | --- | --- |
| `getPatentClaims({ applications, googlePatents }, number)` | `get_patent_claims` | ODP grant XML (US numbers), Google Patents |
| `getPatentClaimsClean({ applications, publications, epoOps? }, number)` | `get_patent_claims_clean` | ODP grant XML and PPUBS full text (US numbers), EPO OPS full text |
| `downloadPatentPdf({ googlePatents, publications, epoOps? }, number)` | `download_patent_pdf` | Google Patents, PPUBS (US numbers), EPO OPS |
| `downloadPatentPdfClean({ publications, epoOps? }, number)` | `download_patent_pdf_clean` | PPUBS (US numbers), EPO OPS |

The clean variants never touch Google Patents; their source types have no
Google member. The parsing helpers are exported too:
`buildCanonicalClaim`, `odpLimitationsFromText`, `googleLimitationsFromHtml`,
`ppubsClaimTexts` and `epoClaimTexts`.

The claims helpers return `{ source, claims, provenance }`, where `source` is
`uspto_odp`, `uspto_ppubs`, `epo_ops` or `google_patents` and `claims` holds
canonical claims: `claim_number`, `limitations` (`{ text, depth }`),
`claim_text` rebuilt from the limitations with four spaces per depth level,
`claim_type` and `depends_on`. Python returned the bare list. ODP and Google
claims carry the nested limitation tree; PPUBS and EPO claims are one
unnested limitation each, since those sources have no structure.

The PDF helpers return `PatentPdf`: `data`, `source` (`google_patents`,
`ppubs` or `epo`, as in Python), `filename`, `patentNumber`, `patentTitle`
(PPUBS only) and `provenance`. Python returned `pdf_bytes` and no provenance.

## Errors

A cascade moves to the next source only when a source cannot serve the
number. For claims, ODP and PPUBS fall through on any `ApiError`,
`ConfigurationError` or validation error, as Python fell through on its
`McpDataCoreError` and `ValueError`; other exceptions are bugs and surface.
EPO OPS and Google Patents fall through only on not-found, so throttling and
authentication failures reach the caller. For PDFs, every source falls
through only on not-found. When no source has the claims or PDF, the helpers
throw an `ApiError` with status 404 and code `NOT_FOUND` whose message names
the sources tried, with Python's wording.

## Changes from Python

Behavior the MCP facade had already corrected stays corrected:

- The EPO claims fallback picks the English claims block and splits it into
  numbered claims. Python numbered each language block as a claim.
- The PDF cascades send only US numbers to PPUBS. Python sent every number
  and relied on a 404, but a PPUBS search can match an unrelated document.

Further corrections made in the port:

- Clean-claims EPO failures other than not-found (throttling, authentication,
  server errors) now surface. The facade had reported them as "Claims not
  found", hiding the fault. This is the one change in facade output, and it
  appears only on those error paths.
- `getPatentClaims` treats a bare number (`10301023`) as US and tries ODP
  first, as the clean variant already did. Python sent it straight to Google.
- Google limitations strip claim numbers rendered as `1 . ` (number in its
  own element). Python's pattern required `1.` and left the number in the
  first limitation of every claim on pages such as US20230012345A1.
- On machine-translated Google pages the limitations hold the translation
  only. Python prefixed each limitation with the original-language text.
- Nested `<claim-text>` elements are no longer repeated in their parent's
  text, and a claim with no nested claim-text becomes one top-level
  limitation instead of an empty list.
- Google claim type and dependency come from the client's claim parser,
  which reads the dependency from the claim wording ("of claim 1", "any one
  of the preceding claims") on pages without claim-ref markup. Python called
  every such claim independent, which covered all dependent claims on the
  EP, WO, JP and CN fixture pages.
- The Google PDF filename and `patentNumber` use the number Google resolved
  rather than the caller's input.

## Verification

[`tests/unified.test.ts`](../tests/unified.test.ts) runs offline. The
limitation parsers are checked against Python output stored in
[`tests/fixtures/unified/python-parity.json`](../tests/fixtures/unified/python-parity.json),
which [`generate_python_parity.py`](../tests/fixtures/unified/generate_python_parity.py)
regenerates by running the Python functions on the 32 claims of US
10,765,880 from the replayed ODP granted-claims cassette, five edge cases,
and the six archived Google Patents pages. ODP limitations and canonical
claim text match exactly. On the four English Google pages the limitations
match exactly apart from the claim-number fix above; on the two translated
pages the depth sequence matches and every limitation is the tail of
Python's text. Fake clients cover source order, fall-through on not-found
and source errors, surfaced faults, the clean-mode restrictions and the
`PatentPdf` shape; the EPO path also replays the recorded EP1000000B1 claims.
The node and browser smokes run `getPatentClaims` on an archived page, and
the node smoke also runs the clean PDF cascade.
