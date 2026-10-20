import { expect, test } from "bun:test";
import { WAF_USER_AGENT } from "../packages/client/src/trademark-search.js";
import { configuredStore } from "../packages/waf-worker/src/cli.js";
import {
  type AcquisitionBrowser,
  type AcquisitionDependencies,
  acquireWafSession,
  assertSafeWorkerEnvironment,
  browserProcessEnvironment,
  refreshWafSession,
} from "../packages/waf-worker/src/index.js";

const secret = "synthetic-private-waf-cookie";
function fakeBrowser(
  options: {
    cookies?: () => Promise<{ name: string; value: string; expires: number }[]>;
    close?: () => Promise<void>;
    goto?: () => Promise<unknown>;
  } = {},
) {
  let closed = 0;
  const browser: AcquisitionBrowser = {
    newContext: async (context) => {
      expect(context.userAgent).toBe(WAF_USER_AGENT);
      return {
        newPage: async () => ({
          goto: async (url, navigation) => {
            expect(url).toBe("https://tmsearch.uspto.gov/");
            expect(navigation.waitUntil).toBe("domcontentloaded");
            return options.goto?.();
          },
        }),
        cookies: async (url) => {
          expect(url).toBe("https://tmsearch.uspto.gov/");
          return options.cookies
            ? options.cookies()
            : [
                {
                  name: "aws-waf-token",
                  value: secret,
                  expires: Date.now() / 1000 + 86400,
                },
              ];
        },
      };
    },
    close: async () => {
      closed++;
      await options.close?.();
    },
  };
  const dependencies: AcquisitionDependencies = {
    launch: async (options) => {
      expect(options.headless).toBe(true);
      expect(options.timeout).toBeGreaterThan(0);
      for (const key of Object.keys(options.env))
        expect(key).toMatch(
          /^(?:PATH|HOME|TMPDIR|TMP|TEMP|LANG|LC_[A-Z_]+|SYSTEMROOT|WINDIR)$/i,
        );
      return browser;
    },
  };
  return { browser, dependencies, closed: () => closed };
}

test("worker publishes only after closing its isolated browser and returns safe metadata", async () => {
  const fake = fakeBrowser();
  let writes = 0;
  const result = await refreshWafSession(
    {
      write: async (session) => {
        expect(fake.closed()).toBe(1);
        expect(session.token).toBe(secret);
        expect(session.userAgent).toBe(WAF_USER_AGENT);
        expect(session.acquired).toBeGreaterThan(0);
        writes++;
      },
    },
    {},
    fake.dependencies,
  );
  expect(result.refreshed).toBe(true);
  expect(writes).toBe(1);
  expect(JSON.stringify(result)).not.toContain(secret);
  expect(fake.closed()).toBe(1);
});

test("cookie polling permits normal page issuance without network-idle waits", async () => {
  let polls = 0;
  const fake = fakeBrowser({
    cookies: async () =>
      ++polls === 1
        ? []
        : [
            {
              name: "aws-waf-token",
              value: secret,
              expires: Date.now() / 1000 + 86400,
            },
          ],
  });
  expect(
    (await acquireWafSession({ timeoutMs: 1000 }, fake.dependencies)).token,
  ).toBe(secret);
  expect(polls).toBe(2);
  expect(fake.closed()).toBe(1);
});

test("invalid or expired cookies fail without publishing or exposing their values", async () => {
  for (const cookie of [
    { value: secret, expires: -1 },
    { value: secret, expires: Date.now() / 1000 - 1 },
    { value: `${secret};other=value`, expires: Date.now() / 1000 + 86400 },
    { value: "", expires: Date.now() / 1000 + 86400 },
  ]) {
    const fake = fakeBrowser({
      cookies: async () => [{ name: "aws-waf-token", ...cookie }],
    });
    let writes = 0;
    try {
      await refreshWafSession(
        {
          write: async () => {
            writes++;
          },
        },
        {},
        fake.dependencies,
      );
      throw new Error("Expected cookie rejection");
    } catch (error) {
      expect(error).toMatchObject({ code: "INVALID_COOKIE" });
      expect(String(error)).not.toContain(secret);
      expect(error).not.toHaveProperty("cause");
    }
    expect(writes).toBe(0);
    expect(fake.closed()).toBe(1);
  }
});

test("navigation and publication errors are sanitized and close the browser", async () => {
  const navigation = fakeBrowser({
    goto: async () => {
      throw new Error(secret);
    },
  });
  await expect(
    acquireWafSession({}, navigation.dependencies),
  ).rejects.toMatchObject({ code: "BROWSER_FAILURE" });
  expect(navigation.closed()).toBe(1);
  const publication = fakeBrowser();
  try {
    await refreshWafSession(
      {
        write: async () => {
          throw new Error(secret);
        },
      },
      {},
      publication.dependencies,
    );
  } catch (error) {
    expect(error).toMatchObject({ code: "PUBLISH_FAILURE" });
    expect(String(error)).not.toContain(secret);
    expect(error).not.toHaveProperty("cause");
  }
  expect(publication.closed()).toBe(1);
});

test("missing cookies and stuck browser operations obey an overall deadline", async () => {
  for (const cookies of [async () => [], () => new Promise<never>(() => {})]) {
    const fake = fakeBrowser({ cookies });
    const start = Date.now();
    await expect(
      acquireWafSession({ timeoutMs: 20 }, fake.dependencies),
    ).rejects.toMatchObject({ code: "TIMEOUT" });
    expect(Date.now() - start).toBeLessThan(1000);
    expect(fake.closed()).toBe(1);
  }
});

test("cancelled acquisition does not launch and late launch completion is closed", async () => {
  const controller = new AbortController();
  controller.abort(new Error(secret));
  let launches = 0;
  const fake = fakeBrowser();
  await expect(
    acquireWafSession(
      { signal: controller.signal },
      {
        launch: async () => {
          launches++;
          return fake.browser;
        },
      },
    ),
  ).rejects.toMatchObject({ code: "CANCELLED" });
  expect(launches).toBe(0);
  let finish: ((browser: AcquisitionBrowser) => void) | undefined;
  const pending = acquireWafSession(
    { timeoutMs: 20 },
    {
      launch: () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    },
  );
  await expect(pending).rejects.toMatchObject({ code: "TIMEOUT" });
  finish?.(fake.browser);
  await Bun.sleep(1);
  expect(fake.closed()).toBe(1);
});

test("failed browser cleanup prevents publication", async () => {
  const fake = fakeBrowser({
    close: async () => {
      throw new Error(secret);
    },
  });
  let writes = 0;
  await expect(
    refreshWafSession(
      {
        write: async () => {
          writes++;
        },
      },
      {},
      fake.dependencies,
    ),
  ).rejects.toMatchObject({ code: "CLEANUP_FAILURE" });
  expect(writes).toBe(0);
});

test("browser protocol diagnostics are rejected before secret acquisition", () => {
  for (const environment of [
    { DEBUG: "pw:protocol" },
    { DEBUG: "*" },
    { PWDEBUG: "console" },
  ])
    expect(() => assertSafeWorkerEnvironment(environment)).toThrow();
  expect(() => assertSafeWorkerEnvironment({})).not.toThrow();
});

test("worker destination configuration is explicit and rejects ambiguous targets", () => {
  expect(
    configuredStore([], { PCA_WAF_TOKEN_FILE: "/tmp/pca-synthetic-waf.json" }),
  ).toHaveProperty("write");
  expect(
    configuredStore(
      ["--secret-resource", "projects/project-id/secrets/waf"],
      {},
    ),
  ).toHaveProperty("write");
  expect(
    configuredStore(["--output-file", "/tmp/pca-synthetic-waf.json"], {
      PCA_WAF_TOKEN_FILE: " ",
    }),
  ).toHaveProperty("write");
  for (const [args, environment] of [
    [[], {}],
    [
      [],
      {
        PCA_WAF_TOKEN_FILE: "/tmp/pca-synthetic-waf.json",
        PCA_WAF_SECRET_RESOURCE: "projects/project-id/secrets/waf",
      },
    ],
    [
      [],
      {
        PCA_WAF_TOKEN_FILE: " ",
        PCA_WAF_SECRET_RESOURCE: "projects/project-id/secrets/waf",
      },
    ],
    [
      [],
      {
        PCA_WAF_TOKEN_FILE: "/tmp/pca-synthetic-waf.json",
        PCA_WAF_SECRET_RESOURCE: " ",
      },
    ],
    [["--output-file"], {}],
    [["--unknown", secret], {}],
    [["--output-file", "/tmp/a", "--output-file", "/tmp/b"], {}],
  ] as [string[], Record<string, string>][]) {
    try {
      configuredStore(args, environment);
      throw new Error("Expected invalid configuration");
    } catch (error) {
      expect(error).toMatchObject({ code: "INVALID_CONFIGURATION" });
      expect(String(error)).not.toContain(secret);
    }
  }
});

test("CLI failure output cannot include browser diagnostics or supplied values", async () => {
  const child = Bun.spawn(
    [
      process.execPath,
      new URL("../packages/waf-worker/src/cli.ts", import.meta.url).pathname,
    ],
    {
      env: { DEBUG: "pw:protocol", PCA_WAF_TOKEN_FILE: secret },
      stdout: "pipe",
      stderr: "pipe",
    },
  );
  const [stdout, stderr, exit] = await Promise.all([
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
    child.exited,
  ]);
  expect(exit).toBe(1);
  expect(stdout).toBe("");
  expect(JSON.parse(stderr)).toEqual({
    refreshed: false,
    code: "INVALID_CONFIGURATION",
  });
  expect(stderr).not.toContain(secret);
});

test("browser child environment excludes office and cloud credentials", () => {
  const environment = browserProcessEnvironment({
    PATH: "/usr/bin",
    HOME: "/tmp/synthetic-home",
    TMPDIR: "/tmp",
    LANG: "en_US.UTF-8",
    LC_TIME: "C",
    SYSTEMROOT: "C:\\Windows",
    USPTO_ODP_API_KEY: secret,
    PCA_WAF_TOKEN_JSON: secret,
    GOOGLE_OAUTH_ACCESS_TOKEN: secret,
    AWS_SECRET_ACCESS_KEY: secret,
    DEBUG: secret,
  });
  expect(environment).toEqual({
    PATH: "/usr/bin",
    HOME: "/tmp/synthetic-home",
    TMPDIR: "/tmp",
    LANG: "en_US.UTF-8",
    LC_TIME: "C",
    SYSTEMROOT: "C:\\Windows",
  });
  expect(JSON.stringify(environment)).not.toContain(secret);
});

test("cancellation while closing the browser prevents publication", async () => {
  const controller = new AbortController();
  const fake = fakeBrowser({
    close: async () => {
      controller.abort(new Error(secret));
    },
  });
  let writes = 0;
  await expect(
    refreshWafSession(
      {
        write: async () => {
          writes++;
        },
      },
      { signal: controller.signal },
      fake.dependencies,
    ),
  ).rejects.toMatchObject({ code: "CANCELLED" });
  expect(fake.closed()).toBe(1);
  expect(writes).toBe(0);
});

test("acquisition cannot return a session after its deadline expires during cleanup", async () => {
  const fake = fakeBrowser({
    close: async () => {
      await Bun.sleep(40);
    },
  });
  await expect(
    acquireWafSession({ timeoutMs: 20 }, fake.dependencies),
  ).rejects.toMatchObject({ code: "TIMEOUT" });
  expect(fake.closed()).toBe(1);
});

test("publication obeys the refresh deadline and receives the cancellation signal", async () => {
  const fake = fakeBrowser();
  let writeSignal: AbortSignal | undefined;
  const start = Date.now();
  await expect(
    refreshWafSession(
      {
        write: async (_session, options) => {
          writeSignal = options?.signal;
          return new Promise<never>(() => {});
        },
      },
      { timeoutMs: 20 },
      fake.dependencies,
    ),
  ).rejects.toMatchObject({ code: "TIMEOUT" });
  expect(writeSignal?.aborted).toBe(true);
  expect(Date.now() - start).toBeLessThan(1000);
  expect(fake.closed()).toBe(1);
});
