import { WAF_USER_AGENT, type WafToken } from "@patent-client-agents/client";

export { WAF_USER_AGENT };
export interface WafSession extends WafToken {
  userAgent: string;
  acquired: number;
}
export interface WafSessionStore {
  read(): Promise<WafSession>;
  write(session: WafSession, options?: { signal?: AbortSignal }): Promise<void>;
}
export class WafSessionError extends Error {
  constructor(message = "The trusted WAF session operation failed.") {
    super(message);
    this.name = "WafSessionError";
  }
}
export const MAX_SESSION_BYTES = 32 * 1024;
export function parseWafSession(value: unknown): WafSession {
  if (!value || typeof value !== "object")
    throw new WafSessionError("Invalid WAF session.");
  const session = value as Record<string, unknown>;
  const userAgent = session.userAgent ?? WAF_USER_AGENT;
  // Python uses ISO timestamps on the wire; internal sessions use epoch seconds.
  const acquired =
    typeof session.acquired === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(
      session.acquired,
    )
      ? Date.parse(session.acquired) / 1000
      : session.acquired;
  const now = Date.now() / 1000;
  if (
    typeof session.token !== "string" ||
    !session.token.length ||
    session.token.length > 16384 ||
    !/^[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]+$/.test(session.token) ||
    typeof userAgent !== "string" ||
    !userAgent.trim() ||
    userAgent.length > 1024 ||
    !/^[\x20-\x7e]+$/.test(userAgent) ||
    typeof session.expires !== "number" ||
    !Number.isFinite(session.expires) ||
    session.expires <= now ||
    typeof acquired !== "number" ||
    !Number.isFinite(acquired) ||
    acquired <= 0 ||
    acquired > now + 300 ||
    acquired >= session.expires
  )
    throw new WafSessionError("Invalid or expired WAF session.");
  const parsed = {
    token: session.token,
    expires: session.expires,
    acquired,
    userAgent,
  };
  if (Buffer.byteLength(JSON.stringify(parsed)) > MAX_SESSION_BYTES)
    throw new WafSessionError("WAF session exceeds its size bound.");
  return parsed;
}
export function encodeWafSession(value: WafSession): Uint8Array {
  const session = parseWafSession(value);
  const bytes = Buffer.from(
    JSON.stringify({
      ...session,
      acquired: new Date(Math.round(session.acquired * 1000)).toISOString(),
    }),
  );
  if (bytes.byteLength > MAX_SESSION_BYTES)
    throw new WafSessionError("WAF session exceeds its size bound.");
  return bytes;
}
export function decodeWafSession(bytes: Uint8Array): WafSession {
  try {
    if (bytes.byteLength > MAX_SESSION_BYTES) throw new Error();
    return parseWafSession(
      JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)),
    );
  } catch {
    throw new WafSessionError("Invalid or expired WAF session data.");
  }
}
export async function withDeadline<T>(
  run: (signal: AbortSignal) => Promise<T>,
  timeoutMs: number,
  parentSignal?: AbortSignal,
): Promise<T> {
  if (!Number.isInteger(timeoutMs) || timeoutMs <= 0 || timeoutMs > 2147483647)
    throw new WafSessionError("Invalid WAF session timeout.");
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  let abort: (() => void) | undefined;
  const interrupted = new Promise<never>((_resolve, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new WafSessionError("WAF session operation timed out."));
    }, timeoutMs);
    abort = () => {
      controller.abort();
      reject(new WafSessionError("WAF session operation was cancelled."));
    };
    parentSignal?.addEventListener("abort", abort, { once: true });
    if (parentSignal?.aborted) abort();
  });
  try {
    return await Promise.race([
      interrupted,
      (async () => {
        controller.signal.throwIfAborted();
        return run(controller.signal);
      })(),
    ]);
  } finally {
    clearTimeout(timer);
    if (abort) parentSignal?.removeEventListener("abort", abort);
  }
}
