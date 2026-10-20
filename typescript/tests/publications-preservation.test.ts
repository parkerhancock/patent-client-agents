import { expect, test } from "bun:test";
import { PublicationsClient } from "../packages/client/src/publications.js";
import {
  convertBiblio,
  convertDocument,
} from "../packages/client/src/publications-models.js";

test("PPUBS converters preserve future fields while normalized values take precedence", () => {
  const source = {
    guid: "US-1-B2",
    type: "USPAT",
    publicationReferenceDocumentNumber: "1",
    pubRefDocNumber: "1",
    datePublished: "20261020",
    publication_date: "conflicting upstream field",
    inventionTitle: "A widget",
    patent_title: "conflicting upstream title",
    claimsHtml: "1. A widget.",
    document: { claims: "conflicting upstream document" },
    futureUpstreamField: { values: [0, false, null, "new"] },
    futureEmptyField: "",
  };
  for (const convert of [convertBiblio, convertDocument]) {
    const result = convert(source);
    expect(result.futureUpstreamField).toEqual(source.futureUpstreamField);
    expect(result.futureEmptyField).toBe("");
    expect(result.publication_number).toBe("1");
    expect(result.publication_date).toBe("2026-10-20");
    expect(result.patent_title).toBe("A widget");
  }
  expect(convertDocument(source).document).toMatchObject({
    claims: [{ number: 1, text: "1. A widget." }],
  });
  expect(source.document).toEqual({ claims: "conflicting upstream document" });
});

test("PPUBS search and document clients retain unmodeled response data", async () => {
  const record = {
    guid: "US-1-B2",
    type: "USPAT",
    publicationReferenceDocumentNumber: "1",
    pubRefDocNumber: "1",
    futureUpstreamField: { addedByOffice: true },
  };
  const client = new PublicationsClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(new Request(input, init).url).pathname;
      if (path === "/pubwebapp/") return new Response("landing");
      if (path === "/api/users/me/session")
        return Response.json({ userCase: { caseId: 1 } });
      if (path === "/api/searches/counts")
        return Response.json({ numResults: 1 });
      if (path === "/api/searches/searchWithBeFamily")
        return Response.json({ numFound: 1, patents: [record] });
      if (path === "/api/patents/highlight/US-1-B2")
        return Response.json(record);
      throw new Error("Unexpected synthetic PPUBS request");
    }) as typeof fetch,
  });
  const search = await client.searchBiblio({ query: "widget" });
  expect(search.docs[0]?.futureUpstreamField).toEqual(
    record.futureUpstreamField,
  );
  const document = await client.getDocument("US-1-B2", { source: "USPAT" });
  expect(document.futureUpstreamField).toEqual(record.futureUpstreamField);
  expect(document.publication_number).toBe("1");
});
