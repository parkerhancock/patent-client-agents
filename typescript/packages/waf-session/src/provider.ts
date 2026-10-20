import { createHash } from "node:crypto";
import {
  WAF_USER_AGENT,
  type WafToken,
  type WafTokenProvider,
} from "@patent-client-agents/client";
import {
  parseWafSession,
  type WafSession,
  WafSessionError,
  type WafSessionStore,
  withDeadline,
} from "./session.js";

const fingerprint = (token: WafToken) =>
  createHash("sha256")
    .update(token.token)
    .update("\0")
    .update(token.userAgent ?? WAF_USER_AGENT)
    .digest("hex");
export function createWafSessionProvider(
  store: Pick<WafSessionStore, "read">,
  options: { pollIntervalMs?: number; timeoutMs?: number } = {},
): WafTokenProvider {
  const interval = options.pollIntervalMs ?? 30000;
  const timeout = options.timeoutMs ?? 10000;
  if (
    !Number.isInteger(interval) ||
    interval < 0 ||
    interval > 2147483647 ||
    !Number.isInteger(timeout) ||
    timeout <= 0 ||
    timeout > 2147483647
  )
    throw new WafSessionError("Invalid WAF session provider timing.");
  let cached: WafSession | undefined;
  let loadedAt = 0;
  let loading: Promise<WafSession> | undefined;
  const rejected = new Set<string>();
  return {
    async load({ forceRefresh, rejectedToken }) {
      if (rejectedToken) {
        rejected.add(fingerprint(rejectedToken));
        if (rejected.size > 32)
          rejected.delete(rejected.values().next().value as string);
        if (cached && rejected.has(fingerprint(cached))) cached = undefined;
      }
      if (
        !forceRefresh &&
        cached &&
        cached.expires * 1000 > Date.now() &&
        Date.now() - loadedAt < interval
      )
        return { ...cached };
      loading ??= withDeadline(async (signal) => {
        const value = await store.read();
        signal.throwIfAborted();
        const next = parseWafSession(value);
        if (rejected.has(fingerprint(next)))
          throw new WafSessionError(
            "The session store still contains a rejected WAF session.",
          );
        cached = next;
        loadedAt = Date.now();
        return next;
      }, timeout).catch(() => {
        throw new WafSessionError(
          "Unable to load a fresh trusted WAF session.",
        );
      });
      const pending = loading;
      try {
        const next = await pending;
        if (rejected.has(fingerprint(next))) {
          cached = undefined;
          throw new WafSessionError(
            "The session store still contains a rejected WAF session.",
          );
        }
        return { ...next };
      } finally {
        if (loading === pending) loading = undefined;
      }
    },
  };
}
