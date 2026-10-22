import type {
  Middleware,
  MiddlewareContext,
  Next,
} from "@prefecthq/fastmcp-ts/server";
import { actorId } from "./crypto.js";
import type { Bucket, BucketState, RateLimitStore } from "./storage.js";
import { callerEmail, type EventWriter, logEvent } from "./usage.js";

/**
 * Per-user byte buckets, after the Python rate_limit.py. Two buckets per
 * user, denominated in response bytes: `minute` (capacity bytes_per_minute,
 * refilled linearly over 60 s) and `day` (bytes_per_day over 86,400 s).
 * A call is checked before it runs (rejected if either bucket is at or
 * below zero) and debited afterwards with max(result bytes, MIN_CHARGE_BYTES),
 * so one large response can drive a bucket negative and the next call waits.
 * Buckets are keyed by the pseudonymous actor id, not the email.
 */
export interface Limits {
  adminEmails: Set<string>;
  mbPerMinute: number;
  mbPerDay: number;
  adminMbPerMinute: number;
  adminMbPerDay: number;
  minChargeBytes: number;
}

type BucketName = "minute" | "day";

export function bucketsFor(email: string, limits: Limits) {
  const admin = limits.adminEmails.has(email.toLowerCase());
  const mb = (value: number) => value * 1024 * 1024;
  return [
    {
      name: "minute" as BucketName,
      capacity: mb(admin ? limits.adminMbPerMinute : limits.mbPerMinute),
      window: 60,
    },
    {
      name: "day" as BucketName,
      capacity: mb(admin ? limits.adminMbPerDay : limits.mbPerDay),
      window: 86_400,
    },
  ];
}

/** Current tokens without writing. Fresh buckets start full; clock skew never refills backwards. */
export function virtualRefill(
  bucket: Bucket | undefined,
  capacity: number,
  window: number,
  now: Date,
): number {
  if (!bucket) return capacity;
  const elapsed = Math.max(
    0,
    (now.getTime() - new Date(bucket.last_refill).getTime()) / 1000,
  );
  return Math.min(capacity, bucket.tokens + elapsed * (capacity / window));
}

export interface RateCheck {
  allowed: boolean;
  bucket?: BucketName;
  retryAfterSeconds?: number;
  remainingBytes?: number;
}

export class RateLimiter {
  constructor(
    private readonly store: RateLimitStore,
    private readonly limits: Limits,
    private readonly clock: () => number = Date.now,
  ) {}

  async check(actor: string, email: string): Promise<RateCheck> {
    const now = new Date(this.clock());
    const state = await this.store.read(actor);
    let remaining = Number.POSITIVE_INFINITY;
    for (const { name, capacity, window } of bucketsFor(email, this.limits)) {
      const tokens = virtualRefill(state?.[name], capacity, window, now);
      if (tokens <= 0)
        return {
          allowed: false,
          bucket: name,
          retryAfterSeconds: Math.abs(tokens) / (capacity / window) + 1,
          remainingBytes: 0,
        };
      remaining = Math.min(remaining, tokens);
    }
    return { allowed: true, remainingBytes: Math.floor(remaining) };
  }

  async debit(actor: string, email: string, cost: number): Promise<void> {
    const now = new Date(this.clock());
    await this.store.update(actor, (current) => {
      const next: BucketState = {};
      for (const { name, capacity, window } of bucketsFor(email, this.limits))
        next[name] = {
          tokens: virtualRefill(current?.[name], capacity, window, now) - cost,
          last_refill: now,
          capacity,
          window_seconds: window,
        };
      return next;
    });
  }
}

export function resultBytes(result: unknown): number {
  try {
    return new TextEncoder().encode(JSON.stringify(result) ?? "").length;
  } catch {
    return 0;
  }
}

/**
 * Gate each tool call. Unauthenticated callers (AUTH_BYPASS) pass through.
 * A rejection is a tool error the client can show, prefixed "[retryable]" as
 * in Python.
 */
export function rateLimitMiddleware(options: {
  limiter: RateLimiter;
  actorHashKey: string;
  minChargeBytes: number;
  write?: EventWriter;
}): Middleware {
  return {
    async onCallTool(context: MiddlewareContext, next: Next) {
      const email = callerEmail(context);
      const actor = await actorId(email, options.actorHashKey);
      if (!actor) return next();
      const check = await options.limiter.check(actor, email);
      if (!check.allowed) {
        const retry = check.retryAfterSeconds ?? 1;
        logEvent(
          "rate_limited",
          {
            actor_id: actor,
            bucket: check.bucket,
            retry_after_seconds: Math.round(retry * 100) / 100,
          },
          options.write,
        );
        throw new Error(
          `[retryable] Rate limit exceeded on ${check.bucket} bucket. Retry in ~${Math.round(retry)}s.`,
        );
      }
      const result = await next();
      try {
        await options.limiter.debit(
          actor,
          email,
          Math.max(resultBytes(result), options.minChargeBytes),
        );
      } catch {
        logEvent("rate_limit_debit_failed", {}, options.write, "WARNING");
      }
      return result;
    },
  };
}
