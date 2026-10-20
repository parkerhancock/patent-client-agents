import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { bodyToBuffer, Cassette, RecordMode } from "cassetter";
import {
  ApiError,
  type ClientOptions,
} from "../packages/client/src/transport.js";
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
  retryRecorded = false,
) {
  let path = resolve(import.meta.dir, "cassettes", `tsdr-live-${name}.yaml`);
  const basePath = path;
  let attempt = 0;
  for (;;) {
    const next = basePath.replace(
      ".yaml",
      `-retry${attempt ? `-${attempt + 1}` : ""}.yaml`,
    );
    if (
      !existsSync(next) &&
      !existsSync(next.replace(".yaml", ".failure.json"))
    )
      break;
    path = next;
    attempt++;
  }
  if (retryRecorded) {
    const previous = existsSync(path) ? new Cassette(path) : undefined;
    previous?.load();
    const unsuccessful =
      existsSync(path.replace(".yaml", ".failure.json")) ||
      previous?.interactions.some((i) => i.response.status >= 400);
    if (!previous && !unsuccessful)
      throw new Error(
        "Explicit retry requires a previously unsuccessful recording.",
      );
    if (unsuccessful) {
      const throttled = previous?.interactions.find(
        (i) => i.response.status === 429,
      );
      if (throttled) {
        const delay = Number(
          throttled.response.headers["retry-after"]?.[0] ?? 60,
        );
        if (Date.now() < Date.parse(throttled.recordedAt) + delay * 1000)
          throw new Error(
            "Recorded TSDR Retry-After interval has not elapsed.",
          );
      }
      path = basePath.replace(
        ".yaml",
        `-retry${attempt ? `-${attempt + 1}` : ""}.yaml`,
      );
    }
  }
  const failurePath = path.replace(".yaml", ".failure.json");
  if (existsSync(failurePath)) {
    const failure = (await Bun.file(failurePath).json()) as {
      status: number;
      code: string;
    };
    throw new ApiError(
      "Previously recorded bounded check produced no HTTP response.",
      failure.status,
      failure.code,
    );
  }
  const record = key !== undefined && !existsSync(path);
  const cassette = new Cassette(path, {
    recordMode: record ? RecordMode.ALL : RecordMode.NONE,
    matchConfig: { matchOn: ["method", "uri"] },
    securityConfig: {
      filterHeaders: filtered,
      filterQueryParameters: ["apiKey", "api_key"],
    },
  });
  cassette.load();
  if (record) await Bun.sleep(6000);
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
            `/ts/cd/casestatus/sn${serial}/v1/info`,
            `/ts/cd/casestatus/sn${serial}/content.html`,
            `/ts/cd/casedocs/sn${serial}/bundle`,
            "/ts/cd/casedocs/bundle.xml",
            "/ts/cd/casedocs/bundle.pdf",
            "/ts/cd/casedocs/bundle.zip",
            "/ts/cd/caseMultiStatus/sn",
            "/last-update/info.xml",
            "/last-update/info.json",
          ].includes(url.pathname) ||
          new RegExp(
            `^/ts/cd/casedoc/sn${serial}/[A-Z]+[0-9]{14}/(info|(content|download)[.](pdf|zip)|1/media)$`,
          ).test(url.pathname) ||
          new RegExp(
            `^/ts/cd/(casestatus|casedocs)/sn${serial}/(content|download)[.](pdf|zip)$`,
          ).test(url.pathname) ||
          /^\/ts\/cd\/casedocs\/sn75757575\/(content|download)[.](pdf|zip)$/.test(
            url.pathname,
          )
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
      const response = await fetch(request, {
        redirect: "manual",
        signal: AbortSignal.timeout(20_000),
      });
      const announced = Number(response.headers.get("content-length"));
      if (announced > limit) {
        await response.body?.cancel();
        throw new ApiError(
          "TSDR recording exceeds its size bound.",
          0,
          "RESPONSE_TOO_LARGE",
        );
      }
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
              throw new ApiError(
                "TSDR recording exceeds its size bound.",
                0,
                "RESPONSE_TOO_LARGE",
              );
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
  } catch (error) {
    if (record && error instanceof ApiError && error.status === 0)
      await Bun.write(
        failurePath,
        JSON.stringify(
          {
            verified: false,
            status: error.status,
            code: error.code,
            observed_at: new Date().toISOString(),
            timeout_ms: 20000,
            max_response_bytes: limit,
            note: "Bounded live attempt did not capture a complete HTTP response; not an upstream HTTP cassette.",
          },
          null,
          2,
        ),
      );
    throw error;
  } finally {
    if (record) await save();
  }
}
export async function tsdrFeatureRecordings(
  key?: string,
  report: (value: TsdrOutcome) => void = () => {},
  selection: { only?: string; retryRecorded?: boolean } = {},
) {
  const outcomes: TsdrOutcome[] = [];
  let stopped = false;
  async function step<T>(
    name: string,
    run: (client: TsdrClient) => Promise<T>,
    summarize: (result: T) => Partial<TsdrOutcome>,
  ) {
    if (stopped || (selection.only && name !== selection.only))
      return undefined;
    try {
      const result = await recording(
        name,
        key,
        run,
        selection.retryRecorded && selection.only === name,
      );
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
        stopped = true;
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
  ) ?? { docId: "NOA20070926100613" };
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
  await step(
    "status-xml",
    (c) => c.getStatusXml(serial),
    (r) => ({ bytes: r.data.length }),
  );
  await step(
    "status-legacy-xml",
    (c) => c.getStatusXml(serial, { legacy: true }),
    (r) => ({ bytes: r.data.length }),
  );
  await step(
    "status-html",
    (c) => c.getStatusHtml(serial),
    (r) => ({ bytes: r.data.length }),
  );
  await step(
    "batch-status",
    (c) => c.batchStatus([serial], { timeoutMs: 20_000 }),
    () => ({}),
  );
  await step(
    "case-bundle-xml",
    (c) => c.getCaseBundleXml(serial),
    (r) => ({ bytes: r.data.length }),
  );
  await step(
    "bundle-xml",
    (c) => c.getBundleXml([serial]),
    (r) => ({ bytes: r.data.length }),
  );
  if (doc?.docId) {
    const documentId = doc.docId;
    for (const [delivery, format] of [
      ["content", "pdf"],
      ["content", "zip"],
      ["download", "zip"],
    ] as const)
      await step(
        `single-document-${delivery}-${format}`,
        (c) =>
          c.downloadDocument(serial, documentId, {
            delivery,
            format,
            timeoutMs: 20_000,
          }),
        (r) => ({ bytes: r.data.length }),
      );
    await step(
      "single-document-page",
      (c) => c.getDocumentPage(serial, documentId, "1"),
      (r) => ({ bytes: r.data.length }),
    );
  }
  for (const delivery of ["content", "download"] as const)
    for (const format of ["pdf", "zip"] as const)
      await step(
        `status-${delivery}-${format}`,
        (c) =>
          c.downloadStatus(serial, { delivery, format, timeoutMs: 20_000 }),
        (r) => ({ bytes: r.data.length }),
      );
  for (const delivery of ["content", "download"] as const)
    for (const format of ["pdf", "zip"] as const)
      await step(
        `small-case-documents-${delivery}-${format}`,
        (c) =>
          c.downloadCaseDocuments("75757575", {
            delivery,
            format,
            timeoutMs: 20_000,
          }),
        (r) => ({ bytes: r.data.length }),
      );
  for (const format of ["pdf", "zip"] as const)
    await step(
      `bundle-${format}`,
      (c) =>
        c.downloadBundle([serial], {
          format,
          date: "2007-09-25",
          timeoutMs: 20_000,
        }),
      (r) => ({ bytes: r.data.length }),
    );
  await step(
    "small-case-candidates",
    (c) => c.getBundleXml(["75757575", "75008897", "72131351", "76515878"]),
    (r) => ({ bytes: r.data.length }),
  );
  return outcomes;
}
