# Current USPTO HTTP operation coverage

Audited October 20, 2026. The current eight portal definitions expose **92 HTTP
method/path operations**. Sixty-three are parsed from the archived entry files;
the other 29 are PTAB companion operations confirmed in the rendered official
Swagger UI. The rendered main definition contains 48 operations. This is a
separate denominator from the 70 public Python domain-client methods.

The [machine-readable map](../references/odp/uspto-operation-coverage.json)
links every operation to its client method, source contract, declared parameters
and media types where available, test evidence, and recorded HTTP interactions.
Test links explicitly distinguish direct method calls from family-level tests;
they do not certify every parameter, response shape, or error condition.

## Current evidence

| Client | Current operations | Direct HTTP 200 | Successful recordings |
| --- | ---: | ---: | ---: |
| `ApplicationsClient` | 16 | 16 | 16 |
| `BulkDataClient` | 3 | 2 | 3 |
| `OfficeActionAnalyticsClient` | 8 | 8 | 8 |
| `OfficeActionsClient` | 6 | 6 | 6 |
| `PetitionsClient` | 5 | 5 | 5 |
| `PtabAppealsClient` | 6 | 6 | 6 |
| `PtabInterferencesClient` | 6 | 6 | 6 |
| `PtabTrialsClient` | 17 | 17 | 17 |
| `TsdrClient` | 25 | 6 | 6 |
| Total | 92 | 72 | 73 |

Successful recordings include direct HTTP 200 and the bulk-file operation's
explicitly described HTTP 302 followed by a recorded HTTP 200 ZIP download from
`data.uspto.gov`. Its official definition incorrectly nests the 302 response
at path-item level; the GET description independently names 302. The machine
map preserves that source anomaly and both recorded interactions separately.
HTTP 200 recordings are matching method/path observations, not proof that every
response is semantically correct. The linked replay tests supply semantic
assertions separately. Distinct content formats on one method/path are one
operation in this table; format-specific behavior still needs its own tests.
Seven fresh authenticated TSDR requests replay successfully: status JSON,
document list XML, last-update JSON/XML, image bytes, and single-document
XML/PDF. Six match operations in the current 25-operation TSDR entry definition;
`GET /ts/cd/rawImage/{serial}` is a supported extra route outside that definition.
The remaining 19 declared TSDR method/path operations lack matching successful
recordings. The current status path's recorded response is JSON; this does not
validate the XML representation advertised by the schema for the same path.
Two upstream HTTP 400 receipts for invalid document identifiers are negative
evidence and do not count toward success.

The binary application download workflow, PPUBS, Assignment Center, and
Trademark Search have separate parity/recording evidence because these eight
entry definitions do not enumerate all of their operations.

## Gaps found by reviewing HTTP contracts

The earlier 70-method inventory could not establish current HTTP completeness.
This audit found 15 GET variants missing from the first implementation:
application search, application export, status codes, Petition Decisions search
and export, and search/export for each of the five PTAB datasets. Their owning
workers added GET dispatch and documented query serialization, while retaining
POST for multi-clause filters/ranges/sorts whose GET representation is not
established by the available examples. Review the linked tests and worker
reports before treating an untested GET request as live-verified.

All 92 operations now have named client entry points. This is implementation
navigation evidence, not a blanket behavioral-parity claim. Fresh live coverage
still differs by operation; the table above reports recorded evidence. Raw
PTAB/common schema files remain unarchived locally.

## Source limitations

The [rendered operation observation](../references/odp/swagger-ui-operations-2026-10-20.json)
records the current method/path list and browser extraction method. The page's
asset inventory observed all seven companion fetch URLs. Exporting a permitted
trial-proceedings asset failed because the browser's supported asset exporter
does not export YAML/other assets. The earlier blocked common-base URL was not
directly navigated to or exported again. No original companion bytes were
obtained in this audit, so the complete-schema flag remains false.

Rendered PTAB GET proceedings documentation lists q, sort, offset, limit,
facets, fields, filters and rangeFilters. Its 413 response example describes a
6 MB upstream payload limit. Missing raw schema parameters are recorded as
unknown in the map, rather than copied from a historical specification and
relabeled current. The `text-to-search` placeholder declares no HTTP method
and is excluded. Some official definitions contain their own inconsistencies:
legacy analytics declare dataset/version path parameters even though their
paths contain literals; TSDR bundle operations omit identifier query parameters.
The map preserves those declarations without inventing a corrected schema.

## Operation map

`Raw` means the current original entry definition is archived. `UI` means the
current method/path was observed in Swagger UI but companion schema bytes are
not archived. Recorded links identify matching HTTP 200 interactions in local
cassettes, or an explicitly labeled declared redirect workflow. The presence of
a cassette does not establish that it has been committed.

| Method and path | Client method | Source | Live evidence |
| --- | --- | --- | --- |
| `GET /api/v1/datasets/products/files/{productIdentifier}/{fileName}` | [BulkDataClient.downloadFile](../packages/client/src/bulkdata.ts) | Raw | [Declared 302 → 200 download](../tests/cassettes/odp-bulk-file.yaml) |
| `GET /api/v1/datasets/products/search` | [BulkDataClient.search](../packages/client/src/bulkdata.ts) | Raw | [odp-bulk-products.yaml](../tests/cassettes/odp-bulk-products.yaml) |
| `GET /api/v1/datasets/products/{productIdentifier}` | [BulkDataClient.getProduct](../packages/client/src/bulkdata.ts) | Raw | [odp-bulk-products.yaml](../tests/cassettes/odp-bulk-products.yaml); [odp-features-bulk-identifier.yaml](../tests/cassettes/odp-features-bulk-identifier.yaml) |
| `GET /api/v1/patent/appeals/decisions/search` | [PtabAppealsClient.search](../packages/client/src/ptab.ts) | UI | [odp-features-appeals-get-search.yaml](../tests/cassettes/odp-features-appeals-get-search.yaml) |
| `GET /api/v1/patent/appeals/decisions/search/download` | [PtabAppealsClient.downloadFile](../packages/client/src/ptab.ts) | UI | [odp-features-appeals-get-csv.yaml](../tests/cassettes/odp-features-appeals-get-csv.yaml); [odp-features-appeals-get-json.yaml](../tests/cassettes/odp-features-appeals-get-json.yaml) |
| `GET /api/v1/patent/appeals/decisions/{documentIdentifier}` | [PtabAppealsClient.getDecision](../packages/client/src/ptab.ts) | UI | [odp-features-appeals-get-search.yaml](../tests/cassettes/odp-features-appeals-get-search.yaml); [odp-features-appeals-identifier.yaml](../tests/cassettes/odp-features-appeals-identifier.yaml) |
| `GET /api/v1/patent/appeals/{appealNumber}/decisions` | [PtabAppealsClient.getDecisionsByNumber](../packages/client/src/ptab.ts) | UI | [odp-features-appeals-by-number.yaml](../tests/cassettes/odp-features-appeals-by-number.yaml) |
| `GET /api/v1/patent/applications/search` | [ApplicationsClient.search](../packages/client/src/applications.ts) | Raw | [odp-application-get-search.yaml](../tests/cassettes/odp-application-get-search.yaml) |
| `GET /api/v1/patent/applications/search/download` | [ApplicationsClient.downloadSearch](../packages/client/src/applications.ts) | Raw | [odp-application-get-download.yaml](../tests/cassettes/odp-application-get-download.yaml) |
| `GET /api/v1/patent/applications/{applicationNumberText}` | [ApplicationsClient.get](../packages/client/src/applications.ts) | Raw | [odp-application-get-search.yaml](../tests/cassettes/odp-application-get-search.yaml); [odp-application.yaml](../tests/cassettes/odp-application.yaml) |
| `GET /api/v1/patent/applications/{applicationNumberText}/adjustment` | [ApplicationsClient.getAdjustment](../packages/client/src/applications.ts) | Raw | [odp-application-adjustment.yaml](../tests/cassettes/odp-application-adjustment.yaml) |
| `GET /api/v1/patent/applications/{applicationNumberText}/assignment` | [ApplicationsClient.getAssignment](../packages/client/src/applications.ts) | Raw | [odp-application-assignment.yaml](../tests/cassettes/odp-application-assignment.yaml) |
| `GET /api/v1/patent/applications/{applicationNumberText}/associated-documents` | [ApplicationsClient.getAssociatedDocuments](../packages/client/src/applications.ts) | Raw | [odp-application-granted-claims.yaml](../tests/cassettes/odp-application-granted-claims.yaml); [odp-documents.yaml](../tests/cassettes/odp-documents.yaml) |
| `GET /api/v1/patent/applications/{applicationNumberText}/attorney` | [ApplicationsClient.getAttorney](../packages/client/src/applications.ts) | Raw | [odp-application-attorney.yaml](../tests/cassettes/odp-application-attorney.yaml) |
| `GET /api/v1/patent/applications/{applicationNumberText}/continuity` | [ApplicationsClient.getContinuity](../packages/client/src/applications.ts) | Raw | [odp-application-continuity.yaml](../tests/cassettes/odp-application-continuity.yaml) |
| `GET /api/v1/patent/applications/{applicationNumberText}/documents` | [ApplicationsClient.getDocuments](../packages/client/src/applications.ts) | Raw | [odp-application-docx.yaml](../tests/cassettes/odp-application-docx.yaml); [odp-application-granted-claims.yaml](../tests/cassettes/odp-application-granted-claims.yaml); [odp-application-pdf.yaml](../tests/cassettes/odp-application-pdf.yaml); [odp-application-xml.yaml](../tests/cassettes/odp-application-xml.yaml); [odp-documents.yaml](../tests/cassettes/odp-documents.yaml) |
| `GET /api/v1/patent/applications/{applicationNumberText}/foreign-priority` | [ApplicationsClient.getForeignPriority](../packages/client/src/applications.ts) | Raw | [odp-application-foreign-priority.yaml](../tests/cassettes/odp-application-foreign-priority.yaml) |
| `GET /api/v1/patent/applications/{applicationNumberText}/meta-data` | [ApplicationsClient.getMetadata](../packages/client/src/applications.ts) | Raw | [odp-application-meta-data.yaml](../tests/cassettes/odp-application-meta-data.yaml) |
| `GET /api/v1/patent/applications/{applicationNumberText}/transactions` | [ApplicationsClient.getTransactions](../packages/client/src/applications.ts) | Raw | [odp-application-transactions.yaml](../tests/cassettes/odp-application-transactions.yaml) |
| `GET /api/v1/patent/interferences/decisions/search` | [PtabInterferencesClient.search](../packages/client/src/ptab.ts) | UI | [odp-features-interferences-get-search.yaml](../tests/cassettes/odp-features-interferences-get-search.yaml) |
| `GET /api/v1/patent/interferences/decisions/search/download` | [PtabInterferencesClient.downloadFile](../packages/client/src/ptab.ts) | UI | [odp-features-interferences-get-csv.yaml](../tests/cassettes/odp-features-interferences-get-csv.yaml); [odp-features-interferences-get-json.yaml](../tests/cassettes/odp-features-interferences-get-json.yaml) |
| `GET /api/v1/patent/interferences/decisions/{documentIdentifier}` | [PtabInterferencesClient.getDecision](../packages/client/src/ptab.ts) | UI | [odp-features-interferences-get-search.yaml](../tests/cassettes/odp-features-interferences-get-search.yaml); [odp-features-interferences-identifier.yaml](../tests/cassettes/odp-features-interferences-identifier.yaml) |
| `GET /api/v1/patent/interferences/{interferenceNumber}/decisions` | [PtabInterferencesClient.getDecisionsByNumber](../packages/client/src/ptab.ts) | UI | [odp-features-interferences-by-number.yaml](../tests/cassettes/odp-features-interferences-by-number.yaml) |
| `GET /api/v1/patent/oa/enriched_cited_reference_metadata/v3/fields` | [OfficeActionAnalyticsClient.getFields](../packages/client/src/office-action-analytics.ts) | Raw | [odp-office-action-analytics-enriched_citations-fields.yaml](../tests/cassettes/odp-office-action-analytics-enriched_citations-fields.yaml) |
| `GET /api/v1/patent/oa/oa_actions/v1/fields` | [OfficeActionAnalyticsClient.getFields](../packages/client/src/office-action-analytics.ts) | Raw | [odp-office-action-analytics-text-fields.yaml](../tests/cassettes/odp-office-action-analytics-text-fields.yaml) |
| `GET /api/v1/patent/oa/oa_citations/v2/fields` | [OfficeActionAnalyticsClient.getFields](../packages/client/src/office-action-analytics.ts) | Raw | [odp-office-action-analytics-citations-fields.yaml](../tests/cassettes/odp-office-action-analytics-citations-fields.yaml) |
| `GET /api/v1/patent/oa/oa_rejections/v2/fields` | [OfficeActionAnalyticsClient.getFields](../packages/client/src/office-action-analytics.ts) | Raw | [odp-office-action-analytics-rejections-fields.yaml](../tests/cassettes/odp-office-action-analytics-rejections-fields.yaml) |
| `GET /api/v1/patent/office-action/search` | [OfficeActionsClient.search](../packages/client/src/office-actions.ts) | Raw | [odp-office-actions-get-search.yaml](../tests/cassettes/odp-office-actions-get-search.yaml) |
| `GET /api/v1/patent/office-action/search/download` | [OfficeActionsClient.download](../packages/client/src/office-actions.ts) | Raw | [odp-office-actions-export-get-csv.yaml](../tests/cassettes/odp-office-actions-export-get-csv.yaml); [odp-office-actions-export-get-json.yaml](../tests/cassettes/odp-office-actions-export-get-json.yaml) |
| `GET /api/v1/patent/office-action/{officeActionRecordIdentifier}` | [OfficeActionsClient.get](../packages/client/src/office-actions.ts) | Raw | [odp-office-actions-get-search.yaml](../tests/cassettes/odp-office-actions-get-search.yaml); [odp-office-actions-get.yaml](../tests/cassettes/odp-office-actions-get.yaml) |
| `GET /api/v1/patent/office-action/{officeActionRecordIdentifier}/download/officeActionText` | [OfficeActionsClient.downloadText](../packages/client/src/office-actions.ts) | Raw | [odp-office-actions-text.yaml](../tests/cassettes/odp-office-actions-text.yaml) |
| `GET /api/v1/patent/status-codes` | [ApplicationsClient.getStatusCodes](../packages/client/src/applications.ts) | Raw | [odp-application-get-status-codes.yaml](../tests/cassettes/odp-application-get-status-codes.yaml) |
| `GET /api/v1/patent/trials/decisions/search` | [PtabTrialsClient.searchDecisions](../packages/client/src/ptab.ts) | UI | [odp-features-decisions-get-search.yaml](../tests/cassettes/odp-features-decisions-get-search.yaml) |
| `GET /api/v1/patent/trials/decisions/search/download` | [PtabTrialsClient.downloadDecisionsFile](../packages/client/src/ptab.ts) | UI | [odp-features-decisions-get-csv.yaml](../tests/cassettes/odp-features-decisions-get-csv.yaml); [odp-features-decisions-get-json.yaml](../tests/cassettes/odp-features-decisions-get-json.yaml) |
| `GET /api/v1/patent/trials/decisions/{documentIdentifier}` | [PtabTrialsClient.getDecision](../packages/client/src/ptab.ts) | UI | [odp-features-decisions-get-search.yaml](../tests/cassettes/odp-features-decisions-get-search.yaml); [odp-features-decisions-identifier.yaml](../tests/cassettes/odp-features-decisions-identifier.yaml) |
| `GET /api/v1/patent/trials/documents/search` | [PtabTrialsClient.searchDocuments](../packages/client/src/ptab.ts) | UI | [odp-features-documents-get-search.yaml](../tests/cassettes/odp-features-documents-get-search.yaml) |
| `GET /api/v1/patent/trials/documents/search/download` | [PtabTrialsClient.downloadDocumentsFile](../packages/client/src/ptab.ts) | UI | [odp-features-documents-get-csv.yaml](../tests/cassettes/odp-features-documents-get-csv.yaml); [odp-features-documents-get-json.yaml](../tests/cassettes/odp-features-documents-get-json.yaml) |
| `GET /api/v1/patent/trials/documents/{documentIdentifier}` | [PtabTrialsClient.getDocument](../packages/client/src/ptab.ts) | UI | [odp-features-documents-get-search.yaml](../tests/cassettes/odp-features-documents-get-search.yaml); [odp-features-documents-identifier.yaml](../tests/cassettes/odp-features-documents-identifier.yaml); [odp-features-ptab-pdf.yaml](../tests/cassettes/odp-features-ptab-pdf.yaml) |
| `GET /api/v1/patent/trials/proceedings/search` | [PtabTrialsClient.searchProceedings](../packages/client/src/ptab.ts) | UI | [odp-features-proceedings-get-search.yaml](../tests/cassettes/odp-features-proceedings-get-search.yaml) |
| `GET /api/v1/patent/trials/proceedings/search/download` | [PtabTrialsClient.downloadProceedingsFile](../packages/client/src/ptab.ts) | UI | [odp-features-proceedings-get-csv.yaml](../tests/cassettes/odp-features-proceedings-get-csv.yaml); [odp-features-proceedings-get-json.yaml](../tests/cassettes/odp-features-proceedings-get-json.yaml) |
| `GET /api/v1/patent/trials/proceedings/{trialNumber}` | [PtabTrialsClient.getProceeding](../packages/client/src/ptab.ts) | UI | [odp-features-proceedings-get-search.yaml](../tests/cassettes/odp-features-proceedings-get-search.yaml); [odp-features-proceedings-identifier.yaml](../tests/cassettes/odp-features-proceedings-identifier.yaml) |
| `GET /api/v1/patent/trials/{trialNumber}/decisions` | [PtabTrialsClient.getDecisionsByTrial](../packages/client/src/ptab.ts) | UI | [odp-features-decisions-by-number.yaml](../tests/cassettes/odp-features-decisions-by-number.yaml) |
| `GET /api/v1/patent/trials/{trialNumber}/documents` | [PtabTrialsClient.getDocumentsByTrial](../packages/client/src/ptab.ts) | UI | [odp-features-documents-by-number.yaml](../tests/cassettes/odp-features-documents-by-number.yaml) |
| `GET /api/v1/petition/decisions/search` | [PetitionsClient.search](../packages/client/src/petitions.ts) | Raw | [odp-features-petitions-get-search.yaml](../tests/cassettes/odp-features-petitions-get-search.yaml) |
| `GET /api/v1/petition/decisions/search/download` | [PetitionsClient.downloadFile](../packages/client/src/petitions.ts) | Raw | [odp-features-petitions-get-csv.yaml](../tests/cassettes/odp-features-petitions-get-csv.yaml); [odp-features-petitions-get-json.yaml](../tests/cassettes/odp-features-petitions-get-json.yaml) |
| `GET /api/v1/petition/decisions/{petitionDecisionRecordIdentifier}` | [PetitionsClient.get](../packages/client/src/petitions.ts) | Raw | [odp-features-petitions-get-search.yaml](../tests/cassettes/odp-features-petitions-get-search.yaml); [odp-features-petitions-identifier.yaml](../tests/cassettes/odp-features-petitions-identifier.yaml) |
| `GET /last-update/info.json` | [TsdrClient.getStatusJson](../packages/client/src/tsdr.ts) | Raw | [tsdr-live-last-update-json.yaml](../tests/cassettes/tsdr-live-last-update-json.yaml) |
| `GET /last-update/info.xml` | [TsdrClient.getLastUpdateXml](../packages/client/src/tsdr.ts) | Raw | [tsdr-live-last-update-xml.yaml](../tests/cassettes/tsdr-live-last-update-xml.yaml) |
| `GET /ts/cd/caseMultiStatus/{type}` | [TsdrClient.batchStatus](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedoc/{caseid}/{docid}/content.pdf` | [TsdrClient.downloadDocument](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedoc/{caseid}/{docid}/content.zip` | [TsdrClient.downloadDocument](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedoc/{caseid}/{docid}/download.pdf` | [TsdrClient.downloadDocument](../packages/client/src/tsdr.ts) | Raw | [tsdr-live-single-document-pdf.yaml](../tests/cassettes/tsdr-live-single-document-pdf.yaml) |
| `GET /ts/cd/casedoc/{caseid}/{docid}/download.zip` | [TsdrClient.downloadDocument](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedoc/{caseid}/{docid}/info` | [TsdrClient.getDocumentInfoXml](../packages/client/src/tsdr.ts) | Raw | [tsdr-live-single-document-xml.yaml](../tests/cassettes/tsdr-live-single-document-xml.yaml) |
| `GET /ts/cd/casedoc/{caseid}/{docid}/{pageid}/media` | [TsdrClient.getDocumentPage](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedocs/bundle.pdf` | [TsdrClient.downloadBundle](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedocs/bundle.xml` | [TsdrClient.getBundleXml](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedocs/bundle.zip` | [TsdrClient.downloadBundle](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedocs/{caseid}/bundle` | [TsdrClient.getCaseBundleXml](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedocs/{caseid}/content.pdf` | [TsdrClient.downloadCaseDocuments](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedocs/{caseid}/content.zip` | [TsdrClient.downloadCaseDocuments](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedocs/{caseid}/download.pdf` | [TsdrClient.downloadCaseDocuments](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedocs/{caseid}/download.zip` | [TsdrClient.downloadCaseDocuments](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casedocs/{caseid}/info` | [TsdrClient.getDocumentsXml](../packages/client/src/tsdr.ts) | Raw | [tsdr-live-documents.yaml](../tests/cassettes/tsdr-live-documents.yaml) |
| `GET /ts/cd/casestatus/{caseid}/content.html` | [TsdrClient.getStatusHtml](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casestatus/{caseid}/content.pdf` | [TsdrClient.downloadStatus](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casestatus/{caseid}/content.zip` | [TsdrClient.downloadStatus](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casestatus/{caseid}/download.pdf` | [TsdrClient.downloadStatus](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casestatus/{caseid}/download.zip` | [TsdrClient.downloadStatus](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `GET /ts/cd/casestatus/{caseid}/info` | [TsdrClient.getStatusXml](../packages/client/src/tsdr.ts) | Raw | [tsdr-live-status.yaml](../tests/cassettes/tsdr-live-status.yaml) |
| `GET /ts/cd/casestatus/{caseid}/v1/info` | [TsdrClient.getStatusXml](../packages/client/src/tsdr.ts) | Raw | Not recorded |
| `POST /api/v1/patent/appeals/decisions/search` | [PtabAppealsClient.search](../packages/client/src/ptab.ts) | UI | [odp-ptab-appeals.yaml](../tests/cassettes/odp-ptab-appeals.yaml) |
| `POST /api/v1/patent/appeals/decisions/search/download` | [PtabAppealsClient.downloadFile](../packages/client/src/ptab.ts) | UI | [odp-features-appeals-post-json.yaml](../tests/cassettes/odp-features-appeals-post-json.yaml) |
| `POST /api/v1/patent/applications/search` | [ApplicationsClient.search](../packages/client/src/applications.ts) | Raw | [odp-application-granted-claims.yaml](../tests/cassettes/odp-application-granted-claims.yaml); [odp-search.yaml](../tests/cassettes/odp-search.yaml) |
| `POST /api/v1/patent/applications/search/download` | [ApplicationsClient.downloadSearch](../packages/client/src/applications.ts) | Raw | [odp-application-post-download.yaml](../tests/cassettes/odp-application-post-download.yaml) |
| `POST /api/v1/patent/interferences/decisions/search` | [PtabInterferencesClient.search](../packages/client/src/ptab.ts) | UI | [odp-ptab-interferences.yaml](../tests/cassettes/odp-ptab-interferences.yaml) |
| `POST /api/v1/patent/interferences/decisions/search/download` | [PtabInterferencesClient.downloadFile](../packages/client/src/ptab.ts) | UI | [odp-features-interferences-post-json.yaml](../tests/cassettes/odp-features-interferences-post-json.yaml) |
| `POST /api/v1/patent/oa/enriched_cited_reference_metadata/v3/records` | [OfficeActionAnalyticsClient.search](../packages/client/src/office-action-analytics.ts) | Raw | [odp-office-action-analytics-enriched_citations-records.yaml](../tests/cassettes/odp-office-action-analytics-enriched_citations-records.yaml) |
| `POST /api/v1/patent/oa/oa_actions/v1/records` | [OfficeActionAnalyticsClient.search](../packages/client/src/office-action-analytics.ts) | Raw | [odp-office-action-analytics-text-records.yaml](../tests/cassettes/odp-office-action-analytics-text-records.yaml) |
| `POST /api/v1/patent/oa/oa_citations/v2/records` | [OfficeActionAnalyticsClient.search](../packages/client/src/office-action-analytics.ts) | Raw | [odp-office-action-analytics-citations-records.yaml](../tests/cassettes/odp-office-action-analytics-citations-records.yaml) |
| `POST /api/v1/patent/oa/oa_rejections/v2/records` | [OfficeActionAnalyticsClient.search](../packages/client/src/office-action-analytics.ts) | Raw | [odp-office-action-analytics-rejections-records.yaml](../tests/cassettes/odp-office-action-analytics-rejections-records.yaml) |
| `POST /api/v1/patent/office-action/search` | [OfficeActionsClient.search](../packages/client/src/office-actions.ts) | Raw | [odp-office-actions.yaml](../tests/cassettes/odp-office-actions.yaml) |
| `POST /api/v1/patent/office-action/search/download` | [OfficeActionsClient.download](../packages/client/src/office-actions.ts) | Raw | [odp-office-actions-export-post-csv.yaml](../tests/cassettes/odp-office-actions-export-post-csv.yaml); [odp-office-actions-export-post-json.yaml](../tests/cassettes/odp-office-actions-export-post-json.yaml) |
| `POST /api/v1/patent/status-codes` | [ApplicationsClient.getStatusCodes](../packages/client/src/applications.ts) | Raw | [odp-application-status-codes.yaml](../tests/cassettes/odp-application-status-codes.yaml) |
| `POST /api/v1/patent/trials/decisions/search` | [PtabTrialsClient.searchDecisions](../packages/client/src/ptab.ts) | UI | [odp-ptab-decisions.yaml](../tests/cassettes/odp-ptab-decisions.yaml) |
| `POST /api/v1/patent/trials/decisions/search/download` | [PtabTrialsClient.downloadDecisionsFile](../packages/client/src/ptab.ts) | UI | [odp-features-decisions-post-csv.yaml](../tests/cassettes/odp-features-decisions-post-csv.yaml); [odp-features-decisions-post-json.yaml](../tests/cassettes/odp-features-decisions-post-json.yaml) |
| `POST /api/v1/patent/trials/documents/search` | [PtabTrialsClient.searchDocuments](../packages/client/src/ptab.ts) | UI | [odp-ptab-documents.yaml](../tests/cassettes/odp-ptab-documents.yaml) |
| `POST /api/v1/patent/trials/documents/search/download` | [PtabTrialsClient.downloadDocumentsFile](../packages/client/src/ptab.ts) | UI | [odp-features-documents-post-csv.yaml](../tests/cassettes/odp-features-documents-post-csv.yaml); [odp-features-documents-post-json.yaml](../tests/cassettes/odp-features-documents-post-json.yaml) |
| `POST /api/v1/patent/trials/proceedings/search` | [PtabTrialsClient.searchProceedings](../packages/client/src/ptab.ts) | UI | [odp-ptab-proceedings.yaml](../tests/cassettes/odp-ptab-proceedings.yaml) |
| `POST /api/v1/patent/trials/proceedings/search/download` | [PtabTrialsClient.downloadProceedingsFile](../packages/client/src/ptab.ts) | UI | [odp-features-proceedings-post-json.yaml](../tests/cassettes/odp-features-proceedings-post-json.yaml) |
| `POST /api/v1/petition/decisions/search` | [PetitionsClient.search](../packages/client/src/petitions.ts) | Raw | [odp-petitions.yaml](../tests/cassettes/odp-petitions.yaml) |
| `POST /api/v1/petition/decisions/search/download` | [PetitionsClient.downloadFile](../packages/client/src/petitions.ts) | Raw | [odp-features-petitions-post-csv.yaml](../tests/cassettes/odp-features-petitions-post-csv.yaml); [odp-features-petitions-post-json.yaml](../tests/cassettes/odp-features-petitions-post-json.yaml) |
