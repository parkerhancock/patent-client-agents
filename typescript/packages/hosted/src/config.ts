import { z } from "zod";

/**
 * Hosted configuration from environment variables. Names follow the Python
 * deploy wrapper (patent_mcp_deploy.config) where one exists. Every variable
 * is documented in docs/hosted.md.
 */
export type Env = Record<string, string | undefined>;

const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);

const booleanValue = z
  .string()
  .trim()
  .toLowerCase()
  .transform((value, context) => {
    if (["1", "true", "yes", "on"].includes(value)) return true;
    if (["", "0", "false", "no", "off"].includes(value)) return false;
    context.addIssue({ code: "custom", message: "Expected true or false." });
    return z.NEVER;
  });

const origin = z
  .string()
  .trim()
  .url()
  .transform((value, context) => {
    const url = new URL(value);
    if (url.protocol !== "https:" && url.protocol !== "http:") {
      context.addIssue({ code: "custom", message: "Use an http(s) URL." });
      return z.NEVER;
    }
    if (url.pathname.replace(/\/+$/, "") !== "" || url.search || url.hash) {
      context.addIssue({
        code: "custom",
        message: "Use a bare origin without a path, query or fragment.",
      });
      return z.NEVER;
    }
    return url.origin;
  });

const positiveInt = (fallback: number) =>
  z.coerce.number().int().positive().default(fallback);

const list = z
  .string()
  .default("")
  .transform((value) =>
    value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );

const schema = z.object({
  PORT: z.coerce.number().int().min(1).max(65535).default(8080),
  HOST: z.string().trim().min(1).default("127.0.0.1"),
  PUBLIC_URL: origin.default("http://localhost:8080"),
  ISSUER_URL: origin.optional(),
  DOWNLOAD_BASE_URL: origin.optional(),
  AUTH_BYPASS: booleanValue.default(false),
  GOOGLE_CLIENT_ID: z.string().trim().optional(),
  GOOGLE_CLIENT_SECRET: z.string().trim().optional(),
  SESSION_SECRET: z.string().optional(),
  ACTOR_HASH_KEY: z.string().optional(),
  TERMS_VERSION: z.string().trim().min(1).default("2026-04-23"),
  STATE_BACKEND: z.enum(["firestore", "memory"]).optional(),
  GCP_PROJECT: z.string().trim().optional(),
  FIRESTORE_DATABASE: z.string().trim().min(1).default("(default)"),
  FIRESTORE_EMULATOR_HOST: z.string().trim().optional(),
  ADMIN_EMAILS: list,
  MB_PER_MINUTE: positiveInt(20),
  MB_PER_DAY: positiveInt(100),
  ADMIN_MB_PER_MINUTE: positiveInt(200),
  ADMIN_MB_PER_DAY: positiveInt(2048),
  MIN_CHARGE_BYTES: positiveInt(1024),
  HIDDEN_TOOLS: z.string().default("search_trademarks"),
  CORPORA_MANIFEST_URI: z.string().trim().optional(),
  CORPORA_CACHE_DIR: z.string().trim().min(1).default("/app/corpora"),
  K_SERVICE: z.string().optional(),
});

/** Credential variables the TypeScript clients read directly from the environment. */
export const CREDENTIAL_FAMILIES: Record<
  string,
  readonly (readonly string[])[]
> = {
  "USPTO ODP": [["USPTO_ODP_API_KEY"]],
  "USPTO TSDR": [["USPTO_TSDR_API_KEY"]],
  "EPO OPS": [
    ["EPO_OPS_API_KEY", "EPO_API_KEY"],
    ["EPO_OPS_API_SECRET", "EPO_API_SECRET"],
  ],
  "KIPO KIPRIS": [["KIPO_KIPRIS_API_KEY"]],
  "USITC EDIS": [["USITC_EDIS_TOKEN", "USITC_EDIS_TOKEN_FILE"]],
  "USITC DataWeb": [["USITC_DATAWEB_TOKEN", "USITC_DATAWEB_TOKEN_FILE"]],
  "Trademark Search WAF session": [
    ["PCA_WAF_TOKEN_JSON", "PCA_WAF_TOKEN_FILE", "PCA_WAF_SECRET_RESOURCE"],
  ],
};

export interface HostedConfig {
  port: number;
  host: string;
  publicUrl: string;
  issuerUrl: string;
  downloadBaseUrl: string;
  authBypass: boolean;
  /** Present unless authBypass. */
  google?: { clientId: string; clientSecret: string };
  sessionSecret?: string;
  actorHashKey?: string;
  termsVersion: string;
  stateBackend: "firestore" | "memory";
  firestore: {
    projectId?: string;
    database: string;
    emulatorHost?: string;
  };
  limits: {
    adminEmails: Set<string>;
    mbPerMinute: number;
    mbPerDay: number;
    adminMbPerMinute: number;
    adminMbPerDay: number;
    minChargeBytes: number;
  };
  hiddenTools: string[];
  corpora: { manifestUri?: string; cacheDir: string };
  /** Configured credential families, by name only. Values never leave the environment. */
  credentials: Record<string, boolean>;
}

export class HostedConfigError extends Error {
  override name = "HostedConfigError";
}

function first(env: Env, ...names: string[]): string | undefined {
  for (const name of names) {
    const value = env[name]?.trim();
    if (value) return value;
  }
  return undefined;
}

export function loadConfig(env: Env): HostedConfig {
  // Empty variables count as unset, except HIDDEN_TOOLS, where "" hides nothing.
  const present = Object.fromEntries(
    Object.entries(env).filter(
      ([name, value]) =>
        value !== undefined && (name === "HIDDEN_TOOLS" || value.trim() !== ""),
    ),
  );
  const parsed = schema.safeParse({
    ...present,
    GOOGLE_CLIENT_ID: first(
      env,
      "GOOGLE_CLIENT_ID",
      "LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_ID",
    ),
    GOOGLE_CLIENT_SECRET: first(
      env,
      "GOOGLE_CLIENT_SECRET",
      "LAW_TOOLS_CORE_GOOGLE_OAUTH_CLIENT_SECRET",
    ),
    GCP_PROJECT: first(env, "GCP_PROJECT", "GOOGLE_CLOUD_PROJECT"),
  });
  if (!parsed.success)
    throw new HostedConfigError(
      `Invalid hosted configuration: ${parsed.error.issues
        .map((issue) => `${issue.path.join(".") || "env"}: ${issue.message}`)
        .join("; ")}`,
    );
  const value = parsed.data;
  const problems: string[] = [];
  if (value.AUTH_BYPASS && value.K_SERVICE)
    problems.push(
      "AUTH_BYPASS is for local runs only and is refused on Cloud Run.",
    );
  const publicUrl = new URL(value.PUBLIC_URL);
  if (
    !value.AUTH_BYPASS &&
    publicUrl.protocol !== "https:" &&
    !LOOPBACK.has(publicUrl.hostname)
  )
    problems.push("PUBLIC_URL must use https unless it is a loopback address.");
  if (!value.AUTH_BYPASS) {
    if (!value.GOOGLE_CLIENT_ID || !value.GOOGLE_CLIENT_SECRET)
      problems.push("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.");
    if (!value.SESSION_SECRET || value.SESSION_SECRET.length < 32)
      problems.push("SESSION_SECRET must be at least 32 characters.");
    if (!value.ACTOR_HASH_KEY || value.ACTOR_HASH_KEY.length < 16)
      problems.push("ACTOR_HASH_KEY must be at least 16 characters.");
  }
  if (problems.length)
    throw new HostedConfigError(
      `Invalid hosted configuration: ${problems.join(" ")}`,
    );
  const credentials = Object.fromEntries(
    Object.entries(CREDENTIAL_FAMILIES).map(([family, groups]) => [
      family,
      groups.every((names) => names.some((name) => env[name]?.trim())),
    ]),
  );
  return {
    port: value.PORT,
    host: value.HOST,
    publicUrl: value.PUBLIC_URL,
    issuerUrl: value.ISSUER_URL ?? value.PUBLIC_URL,
    downloadBaseUrl: value.DOWNLOAD_BASE_URL ?? value.PUBLIC_URL,
    authBypass: value.AUTH_BYPASS,
    ...(value.GOOGLE_CLIENT_ID && value.GOOGLE_CLIENT_SECRET
      ? {
          google: {
            clientId: value.GOOGLE_CLIENT_ID,
            clientSecret: value.GOOGLE_CLIENT_SECRET,
          },
        }
      : {}),
    ...(value.SESSION_SECRET ? { sessionSecret: value.SESSION_SECRET } : {}),
    ...(value.ACTOR_HASH_KEY ? { actorHashKey: value.ACTOR_HASH_KEY } : {}),
    termsVersion: value.TERMS_VERSION,
    stateBackend:
      value.STATE_BACKEND ?? (value.AUTH_BYPASS ? "memory" : "firestore"),
    firestore: {
      ...(value.GCP_PROJECT ? { projectId: value.GCP_PROJECT } : {}),
      database: value.FIRESTORE_DATABASE,
      ...(value.FIRESTORE_EMULATOR_HOST
        ? { emulatorHost: value.FIRESTORE_EMULATOR_HOST }
        : {}),
    },
    limits: {
      adminEmails: new Set(value.ADMIN_EMAILS.map((e) => e.toLowerCase())),
      mbPerMinute: value.MB_PER_MINUTE,
      mbPerDay: value.MB_PER_DAY,
      adminMbPerMinute: value.ADMIN_MB_PER_MINUTE,
      adminMbPerDay: value.ADMIN_MB_PER_DAY,
      minChargeBytes: value.MIN_CHARGE_BYTES,
    },
    hiddenTools: value.HIDDEN_TOOLS.split(",")
      .map((name) => name.trim())
      .filter(Boolean),
    corpora: {
      ...(value.CORPORA_MANIFEST_URI
        ? { manifestUri: value.CORPORA_MANIFEST_URI }
        : {}),
      cacheDir: value.CORPORA_CACHE_DIR,
    },
    credentials,
  };
}
