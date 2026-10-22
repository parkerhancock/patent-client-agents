import { describe, expect, test } from "bun:test";
import { generateKeyPairSync } from "node:crypto";
import { Client } from "@prefecthq/fastmcp-ts/client";
import {
  downloadOptions,
  fileCredentials,
  HostedConfigError,
  loadConfig,
  metadataCredentials,
  prepareCorpora,
} from "../packages/hosted/src/index.js";
import { GcsBlobStore } from "../packages/mcp/src/gcs-blob-store.js";
import { createServer } from "../packages/mcp/src/index.js";
import { hostedEnv } from "./hosted-helpers.js";

const jwtPart = (token: string, index: number) =>
  JSON.parse(
    Buffer.from(token.split(".")[index] ?? "", "base64url").toString("utf8"),
  );

describe("hosted configuration", () => {
  test("bypass mode needs nothing and defaults to memory state", () => {
    const config = loadConfig({ AUTH_BYPASS: "true" });
    expect(config).toMatchObject({
      authBypass: true,
      port: 8080,
      host: "127.0.0.1",
      publicUrl: "http://localhost:8080",
      issuerUrl: "http://localhost:8080",
      stateBackend: "memory",
      termsVersion: "2026-04-23",
      hiddenTools: ["search_trademarks"],
      corpora: { cacheDir: "/app/corpora" },
    });
    expect(config.google).toBeUndefined();
  });

  test("OAuth mode requires Google credentials and strong secrets", () => {
    expect(() => loadConfig({})).toThrow(HostedConfigError);
    const missing = () => loadConfig({ GOOGLE_CLIENT_ID: "id" });
    expect(missing).toThrow("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET");
    expect(() => loadConfig(hostedEnv({ SESSION_SECRET: "short" }))).toThrow(
      "SESSION_SECRET must be at least 32 characters",
    );
    expect(() => loadConfig(hostedEnv({ ACTOR_HASH_KEY: "short" }))).toThrow(
      "ACTOR_HASH_KEY must be at least 16 characters",
    );
    const config = loadConfig(hostedEnv({ STATE_BACKEND: "" }));
    expect(config.stateBackend).toBe("firestore");
    expect(config.google?.clientId).toBe(
      "test-client.apps.googleusercontent.com",
    );
  });

  test("legacy LAW_TOOLS_CORE Google variable names are accepted", () => {
    const { GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, ...rest } = hostedEnv();
    const config = loadConfig({
      ...rest,
      LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID: GOOGLE_CLIENT_ID,
      LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_SECRET: GOOGLE_CLIENT_SECRET,
    });
    expect(config.google?.clientId).toBe(GOOGLE_CLIENT_ID);
  });

  test("public URLs are bare origins, HTTPS unless loopback", () => {
    expect(
      loadConfig(hostedEnv({ PUBLIC_URL: "https://x.run.app/" })).publicUrl,
    ).toBe("https://x.run.app");
    expect(() =>
      loadConfig(hostedEnv({ PUBLIC_URL: "http://x.run.app" })),
    ).toThrow("https");
    expect(() =>
      loadConfig(hostedEnv({ PUBLIC_URL: "https://x.run.app/sub" })),
    ).toThrow("bare origin");
    const config = loadConfig(
      hostedEnv({
        PUBLIC_URL: "https://shadow.run.app",
        ISSUER_URL: "https://issuer.example",
        DOWNLOAD_BASE_URL: "https://downloads.example",
      }),
    );
    expect(config).toMatchObject({
      issuerUrl: "https://issuer.example",
      downloadBaseUrl: "https://downloads.example",
    });
  });

  test("auth bypass is refused on Cloud Run", () => {
    expect(() =>
      loadConfig({ AUTH_BYPASS: "true", K_SERVICE: "patent-mcp-ts" }),
    ).toThrow("refused on Cloud Run");
    expect(() => loadConfig({ AUTH_BYPASS: "maybe" })).toThrow("AUTH_BYPASS");
  });

  test("limits, admins, hidden tools and Firestore settings parse", () => {
    const config = loadConfig(
      hostedEnv({
        ADMIN_EMAILS: " Admin@Example.com , other@example.com ",
        MB_PER_MINUTE: "5",
        MB_PER_DAY: "50",
        HIDDEN_TOOLS: "search_trademarks, search_epo",
        GOOGLE_CLOUD_PROJECT: "proj",
        FIRESTORE_DATABASE: "ts",
        PORT: "9000",
      }),
    );
    expect([...config.limits.adminEmails]).toEqual([
      "admin@example.com",
      "other@example.com",
    ]);
    expect(config.limits).toMatchObject({
      mbPerMinute: 5,
      mbPerDay: 50,
      minChargeBytes: 1024,
    });
    expect(config.hiddenTools).toEqual(["search_trademarks", "search_epo"]);
    expect(config.firestore).toEqual({ projectId: "proj", database: "ts" });
    expect(config.port).toBe(9000);
    expect(loadConfig(hostedEnv({ HIDDEN_TOOLS: "" })).hiddenTools).toEqual([]);
    expect(() => loadConfig(hostedEnv({ MB_PER_DAY: "-1" }))).toThrow(
      "MB_PER_DAY",
    );
  });

  test("credential families are reported by presence only", () => {
    const config = loadConfig({
      AUTH_BYPASS: "true",
      USPTO_ODP_API_KEY: "secret-value",
      EPO_OPS_API_KEY: "k",
    });
    expect(config.credentials["USPTO ODP"]).toBe(true);
    expect(config.credentials["EPO OPS"]).toBe(false);
    expect(JSON.stringify(config)).not.toContain("secret-value");
  });
});

describe("download store", () => {
  test("DOWNLOAD_BUCKET switches downloads to GCS signed URLs", () => {
    expect(
      downloadOptions(loadConfig({ AUTH_BYPASS: "true" })).blobStore,
    ).toBeUndefined();
    const config = loadConfig({
      AUTH_BYPASS: "true",
      DOWNLOAD_BUCKET: "pca-downloads",
      DOWNLOAD_TTL_SECONDS: "3600",
    });
    expect(config.downloadStore).toMatchObject({
      bucket: "pca-downloads",
      ttlSeconds: 3600,
    });
    expect(downloadOptions(config).blobStore).toBeInstanceOf(GcsBlobStore);
  });
});

describe("corpus bootstrap", () => {
  test("runs only when a manifest is configured and exports the reader paths", async () => {
    const calls: string[][] = [];
    const bootstrap = async (uri: string, dir: string) => {
      calls.push([uri, dir]);
      return { MPEP_CORPUS_PATH: `${dir}/mpep/mpep.db.zst` };
    };
    const env: Record<string, string | undefined> = {};
    await prepareCorpora({ cacheDir: "/c" }, bootstrap, env);
    await prepareCorpora(
      { manifestUri: "gs://b/ts/manifest.json", cacheDir: "/c" },
      bootstrap,
      env,
    );
    expect(calls).toEqual([["gs://b/ts/manifest.json", "/c"]]);
    expect(env.MPEP_CORPUS_PATH).toBe("/c/mpep/mpep.db.zst");
  });
});

describe("Google credentials for Firestore", () => {
  test("service account keys mint tokens with a signed JWT assertion", async () => {
    const { privateKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
    const requests: URLSearchParams[] = [];
    const credentials = fileCredentials(
      {
        type: "service_account",
        client_email: "sa@proj.iam.gserviceaccount.com",
        private_key: privateKey
          .export({ type: "pkcs8", format: "pem" })
          .toString(),
        project_id: "proj",
      },
      async (_url, init) => {
        requests.push(new URLSearchParams(String(init?.body)));
        return Response.json({ access_token: "sa-token", expires_in: 3600 });
      },
    );
    expect(await credentials.token()).toBe("sa-token");
    expect(await credentials.token()).toBe("sa-token");
    expect(requests).toHaveLength(1);
    expect(await credentials.projectId()).toBe("proj");
    const assertion = requests[0]?.get("assertion") ?? "";
    expect(jwtPart(assertion, 0).alg).toBe("RS256");
    expect(jwtPart(assertion, 1)).toMatchObject({
      iss: "sa@proj.iam.gserviceaccount.com",
      aud: "https://oauth2.googleapis.com/token",
      scope: "https://www.googleapis.com/auth/datastore",
    });
  });

  test("gcloud user credentials refresh and carry the quota project", async () => {
    const credentials = fileCredentials(
      {
        type: "authorized_user",
        client_id: "c",
        client_secret: "s",
        refresh_token: "r",
        quota_project_id: "quota",
      },
      async (_url, init) => {
        const form = new URLSearchParams(String(init?.body));
        expect(form.get("grant_type")).toBe("refresh_token");
        return Response.json({ access_token: "user-token", expires_in: 10 });
      },
    );
    expect(await credentials.token()).toBe("user-token");
    expect(await credentials.headers()).toEqual({
      "x-goog-user-project": "quota",
    });
  });

  test("the metadata server supplies tokens and the project on Cloud Run", async () => {
    const seen: string[] = [];
    const credentials = metadataCredentials(async (url, init) => {
      seen.push(String(url));
      expect(new Headers(init?.headers).get("metadata-flavor")).toBe("Google");
      return String(url).endsWith("/project/project-id")
        ? new Response("cloud-project")
        : Response.json({ access_token: "md-token", expires_in: 3599 });
    });
    expect(await credentials.token()).toBe("md-token");
    expect(await credentials.projectId()).toBe("cloud-project");
    expect(seen[0]).toContain("/instance/service-accounts/default/token");
    await expect(
      metadataCredentials(
        async () => new Response("", { status: 404 }),
      ).token(),
    ).rejects.toThrow("HTTP 404");
  });
});

describe("createServer hiddenTools", () => {
  async function names(hiddenTools?: string[]) {
    const server = createServer({
      toolset: "full",
      ...(hiddenTools ? { hiddenTools } : {}),
    });
    const client = await Client.connect(server, {
      versionNegotiation: { mode: "legacy" },
    });
    try {
      return {
        listed: (await client.listTools()).map((tool) => tool.name),
        call: hiddenTools?.[0]
          ? await client.callTool(hiddenTools[0], {}).then(
              () => "called",
              (error: Error) => error.message,
            )
          : undefined,
      };
    } finally {
      await client.close();
      await server.close();
    }
  }

  test("hides named tools from the full toolset too, and ignores unknown names", async () => {
    const all = await names();
    expect(all.listed).toContain("search_applications");
    const hidden = await names(["search_applications", "no_such_tool"]);
    expect(hidden.listed).not.toContain("search_applications");
    expect(hidden.listed).toHaveLength(all.listed.length - 1);
    expect(hidden.call).toContain("Unknown tool");
  });
});
