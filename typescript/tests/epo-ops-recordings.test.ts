import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import type {
  EpoBiblioResponse,
  EpoCitationResponse,
  EpoEquivalentsResponse,
  EpoFamilyResponse,
  EpoFullTextResponse,
  EpoLegalEventsResponse,
  EpoNumberConversionResponse,
  EpoResult,
  EpoSearchResponse,
  FamilyEvidence,
  RegisterBiblioResponse,
  RegisterEventsResponse,
  RegisterProceduralStepsResponse,
  UnitaryPatentPackage,
} from "../packages/client/src/epo-ops.js";
import {
  cassettePath,
  epoRecording,
  operations,
} from "./epo-ops-recordings.js";

const replay = <T>(name: string) => epoRecording<EpoResult<T>>(name);

test("every recorded EPO OPS cassette omits credentials and caller IPs", async () => {
  for (const name of Object.keys(operations)) {
    const text = await readFile(cassettePath(name), "utf8");
    expect(text).toContain('access_token: "[FILTERED]"');
    expect(text).not.toMatch(/^\s+authorization:/im);
    expect(text).not.toMatch(/Bearer [A-Za-z0-9]/);
    expect(text).not.toMatch(/x-epo-client-ip|x-epo-forwarded/i);
  }
});

test("real search, empty search and US pre-grant normalization", async () => {
  const search = await replay<EpoSearchResponse>("search");
  expect(search.data.total_results).toBeGreaterThan(100);
  expect(search.data.results).toHaveLength(5);
  expect(search.data.results[0]?.docdb_number).toMatch(/^[A-Z]{2}\d+[A-Z]\d?$/);
  expect(search.provenance.source_url).toContain("/published-data/search");
  const empty = await replay<EpoSearchResponse>("search-empty");
  expect(empty.data).toMatchObject({ total_results: 0, results: [] });
  const us = await replay<EpoBiblioResponse>("biblio-us-pgpub");
  expect(us.data.documents[0]?.docdb_number).toBe("US2005262543A1");
  expect(us.provenance.source_url).toContain("/US2005262543A1/biblio");
});

test("real biblio, citations, equivalents and number conversion", async () => {
  const biblio = await replay<EpoBiblioResponse>("biblio");
  expect(biblio.data.documents[0]).toMatchObject({
    docdb_number: "EP1000000A1",
    family_id: "19768124",
    title:
      "Apparatus for manufacturing green bricks for the brick manufacturing industry",
  });
  const citations = await replay<EpoCitationResponse>("citations");
  expect(citations.data.citations.length).toBeGreaterThan(0);
  expect(citations.data.citations[0]).toMatchObject({
    cited_phase: "national-search-report",
    categories: ["A"],
  });
  const equivalents = await replay<EpoEquivalentsResponse>("equivalents");
  expect(equivalents.data.equivalents.map((item) => item.doc_number)).toContain(
    "US6093011",
  );
  const conversion =
    await replay<EpoNumberConversionResponse>("number-conversion");
  expect(conversion.data.output_document).toMatchObject({
    country: "EP",
    doc_number: "1000000",
    kind: "A1",
    format: "docdb",
  });
  expect(conversion.data.messages).toEqual(["SUCCESS"]);
});

test("real full text keeps one claim set per language", async () => {
  const claims = await replay<EpoFullTextResponse>("claims");
  expect(claims.data.docdb_number).toBe("EP1000000B1");
  expect(claims.data.claims.map((claim) => claim.language)).toEqual([
    "de",
    "fr",
    "en",
  ]);
  expect(claims.data.claims[2]?.text).toStartWith("1. Apparatus");
  expect(claims.data.claims[2]?.text).toContain("\n11. Apparatus");
  const description = await replay<EpoFullTextResponse>("description");
  expect(description.data.description?.length).toBeGreaterThan(5000);
});

test("real family, legal events and register views", async () => {
  const family = await replay<EpoFamilyResponse>("family");
  expect(family.data.num_records).toBe(family.data.members.length);
  expect(family.data.members[0]?.publication_number).toBe("EP1000000A1");
  const legal = await replay<EpoLegalEventsResponse>("legal-events");
  expect(legal.data.events.length).toBeGreaterThan(10);
  expect(legal.data.events[0]?.event_code).toMatch(/^[A-Z]{2}\.\w+/);
  const biblio = await replay<RegisterBiblioResponse>("register-biblio");
  expect(biblio.provenance.source_name).toBe("European Patent Register");
  expect(biblio.data.bibliographic_status).toBe(
    "No opposition filed within time limit",
  );
  expect(biblio.data.titles.map((title) => title.language)).toContain("en");
  expect(biblio.data.party_sets.map((set) => set.role)).toContain(
    "representative",
  );
  const events = await replay<RegisterEventsResponse>("register-events");
  expect(events.data.events.length).toBeGreaterThan(10);
  const steps = await replay<RegisterProceduralStepsResponse>(
    "register-procedural-steps",
  );
  expect(steps.data.procedural_steps[0]?.dates[0]?.date).toMatch(/^\d{8}$/);
});

test("real Unitary Patent register record and absence", async () => {
  const registered = await replay<UnitaryPatentPackage | null>(
    "unitary-patent",
  );
  expect(registered.data).toMatchObject({
    epo_number: "EP4108782",
    is_registered: true,
    latest_status: { status_code: "9", text: "Unitary effect registered" },
  });
  const none = await replay<UnitaryPatentPackage | null>("unitary-patent-none");
  expect(none.data).toBeNull();
});

test("real CPC retrieval, search, mapping and CPCI allocations", async () => {
  const cpc = await replay<{
    scheme: { items: { symbol: string; children: unknown[] }[] };
  }>("cpc-retrieve");
  expect(cpc.data.scheme.items[0]?.symbol).toBe("H04L9/32");
  expect(cpc.data.scheme.items[0]?.children.length).toBeGreaterThan(0);
  const search = await replay<{ results: { classification_symbol: string }[] }>(
    "cpc-search",
  );
  expect(search.data.results[0]?.classification_symbol).toBe("G06N20/00");
  const map = await replay<{ mappings: { ipc: string | null }[] }>("cpc-map");
  expect(map.data.mappings[0]?.ipc).toBe("H04L9/32");
  const cpci = await replay<{ records: { classifications: unknown[] }[] }>(
    "cpci-biblio",
  );
  expect(cpci.data.records[0]?.classifications.length).toBeGreaterThan(0);
});

test("real family evidence is source-separated", async () => {
  const evidence = await epoRecording<FamilyEvidence>("family-evidence");
  expect(evidence.publication_number).toBe("EP1000000A1");
  for (const view of [
    "inpadoc_family",
    "simple_family_equivalents",
    "backward_citations",
    "worldwide_legal_events",
    "register_biblio",
    "register_events",
    "register_procedural_steps",
  ] as const)
    expect(evidence[view].outcome).toBe("ok");
  expect(evidence.limitations).toHaveLength(4);
});

test("real full-document PDF merges every page", async () => {
  const pdf = await epoRecording<
    EpoResult<Uint8Array> & { pages: number; publicationNumber: string }
  >("pdf");
  expect(new TextDecoder().decode(pdf.data.slice(0, 5))).toBe("%PDF-");
  expect(pdf.publicationNumber).toBe("EP1000000A1");
  const { PDFDocument } = await import("pdf-lib");
  expect((await PDFDocument.load(pdf.data)).getPageCount()).toBe(pdf.pages);
});
