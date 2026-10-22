import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import { EdisClient, HtsClient } from "../packages/client/src/index.js";

export const usitcCassette = resolve(
  import.meta.dir,
  "cassettes",
  "usitc.yaml",
);
type Edis = EdisClient;
export interface UsitcRecording {
  /** 337-1380 lists two phase rows (Other1, Violation). */
  investigation: Awaited<ReturnType<Edis["listInvestigations"]>>;
  phase: Awaited<ReturnType<Edis["listInvestigations"]>>;
  missing: Awaited<ReturnType<Edis["listInvestigations"]>>;
  documents: Awaited<ReturnType<Edis["listDocuments"]>>;
  emptyPage: Awaited<ReturnType<Edis["listDocuments"]>>;
  attachments: Awaited<ReturnType<Edis["listAttachments"]>>;
  hts: Awaited<ReturnType<HtsClient["search"]>>;
  export: Awaited<ReturnType<HtsClient["exportRange"]>>;
}

/**
 * Replay (default) or record public EDIS metadata and HTS calls. Recording
 * sends no token (these routes are public) and spaces requests out: the
 * Akamai edge in front of USITC blocks an address for a while after bursts.
 */
export async function usitcRecording(record = false): Promise<UsitcRecording> {
  if (!record && !existsSync(usitcCassette))
    throw new Error("Missing USITC cassette.");
  const pause = () =>
    record ? new Promise((done) => setTimeout(done, 15000)) : undefined;
  let result: UsitcRecording | undefined;
  await useCassette(
    usitcCassette,
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri"],
      filterHeaders: ["authorization", "cookie", "set-cookie"],
    },
    async () => {
      const edis = new EdisClient({ retryLimit: 0, token: "" });
      const hts = new HtsClient({ retryLimit: 0 });
      const investigation = await edis.listInvestigations({
        investigationNumber: "337-1380",
      });
      await pause();
      const phase = await edis.listInvestigations({
        investigationNumber: "337-1380",
        investigationPhase: "Violation",
      });
      await pause();
      const missing = await edis.listInvestigations({
        investigationNumber: "337-9999999",
      });
      await pause();
      const documents = await edis.listDocuments({
        investigationNumber: "337-1380",
        pageNumber: 1,
      });
      await pause();
      const emptyPage = await edis.listDocuments({
        investigationNumber: "337-1380",
        pageNumber: 99,
      });
      await pause();
      const attachments = await edis.listAttachments(856966);
      await pause();
      const htsResult = await hts.search("semiconductor");
      await pause();
      const exported = await hts.exportRange("0101", "0102");
      result = {
        investigation,
        phase,
        missing,
        documents,
        emptyPage,
        attachments,
        hts: htsResult,
        export: exported,
      };
    },
  );
  return result as UsitcRecording;
}
