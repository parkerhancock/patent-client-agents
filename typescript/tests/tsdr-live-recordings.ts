import { resolve } from "node:path";
import { bodyToBuffer, Cassette, RecordMode } from "cassetter";
import type { ClientOptions } from "../packages/client/src/transport.js";
import { TsdrClient } from "../packages/client/src/tsdr.js";

const serial = "78787878"; // Existing real Python TSDR cassette case.
const limit = 4 * 1024 * 1024;
const filtered = ["uspto-api-key", "authorization", "cookie", "set-cookie"];
const headers = (value: Headers) =>
  Object.fromEntries(
    [...value]
      .filter(([key]) => !filtered.includes(key.toLowerCase()))
      .map(([key, item]) => [key, [item]]),
  );
export interface TsdrOutcome {
  name: string;
  verified: boolean;
  status?: number;
  code?: string;
  count?: number;
  bytes?: number;
}
async function recording<T>(
  name: string,
  key: string | undefined,
  run: (client: TsdrClient) => Promise<T>,
) {
  const path = resolve(import.meta.dir, "cassettes", `tsdr-live-${name}.yaml`);
  const record = key !== undefined;
  const cassette = new Cassette(path, {
    recordMode: record ? RecordMode.ALL : RecordMode.NONE,
    matchConfig: { matchOn: ["method", "uri"] },
    securityConfig: {
      filterHeaders: filtered,
      filterQueryParameters: ["apiKey", "api_key"],
    },
  });
  cassette.load();
  const fetcher = Object.assign(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = new Request(input, init);
      const url = new URL(request.url);
      if (
        url.origin !== "https://tsdrapi.uspto.gov" ||
        request.method !== "GET" ||
        !(
          [
            `/ts/cd/casestatus/sn${serial}/info`,
            `/ts/cd/casedocs/sn${serial}/info`,
            `/ts/cd/rawImage/${serial}`,
            "/last-update/info.xml",
            "/last-update/info.json",
          ].includes(url.pathname) ||
          new RegExp(
            `^/ts/cd/casedoc/sn${serial}/[A-Z]+[0-9]{14}/(info|download[.]pdf)$`,
          ).test(url.pathname)
        )
      )
        throw new Error("Unexpected TSDR recording route.");
      if (!record) {
        const result = cassette.play(
          "GET",
          request.url,
          headers(request.headers),
          null,
        );
        return new Response(new Uint8Array(bodyToBuffer(result.body)), {
          status: result.status,
          headers: Object.fromEntries(
            Object.entries(result.headers).map(([k, v]) => [k, v.join(", ")]),
          ),
        });
      }
      await Bun.sleep(1100);
      const response = await fetch(request, {
        redirect: "manual",
        signal: AbortSignal.timeout(20_000),
      });
      const chunks: Uint8Array[] = [];
      let size = 0;
      const reader = response.body?.getReader();
      try {
        if (reader)
          for (;;) {
            const chunk = await reader.read();
            if (chunk.done) break;
            size += chunk.value.byteLength;
            if (size > limit) {
              await reader.cancel();
              throw new Error("TSDR recording size limit exceeded.");
            }
            chunks.push(chunk.value);
          }
      } finally {
        reader?.releaseLock();
      }
      const body = Buffer.concat(chunks);
      const decodedHeaders = new Headers(response.headers);
      decodedHeaders.delete("content-encoding");
      decodedHeaders.delete("content-length");
      const safeHeaders = headers(decodedHeaders);
      if (
        key &&
        (body.includes(Buffer.from(key)) ||
          JSON.stringify(safeHeaders).includes(key))
      )
        throw new Error("Credential reflection rejected before recording.");
      cassette.record(
        "GET",
        request.url,
        headers(request.headers),
        null,
        response.status,
        safeHeaders,
        body,
      );
      return new Response(body, {
        status: response.status,
        headers: decodedHeaders,
      });
    },
    { preconnect: fetch.preconnect },
  ) as typeof fetch;
  const options: ClientOptions = {
    apiKey: key ?? "replay-placeholder",
    fetch: fetcher,
    retryLimit: 0,
    timeoutMs: 20_000,
    maxResponseBytes: limit,
  };
  const save = async () => {
    const serialized = cassette.toYaml();
    if (key && serialized.includes(key))
      throw new Error("Recorded credential check failed.");
    cassette.save();
  };
  try {
    return await run(new TsdrClient(options));
  } finally {
    if (record) await save();
  }
}
export async function tsdrFeatureRecordings(
  key?: string,
  report: (value: TsdrOutcome) => void = () => {},
) {
  const outcomes: TsdrOutcome[] = [];
  async function step<T>(
    name: string,
    run: (client: TsdrClient) => Promise<T>,
    summarize: (result: T) => Partial<TsdrOutcome>,
  ) {
    try {
      const result = await recording(name, key, run);
      const outcome = { name, verified: true, ...summarize(result) };
      outcomes.push(outcome);
      report(outcome);
      return result;
    } catch (error) {
      const e = error as { status?: number; code?: string };
      const outcome = {
        name,
        verified: false,
        ...(e.status === undefined ? {} : { status: e.status }),
        code: e.code ?? "CONTRACT_ERROR",
      };
      outcomes.push(outcome);
      report(outcome);
      if (e.status === 401 || e.status === 403 || e.status === 429)
        throw new Error(
          "TSDR authorization or rate limit stopped bounded checks.",
        );
      return undefined;
    }
  }
  await step(
    "status",
    (c) => c.getStatus(serial),
    (r) => ({ count: r.data.serialNumber ? 1 : 0 }),
  );
  const documents = await step(
    "documents",
    (c) => c.getDocuments(serial),
    (r) => ({ count: r.documents.length }),
  );
  await step(
    "last-update-json",
    (c) => c.getStatusJson(serial),
    () => ({}),
  );
  await step(
    "last-update-xml",
    (c) => c.getLastUpdateXml(serial),
    (r) => ({ bytes: r.data.length }),
  );
  await step(
    "image",
    (c) => c.getImage(serial),
    (r) => ({ bytes: r.data.length }),
  );
  const doc = documents?.documents.find(
    (d) =>
      d.pageCount != null &&
      d.pageCount <= 2 &&
      /^[A-Z]+[0-9]{14}$/.test(d.docId ?? ""),
  );
  if (doc?.docId) {
    const documentId = doc.docId;
    await step(
      "single-document-xml",
      (c) => c.getDocumentInfoXml(serial, documentId),
      (r) => ({ bytes: r.data.length }),
    );
    await step(
      "single-document-pdf",
      (c) => c.downloadDocument(serial, documentId, { timeoutMs: 20_000 }),
      (r) => ({ bytes: r.data.length }),
    );
  }
  return outcomes;
}
