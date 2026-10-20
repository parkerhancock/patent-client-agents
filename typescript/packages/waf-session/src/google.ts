import { crc32c } from "./crc32c.js";
import {
  decodeWafSession,
  encodeWafSession,
  MAX_SESSION_BYTES,
  WafSessionError,
  type WafSessionStore,
  withDeadline,
} from "./session.js";

const metadataUrl =
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token";
const responseLimit = 64 * 1024;
async function json(
  response: Response,
  signal: AbortSignal,
  maxBytes = responseLimit,
): Promise<Record<string, unknown>> {
  const reader = response.body?.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  const abort = () => {
    void reader?.cancel().catch(() => {});
  };
  signal.addEventListener("abort", abort, { once: true });
  try {
    signal.throwIfAborted();
    if (
      !response.ok ||
      Number(response.headers.get("content-length")) > maxBytes
    ) {
      await reader?.cancel();
      throw new Error();
    }
    if (reader)
      for (;;) {
        const chunk = await reader.read();
        signal.throwIfAborted();
        if (chunk.done) break;
        length += chunk.value.byteLength;
        if (length > maxBytes) {
          await reader.cancel();
          throw new Error();
        }
        chunks.push(chunk.value);
      }
    const parsed: unknown = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
      throw new Error();
    return parsed as Record<string, unknown>;
  } finally {
    signal.removeEventListener("abort", abort);
    reader?.releaseLock();
  }
}
export function createGoogleWafSessionStore(
  resource: string,
  options: { fetch?: typeof fetch; timeoutMs?: number } = {},
): WafSessionStore {
  if (
    !/^projects\/[A-Za-z0-9_-]+\/secrets\/[A-Za-z0-9_-]{1,255}$/.test(resource)
  )
    throw new WafSessionError("Invalid Google WAF secret resource.");
  const fetcher = options.fetch ?? fetch;
  const timeoutMs = options.timeoutMs ?? 10000;
  async function request(
    write?: { data: string; dataCrc32c: string },
    parentSignal?: AbortSignal,
  ) {
    return withDeadline(
      async (signal) => {
        signal.throwIfAborted();
        const authResponse = await fetcher(metadataUrl, {
          headers: { "Metadata-Flavor": "Google" },
          redirect: "error",
          signal,
        });
        signal.throwIfAborted();
        if (authResponse.headers.get("metadata-flavor") !== "Google") {
          await authResponse.body?.cancel();
          throw new Error();
        }
        const auth = await json(authResponse, signal, 8192);
        if (
          typeof auth.access_token !== "string" ||
          !auth.access_token ||
          /[\r\n]/.test(auth.access_token) ||
          auth.token_type !== "Bearer"
        )
          throw new Error();
        signal.throwIfAborted();
        const response = await fetcher(
          `https://secretmanager.googleapis.com/v1/${resource}${write === undefined ? "/versions/latest:access" : ":addVersion"}`,
          {
            method: write === undefined ? "GET" : "POST",
            redirect: "error",
            signal,
            headers: {
              Authorization: `Bearer ${auth.access_token}`,
              ...(write === undefined
                ? {}
                : { "Content-Type": "application/json" }),
            },
            ...(write === undefined
              ? {}
              : { body: JSON.stringify({ payload: write }) }),
          },
        );
        return json(response, signal);
      },
      timeoutMs,
      parentSignal,
    );
  }
  return {
    async read() {
      try {
        const result = await request();
        const payload = result.payload as
          | { data?: unknown; dataCrc32c?: unknown }
          | undefined;
        if (
          typeof payload?.data !== "string" ||
          !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(
            payload.data,
          )
        )
          throw new Error();
        const bytes = Buffer.from(payload.data, "base64");
        if (bytes.byteLength > MAX_SESSION_BYTES) throw new Error();
        if (
          payload.dataCrc32c !== undefined &&
          (typeof payload.dataCrc32c !== "string" ||
            !/^\d+$/.test(payload.dataCrc32c) ||
            Number(payload.dataCrc32c) !== crc32c(bytes))
        )
          throw new Error();
        return decodeWafSession(bytes);
      } catch {
        throw new WafSessionError(
          "Unable to read the current Google WAF session secret.",
        );
      }
    },
    async write(session, options = {}) {
      try {
        options.signal?.throwIfAborted();
        const bytes = encodeWafSession(session);
        await request(
          {
            data: Buffer.from(bytes).toString("base64"),
            dataCrc32c: String(crc32c(bytes)),
          },
          options.signal,
        );
      } catch {
        throw new WafSessionError(
          "Unable to publish the Google WAF session secret.",
        );
      }
    },
  };
}
