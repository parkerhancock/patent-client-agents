# Delete-verdict tests kept because they are the only coverage

The audit marked these tests for deletion, but each one is the only test that
executes the listed source lines (per-test coverage on main at 74eca08). They
stay until a behavioral test covers the same lines; then delete them.

| Test | Only coverage of |
| --- | --- |
| `tests/canlii/test_client.py::TestModuleLevelApi::test_get_client_returns_canlii_client` | `canlii/api.py` (1 lines) |
| `tests/cpc/test_api.py::TestGetClient::test_creates_client_with_both` | `cpc/api.py` (1 lines; `epo_ops/client.py` is now covered by the transport tests) |
| `tests/dpma_register/test_api.py::test_api_helper_delegates_to_client` | `dpma_register/api.py` (12 lines) |
| `tests/dpma_statutes/test_api.py::test_get_client_returns_client` | `dpma_statutes/api.py` (1 lines) |
| `tests/epo_ops/test_api.py::test_convert_number` | `epo_ops/api.py` (7 lines) |
| `tests/epo_ops/test_api.py::test_download_pdf` | `epo_ops/api.py` (3 lines) |
| `tests/epo_ops/test_api.py::test_fetch_biblio` | `epo_ops/api.py` (3 lines) |
| `tests/epo_ops/test_api.py::test_fetch_family` | `epo_ops/api.py` (7 lines) |
| `tests/epo_ops/test_api.py::test_fetch_legal_events` | `epo_ops/api.py` (3 lines) |
| `tests/epo_ops/test_api.py::test_search_published` | `epo_ops/api.py` (4 lines) |
| `tests/epo_ops/test_parsing.py::TestAsElement::test_unsupported_type_raises` | `epo_ops/parsing.py` (1 lines) |
| `tests/epo_ops/test_parsing.py::TestTextExtraction::test_collect_texts` | `epo_ops/parsing.py` (1 lines) |
| `tests/epo_ops/test_parsing.py::TestTextExtraction::test_collect_texts_strips_whitespace` | `epo_ops/parsing.py` (1 lines) |
| `tests/epo_ops/test_parsing.py::TestXmlParseError::test_inherits_from_core` | `epo_ops/parsing.py` (1 lines) |
| `tests/epo_ops/test_parsing.py::TestXmlParseError::test_stores_source_and_content` | `epo_ops/parsing.py` (1 lines) |
| `tests/fees/test_models.py::TestFeeScheduleValidation::test_partial_coverage_accepts_explicit_gaps` | `fees/models.py` (1 lines) |
| `tests/google_patents/test_api.py::test_fetch` | `google_patents/api.py` (3 lines) |
| `tests/google_patents/test_api.py::test_fetch_pdf` | `google_patents/api.py` (3 lines) |
| `tests/google_patents/test_api.py::test_search_calls_client` | `google_patents/api.py` (28 lines) |
| `tests/google_patents/test_api_utils.py::TestGetClient::test_returns_google_patents_client` | `google_patents/api.py` (1 lines); `google_patents/client.py` (1 lines) |
| `tests/google_patents/test_api_utils.py::TestGetClient::test_with_cache_disabled` | `google_patents/api.py` (1 lines); `google_patents/client.py` (1 lines) |
| `tests/google_patents/test_api_utils.py::TestGetClient::test_with_cache_enabled` | `google_patents/api.py` (1 lines); `google_patents/client.py` (1 lines) |
| `tests/google_patents/test_parsers_figures.py::TestParseInt::test_returns_none_for_empty` | `google_patents/parsers/figures.py` (1 lines) |
| `tests/google_patents/test_parsers_figures.py::TestParseInt::test_returns_none_for_invalid` | `google_patents/parsers/figures.py` (2 lines) |
| `tests/ilpo_statutes/test_api.py::test_get_client_returns_instance` | `ilpo_statutes/api.py` (1 lines) |
| `tests/inpi_br_statutes/test_api.py::test_get_client_returns_an_unentered_client` | `inpi_br_statutes/api.py` (1 lines) |
| `tests/inpi_br_statutes/test_build.py::test_main_cli_smoke` | `inpi_br_statutes/corpus/build.py` (2 lines) |
| `tests/inpi_pi/test_resources.py::test_usage_resource_returns_human_text` | `inpi_pi/resources.py` (1 lines) |
| `tests/ipi_swissreg/test_api.py::test_api_helper_delegates_to_client` | `ipi_swissreg/api.py` (16 lines) |
| `tests/ipo_in_mppp/test_api.py::test_get_client` | `ipo_in_mppp/api.py` (1 lines) |
| `tests/ipo_in_statutes/test_api.py::test_get_client_returns_client` | `ipo_in_statutes/api.py` (1 lines) |
| `tests/iponz_new_zealand/test_api.py::test_api_helper_delegates_to_client` | `iponz_new_zealand/api.py` (14 lines) |
| `tests/ipos_manuals/test_api.py::test_get_client_returns_concrete_client` | `ipos_manuals/api.py` (1 lines) |
| `tests/ipos_manuals/test_build.py::test_extract_pdf_text_with_blank_pdf` | `ipos_manuals/corpus/build.py` (9 lines) |
| `tests/ipos_manuals/test_build.py::test_fetcher_fetch_returns_text` | `ipos_manuals/corpus/build.py` (28 lines) |
| `tests/ipos_manuals/test_build.py::test_main_handles_keyboard_interrupt` | `ipos_manuals/corpus/build.py` (3 lines) |
| `tests/ipos_statutes/test_api.py::test_get_client_returns_concrete_client` | `ipos_statutes/api.py` (1 lines) |
| `tests/ipos_statutes/test_build.py::test_extract_pdf_text_with_minimal_pdf` | `ipos_statutes/corpus/build.py` (6 lines) |
| `tests/ipos_statutes/test_build.py::test_fetcher_fetch_retries_then_succeeds` | `ipos_statutes/corpus/build.py` (19 lines) |
| `tests/ipos_statutes/test_build.py::test_main_handles_keyboard_interrupt` | `ipos_statutes/corpus/build.py` (3 lines) |
| `tests/jpo/test_models.py::TestApiResult::test_is_success_false` | `jpo/models.py` (1 lines) |
| `tests/jpo/test_models.py::TestApiResult::test_is_success_true` | `jpo/models.py` (1 lines) |
| `tests/jpo/test_models.py::TestPctNationalPhaseData::test_minimal` | `jpo/models.py` (1 lines) |
| `tests/kipo_kipris/test_models.py::test_usage_resource_uri_and_body` | `kipo_kipris/resources.py` (6 lines) |
| `tests/oepm_spain/test_api.py::test_api_helpers_delegate` | `oepm_spain/api.py` (6 lines) |
| `tests/thai_dip/test_api.py::test_api_helpers_delegate` | `thai_dip/api.py` (18 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_patent_alteration_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_patent_annuity_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_patent_change_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_patent_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_patent_divide_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_patent_priority_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_patent_publication_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_patent_rights_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_patent_twins_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_trademark_change_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_trademark_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_trademark_divide_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_trademark_image_urls_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_trademark_priority_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_tipo_trademark_rights_delegates` | `tipo_opdata/api.py` (2 lines) |
| `tests/tipo_opdata/test_api.py::test_get_usage_resource_returns_text` | `tipo_opdata/resources.py` (1 lines) |
| `tests/tipo_opdata/test_api.py::test_search_tipo_patents_delegates` | `tipo_opdata/api.py` (10 lines) |
| `tests/tipo_opdata/test_api.py::test_search_tipo_trademarks_delegates` | `tipo_opdata/api.py` (10 lines) |
| `tests/tipo_opdata/test_api.py::test_usage_resource_uri_is_namespaced` | `tipo_opdata/resources.py` (5 lines) |
| `tests/tipo_opdata/test_mcp_envelope.py::test_dump_invalid_type_raises` | `mcp/tools/tipo_opdata.py` (2 lines) |
| `tests/tipo_opdata/test_mcp_envelope.py::test_dump_passthrough_dict` | `mcp/tools/tipo_opdata.py` (2 lines) |
| `tests/tw_trade_secrets/test_api.py::test_get_client_returns_client` | `tw_trade_secrets/api.py` (1 lines) |
| `tests/uspto_applications/test_api.py::test_get_application` | `uspto_applications/api.py` (7 lines) |
| `tests/uspto_applications/test_api.py::test_get_family` | `uspto_applications/api.py` (7 lines) |
| `tests/uspto_applications/test_api.py::test_list_documents` | `uspto_applications/api.py` (9 lines) |
| `tests/uspto_applications/test_api.py::test_search_applications` | `uspto_applications/api.py` (19 lines) |
| `tests/uspto_bulkdata/test_api.py::test_get_product` | `uspto_bulkdata/api.py` (15 lines) |
| `tests/uspto_bulkdata/test_api.py::test_search_products` | `uspto_bulkdata/api.py` (16 lines) |
| `tests/uspto_odp/test_base.py::TestFormatBool::test_false_returns_false_string` | `uspto_odp/clients/base.py` (2 lines) |
| `tests/uspto_odp/test_base.py::TestFormatBool::test_none_returns_none` | `uspto_odp/clients/base.py` (2 lines) |
| `tests/uspto_odp/test_base.py::TestFormatBool::test_true_returns_true_string` | `uspto_odp/clients/base.py` (2 lines) |
| `tests/uspto_odp/test_client.py::TestUsptoOdpClientNormalization::test_normalize_application_number` | `uspto_odp/client.py` (1 lines) |
| `tests/uspto_odp/test_client.py::TestUsptoOdpClientSubClientProperties::test_context_manager_closes_all` | `uspto_odp/client.py` (8 lines) |
| `tests/uspto_petitions/test_api.py::test_download_petitions` | `uspto_petitions/api.py` (16 lines) |
| `tests/uspto_petitions/test_api.py::test_get_petition` | `uspto_petitions/api.py` (9 lines) |
| `tests/uspto_petitions/test_api.py::test_search_petitions` | `uspto_petitions/api.py` (16 lines) |
| `tests/uspto_publications/test_api.py::test_search_delegates` | `uspto_publications/api.py` (12 lines) |
| `tests/uspto_tmsearch/test_models.py::TestTrademarkSearchResponse::test_empty_response` | `uspto_tmsearch/models.py` (1 lines) |
| `tests/uspto_tmsearch/test_models.py::TestTrademarkSearchResponse::test_with_results` | `uspto_tmsearch/models.py` (1 lines) |
| `tests/uspto_tmsearch/test_models.py::TestTrademarkSearchResult::test_is_live_property` | `uspto_tmsearch/models.py` (1 lines) |
| `tests/uspto_trademark_assignments/test_models.py::TestTrademarkAssignmentRecord::test_basic_parsing` | `uspto_trademark_assignments/models.py` (1 lines) |
| `tests/uspto_trademark_assignments/test_models.py::TestTrademarkAssignmentSearchResponse::test_basic_parsing` | `uspto_trademark_assignments/models.py` (1 lines) |
| `tests/uspto_trademark_assignments/test_models.py::TestTrademarkAssignmentSearchResponse::test_empty_response` | `uspto_trademark_assignments/models.py` (1 lines) |
| `tests/wipo_lex/test_client.py::TestModuleLevelApi::test_search_via_module_api` | `wipo_lex/api.py` (2 lines) |
