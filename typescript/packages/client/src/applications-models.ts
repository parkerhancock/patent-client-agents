import type { Provenance, RequestOptions } from "./models.js";
export type IdentifierType = "application" | "patent" | "publication";
export type ApplicationDataset =
  | "meta-data"
  | "adjustment"
  | "assignment"
  | "attorney"
  | "continuity"
  | "foreign-priority"
  | "transactions"
  | "associated-documents";
export interface ApplicationDataResponse {
  data: Record<string, unknown>;
  provenance: Provenance;
}
export interface FamilyNode extends Record<string, unknown> {
  applicationNumber: string;
  dataSource: "uspto_odp" | "unknown";
}
export interface FamilyEdge extends Record<string, unknown> {
  fromApplication: string;
  toApplication: string;
}
export interface FamilyGraphResponse {
  rootApplication: string;
  nodes: FamilyNode[];
  edges: FamilyEdge[];
  missingApplications: string[];
  metadata: { nodeCount: number; edgeCount: number; missingCount: number };
  provenance: Provenance;
}
export interface FamilyOptions extends RequestOptions {
  identifierType?: IdentifierType;
  batchSize?: number;
  /** Stops unexpectedly large graphs rather than silently truncating them. */
  maxApplications?: number;
}

export interface ApplicationDocumentBatchOptions extends RequestOptions {
  documentCodes?: string[];
  documentIdentifiers?: string[];
  format?: "pdf" | "xml" | "docx";
  officialDateFrom?: string;
  officialDateTo?: string;
  /** Refuse oversized selections before requesting document bytes. */
  maxDocuments?: number;
  /** Maximum combined document bytes; defaults to 64 MiB. */
  maxTotalBytes?: number;
}
