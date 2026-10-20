import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { bodyToBuffer, Cassette, RecordMode } from "cassetter";
import {
  OFFICE_ACTION_ANALYTICS_DATASETS,
  OfficeActionAnalyticsClient,
} from "../packages/client/src/office-action-analytics.js";
import { OfficeActionsClient } from "../packages/client/src/office-actions.js";
import type { ClientOptions } from "../packages/client/src/transport.js";

const directory = resolve(import.meta.dir, "cassettes");
const secretParameters = [
  "Expires",
  "Signature",
  "Key-Pair-Id",
  "X-Amz-Signature",
  "X-Amz-Credential",
  "X-Amz-Security-Token",
  "apiKey",
];
function safeLocation(value: string) {
  const url = new URL(value);
  for (const key of secretParameters)
    if (url.searchParams.has(key)) url.searchParams.set(key, "[FILTERED]");
  return url.href;
}
const headerMap = (headers: Headers) =>
  Object.fromEntries([...headers].map(([key, value]) => [key, [value]]));
async function smallBody(response: Response) {
  const reader = response.clone().body?.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  if (reader)
    try {
      for (;;) {
        const chunk = await reader.read();
        if (chunk.done) break;
        length += chunk.value.byteLength;
        if (length > 4 * 1024 * 1024) {
          await reader.cancel();
          throw new Error("OA recording exceeds 4 MiB limit.");
        }
        chunks.push(chunk.value);
      }
    } finally {
      reader.releaseLock();
    }
  return Buffer.concat(chunks);
}
export async function officeActionRecording<T>(
  name: string,
  mode: "all" | "none",
  run: (options: ClientOptions) => Promise<T>,
): Promise<T> {
  const path = resolve(directory, `odp-${name}.yaml`);
  const record = mode === "all" && !existsSync(path);
  const cassette = new Cassette(path, {
    recordMode: record ? RecordMode.ALL : RecordMode.NONE,
    matchConfig: { matchOn: ["method", "uri", "json_body", "body"] },
    securityConfig: {
      filterHeaders: [
        "x-api-key",
        "authorization",
        "cookie",
        "set-cookie",
        "x-access-token",
      ],
      filterQueryParameters: secretParameters,
    },
  });
  cassette.load();
  const fetcher = (async (input, init) => {
    const request = new Request(input, init);
    if (new URL(request.url).origin !== "https://api.uspto.gov")
      throw new Error("OA recorder accepts only the official ODP origin.");
    const requestBody =
      request.method === "GET"
        ? null
        : Buffer.from(await request.clone().arrayBuffer());
    if (!record) {
      const response = cassette.play(
        request.method,
        request.url,
        headerMap(request.headers),
        requestBody,
      );
      return new Response(new Uint8Array(bodyToBuffer(response.body)), {
        status: response.status,
        headers: Object.fromEntries(
          Object.entries(response.headers).map(([key, value]) => [
            key,
            value.join(", "),
          ]),
        ),
      });
    }
    await Bun.sleep(1100);
    const response = await fetch(request);
    const headers = new Headers(response.headers);
    const location = headers.get("location");
    if (location)
      headers.set(
        "location",
        safeLocation(new URL(location, request.url).href),
      );
    let body = await smallBody(response);
    if (response.status >= 300 && response.status < 400)
      body = Buffer.from(
        body
          .toString("utf8")
          .replace(
            /((?:Expires|Signature|Key-Pair-Id|X-Amz-Signature|X-Amz-Credential|X-Amz-Security-Token))=[^&\s"<>]+/gi,
            "$1=[FILTERED]",
          ),
      );
    cassette.record(
      request.method,
      request.url,
      headerMap(request.headers),
      requestBody,
      response.status,
      headerMap(headers),
      body,
    );
    return response;
  }) as typeof fetch;
  try {
    return await run({
      ...(record ? {} : { apiKey: "replay-placeholder" }),
      fetch: fetcher,
      retryLimit: 0,
      timeoutMs: 20_000,
      maxResponseBytes: 4 * 1024 * 1024,
    });
  } finally {
    if (record) cassette.save();
  }
}
export interface RecordingOutcome {
  name: string;
  verified: boolean;
  status?: number;
  code?: string;
  count?: number;
  bytes?: number;
  returned?: number;
}
export async function officeActionFeatureRecordings(
  mode: "all" | "none",
  report: (outcome: RecordingOutcome) => void = () => {},
) {
  const outcomes: RecordingOutcome[] = [];
  async function step<T>(
    name: string,
    run: (options: ClientOptions) => Promise<T>,
    summarize: (value: T) => Partial<RecordingOutcome>,
  ) {
    try {
      const result = await officeActionRecording(name, mode, run);
      const outcome = { name, verified: true, ...summarize(result) };
      outcomes.push(outcome);
      report(outcome);
      return result;
    } catch (error) {
      const status =
        typeof error === "object" &&
        error &&
        "status" in error &&
        typeof error.status === "number"
          ? error.status
          : undefined;
      const code =
        typeof error === "object" &&
        error &&
        "code" in error &&
        typeof error.code === "string"
          ? error.code
          : "CONTRACT_ERROR";
      const outcome = {
        name,
        verified: false,
        ...(status === undefined ? {} : { status }),
        code,
      };
      outcomes.push(outcome);
      report(outcome);
      if (status === 429)
        throw new Error(
          "ODP rate limit reached; stop recording and preserve existing successes.",
        );
      return undefined;
    }
  }
  const search = await step(
    "office-actions-get-search",
    (options) =>
      new OfficeActionsClient(options).search({
        method: "GET",
        query: "documentCode:CTNF",
        limit: 1,
      }),
    (value) => ({ count: value.count ?? value.officeActionDataBag.length }),
  );
  const id = search?.officeActionDataBag[0]?.officeActionRecordIdentifier;
  if (!id)
    throw new Error(
      "A recorded positive office action identifier is required.",
    );
  await step(
    "office-actions-get",
    (options) => new OfficeActionsClient(options).get(id),
    (value) => ({ count: value.count ?? value.officeActionDataBag.length }),
  );
  await step(
    "office-actions-text",
    (options) => new OfficeActionsClient(options).downloadText(id),
    (value) => ({ bytes: new TextEncoder().encode(value.data).byteLength }),
  );
  for (const method of ["GET", "POST"] as const)
    for (const format of ["csv", "json"] as const)
      await step(
        `office-actions-export-${method.toLowerCase()}-${format}`,
        (options) =>
          new OfficeActionsClient(options).download({
            method,
            format,
            query: `officeActionRecordIdentifier:${id}`,
            limit: 1,
          }),
        (value) => {
          const text = new TextDecoder().decode(value.data);
          const count =
            format === "json"
              ? (JSON.parse(text) as { officeActionsData: unknown[] })
                  .officeActionsData.length
              : text.trim().split(/\r?\n/).length - 1;
          return { bytes: value.data.byteLength, count };
        },
      );
  for (const dataset of OFFICE_ACTION_ANALYTICS_DATASETS) {
    await step(
      `office-action-analytics-${dataset}-fields`,
      (options) => new OfficeActionAnalyticsClient(options).getFields(dataset),
      (value) => ({ count: value.data.fields.length }),
    );
    await step(
      `office-action-analytics-${dataset}-records`,
      (options) =>
        new OfficeActionAnalyticsClient(options).search(dataset, "*:*", {
          rows: 1,
        }),
      (value) => ({ count: value.numFound, returned: value.results.length }),
    );
  }
  return outcomes;
}
