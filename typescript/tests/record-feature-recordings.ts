import { BulkDataClient } from "../packages/client/src/bulkdata.js";
import { PetitionsClient } from "../packages/client/src/petitions.js";
import {
  PtabAppealsClient,
  PtabInterferencesClient,
  PtabTrialsClient,
} from "../packages/client/src/ptab.js";
import { recorded } from "./cassettes.js";
export async function recordFeatures(
  mode: "all" | "none",
  report: (result: object) => void = () => {},
  only?: string[],
) {
  const options = {
    ...(mode === "none" ? { apiKey: "replay-placeholder" } : {}),
    retryLimit: 0,
    timeoutMs: 20000,
    maxResponseBytes: 4 * 1024 * 1024,
  };
  const trials = new PtabTrialsClient(options),
    appeals = new PtabAppealsClient(options),
    interferences = new PtabInterferencesClient(options),
    petitions = new PetitionsClient(options),
    bulk = new BulkDataClient(options);
  const signal = () => ({ signal: AbortSignal.timeout(20000) });
  const families = [
    {
      name: "proceedings",
      field: "trialNumber",
      number: "IPR2027-00017",
      id: "IPR2027-00017",
      search: trials.searchProceedings.bind(trials),
      download: trials.downloadProceedings.bind(trials),
      downloadFile: trials.downloadProceedingsFile.bind(trials),
      get: trials.getProceeding.bind(trials),
    },
    {
      name: "decisions",
      field: "trialNumber",
      number: "IPR2025-00916",
      id: "171376473",
      search: trials.searchDecisions.bind(trials),
      download: trials.downloadDecisions.bind(trials),
      downloadFile: trials.downloadDecisionsFile.bind(trials),
      get: trials.getDecision.bind(trials),
      byNumber: trials.getDecisionsByTrial.bind(trials),
    },
    {
      name: "documents",
      field: "trialNumber",
      number: "IPR2025-00916",
      id: "171376473",
      search: trials.searchDocuments.bind(trials),
      download: trials.downloadDocuments.bind(trials),
      downloadFile: trials.downloadDocumentsFile.bind(trials),
      get: trials.getDocument.bind(trials),
      byNumber: trials.getDocumentsByTrial.bind(trials),
    },
    {
      name: "appeals",
      field: "appealNumber",
      number: "2026003167",
      id: "4445cc91-1c7c-46c1-aebb-4a35892af716",
      search: appeals.search.bind(appeals),
      download: appeals.download.bind(appeals),
      downloadFile: appeals.downloadFile.bind(appeals),
      get: appeals.getDecision.bind(appeals),
      byNumber: appeals.getDecisionsByNumber.bind(appeals),
    },
    {
      name: "interferences",
      field: "interferenceNumber",
      number: "106130",
      id: "229ba0b8d5f70d2e45cc36b79476f56f3faf51bd26c7ccc977208e7b",
      search: interferences.search.bind(interferences),
      download: interferences.download.bind(interferences),
      downloadFile: interferences.downloadFile.bind(interferences),
      get: interferences.getDecision.bind(interferences),
      byNumber: interferences.getDecisionsByNumber.bind(interferences),
    },
  ];
  const results: Record<string, { count?: number; bytes?: number }> = {};
  const run = async (name: string, operation: () => Promise<unknown>) => {
    const record = mode === "all" && (!only || only.includes(name));
    if (record) await Bun.sleep(1000);
    const result = await recorded(
      `features-${name}`,
      operation,
      record ? "all" : "none",
    );
    if (!result || typeof result !== "object")
      throw new Error("Expected result object");
    const row = result as { data?: unknown; count?: number };
    if (row.data instanceof Uint8Array) {
      if (!row.data.length) throw new Error("Expected nonempty download");
      results[name] = { bytes: row.data.length };
    } else {
      if (row.count === undefined || row.count < 1)
        throw new Error("Expected at least one source record");
      results[name] = { count: row.count };
    }
    report({ name, ...results[name] });
  };
  for (const family of families) {
    const query = `${family.field}:${family.number}`;
    const input = () => ({ query, limit: 1, ...signal() });
    await run(`${family.name}-get-search`, () =>
      family.search({ ...input(), method: "GET" }),
    );
    await run(`${family.name}-get-json`, () =>
      family.download({ ...input(), method: "GET" }),
    );
    await run(`${family.name}-post-json`, () =>
      family.download({ ...input(), method: "POST" }),
    );
    await run(`${family.name}-get-csv`, () =>
      family.downloadFile({ ...input(), method: "GET", fileFormat: "csv" }),
    );
    if (family.name === "decisions" || family.name === "documents")
      await run(`${family.name}-post-csv`, () =>
        family.downloadFile({ ...input(), method: "POST", fileFormat: "csv" }),
      );
    await run(`${family.name}-identifier`, () =>
      family.get(family.id, signal()),
    );
    if (family.byNumber)
      await run(`${family.name}-by-number`, () =>
        family.byNumber(family.number, signal()),
      );
  }
  const petitionId = "0b9ea48d-43c9-5197-8bf1-126d965816a7";
  const petition = () => ({
    query: `petitionDecisionRecordIdentifier:${petitionId}`,
    limit: 1,
    ...signal(),
  });
  await run("petitions-get-search", () =>
    petitions.search({ ...petition(), method: "GET" }),
  );
  await run("petitions-get-json", () =>
    petitions.download({ ...petition(), method: "GET" }),
  );
  await run("petitions-post-json", () =>
    petitions.download({ ...petition(), method: "POST" }),
  );
  await run("petitions-get-csv", () =>
    petitions.downloadFile({ ...petition(), method: "GET", fileFormat: "csv" }),
  );
  await run("petitions-post-csv", () =>
    petitions.downloadFile({
      ...petition(),
      method: "POST",
      fileFormat: "csv",
    }),
  );
  await run("petitions-identifier", () => petitions.get(petitionId, signal()));
  await run("bulk-identifier", () =>
    bulk.getProduct("PTFWPRE", { includeFiles: true, limit: 1, ...signal() }),
  );
  return results;
}
