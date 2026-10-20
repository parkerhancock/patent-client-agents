# USPTO Python feature inventory

Audited October 20, 2026 from the local Python source using AST extraction. This is the parity target, not a claim that the TypeScript implementation or upstream live service has been verified. Method names are Python names; equivalent TypeScript behavior may use idiomatic names. Count each domain client once: the unified ODP client and one-shot facades below delegate to these same features. Lifecycle methods, models, private helpers, and inherited transport methods are excluded from the operation count.

## Domain clients

70 public domain-client methods across 12 clients. Search variants, pagination helpers, and download encodings remain separate behaviors even where they share an HTTP route.

| Source / client | Public methods |
| --- | --- |
| [`uspto_assignments/client.py`](../../src/patent_client_agents/uspto_assignments/client.py) · `AssignmentCenterClient` | `search`, `details` |
| [`uspto_odp/clients/applications.py`](../../src/patent_client_agents/uspto_odp/clients/applications.py) · `ApplicationsClient` | `search`, `get`, `get_documents`, `download_document`, `download_document_xml`, `download_document_docx`, `download_documents`, `get_assignment`, `get_family`, `get_granted_claims`, `resolve_identifier` |
| [`uspto_odp/clients/bulkdata.py`](../../src/patent_client_agents/uspto_odp/clients/bulkdata.py) · `BulkDataClient` | `search`, `get_product` |
| [`uspto_odp/clients/petitions.py`](../../src/patent_client_agents/uspto_odp/clients/petitions.py) · `PetitionsClient` | `search`, `download`, `get` |
| [`uspto_odp/clients/ptab_appeals.py`](../../src/patent_client_agents/uspto_odp/clients/ptab_appeals.py) · `PtabAppealsClient` | `search`, `get_decision`, `get_decisions_by_number`, `download` |
| [`uspto_odp/clients/ptab_interferences.py`](../../src/patent_client_agents/uspto_odp/clients/ptab_interferences.py) · `PtabInterferencesClient` | `search`, `get_decision`, `get_decisions_by_number`, `download` |
| [`uspto_odp/clients/ptab_trials.py`](../../src/patent_client_agents/uspto_odp/clients/ptab_trials.py) · `PtabTrialsClient` | `search_proceedings`, `get_proceeding`, `download_proceedings`, `search_decisions`, `get_decision`, `get_decisions_by_trial`, `download_decisions`, `search_documents`, `get_document`, `get_documents_by_trial`, `download_documents`, `download_document_pdf` |
| [`uspto_office_actions/client.py`](../../src/patent_client_agents/uspto_office_actions/client.py) · `OfficeActionClient` | `search_rejections`, `search_citations`, `search_office_action_text`, `search_enriched_citations` |
| [`uspto_publications/client.py`](../../src/patent_client_agents/uspto_publications/client.py) · `PublicSearchClient` | `search_biblio`, `get_document`, `download_pdf`, `download_pdf_base64`, `resolve_document_by_publication_number` |
| [`uspto_tmsearch/client.py`](../../src/patent_client_agents/uspto_tmsearch/client.py) · `TmsearchClient` | `search_wordmark`, `search_owner`, `search_goods_services`, `get_by_serial`, `get_by_registration`, `search`, `search_all` |
| [`uspto_trademark_assignments/client.py`](../../src/patent_client_agents/uspto_trademark_assignments/client.py) · `TrademarkAssignmentClient` | `search_by_assignee`, `search_by_assignor`, `search_by_serial`, `search_by_registration`, `search_by_reel_frame`, `search`, `search_all` |
| [`uspto_tsdr/client.py`](../../src/patent_client_agents/uspto_tsdr/client.py) · `TsdrClient` | `get_status`, `get_status_json`, `get_last_update`, `get_documents`, `download_documents_pdf`, `download_documents_zip`, `get_image`, `get_status_html`, `batch_status` |

## Behavior checklist

| Family | Behaviors to preserve |
| --- | --- |
| Applications | Query/filter/range/sort/field/facet/pagination/raw-payload options; get by application number; document listing and date/code filters; single/batch binary downloads; XML parsing; DOCX conversion; assignment data; continuity family graph; granted claims; patent/publication/application identifier resolution. |
| PTAB | Proceedings, decisions, documents; search and export; exact identifiers and trial/appeal/interference lookup; PDF download. Do not merge appeal/interference response bags or namespaces with trials. |
| Petitions | Search/export/get; current 5.0 final-decision text and metadata contract must be checked separately from the historical Python schema. |
| Bulk data | Catalog search and product detail, with file download metadata. Current official OpenAPI also declares direct product-file download. |
| Office Actions | Four migrated analytics APIs: rejections, citations, text retrieval, enriched citations. Current 5.0 Office Action search/get/export/full-text download is additional coverage. |
| Patent assignments | Assignment Center search and detail with structured parties, properties, conveyance, and reel/frame data. |
| Trademark assignments | Search by assignee/assignor/serial/registration/reel-frame; generic search and multi-page collection. |
| TSDR | Parsed XML status, raw JSON, last-update metadata, document listing, PDF/ZIP downloads, mark image, status HTML, batch status. Separate TSDR API key and server. |
| Public Patent Search | Bibliographic search, full structured document including claims/references, PDF bytes/base64, publication-number resolution and source selection. Preserve query syntax checking and publication normalization. |
| Trademark Search | Wordmark/owner/goods-services query helpers; serial/registration lookup; generic search and all-pages collection; session token acquisition/refresh. |

## Delegating facades

These are compatibility/convenience entry points, not additional upstream APIs.

| Source | Public functions / methods |
| --- | --- |
| [`uspto_applications/api.py`](../../src/patent_client_agents/uspto_applications/api.py) | `get_client`, `search_applications`, `get_application`, `list_documents`, `get_family`, `search_trial_proceedings`, `get_trial_proceeding`, `search_trial_decisions`, `get_trial_decisions_by_trial`, `search_trial_documents`, `get_trial_documents_by_trial`, `search_appeal_decisions`, `get_appeal_decisions_by_number`, `search_interference_decisions`, `get_interference_decisions_by_number` |
| [`uspto_bulkdata/api.py`](../../src/patent_client_agents/uspto_bulkdata/api.py) | `get_client`, `search_products`, `get_product` |
| [`uspto_odp/client.py`](../../src/patent_client_agents/uspto_odp/client.py) | `search_applications`, `get_application`, `get_documents`, `get_family`, `get_assignment`, `download_document`, `download_documents`, `search_bulk_datasets`, `get_bulk_dataset_product`, `search_petitions`, `download_petitions`, `get_petition`, `search_trial_proceedings`, `get_trial_proceeding`, `download_trial_proceedings`, `search_trial_decisions`, `get_trial_decision`, `get_trial_decisions_by_trial`, `download_trial_decisions`, `search_trial_documents`, `get_trial_document`, `get_trial_documents_by_trial`, `download_trial_documents`, `search_appeal_decisions`, `get_appeal_decision`, `get_appeal_decisions_by_number`, `download_appeal_decisions`, `search_interference_decisions`, `get_interference_decision`, `get_interference_decisions_by_number`, `download_interference_decisions` |
| [`uspto_petitions/api.py`](../../src/patent_client_agents/uspto_petitions/api.py) | `get_client`, `search_petitions`, `get_petition`, `download_petitions` |
| [`uspto_publications/api.py`](../../src/patent_client_agents/uspto_publications/api.py) | `get_client`, `search`, `get_document`, `download_pdf`, `resolve_publication`, `resolve_and_download_pdf` |

`uspto_publications.api.resolve_and_download_pdf` composes resolution and download and returns a `PdfResponse` with base64 data and publication/title metadata. Preserve the workflow even if exposing bytes separately. `get_client` and context-manager/close behavior are resource lifecycle concerns rather than API operations.

## Local parsing and documentation contracts

These need parity decisions even though they do not add network endpoints.

| Source | Public helpers |
| --- | --- |
| [`uspto_odp/xml_parser.py`](../../src/patent_client_agents/uspto_odp/xml_parser.py) | `parse_claims_xml`, `parse_grant_claims_xml`, `parse_spec_xml`, `parse_document_xml` |
| [`uspto_publications/utils.py`](../../src/patent_client_agents/uspto_publications/utils.py) | `html_to_text`, `ClaimsParser.parse`, `normalize_publication_number` |
| [`uspto_publications/resources.py`](../../src/patent_client_agents/uspto_publications/resources.py) | `get_search_guide`, `get_searchable_indexes_resource` |
| [`uspto_odp/resources.py`](../../src/patent_client_agents/uspto_odp/resources.py) | `get_odp_swagger_spec` |
| [`uspto_bulkdata/resources.py`](../../src/patent_client_agents/uspto_bulkdata/resources.py) | `get_product_guide`, `get_bulkdata_response_schema`, `get_patent_data_schema`, `get_petition_decision_schema` |

`uspto_publications.client.check_query_syntax` is also public. ODP resources additionally publish search-guide, field-catalog, status-code, and Swagger resource URI/constants. Bulk-data resources publish product guidance and JSON schema text. These historical documentation snapshots must retain their source/freshness labels when exposed through MCP.

Models are contracts rather than separate operations: preserve absent-versus-null semantics, arrays/bags, identifiers, claims and dependency metadata, parties, dates, pagination, unknown upstream fields, and provenance. Source model files live alongside each client and in `uspto_odp/models/`.

The current-source archive and unresolved-schema limitations are documented in [odp-research.md](odp-research.md). Implementation/live/cassette status belongs in [port-status.md](port-status.md), which must be checked before claiming feature completeness.

`SearchPayload.model_dump_pruned` in `uspto_odp/clients/base.py` serializes the request model and is excluded from the domain-method count; preserve payload-pruning behavior where the public search contract relies on it.

## Current TypeScript method mapping

A source-level audit on October 20 found a named TypeScript counterpart for every one of the 70 domain methods below. This checks method declarations only; it does not verify signatures, semantics, error handling, formats, cassette coverage, or live operation. PTAB appeal/interference `search` and `download` are inherited from the shared PTAB client. See [machine-readable mapping](../references/odp/uspto-parity-methods.json) for source paths.

| Python client.method | TypeScript source and method | Name present |
| --- | --- | --- |
| `ApplicationsClient.search` | [applications.ts](../../typescript/packages/client/src/applications.ts) · `search` | Yes |
| `ApplicationsClient.get` | [applications.ts](../../typescript/packages/client/src/applications.ts) · `get` | Yes |
| `ApplicationsClient.get_documents` | [applications.ts](../../typescript/packages/client/src/applications.ts) · `getDocuments` | Yes |
| `ApplicationsClient.download_document` | [applications.ts](../../typescript/packages/client/src/applications.ts) · `downloadDocument` | Yes |
| `ApplicationsClient.download_document_xml` | [applications.ts](../../typescript/packages/client/src/applications.ts) · `downloadDocumentXml` | Yes |
| `ApplicationsClient.download_document_docx` | [applications.ts](../../typescript/packages/client/src/applications.ts) · `downloadDocumentDocx` | Yes |
| `ApplicationsClient.download_documents` | [applications.ts](../../typescript/packages/client/src/applications.ts) · `downloadDocuments` | Yes |
| `ApplicationsClient.get_assignment` | [applications.ts](../../typescript/packages/client/src/applications.ts) · `getAssignment` | Yes |
| `ApplicationsClient.get_family` | [applications.ts](../../typescript/packages/client/src/applications.ts) · `getFamily` | Yes |
| `ApplicationsClient.get_granted_claims` | [applications.ts](../../typescript/packages/client/src/applications.ts) · `getGrantedClaims` | Yes |
| `ApplicationsClient.resolve_identifier` | [applications.ts](../../typescript/packages/client/src/applications.ts) · `resolveIdentifier` | Yes |
| `BulkDataClient.search` | [bulkdata.ts](../../typescript/packages/client/src/bulkdata.ts) · `search` | Yes |
| `BulkDataClient.get_product` | [bulkdata.ts](../../typescript/packages/client/src/bulkdata.ts) · `getProduct` | Yes |
| `PetitionsClient.search` | [petitions.ts](../../typescript/packages/client/src/petitions.ts) · `search` | Yes |
| `PetitionsClient.download` | [petitions.ts](../../typescript/packages/client/src/petitions.ts) · `download` | Yes |
| `PetitionsClient.get` | [petitions.ts](../../typescript/packages/client/src/petitions.ts) · `get` | Yes |
| `PtabTrialsClient.search_proceedings` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `searchProceedings` | Yes |
| `PtabTrialsClient.get_proceeding` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `getProceeding` | Yes |
| `PtabTrialsClient.download_proceedings` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `downloadProceedings` | Yes |
| `PtabTrialsClient.search_decisions` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `searchDecisions` | Yes |
| `PtabTrialsClient.get_decision` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `getDecision` | Yes |
| `PtabTrialsClient.get_decisions_by_trial` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `getDecisionsByTrial` | Yes |
| `PtabTrialsClient.download_decisions` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `downloadDecisions` | Yes |
| `PtabTrialsClient.search_documents` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `searchDocuments` | Yes |
| `PtabTrialsClient.get_document` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `getDocument` | Yes |
| `PtabTrialsClient.get_documents_by_trial` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `getDocumentsByTrial` | Yes |
| `PtabTrialsClient.download_documents` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `downloadDocuments` | Yes |
| `PtabTrialsClient.download_document_pdf` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `downloadDocumentPdf` | Yes |
| `PtabAppealsClient.search` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `search` | Yes |
| `PtabAppealsClient.get_decision` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `getDecision` | Yes |
| `PtabAppealsClient.get_decisions_by_number` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `getDecisionsByNumber` | Yes |
| `PtabAppealsClient.download` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `download` | Yes |
| `PtabInterferencesClient.search` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `search` | Yes |
| `PtabInterferencesClient.get_decision` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `getDecision` | Yes |
| `PtabInterferencesClient.get_decisions_by_number` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `getDecisionsByNumber` | Yes |
| `PtabInterferencesClient.download` | [ptab.ts](../../typescript/packages/client/src/ptab.ts) · `download` | Yes |
| `OfficeActionClient.search_rejections` | [office-action-analytics.ts](../../typescript/packages/client/src/office-action-analytics.ts) · `searchRejections` | Yes |
| `OfficeActionClient.search_citations` | [office-action-analytics.ts](../../typescript/packages/client/src/office-action-analytics.ts) · `searchCitations` | Yes |
| `OfficeActionClient.search_office_action_text` | [office-action-analytics.ts](../../typescript/packages/client/src/office-action-analytics.ts) · `searchOfficeActionText` | Yes |
| `OfficeActionClient.search_enriched_citations` | [office-action-analytics.ts](../../typescript/packages/client/src/office-action-analytics.ts) · `searchEnrichedCitations` | Yes |
| `AssignmentCenterClient.search` | [assignments.ts](../../typescript/packages/client/src/assignments.ts) · `search` | Yes |
| `AssignmentCenterClient.details` | [assignments.ts](../../typescript/packages/client/src/assignments.ts) · `details` | Yes |
| `TrademarkAssignmentClient.search_by_assignee` | [trademark-assignments.ts](../../typescript/packages/client/src/trademark-assignments.ts) · `searchByAssignee` | Yes |
| `TrademarkAssignmentClient.search_by_assignor` | [trademark-assignments.ts](../../typescript/packages/client/src/trademark-assignments.ts) · `searchByAssignor` | Yes |
| `TrademarkAssignmentClient.search_by_serial` | [trademark-assignments.ts](../../typescript/packages/client/src/trademark-assignments.ts) · `searchBySerial` | Yes |
| `TrademarkAssignmentClient.search_by_registration` | [trademark-assignments.ts](../../typescript/packages/client/src/trademark-assignments.ts) · `searchByRegistration` | Yes |
| `TrademarkAssignmentClient.search_by_reel_frame` | [trademark-assignments.ts](../../typescript/packages/client/src/trademark-assignments.ts) · `searchByReelFrame` | Yes |
| `TrademarkAssignmentClient.search` | [trademark-assignments.ts](../../typescript/packages/client/src/trademark-assignments.ts) · `search` | Yes |
| `TrademarkAssignmentClient.search_all` | [trademark-assignments.ts](../../typescript/packages/client/src/trademark-assignments.ts) · `searchAll` | Yes |
| `TsdrClient.get_status` | [tsdr.ts](../../typescript/packages/client/src/tsdr.ts) · `getStatus` | Yes |
| `TsdrClient.get_status_json` | [tsdr.ts](../../typescript/packages/client/src/tsdr.ts) · `getStatusJson` | Yes |
| `TsdrClient.get_last_update` | [tsdr.ts](../../typescript/packages/client/src/tsdr.ts) · `getLastUpdate` | Yes |
| `TsdrClient.get_documents` | [tsdr.ts](../../typescript/packages/client/src/tsdr.ts) · `getDocuments` | Yes |
| `TsdrClient.download_documents_pdf` | [tsdr.ts](../../typescript/packages/client/src/tsdr.ts) · `downloadDocumentsPdf` | Yes |
| `TsdrClient.download_documents_zip` | [tsdr.ts](../../typescript/packages/client/src/tsdr.ts) · `downloadDocumentsZip` | Yes |
| `TsdrClient.get_image` | [tsdr.ts](../../typescript/packages/client/src/tsdr.ts) · `getImage` | Yes |
| `TsdrClient.get_status_html` | [tsdr.ts](../../typescript/packages/client/src/tsdr.ts) · `getStatusHtml` | Yes |
| `TsdrClient.batch_status` | [tsdr.ts](../../typescript/packages/client/src/tsdr.ts) · `batchStatus` | Yes |
| `PublicSearchClient.search_biblio` | [publications.ts](../../typescript/packages/client/src/publications.ts) · `searchBiblio` | Yes |
| `PublicSearchClient.get_document` | [publications.ts](../../typescript/packages/client/src/publications.ts) · `getDocument` | Yes |
| `PublicSearchClient.download_pdf` | [publications.ts](../../typescript/packages/client/src/publications.ts) · `downloadPdf` | Yes |
| `PublicSearchClient.download_pdf_base64` | [publications.ts](../../typescript/packages/client/src/publications.ts) · `downloadPdfBase64` | Yes |
| `PublicSearchClient.resolve_document_by_publication_number` | [publications.ts](../../typescript/packages/client/src/publications.ts) · `resolveDocumentByPublicationNumber` | Yes |
| `TmsearchClient.search_wordmark` | [trademark-search.ts](../../typescript/packages/client/src/trademark-search.ts) · `searchWordmark` | Yes |
| `TmsearchClient.search_owner` | [trademark-search.ts](../../typescript/packages/client/src/trademark-search.ts) · `searchOwner` | Yes |
| `TmsearchClient.search_goods_services` | [trademark-search.ts](../../typescript/packages/client/src/trademark-search.ts) · `searchGoodsServices` | Yes |
| `TmsearchClient.get_by_serial` | [trademark-search.ts](../../typescript/packages/client/src/trademark-search.ts) · `getBySerial` | Yes |
| `TmsearchClient.get_by_registration` | [trademark-search.ts](../../typescript/packages/client/src/trademark-search.ts) · `getByRegistration` | Yes |
| `TmsearchClient.search` | [trademark-search.ts](../../typescript/packages/client/src/trademark-search.ts) · `search` | Yes |
| `TmsearchClient.search_all` | [trademark-search.ts](../../typescript/packages/client/src/trademark-search.ts) · `searchAll` | Yes |

The TypeScript library now provides the historical documentation constants and
public resource helpers in `packages/client/src/uspto-resources.ts`, with static
content bundled independently of Python. MCP registration is in
`packages/mcp/src/resources.ts`: all ten historical Python resource URIs plus a
separate `resource://uspto-odp/current-main-swagger` index are available.
Historical guides/status codes are labeled as unverified snapshots, the bulk
product guide is labeled 2025, and the current main Swagger is explicitly an
incomplete external-reference index. JSON schema resource descriptions carry
freshness information while schema bytes remain unchanged. Five focused tests
verify content preservation, JSON parsing, snapshot distinction, all resource
reads/listings, and authorization denial. This closes static resource parity;
it does not refresh historical documentation against current upstream behavior.


## Current HTTP operations are a separate coverage target

The [current operation audit](uspto-operation-coverage.md) maps 92 method/path
operations across the eight current portal definitions to client methods,
declared request/response contracts, tests, and recorded HTTP interactions.
Sixty-three operations come from archived original entry files and 29 PTAB
operations were confirmed in the rendered current Swagger UI. It found 15 GET
variants that the earlier 70-method name check did not detect; the owning
workers added their dispatch and query handling. All 92 now have named entry
points, with per-operation evidence and limitations in the machine-readable
map. Neither that mapping nor a matching method declaration proves complete
behavioral parity or a resolved upstream schema bundle.
