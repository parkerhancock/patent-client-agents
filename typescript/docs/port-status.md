# USPTO API port status

October 20, 2026. The independent Bun/TypeScript library covers all 70 inventoried
public Python domain methods across 12 USPTO network clients, plus current
ODP 5.0 additions and every route in the archived TSDR definition. This is
implementation coverage; verification below distinguishes live responses from
synthetic contracts. The Python package remains separate.

| Capability | Library and MCP | Verification |
| --- | --- | --- |
| Applications: search/get, metadata, adjustment, assignments, attorneys, continuity, foreign priority, transactions, status codes | Implemented; normalized and raw views | Real ODP cassettes for all listed datasets; live GET/POST and exports; synthetic pagination, filters and malformed responses |
| Document listing and associated metadata | Implemented; lean paginated file history | Live official sample has 184 documents |
| PDF/XML/DOCX, claims, family graph, identifier resolution and search exports | Implemented; REST artifacts for downloads | Real PDF/XML/DOCX and 32 granted claims; live CSV export; family traversal and edge cases synthetic; filtered file-history ZIP with manifest |
| PTAB trials, decisions, documents, appeals and interferences | Implemented; consolidated tools, JSON/CSV/PDF retrieval | Live GET/POST searches, identifiers, by-number lists, JSON/CSV exports and 1,249,216-byte PDF |
| Petition Decisions, including current outcome/status/text fields | Implemented | Live GET/POST search, detail and JSON/CSV exports |
| Bulk product catalog, details and file downloads | Implemented | Live catalog and 1,635-byte ZIP via approved data.uspto.gov redirect; larger files subject to explicit size limits |
| New Office Actions search, retrieval, exports and text download | All six official operations implemented | Live responses for all six operations, including JSON/CSV exports and text |
| Four legacy Office Action analytics datasets | All eight current records/field operations implemented | Live responses for all eight records/field operations |
| Patent and trademark assignments | Implemented | Three current Assignment Center v3 recordings, including 99 NIKE trademark matches |
| Patent Public Search | Search, document, publication resolution, PDF/base64 implemented | Native Bun live search/document/PDF success: 18 pages, 1,214,076 bytes; archived document verifies all 26 parsed claims |
| Trademark Search | Implemented with supplied WAF session, refresh callback or fresh-session provider; separate browser worker | Native Bun HTTP200 replays offline; fresh worker acquisition and protected-file delivery passed through default MCP and both Linux ARM64/AMD64 worker images |
| TSDR | All 25 archived official routes; source-derived document IDs; separate API key; MCP batch identifier types, ranges and filtered multicase XML/PDF/ZIP | Complete route-contract tests; successful live recordings for all 25 declared operations plus mark image; PDF/ZIP/XML/HTML checked offline; actual MCP option-forwarding and invalid-combination regressions |
| MPEP (additional corpus scope) | Read-only SQLite/FTS search, section/href lookup, installed versions/status; thin MCP tools and protected artifacts | Fresh pinned `E9_R-01.2024` build from all 42 official TOC roots, 29 chapters and 3,055 rows; compressed corpus and default MCP verification passed; legacy preparation preserves unknown release metadata |
| Search guides, field/status catalogs, schemas and Swagger resources | Eleven labeled MCP resources and pure library helpers | Resource enumeration, content and authorization tests; historical source labels preserved |
| REST document retrieval | MCP-issued single-use links by default; authenticated REST concurrently available; stdio files | Actual listener verifies expiry, issuer, audience, scope, ownership; signature, capacity, MIME and cleanup tests |
| EPO OPS and CPC (EPO scope) | Search, biblio, full text, citations, equivalents, INPADOC family, legal events, EP Register views, Unitary Patent package, family evidence, number conversion, merged PDF, CPC retrieval/search/mapping/media/CPCI; eight intent-based MCP tools under `epo:read` | 22 live recordings on October 21 replay offline; synthetic OAuth2, error and MCP tests. See [EPO OPS](epo-ops.md) |
| Fee schedules (EPO, Unitary Patent and USPTO; CIPO, CNIPA, DPMA, IP Australia, ILPO, IMPI) | `FeesClient` with Python-parity office resolution; EPO EPC and Unitary Patent schedules from the live EPO fee feed; USPTO patent (412 fees), trademark (113) and design (42) schedules from the USPTO fee schedule page, mapped by fee code; three MCP tools under `fees:read` | Live recordings replay offline; Article 2 RFeesUPP cross-check for the EPO and an eCFR Title 37 cross-check for the USPTO; seven Python USPTO categorization bugs corrected; 22 other offices report not yet ported. See [fees](fees.md) |
| Google Patents | Page metadata, claims, limitations, description Markdown, figures, citations, family, events; search; PDFs; three MCP tools under `patents:read` | Archived real pages and live recordings; parsers run in Bun, Node and Chromium. See [Google Patents](google-patents.md) |
| Federal Circuit opinions | Opinions and orders search with date and origin filters, Python-parity patent classifier, PDF downloads; three MCP tools under `cafc:read` | Live recording on October 21 replays offline; classifier matches Python on 426 inputs. See [CAFC](cafc.md) |
| UPC statutes | UPCA with the Statute, Rules of Procedure and Table of Court Fees in en/fr/de from the May 14, 2026 Python snapshot; three MCP tools and a status resource under `upc:read` | Real-row fixtures; full snapshot read through library, full and curated servers; German RoP text hash matches Python. See [UPC statutes](upc-statutes.md) |
| DPMA statutes | All six German IP Acts (PatG, MarkenG, GebrMG, DesignG, UrhG, GeschGehG) in full, 778 sections, built in TypeScript from the official gesetze-im-internet.de XML retrieved October 22, 2026, with each Act's Stand recorded; two MCP tools and a status resource under `dpma:read`; curated `corpus='dpma'` routed | The fixture is 16 real sections from that build; sections match the official HTML pages in spot checks. The schema is Python's; the Python connector still ships only its 12-row seed and the deployed Python server has no DPMA corpus at all. See [DPMA statutes](dpma-statutes.md) |
| WIPO Lex legislation | Legislation search and detail scraped from WIPO Lex, with row counts checked against the page; two MCP tools under `wipo:read` | Archived pages and a live recording on October 21; five Python bugs corrected. See [WIPO Lex](wipo-lex.md) |
| U.S. Copyright Office public records | Registration and recorded-document search and record lookup; two MCP tools under `copyright:read` | Live recording on October 21 across all four record families; works over HTTP/1.1 in Bun and Node. See [copyright](copyright.md) |
| TMEP | Read-only outline corpus from the deployed May 13, 2026 snapshot (1,751 sections); two MCP tools and a status resource under `uspto:read` | Real-row fixtures; full corpus read through library, full and curated servers, matching Python's section HTML and search hits. See [TMEP](tmep.md) |
| UKIPO Manual of Patent Practice (MoPP) | Read-only outline corpus from the deployed May 14, 2026 snapshot (192 pages); two MCP tools and a status resource under `ukipo:read`; routed by the curated facade as `ukipo_mopp` | Real-row fixtures; full corpus read through library, full and curated servers, matching Python's section HTML and top search hits; six Python bugs corrected. See [UKIPO MoPP](ukipo-mopp.md) |
| USITC | HTS search, IDS investigations and DataWeb reports without credentials; EDIS investigations, documents and attachment downloads with `USITC_EDIS_TOKEN`; tools under `usitc:read` | Public EDIS, HTS and IDS paths recorded and checked live; EDIS downloads and DataWeb reports tested synthetically only because both deployed tokens have expired (EDIS May 27, DataWeb September 27, 2026). See [USITC](usitc.md) |
| KIPO KIPRIS Plus | Patent/utility model, trademark and design search and lookup on the live KIPRIS Plus API (Python's OpenAPI host now answers 503); nine MCP tools under `kipo:read` when `KIPO_KIPRIS_API_KEY` is set | Built from the official KIPRIS Plus operation pages and their documented responses; not live-checked because no key exists. See [KIPRIS](kipris.md) |
| Taiwan Trade Secrets Act | All 25 Articles of the official English translation (amended January 15, 2020), retrieved October 22, 2026 and bundled in the package; two MCP tools and a status resource under `tw:read`; `tw_trade_secrets` in the curated legal-reference facade | Generated module checked against the archived page; search hits and snippets match Python's reader over the same text. Python's seed paraphrased 7 Articles and is not used. See [Taiwan Trade Secrets Act](tw-trade-secrets.md) |
| IPO India statutes and MPPP | Every section of the Patents Act 1970 (175), Designs Act 2000 (48), Trade Marks Act 1999 (169) and Copyright Act 1957 (105), every rule of the Patents Rules 2003 (155), and all of MPPP v3.0 (260 numbered paragraphs and chapters), built by `scripts/build-ipo-in-corpora.ts` from the official texts with sources, versions and hashes in `references/ipo-in/sources.json`; four MCP tools and two status resources under `ipoin:read`; curated `india_statutes` / `india_mppp` routing | Every row matches a fresh parse of the archived sources; spot checks of Patents Act ss. 3(d), 25 and 107A, Rule 13, Trade Marks Act s. 9 and MPPP 09.03 and 07.02; full and curated servers and the four live facade probes verified. The deployed Python server has no India corpus at all. See [IPO India](ipo-in.md) |
| UPC decisions | Not ported | unifiedpatentcourt.org now serves a Cloudflare challenge on every page except `robots.txt` and the decision PDFs, from both a home and an office connection (October 21); the Python connector fails the same way. A passive Chromium load (the WAF worker's method, headless or headed) stays on the challenge for 30 seconds and receives no `cf_clearance` cookie, so the worker cannot obtain a session without challenge interaction or automation masking, which the project does not do. Decision PDFs still download directly, but nothing that lists them does |
| Curated facade toolset | The deployed `patent-client-facade` tool names and parameters over the TypeScript clients, behind `toolset: "curated"` | Contract test against the exported Python schemas; 37 routing tests. See [facade](facade.md) |
| EPO legal corpora (EPC, Case Law, Guidelines, PCT-EPO and UP Guidelines) | Read-only SQLite/FTS readers with book-specific citations; ten MCP tools, five status resources, `epo:read` scope | Real-row fixtures for all five books; all five May 14, 2026 Python snapshots prepared, Zstandard-packaged, pinned and read through library and default MCP on October 21. Edition labels unverified; not deployed |

The [feature inventory](uspto-feature-inventory.md) maps every Python method to
its TypeScript counterpart. It excludes legal manuals, fees and CPC connectors
under other namespaces, and excludes aliases/facade wrappers from the domain
count. Library naming and normalization follow TypeScript conventions; this is
not a drop-in replacement for Python imports. MCP uses consolidated intent-based
tools rather than one tool per REST route.

## Remaining verification and deployment limits

All eight portal Swagger entry definitions and all seven original companions
are archived with hashes. Dev-browser captured the companion response bodies;
the captured main file matches the existing archive hash. All referenced files
are present, but two petition schema pointers in the official main file target
missing definitions in the official common file. The original archive is
complete; transitive schema resolution remains incomplete. Source files are
preserved without silently repairing those upstream defects. See
[source review](odp-research.md).

TSDR uses USPTO_TSDR_API_KEY; fresh verification used the existing deployed
Secret Manager key without saving its value locally. See [deployed authentication](deployed-uspto-auth.md).
Trademark Search needs an externally supplied
current WAF token with its matching User-Agent, or a trusted refresh callback.
The separate optional Bun/Playwright worker now acquires sessions and publishes
them through protected files or Secret Manager. Configured MCP providers load
rotated sessions without restarting. See [worker setup](waf-worker.md). No
production worker/job cutover has been performed. Native Fetch behavior remains
a separate verification from Python curl_cffi's TLS behavior. PPUBS native Bun behavior was
verified for the recorded sample, not guaranteed for every future WAF policy.

The [operation evidence map](uspto-operation-coverage.md) now links successful
recordings for all 92 inventoried method/path operations. This verifies the
recorded public samples, not every parameter combination or every record.
Default tests never silently fall back to live traffic.
Missing required cassettes fail. Recorders are deliberate and bounded; signed
redirect credentials must be scrubbed from locations and response bodies as
well as request URIs. Preserve successful recordings when refreshing a subset,
and respect upstream 429 responses.

A final library/MCP audit closed PPUBS unknown-field preservation and TSDR MCP
batch/bundle option gaps. Normalized PPUBS values remain authoritative over raw
name collisions. No further missing method or route was found within the stated
70-method, 12-client USPTO network scope; legal manuals, fees and CPC remain
outside that inventory.

MPEP now adds a corpus connector beyond that 12-client network inventory. The
fresh local artifact has verified base-release identity and explicit cutoff,
build/sync time and interim-update coverage. Later guidance is not incorporated.
Appendix/form-paragraph/index extraction granularity is recorded in its manifest;
root coverage is not a promise of every separately linked child document.
The older May 21 artifact remains an unknown release after standalone preparation.
Whole-file Zstandard distribution now reduces the fresh artifact from 48.70 MB
to 17.01 MB, with independent file/decoded pins and unchanged source metadata.
The [corpus pattern](corpus-pattern.md) documents bounded in-memory loading.
See [MPEP setup](mpep.md), [source review](mpep-source-review.md) and
[connector patterns](connector-patterns.md). Neither artifact was deployed.

Remote identity-provider login/discovery and hosted HTTPS are not deployed.
MCP-issued single-use links are the default until host credential injection
stabilizes. They expire after 15 minutes by default; the first GET consumes the
link before file reading. HEAD does not consume it, and Range requests are
rejected without consumption. Failed or interrupted GETs require a new MCP link.
Authenticated REST remains available for the same artifact by removing the
expires/signature URL parameters and supplying a bearer token. It does not
consume the link and remains available until artifact expiry. A trusted host
downloader for supplying OAuth tokens outside model context is not implemented.
MCP scope is odp:read for ODP, uspto:read for other USPTO families, and
REST documents:read for artifacts. REST ownership uses the originating issuer
and subject. A separately configured REST audience must preserve that identity.

The per-process artifact cache is bounded, expires idle artifacts and removes
owned files on graceful shutdown. Abrupt crashes may leave temporary files.
Multiple replicas need shared storage or request affinity. Responses default to
a 64 MiB buffering limit; this implementation does not stream multi-gigabyte
bulk dumps. Native streaming can be added when that workflow is needed.
Library cancellation includes response-body deadlines and caller aborts. MCP
cancellation propagation awaits a supported FastMCP context signal. Rust/WASM extraction remains a profiling-driven path.

## EPO Open Patent Services

October 21, 2026. The [EPO OPS port](epo-ops.md) covers every public method of
the Python `epo_ops` and `cpc` clients and the Python MCP family-intelligence
aggregate, and establishes the first upstream OAuth2 token lifecycle. All 22
recorded operations succeeded live with the deployed OPS credentials read into
memory; recordings omit tokens, client ids and caller IP headers. This verifies
the recorded samples, not every OPS service or parameter. OPS tools are not
deployed, and `getCpcMedia` is tested only for id validation.

## EPO legal corpora

October 21, 2026. Five EPO books join MPEP as offline corpus connectors; see
[EPO legal corpora](epo-legal.md). This is implementation plus local artifact
verification, not EPO network coverage; OPS and CPC are covered by
[EPO OPS](epo-ops.md).
The installed snapshots record EPC 2020, Case Law 2022, Guidelines 2024,
PCT-EPO Guidelines 2024 and UP Guidelines 2026 as crawl-path editions. No
release check confirms those are EPO's current editions. Fresh builds still use
the Python builders. The crawled text has an upstream heading defect that
hides some heading words from search. No artifact was deployed.

## Fee schedules

October 21, 2026. EPO fees establish the TypeScript [fee pattern](fees.md):
decimal-string amounts, published effective dates kept apart from retrieval
time, explicit code maps that report unmapped codes, and renewal coverage
computed from the parsed rows. The port separates Unitary Patent fees from EP
application fees, which the Python schedule mixes. The other 23 offices in the
Python fees package are not ported. Nothing is deployed.

## Runtimes

October 21, 2026. The client library runs in Bun, Node and browsers, with
WebAssembly SQLite and Zstandard in every runtime and an authenticated relay
for office APIs a browser cannot call directly. Node and headless-Chromium
smoke tests are part of `bun run check`. See [runtimes](runtimes.md). The relay
is not deployed or tried against real office endpoints.

## Google Patents

October 21, 2026. The [Google Patents port](google-patents.md) establishes the
whole-page HTML pattern and corrects several places where the Python parser
has fallen behind Google's current markup or query rules. It is unofficial and
throttled; nothing is deployed.

## Curated facade

October 21, 2026. The [curated toolset](facade.md) serves the deployed facade's
tool surface with identical inputs. Twenty-nine of the thirty Python tools are
served; `search_upc_decisions` waits on access to the UPC decisions site, which
now sits behind a Cloudflare challenge. All
served tools and modes passed a live check on October 21; not deployed.
