import { ApiError, type Provenance } from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  asList,
  type FacadeClients,
  facadeToolOptions,
  listEnvelope,
  notPorted,
} from "./shared.js";

export const PTAB_TYPES = [
  "proceeding",
  "trial_decision",
  "trial_document",
  "appeal_decision",
  "interference_decision",
] as const;
export type PtabType = (typeof PTAB_TYPES)[number];
const ptabType = z.enum(PTAB_TYPES);

type Row = Record<string, unknown>;
const obj = (value: unknown): Row =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Row)
    : {};

/** Lean projection of a PTAB record, field for field with Python's _stub_ptab_record. */
export function stubPtabRecord(record: Row, type: PtabType): Row {
  const out: Row = { type };
  if (type === "proceeding") {
    const meta = obj(record.trialMetaData);
    const owner = obj(record.patentOwnerData ?? record.respondentData);
    const petitioner = obj(record.regularPetitionerData);
    return Object.assign(out, {
      trial_number: record.trialNumber ?? null,
      trial_type_code: meta.trialTypeCode ?? null,
      status: meta.trialStatusCategory ?? null,
      petition_filing_date: meta.petitionFilingDate ?? null,
      institution_decision_date: meta.institutionDecisionDate ?? null,
      latest_decision_date: meta.latestDecisionDate ?? null,
      termination_date: meta.terminationDate ?? null,
      patent_number: owner.patentNumber ?? null,
      application_number: owner.applicationNumberText ?? null,
      patent_owner:
        owner.patentOwnerName ?? owner.realPartyInInterestName ?? null,
      petitioner: petitioner.realPartyInInterestName ?? null,
    });
  }
  if (type === "trial_decision" || type === "trial_document") {
    const document = obj(record.documentData);
    Object.assign(out, {
      trial_number: record.trialNumber ?? null,
      document_identifier: document.documentIdentifier ?? null,
      document_type: document.documentTypeDescriptionText ?? null,
      document_title:
        document.documentTitleText ?? document.documentName ?? null,
      filing_date: document.documentFilingDate ?? null,
      filing_party: document.filingPartyCategory ?? null,
    });
    if (type === "trial_decision") {
      const decision = obj(record.decisionData);
      Object.assign(out, {
        decision_type: decision.decisionTypeCategory ?? null,
        decision_issue_date: decision.decisionIssueDate ?? null,
        trial_outcome: decision.trialOutcomeCategory ?? null,
      });
    }
    return out;
  }
  if (type === "appeal_decision") {
    const document = obj(record.documentData);
    const decision = obj(record.decisionData);
    const appellant = obj(record.appellantData);
    return Object.assign(out, {
      appeal_number: record.appealNumber ?? null,
      document_identifier: document.documentIdentifier ?? null,
      decision_issue_date: decision.decisionIssueDate ?? null,
      decision_type: decision.decisionTypeCategory ?? null,
      appeal_outcome: decision.appealOutcomeCategory ?? null,
      application_number: appellant.applicationNumberText ?? null,
      patent_number: appellant.patentNumber ?? null,
      applicant:
        appellant.patentOwnerName ?? appellant.realPartyInInterestName ?? null,
    });
  }
  const document = obj(record.decisionDocumentData ?? record.documentData);
  const senior = obj(record.seniorPartyData);
  const junior = obj(record.juniorPartyData);
  return Object.assign(out, {
    interference_number: record.interferenceNumber ?? null,
    document_identifier: document.documentIdentifier ?? null,
    decision_issue_date: document.decisionIssueDate ?? null,
    decision_type: document.decisionTypeCategory ?? null,
    interference_outcome: document.interferenceOutcomeCategory ?? null,
    senior_party:
      senior.realPartyInInterestName ?? senior.patentOwnerName ?? null,
    junior_party:
      junior.realPartyInInterestName ?? junior.patentOwnerName ?? null,
  });
}

/** One-line summary of a single PTAB record, as Python's _summarize_ptab. */
function summarizePtab(record: Row, type: PtabType): string {
  const stub = stubPtabRecord(record, type);
  if (type === "proceeding")
    return `**PTAB trial ${stub.trial_number ?? "(no trial#)"}** (${stub.trial_type_code ?? ""}) — ${stub.status ?? "(unknown status)"}\nPatent owner: ${stub.patent_owner ?? "(no owner)"}.`;
  if (type === "trial_decision" || type === "trial_document")
    return `**PTAB trial ${type.replace("trial_", "")} ${stub.document_identifier ?? "(no doc id)"}** — ${stub.document_title ?? "(no title)"}${stub.decision_type ? ` (${stub.decision_type})` : ""}\nTrial: ${stub.trial_number ?? "(no trial#)"}. Filed ${stub.filing_date ?? "?"}.`;
  if (type === "appeal_decision")
    return `**PTAB appeal decision ${stub.document_identifier ?? "(no doc id)"}** — appeal ${stub.appeal_number ?? "(no appeal#)"}, outcome: ${stub.appeal_outcome ?? "(no outcome)"}\nIssued ${stub.decision_issue_date ?? "?"}.`;
  return `**PTAB interference decision ${stub.document_identifier ?? "(no doc id)"}** — interference ${stub.interference_number ?? "(no intf#)"}, outcome: ${stub.interference_outcome ?? "(no outcome)"}\nIssued ${stub.decision_issue_date ?? "?"}.`;
}

const BAG: Record<PtabType, string> = {
  proceeding: "patentTrialProceedingDataBag",
  trial_decision: "patentTrialDocumentDataBag",
  trial_document: "patentTrialDocumentDataBag",
  appeal_decision: "patentAppealDataBag",
  interference_decision: "patentInterferenceDataBag",
};
type PtabResponse = { count: number; provenance: Provenance } & Record<
  string,
  unknown
>;
const records = (response: PtabResponse, type: PtabType) =>
  ((response[BAG[type]] as Row[] | undefined) ?? []).filter(
    (row) => row && typeof row === "object",
  );

function ptabSearch(clients: FacadeClients, type: PtabType) {
  return (options: { query: string; limit: number; offset: number }) =>
    (type === "proceeding"
      ? clients.trials.searchProceedings(options)
      : type === "trial_decision"
        ? clients.trials.searchDecisions(options)
        : type === "trial_document"
          ? clients.trials.searchDocuments(options)
          : type === "appeal_decision"
            ? clients.appeals.search(options)
            : clients.interferences.search(options)) as Promise<PtabResponse>;
}
function ptabGet(clients: FacadeClients, type: PtabType) {
  return (id: string) =>
    (type === "proceeding"
      ? clients.trials.getProceeding(id)
      : type === "trial_decision"
        ? clients.trials.getDecision(id)
        : type === "trial_document"
          ? clients.trials.getDocument(id)
          : type === "appeal_decision"
            ? clients.appeals.getDecision(id)
            : clients.interferences.getDecision(id)) as Promise<PtabResponse>;
}
const isNotFound = (error: unknown) =>
  error instanceof ApiError &&
  (error.status === 404 || error.code === "NOT_FOUND");

/** Python-compatible opaque cursor: base64 JSON of {offset, limit}. */
function encodeCursor(offset: number, limit: number) {
  return Buffer.from(JSON.stringify({ offset, limit })).toString("base64url");
}
function decodeCursor(cursor: string): { offset: number; limit: number } {
  try {
    const parsed = z
      .object({
        offset: z.number().int().nonnegative(),
        limit: z.number().int().positive(),
      })
      .parse(JSON.parse(Buffer.from(cursor, "base64url").toString("utf8")));
    return parsed;
  } catch {
    throw new Error("invalid PTAB next_cursor");
  }
}
const odpProvenance = (path: string): Provenance => ({
  source_url: `https://api.uspto.gov${path}`,
  source_name: "USPTO Open Data Portal",
  retrieved_at: new Date().toISOString(),
  cache_hit: false,
});

const LITIGATION_PTAB_TYPE_DESCRIPTION =
  "forum='ptab' only: which PTAB record kind to search. 'proceeding' = AIA trials (IPR/PGR/CBM/DER); 'trial_decision'/'trial_document' = filings in those trials; 'appeal_decision' = ex parte appeals; 'interference_decision' = pre-AIA interferences.";

export function registerLitigationFacade(
  server: FastMCP,
  clients: FacadeClients,
  auth?: AuthCheck,
): void {
  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "search_litigation",
      description:
        "Search a patent tribunal's records by free text — PTAB proceedings/decisions or Federal Circuit opinions.\n\nRoutes to the right tribunal by ``forum``. On this server only forum='ptab' is available; Federal Circuit (forum='cafc') search is not yet ported. For one record by identifier use ``get_litigation``.\n\nRelated tools: get_litigation, list_ptab_children.",
      input: z.object({
        forum: z
          .enum(["ptab", "cafc"])
          .describe(
            "Which tribunal's free-text index to search. 'ptab' = USPTO Patent Trial and Appeal Board records (AIA trials, ex parte appeals, pre-AIA interferences). 'cafc' = U.S. Court of Appeals for the Federal Circuit opinions and orders (not yet available on this server).",
          ),
        query: z.string().min(1).describe("Free-text search query."),
        limit: z
          .number()
          .int()
          .min(1)
          .max(100)
          .default(25)
          .describe("Maximum source rows per page (CAFC: 1-100)."),
        full: z
          .boolean()
          .default(false)
          .describe(
            "False (default) = lean stub per hit (small). True = full record per hit (large; prefer get_litigation for a single record).",
          ),
        ptab_type: ptabType
          .default("proceeding")
          .describe(LITIGATION_PTAB_TYPE_DESCRIPTION),
        patent_only: z
          .boolean()
          .default(false)
          .describe(
            "forum='cafc' only: case-name heuristic; can miss patent cases.",
          ),
        offset: z
          .number()
          .int()
          .nonnegative()
          .default(0)
          .describe("Number of source records to skip (PTAB or CAFC)."),
        next_cursor: z
          .string()
          .max(2048)
          .nullable()
          .default(null)
          .describe(
            "Continuation from the previous response; overrides offset and limit. Keep forum, query, ptab_type, and patent_only unchanged.",
          ),
      }),
    },
    async (input) => {
      if (input.forum === "cafc")
        notPorted(
          "Federal Circuit (CAFC) opinion search",
          "Use forum='ptab' for PTAB records.",
        );
      let { offset, limit } = input;
      if (input.next_cursor)
        ({ offset, limit } = decodeCursor(input.next_cursor));
      const type = input.ptab_type;
      const response = await ptabSearch(
        clients,
        type,
      )({ query: input.query, limit, offset });
      const rows = records(response, type);
      const total = response.count;
      if (!Number.isSafeInteger(total) || total < 0)
        throw new Error(
          "PTAB search omitted a valid total count; coverage is unknown",
        );
      if (
        (rows.length && offset + rows.length > total) ||
        (!rows.length && offset < total)
      )
        throw new Error(
          "PTAB search page contradicts its total count; retry the source query",
        );
      const more = offset + rows.length < total;
      return {
        ...listEnvelope(
          `PTAB ${type} — \`${input.query}\`: ${rows.length} of ${total} hits at offset ${offset}.`,
          input.full
            ? rows.map((row) => ({ ...row }))
            : rows.map((row) => stubPtabRecord(row, type)),
          response.provenance,
        ),
        more_available: more,
        next_cursor: more ? encodeCursor(offset + rows.length, limit) : null,
      };
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "get_litigation",
      description:
        "Fetch one tribunal record by identifier — a PTAB record, USITC investigation, or UPC decision.\n\nAlways returns a ``ListEnvelope`` (stable shape whether you pass one id or many). On this server only forum='ptab' is available; UPC decisions are not yet ported. Find identifiers with ``search_litigation``. For child records of a PTAB trial use ``list_ptab_children``.\n\nRelated tools: search_litigation, list_ptab_children.",
      input: z.object({
        forum: z
          .enum(["ptab", "upc"])
          .describe(
            "Which tribunal the identifier names. 'ptab' = USPTO Patent Trial and Appeal Board record. 'upc' = Unified Patent Court decision (not yet available on this server).",
          ),
        identifier: z
          .union([z.string().min(1), z.array(z.string().min(1)).min(1).max(50)])
          .describe(
            "The record identifier, or a list for portfolio workflows. By forum: ptab → trial number (e.g. 'IPR2024-00001') or a document identifier for non-proceeding ptab_type; upc → canonical case id (e.g. 'UPC_CFI_1747/2025', 'UPC_CoA_335/2023').",
          ),
        ptab_type: ptabType
          .default("proceeding")
          .describe(
            "forum='ptab' only: what the identifier names. 'proceeding' takes a trial number; the others take a document identifier from search_litigation(forum='ptab').",
          ),
      }),
    },
    async (input) => {
      if (input.forum === "upc")
        notPorted(
          "Unified Patent Court (UPC) decision retrieval",
          "Use forum='ptab'.",
        );
      const type = input.ptab_type;
      const ids = asList(input.identifier);
      const get = ptabGet(clients, type);
      const items: Row[] = [];
      const notFound: string[] = [];
      let provenance: Provenance | undefined;
      // Bounded fan-out, four at a time, preserving input order.
      for (let start = 0; start < ids.length; start += 4) {
        const batch = await Promise.all(
          ids.slice(start, start + 4).map(async (id) => {
            try {
              return { id, response: await get(id) };
            } catch (error) {
              if (typeof input.identifier !== "string" && isNotFound(error))
                return { id };
              throw error;
            }
          }),
        );
        for (const { id, response } of batch) {
          if (!response) {
            notFound.push(id);
            continue;
          }
          provenance ??= response.provenance;
          items.push(...records(response, type).map((row) => ({ ...row })));
        }
      }
      const first = items[0];
      const summary =
        ids.length === 1 && first
          ? summarizePtab(first, type)
          : `${items.length} PTAB ${type} records retrieved for ${ids.length - notFound.length} of ${ids.length} identifiers.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
      const path = `/api/v1/ptab/${type.replace("_", "-")}s${ids.length === 1 ? `/${ids[0]}` : ""}`;
      return {
        ...listEnvelope(summary, items, provenance ?? odpProvenance(path)),
        not_found: notFound,
      };
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "list_ptab_children",
      description:
        "List Patent Trial and Appeal Board (PTAB) children — decisions or documents attached to a parent record.\n\nThe parent can be an AIA trial number, a USPTO application number (for ex parte appeals), or a pre-AIA interference number. For trials, pass ``include='both'`` to enumerate decisions and party filings in one call. Use the document identifiers to fetch full records via ``get_litigation`` or PDFs via ``download_document`` (source='ptab_trial', 'ptab_trial_docs', 'ptab_appeal' or 'ptab_interference').\n\nRelated tools: search_litigation, get_litigation, download_document.",
      input: z.object({
        parent_type: z
          .string()
          .describe(
            "What the ``parent_identifier`` refers to. 'trial' — an AIA trial number (e.g. 'IPR2024-00001'); lists decisions and/or documents. 'application' — a USPTO application number; lists ex parte appeal decisions for it. 'interference' — an interference number; lists decisions.",
          ),
        parent_identifier: z
          .string()
          .min(1)
          .describe("Trial number, application number, or interference number"),
        include: z
          .string()
          .default("decisions")
          .describe(
            "For parent_type='trial' only: 'decisions' (default), 'documents', or 'both'. Appeals and interferences only return decisions.",
          ),
      }),
    },
    async (input) => {
      const parent = input.parent_type.trim().toLowerCase();
      const include = input.include.trim().toLowerCase();
      const id = input.parent_identifier;
      if (!["trial", "application", "interference"].includes(parent))
        throw new Error(
          `parent_type must be 'trial', 'application', or 'interference'; got '${input.parent_type}'`,
        );
      if (parent === "trial") {
        if (!["decisions", "documents", "both"].includes(include))
          throw new Error(
            `include must be 'decisions', 'documents', or 'both' for trials; got '${input.include}'`,
          );
        const items: Row[] = [];
        let provenance: Provenance | undefined;
        if (include !== "documents") {
          const response = (await clients.trials.getDecisionsByTrial(
            id,
          )) as PtabResponse;
          provenance ??= response.provenance;
          for (const row of records(response, "trial_decision"))
            items.push(
              stubPtabRecord({ ...row, trialNumber: id }, "trial_decision"),
            );
        }
        if (include !== "decisions") {
          const response = (await clients.trials.getDocumentsByTrial(
            id,
          )) as PtabResponse;
          provenance ??= response.provenance;
          for (const row of records(response, "trial_document"))
            items.push(
              stubPtabRecord({ ...row, trialNumber: id }, "trial_document"),
            );
        }
        return listEnvelope(
          `PTAB trial ${id} — ${items.length} ${include} record${items.length === 1 ? "" : "s"}.`,
          items,
          provenance ?? odpProvenance(`/api/v1/ptab/trials/${id}/${include}`),
        );
      }
      if (include !== "decisions")
        throw new Error(
          `parent_type='${parent}' only supports include='decisions'`,
        );
      if (parent === "application") {
        let response: PtabResponse | undefined;
        try {
          response = (await clients.appeals.getDecisionsByNumber(
            id,
          )) as PtabResponse;
        } catch (error) {
          // ODP answers 404 when an application has no appeal decisions.
          if (!isNotFound(error)) throw error;
        }
        const items = response
          ? records(response, "appeal_decision").map((row) =>
              stubPtabRecord(row, "appeal_decision"),
            )
          : [];
        return listEnvelope(
          `PTAB ex parte appeal decisions for application ${id} — ${items.length} decision${items.length === 1 ? "" : "s"}.`,
          items,
          response?.provenance ??
            odpProvenance(`/api/v1/ptab/appeals/by-application/${id}`),
        );
      }
      const response = (await clients.interferences.getDecisionsByNumber(
        id,
      )) as PtabResponse;
      const items = records(response, "interference_decision").map((row) =>
        stubPtabRecord(row, "interference_decision"),
      );
      return listEnvelope(
        `PTAB interference decisions for ${id} — ${items.length} decision${items.length === 1 ? "" : "s"}.`,
        items,
        response.provenance,
      );
    },
  );
}
