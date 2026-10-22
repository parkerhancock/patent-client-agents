import type {
  Middleware,
  MiddlewareContext,
  Next,
} from "@prefecthq/fastmcp-ts/server";
import { actorId } from "./crypto.js";
import type { UsageSink } from "./storage.js";

/**
 * Structured stdout events and the per-tool-call usage log, after the Python
 * observability.py. Cloud Run ingests each stdout line as jsonPayload.
 *
 * Events (field names are an interface; Python's `email` field is omitted):
 *   tool_call     actor_id, tool, duration_ms, ok, error, args (preview)
 *   rate_limited  actor_id, bucket, retry_after_seconds
 */
export type EventWriter = (line: string) => void;

const stdout: EventWriter = (line) => {
  process.stdout.write(`${line}\n`);
};

export function logEvent(
  event: string,
  fields: Record<string, unknown>,
  write: EventWriter = stdout,
  severity = "INFO",
) {
  write(
    JSON.stringify({
      severity,
      event,
      ts: new Date().toISOString(),
      ...fields,
    }),
  );
}

/** The caller's lowercased email from the verified token, or "unauthenticated". */
export function callerEmail(context: MiddlewareContext): string {
  const email = context.mcpContext.auth?.claims.email;
  return typeof email === "string" && email
    ? email.toLowerCase()
    : "unauthenticated";
}

/** Truncate long string arguments so logs never carry whole documents. */
export function previewArgs(args: unknown, maxLength = 200) {
  if (!args || typeof args !== "object" || Array.isArray(args)) return {};
  return Object.fromEntries(
    Object.entries(args as Record<string, unknown>).map(([key, value]) => [
      key,
      typeof value === "string" && value.length > maxLength
        ? `${value.slice(0, maxLength)}...[${value.length} total]`
        : value,
    ]),
  );
}

function toolCall(context: MiddlewareContext) {
  const request = (context.request ?? {}) as {
    name?: unknown;
    arguments?: unknown;
  };
  return {
    name: typeof request.name === "string" ? request.name : "unknown",
    arguments: request.arguments,
  };
}

function resultError(result: unknown): string | null {
  if (!result || typeof result !== "object") return null;
  const { isError, content } = result as {
    isError?: unknown;
    content?: unknown;
  };
  if (isError !== true) return null;
  const text = Array.isArray(content)
    ? content.find(
        (item): item is { type: "text"; text: string } =>
          typeof item === "object" &&
          item !== null &&
          (item as { type?: unknown }).type === "text",
      )?.text
    : undefined;
  return (text ?? "Tool returned an error.").slice(0, 500);
}

export interface UsageOptions {
  sink?: UsageSink;
  actorHashKey?: string;
  write?: EventWriter;
  now?: () => number;
}

/**
 * Log every tool call to stdout and, for authenticated callers, one usage
 * record. A failed usage write never fails the tool call.
 */
export function usageMiddleware(options: UsageOptions): Middleware {
  const now = options.now ?? (() => performance.now());
  return {
    async onCallTool(context: MiddlewareContext, next: Next) {
      const call = toolCall(context);
      const email = callerEmail(context);
      const started = now();
      let error: string | null = null;
      try {
        const result = await next();
        error = resultError(result);
        return result;
      } catch (thrown) {
        error =
          thrown instanceof Error
            ? `${thrown.name}: ${thrown.message}`.slice(0, 500)
            : "Error";
        throw thrown;
      } finally {
        const duration = Math.round((now() - started) * 10) / 10;
        const actor = await actorId(email, options.actorHashKey ?? "");
        logEvent(
          "tool_call",
          {
            actor_id: actor ?? null,
            tool: call.name,
            duration_ms: duration,
            ok: error === null,
            error,
            args: previewArgs(call.arguments),
          },
          options.write,
        );
        if (options.sink && actor)
          try {
            await options.sink.record({
              actor_id: actor,
              tool: call.name,
              ts: new Date(),
              duration_ms: duration,
              ok: error === null,
              error,
            });
          } catch {
            logEvent(
              "usage_write_failed",
              { tool: call.name },
              options.write,
              "WARNING",
            );
          }
      }
    },
  };
}
