import { createHash } from "node:crypto";
import { ApplicationsClient } from "../packages/client/src/applications.js";
import { applicationNumber, recorded } from "./cassettes.js";

export const applicationDatasets = [
  "meta-data",
  "adjustment",
  "assignment",
  "attorney",
  "continuity",
  "foreign-priority",
  "transactions",
] as const;
export function artifactDigest(bytes: Uint8Array | string) {
  return createHash("sha256").update(bytes).digest("hex");
}
export async function applicationFeatureRecordings(
  mode: "none" | "all",
  report: (value: unknown) => void = () => {},
  only?: string[],
) {
  const recordingMode = (name: string) =>
    mode === "all" && (!only || only.includes(name)) ? "all" : "none";
  const api = new ApplicationsClient({
    ...(mode === "none" ? { apiKey: "replay-placeholder" } : {}),
    retryLimit: 0,
    timeoutMs: 20_000,
  });
  const datasets: Record<string, Record<string, unknown>> = {};
  for (const dataset of applicationDatasets) {
    const response = await recorded(
      `application-${dataset}`,
      () =>
        api.getData(applicationNumber, dataset, {
          signal: AbortSignal.timeout(20_000),
        }),
      recordingMode(dataset),
    );
    datasets[dataset] = response.data;
    report({ dataset, sourceKeys: Object.keys(response.data) });
  }
  const status = await recorded(
    "application-status-codes",
    () =>
      api.getStatusCodes(
        { q: "applicationStatusCode:150" },
        { signal: AbortSignal.timeout(20_000) },
      ),
    recordingMode("status-codes"),
  );
  report({ dataset: "status-codes", sourceKeys: Object.keys(status.data) });
  // Reuse the successful real document-list recording; no live traffic is allowed in replay.
  const documents = await recorded("documents", () =>
    api.getDocuments(applicationNumber),
  );
  const artifacts: Record<
    string,
    { documentIdentifier: string; size: number; sha256: string }
  > = {};
  for (const [format, sourceFormat] of [
    ["pdf", "PDF"],
    ["xml", "XML"],
    ["docx", "MS_WORD"],
  ] as const) {
    const document = documents.documents.find(
      (document) =>
        typeof document.documentIdentifier === "string" &&
        Array.isArray(document.downloadOptionBag) &&
        document.downloadOptionBag.some(
          (option) =>
            option &&
            typeof option === "object" &&
            (option as Record<string, unknown>).mimeTypeIdentifier ===
              sourceFormat,
        ),
    );
    if (!document || typeof document.documentIdentifier !== "string") {
      report({ format, available: false });
      continue;
    }
    const id = document.documentIdentifier;
    const response = await recorded<{ data: Uint8Array | string }>(
      `application-${format}`,
      () =>
        format === "xml"
          ? api.downloadDocumentXml(applicationNumber, id, {
              signal: AbortSignal.timeout(30_000),
            })
          : api.downloadDocument(applicationNumber, id, {
              format,
              signal: AbortSignal.timeout(30_000),
            }),
      recordingMode(format),
    );
    const size =
      typeof response.data === "string"
        ? new TextEncoder().encode(response.data).length
        : response.data.length;
    const signature =
      typeof response.data === "string"
        ? response.data.trimStart()
        : new TextDecoder().decode(response.data.subarray(0, 8));
    if (
      format === "pdf"
        ? !signature.startsWith("%PDF-")
        : format === "docx"
          ? !signature.startsWith("PK")
          : !signature.startsWith("<")
    )
      throw new Error(`Invalid real ${format} document signature.`);
    artifacts[format] = {
      documentIdentifier: id,
      size,
      sha256: artifactDigest(response.data),
    };
    report({ format, ...artifacts[format] });
  }
  const application = await recorded("application", () =>
    api.get(applicationNumber),
  );
  const patent = application.patentBag[0]?.patentNumber;
  let claims:
    | Awaited<ReturnType<ApplicationsClient["getGrantedClaims"]>>
    | undefined;
  if (patent) {
    claims = await recorded(
      "application-granted-claims",
      () =>
        api.getGrantedClaims(patent, { signal: AbortSignal.timeout(30_000) }),
      recordingMode("granted-claims"),
    );
    report({ dataset: "granted-claims", count: claims.claims?.length ?? 0 });
  }
  return { datasets, status, artifacts, claims };
}
