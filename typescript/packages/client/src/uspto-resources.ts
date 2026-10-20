import * as data from "./uspto-resource-data.js";

export const ODP_SEARCH_GUIDE_RESOURCE_URI =
  "resource://uspto-odp/search-guide";
export const ODP_FIELD_CATALOG_RESOURCE_URI =
  "resource://uspto-odp/field-catalog";
export const ODP_STATUS_CODES_RESOURCE_URI =
  "resource://uspto-odp/application-status-codes";
export const ODP_SWAGGER_RESOURCE_URI = "resource://uspto-odp/swagger";
export const CURRENT_ODP_SWAGGER_RESOURCE_URI =
  "resource://uspto-odp/current-main-swagger";
export const SEARCH_GUIDE_RESOURCE_URI =
  "resource://uspto-publications/search-guide";
export const SEARCHABLE_INDEX_RESOURCE_URI =
  "resource://uspto-publications/searchable-indexes";
export const BULKDATA_PRODUCT_GUIDE_RESOURCE_URI =
  "resource://uspto-bulkdata/product-guide-2025";
export const BULKDATA_RESPONSE_SCHEMA_RESOURCE_URI =
  "resource://uspto-bulkdata/bulkdata-response-schema";
export const PATENT_DATA_SCHEMA_RESOURCE_URI =
  "resource://uspto-bulkdata/patent-data-schema";
export const PETITION_DECISION_SCHEMA_RESOURCE_URI =
  "resource://uspto-bulkdata/petition-decision-schema";

const historicalNotice =
  "> Historical Python-package snapshot copied October 20, 2026. Its original content date is unverified; routes, fields, limits, and status codes may be outdated. Consult the current official API and recorded responses before relying on this reference.\n\n";
export const ODP_SEARCH_GUIDE = historicalNotice + data.ODP_SEARCH_GUIDE;
export const ODP_FIELD_CATALOG = historicalNotice + data.ODP_FIELD_CATALOG;
export const ODP_STATUS_CODES = historicalNotice + data.ODP_STATUS_CODES;

/** Historical Python schema, reviewed January 27, 2026 against portal 3.0. */
export function getOdpSwaggerSpec(): string {
  return (
    "# Historical Python-package OpenAPI snapshot; reviewed 2026-01-27 against portal 3.0.\n# Not the current complete ODP schema.\n" +
    data.LEGACY_ODP_SWAGGER
  );
}
/** Current main index only: seven external companion files are not bundled. */
export function getCurrentOdpSwaggerSpec(): string {
  return (
    "# Official main OpenAPI index retrieved 2026-10-20 from https://data.uspto.gov/swagger/swagger.yaml\n# Portal release 5.0 (2026-10-02); this spec declares info.version 1.0.0.\n# INCOMPLETE BUNDLE: seven external companion files are not included.\n" +
    data.CURRENT_ODP_SWAGGER
  );
}
export function getSearchGuide(): string {
  return historicalNotice + data.PUBLICATIONS_SEARCH_GUIDE;
}
export function getSearchableIndexesResource(): string {
  return historicalNotice + data.PUBLICATIONS_SEARCHABLE_INDEXES;
}
export function getProductGuide(): string {
  return (
    "> Historical 2025 product guide copied from the Python package October 20, 2026. This is not a current product catalog.\n\n" +
    data.BULKDATA_PRODUCT_GUIDE
  );
}
/** Historical bundled JSON schemas; not refreshed against current companion files. */
export function getBulkdataResponseSchema(): string {
  return data.BULKDATA_RESPONSE_SCHEMA;
}
export function getPatentDataSchema(): string {
  return data.PATENT_DATA_SCHEMA;
}
export function getPetitionDecisionSchema(): string {
  return data.PETITION_DECISION_SCHEMA;
}

export interface UsptoDocumentationResource {
  readonly uri: string;
  readonly name: string;
  readonly description: string;
  readonly mimeType: string;
  readonly read: () => string;
}
const historical =
  "Historical Python-package reference; original content date unverified, copied 2026-10-20. Not current API verification.";
export const USPTO_DOCUMENTATION_RESOURCES: readonly UsptoDocumentationResource[] =
  [
    {
      uri: ODP_SEARCH_GUIDE_RESOURCE_URI,
      name: "ODP search guide (historical)",
      description: historical,
      mimeType: "text/markdown",
      read: () => ODP_SEARCH_GUIDE,
    },
    {
      uri: ODP_FIELD_CATALOG_RESOURCE_URI,
      name: "ODP field catalog (historical)",
      description: historical,
      mimeType: "text/markdown",
      read: () => ODP_FIELD_CATALOG,
    },
    {
      uri: ODP_STATUS_CODES_RESOURCE_URI,
      name: "ODP application status codes (historical)",
      description: historical,
      mimeType: "text/markdown",
      read: () => ODP_STATUS_CODES,
    },
    {
      uri: ODP_SWAGGER_RESOURCE_URI,
      name: "ODP OpenAPI (historical Python snapshot)",
      description:
        "Historical Python schema reviewed 2026-01-27 against portal 3.0; not current complete schema.",
      mimeType: "application/yaml",
      read: getOdpSwaggerSpec,
    },
    {
      uri: CURRENT_ODP_SWAGGER_RESOURCE_URI,
      name: "ODP main OpenAPI index (2026-10-20; incomplete bundle)",
      description:
        "Official main index downloaded 2026-10-20; portal 5.0, spec 1.0.0. Seven external companion files remain unbundled. This is not a complete schema bundle.",
      mimeType: "application/yaml",
      read: getCurrentOdpSwaggerSpec,
    },
    {
      uri: SEARCH_GUIDE_RESOURCE_URI,
      name: "Patent Public Search guide (historical)",
      description: historical,
      mimeType: "text/markdown",
      read: getSearchGuide,
    },
    {
      uri: SEARCHABLE_INDEX_RESOURCE_URI,
      name: "Patent Public Search indexes (historical)",
      description: historical,
      mimeType: "text/markdown",
      read: getSearchableIndexesResource,
    },
    {
      uri: BULKDATA_PRODUCT_GUIDE_RESOURCE_URI,
      name: "Bulk data product guide (2025)",
      description:
        "Historical 2025 guide copied 2026-10-20; query the API for the current catalog.",
      mimeType: "text/markdown",
      read: getProductGuide,
    },
    {
      uri: BULKDATA_RESPONSE_SCHEMA_RESOURCE_URI,
      name: "Bulk data response schema (historical)",
      description: historical,
      mimeType: "application/schema+json",
      read: getBulkdataResponseSchema,
    },
    {
      uri: PATENT_DATA_SCHEMA_RESOURCE_URI,
      name: "Patent data schema (historical)",
      description: historical,
      mimeType: "application/schema+json",
      read: getPatentDataSchema,
    },
    {
      uri: PETITION_DECISION_SCHEMA_RESOURCE_URI,
      name: "Petition decision schema (historical)",
      description: historical,
      mimeType: "application/schema+json",
      read: getPetitionDecisionSchema,
    },
  ];
