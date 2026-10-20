import { WAF_USER_AGENT } from "@patent-client-agents/client";
import {
  parseWafSession,
  type WafSession,
  type WafSessionStore,
} from "@patent-client-agents/waf-session";

const target = "https://tmsearch.uspto.gov/";
export type WafWorkerFailure =
  | "INVALID_CONFIGURATION"
  | "TIMEOUT"
  | "CANCELLED"
  | "INVALID_COOKIE"
  | "BROWSER_FAILURE"
  | "CLEANUP_FAILURE"
  | "PUBLISH_FAILURE";
export class WafWorkerError extends Error {
  constructor(readonly code: WafWorkerFailure) {
    super("WAF refresh worker failed.");
    this.name = "WafWorkerError";
  }
}

interface Cookie {
  name: string;
  value: string;
  expires: number;
}
interface BrowserContext {
  newPage(): Promise<{
    goto(
      url: string,
      options: { waitUntil: "domcontentloaded"; timeout: number },
    ): Promise<unknown>;
  }>;
  cookies(url: string): Promise<Cookie[]>;
}
export interface AcquisitionBrowser {
  newContext(options: { userAgent: string }): Promise<BrowserContext>;
  close(): Promise<void>;
}
export interface AcquisitionDependencies {
  launch(options: {
    headless: boolean;
    timeout: number;
    env: Record<string, string>;
  }): Promise<AcquisitionBrowser>;
}
export interface AcquisitionOptions {
  timeoutMs?: number;
  signal?: AbortSignal;
}

/** Browser diagnostics can expose cookie-bearing protocol messages. */
export function assertSafeWorkerEnvironment(
  environment: Record<string, string | undefined> = process.env,
) {
  if (environment.DEBUG?.trim() || environment.PWDEBUG?.trim())
    throw new WafWorkerError("INVALID_CONFIGURATION");
}

/** Browser children need OS settings, not the worker's office or cloud credentials. */
export function browserProcessEnvironment(
  environment: Record<string, string | undefined> = process.env,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(environment).filter(
      (entry): entry is [string, string] =>
        entry[1] !== undefined &&
        /^(?:PATH|HOME|TMPDIR|TMP|TEMP|LANG|LC_[A-Z_]+|SYSTEMROOT|WINDIR)$/i.test(
          entry[0],
        ),
    ),
  );
}

function aborted(caller?: AbortSignal) {
  return new WafWorkerError(caller?.aborted ? "CANCELLED" : "TIMEOUT");
}
function untilAbort<T>(
  promise: Promise<T>,
  signal: AbortSignal,
  caller?: AbortSignal,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const abort = () => reject(aborted(caller));
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) abort();
    void promise
      .then(resolve, reject)
      .finally(() => signal.removeEventListener("abort", abort));
  });
}
async function closeBrowser(browser: AcquisitionBrowser, timeoutMs: number) {
  await untilAbort(
    browser.close(),
    AbortSignal.timeout(Math.min(timeoutMs, 5000)),
  );
}

/** Acquires only the cookie issued by the official site; it performs no challenge interaction. */
export async function acquireWafSession(
  options: AcquisitionOptions = {},
  dependencies?: AcquisitionDependencies,
): Promise<WafSession> {
  assertSafeWorkerEnvironment();
  const timeoutMs = options.timeoutMs ?? 60_000;
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 300_000)
    throw new WafWorkerError("INVALID_CONFIGURATION");
  const deadline = AbortSignal.timeout(timeoutMs);
  const signal = options.signal
    ? AbortSignal.any([deadline, options.signal])
    : deadline;
  let browser: AcquisitionBrowser | undefined;
  let finished = false;
  let acquiredSession: WafSession | undefined;
  let failure: WafWorkerError | undefined;
  try {
    if (signal.aborted) throw aborted(options.signal);
    const launch =
      dependencies?.launch ??
      (async (launchOptions) => {
        const { chromium } = await import("playwright");
        return chromium.launch(launchOptions);
      });
    const launching = launch({
      headless: true,
      timeout: timeoutMs,
      env: browserProcessEnvironment(),
    }).then((created) => {
      browser = created;
      // A launch can settle after the caller's deadline has already fired.
      if (finished) void closeBrowser(created, timeoutMs).catch(() => {});
      return created;
    });
    const activeBrowser = await untilAbort(launching, signal, options.signal);
    const context = await untilAbort(
      activeBrowser.newContext({ userAgent: WAF_USER_AGENT }),
      signal,
      options.signal,
    );
    const page = await untilAbort(context.newPage(), signal, options.signal);
    await untilAbort(
      page.goto(target, { waitUntil: "domcontentloaded", timeout: timeoutMs }),
      signal,
      options.signal,
    );
    for (;;) {
      const cookies = await untilAbort(
        context.cookies(target),
        signal,
        options.signal,
      );
      const cookie = cookies.find(
        (candidate) => candidate.name === "aws-waf-token",
      );
      if (cookie) {
        try {
          acquiredSession = parseWafSession({
            token: cookie.value,
            expires: cookie.expires,
            acquired: Date.now() / 1000,
            userAgent: WAF_USER_AGENT,
          });
        } catch {
          throw new WafWorkerError("INVALID_COOKIE");
        }
        break;
      }
      await untilAbort(Bun.sleep(250), signal, options.signal);
    }
  } catch (error) {
    failure =
      error instanceof WafWorkerError
        ? error
        : new WafWorkerError("BROWSER_FAILURE");
  } finally {
    finished = true;
    if (browser) {
      try {
        await closeBrowser(browser, timeoutMs);
      } catch {
        failure ??= new WafWorkerError("CLEANUP_FAILURE");
      }
    }
  }
  if (signal.aborted) throw aborted(options.signal);
  if (failure) throw failure;
  if (!acquiredSession) throw new WafWorkerError("BROWSER_FAILURE");
  return acquiredSession;
}

/** Publishes privately and returns only safe scheduling metadata.
 * Cancellation during a remote write can leave its commit outcome unknown; never retry blindly.
 */
export async function refreshWafSession(
  store: Pick<WafSessionStore, "write">,
  options: AcquisitionOptions = {},
  dependencies?: AcquisitionDependencies,
) {
  const timeoutMs = options.timeoutMs ?? 60_000;
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 300_000)
    throw new WafWorkerError("INVALID_CONFIGURATION");
  const deadline = AbortSignal.timeout(timeoutMs);
  const signal = options.signal
    ? AbortSignal.any([deadline, options.signal])
    : deadline;
  try {
    const session = await acquireWafSession(
      { timeoutMs, signal },
      dependencies,
    );
    if (signal.aborted) throw aborted(options.signal);
    try {
      await untilAbort(
        store.write(session, { signal }),
        signal,
        options.signal,
      );
    } catch (error) {
      if (signal.aborted) throw aborted(options.signal);
      throw error instanceof WafWorkerError
        ? error
        : new WafWorkerError("PUBLISH_FAILURE");
    }
    if (signal.aborted) throw aborted(options.signal);
    return {
      refreshed: true,
      expires: session.expires,
      acquired: session.acquired,
    };
  } catch (error) {
    if (signal.aborted) throw aborted(options.signal);
    throw error;
  }
}
