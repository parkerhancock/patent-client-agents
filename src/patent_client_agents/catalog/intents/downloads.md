# Patent / Publication / Document Downloads

Two distinct download surfaces:

1. **`download_patent_pdf`** — cross-source patent PDF cascade (Google → PPUBS → EPO).
2. **`get_jpo_documents`** — JPO file-history bundle for patent / design / trademark.

PTAB and ODP file-history downloads are documented separately (see
[Not included](#not-included)).

## Patent PDF download (cross-source)

Download a patent or publication PDF with worldwide coverage via a cascade
across three backends.

### Cascade order

1. **Google Patents** — preferred. PDFs are already OCR'ed (text extraction
   works directly; no post-processing needed).
2. **USPTO PPUBS** — US patents and published applications. Assembled from
   image pages; **not OCR'ed**.
3. **EPO OPS** — worldwide fallback. Assembled from image pages across all
   EPO-covered jurisdictions; **not OCR'ed**.

The cascade advances only on "not found" signals from a source
(`NotFoundError`, `FileNotFoundError`, missing-PDF `ValueError`). Hard
errors — auth failures, transient 5xx, rate limits — **surface
immediately** rather than being masked by silent fallback, so you don't
retry a legitimate failure against two more backends.

PPUBS cleanly 404s for non-US numbers (via its publication-number resolver),
so the cascade runs unconditionally regardless of country — no US/non-US
branching in the caller.

### Why not ODP?

USPTO ODP exposes PDFs only through the **prosecution document** endpoint,
which requires multi-step resolution (resolve patent → application number →
list file history → find grant document → download). There is no single-call
`number → PDF` surface. ODP's strength in this domain (prosecution
documents) is already exposed via `get_file_history_item`.

### Python API

```python
from patent_client_agents import download_patent_pdf

pdf = await download_patent_pdf("US10000000B2")
# PatentPdf(pdf_bytes=b"...", source="google_patents", filename="US10000000B2.pdf",
#           patent_number="US10000000B2", patent_title=None)

pdf.pdf_bytes      # raw bytes
pdf.source         # "google_patents" | "ppubs" | "epo"
pdf.filename       # suggested filename
```

`PatentPdf` is a frozen dataclass — stable for logging, serialization, and
pattern matching.

### MCP tool

```
download_patent_pdf(patent_number) -> dict
```

Returns the standard download response (`download_url` or `file_path`,
`filename`, `content_type`, `size_bytes`) plus a `source` field indicating
which backend served the bytes. Agents can check `source` to decide whether
OCR is needed before text extraction.

## JPO document bundles

The JPO `app_doc_cont_*` endpoints return a ZIP of file-history
documents — XML for patents, HTM for designs and trademarks (handbook
v14 §2(1)). Both formats are Shift-JIS encoded. Three `doc_kind` slices
× three `ip_type` registers = nine combinations, all served by one
tool.

```
get_jpo_documents(
    application_number,
    doc_kind: Literal["application", "mailed", "refusal"] = "mailed",
    ip_type: Literal["patent", "design", "trademark"] = "patent",
    parse: bool = True,
) -> dict
```

`doc_kind` slices:

- `"application"` — applicant-filed opinions and amendments
- `"mailed"` — JPO-mailed notices (rejections + decisions of grant)
- `"refusal"` — strict subset of `"mailed"`: refusal-reason notices only

When `parse=True` (the default), the tool fetches the bundle, decodes
the Shift-JIS payloads, and returns parsed entries inline (with body
text, examiner, statute references, etc.) plus a signed `download_url`
for the raw ZIP.

When `parse=False`, the tool fetches the bundle, caches the bytes for
the signed URL, and returns just the bundle metadata + the standard
download response (`download_url`, `filename`, `content_type`,
`size_bytes`, `expires_at`). Use this when handing the URL to a human
reviewer or to a separate processing pipeline that doesn't need parsed
entries in agent context.

Empty bundles (status 107/108) return `{}` regardless of `parse`. For
oversize bundles (>10 MB), JPO returns a redirect URL; the tool
resolves it transparently — agents always receive bytes, never a
"go fetch this other URL".

Daily quota is 100/day per `app_doc_cont_*` endpoint. Documents are
only available for filings after January 2019 (matches J-PlatPat search
scope). See [../sources/jpo.md](../sources/jpo.md) for full client
reference, status-code semantics, and quirks.

## Not included

- PTAB trial documents and decisions — use the container-bulk tools
  (`download_ptab_trial_documents`, `download_ptab_trial_decisions`,
  `download_ptab_appeal_decisions`, `download_ptab_interference_decisions`).
  These are a different document class (trial filings, not patent PDFs)
  with their own identifier space. n=1 is a raw PDF; n>1 is a zip.
- File-history documents — use `download_file_history(application_number,
  item_ids=[document_identifier])` for a single PDF (or a list of
  identifiers for a bulk zip). `get_file_history_item` returns available text
  without OCR. It returns a signed original PDF when no text layer exists.
  Its explicit `format='pdf'` mode was removed in favor of
  `download_file_history`.
