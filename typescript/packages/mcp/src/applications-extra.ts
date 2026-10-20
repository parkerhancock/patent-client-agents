import type { ApplicationsClient } from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailEnvelope,
  detailToolOptions,
  downloadResult,
} from "./shared.js";

export function registerApplicationExtraTools(
  server: FastMCP,
  client: ApplicationsClient,
  auth?: AuthCheck,
) {
  const common = detailToolOptions(auth);
  const application_number = z.string().min(1);
  const identifier_type = z
    .enum(["application", "patent", "publication"])
    .default("patent");
  server.tool(
    {
      ...common,
      name: "get_application_data",
      description:
        "Retrieve a specific USPTO application dataset: metadata, term adjustment, assignments, attorney, continuity, foreign priority, transactions, or associated documents. Status-code searches accept a source search payload.",
      input: z.object({
        application_number: application_number.optional(),
        dataset: z.enum([
          "meta-data",
          "adjustment",
          "assignment",
          "attorney",
          "continuity",
          "foreign-priority",
          "transactions",
          "associated-documents",
          "status-codes",
        ]),
        status_query: z.record(z.string(), z.unknown()).optional(),
      }),
    },
    async (input) => {
      if (input.dataset === "status-codes") {
        const response = await client.getStatusCodes(input.status_query);
        return detailEnvelope(
          "Application status codes.",
          response.data,
          response.provenance,
        );
      }
      if (!input.application_number)
        throw new Error(
          "application_number is required for application datasets.",
        );
      const response = await client.getData(
        input.application_number,
        input.dataset,
      );
      return detailEnvelope(
        `${input.dataset} for ${input.application_number}.`,
        response.data,
        response.provenance,
      );
    },
  );
  server.tool(
    {
      ...common,
      name: "resolve_application",
      description:
        "Resolve an application, granted patent, or publication number to its USPTO application number.",
      input: z.object({ identifier: z.string().min(1), identifier_type }),
    },
    async (input) => {
      const response = await client.resolveIdentifier(
        input.identifier,
        input.identifier_type,
      );
      return detailEnvelope(
        "Resolved application.",
        { application_number: response.applicationNumber },
        response.provenance,
      );
    },
  );
  server.tool(
    {
      ...common,
      name: "get_application_family",
      description:
        "Traverse USPTO parent and child continuity records to build a family graph, including missing applications.",
      input: z.object({
        identifier: z.string().min(1),
        identifier_type,
        batch_size: z.number().int().min(1).max(100).default(25),
        max_applications: z.number().int().positive().max(10_000).default(1000),
      }),
    },
    async (input) => {
      const response = await client.getFamily(input.identifier, {
        identifierType: input.identifier_type,
        batchSize: input.batch_size,
        maxApplications: input.max_applications,
      });
      return detailEnvelope(
        `${response.nodes.length} applications and ${response.edges.length} family links.`,
        response,
        response.provenance,
      );
    },
  );
  server.tool(
    {
      ...common,
      name: "download_application_document",
      description:
        "Retrieve an application file-history PDF, XML archive, or DOCX as a temporary download URL. XML and DOCX must be advertised in document metadata. Binary content is delivered outside MCP context.",
      input: z.object({
        application_number,
        document_identifier: z.string().min(1),
        format: z.enum(["pdf", "xml", "docx"]).default("pdf"),
      }),
    },
    async (input) => {
      if (input.format === "xml") {
        const response = await client.downloadDocumentXml(
          input.application_number,
          input.document_identifier,
        );
        return downloadResult(
          new TextEncoder().encode(response.data),
          `${input.document_identifier}.xml`,
          "application/xml",
          response.provenance,
        );
      }
      const response = await client.downloadDocument(
        input.application_number,
        input.document_identifier,
        { format: input.format },
      );
      return downloadResult(
        response.data,
        `${input.document_identifier}.${input.format}`,
        input.format === "pdf"
          ? "application/pdf"
          : "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        response.provenance,
      );
    },
  );
  server.tool(
    {
      ...common,
      name: "download_application_search",
      description:
        "Download application search results with the USPTO PatentDownloadRequest payload. Binary content is delivered via a temporary download URL.",
      input: z.object({ payload: z.record(z.string(), z.unknown()) }),
    },
    async (input) => {
      const response = await client.downloadSearch(input.payload);
      const type =
        response.headers.get("content-type") ?? "application/octet-stream";
      return downloadResult(
        response.data,
        "applications-search.download",
        type,
        response.provenance,
      );
    },
  );
  server.tool(
    {
      ...common,
      name: "get_granted_claims",
      description:
        "Retrieve structured granted claims from USPTO grant XML, preserving nested claim text and dependency references.",
      input: z.object({ patent_number: z.string().min(1) }),
    },
    async (input) => {
      const response = await client.getGrantedClaims(input.patent_number);
      return detailEnvelope(
        response.claims
          ? `${response.claims.length} granted claims.`
          : "No grant XML is available.",
        { claims: response.claims },
        response.provenance,
      );
    },
  );
}
