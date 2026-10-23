// Runs the live facade cases against two deployed servers, the TypeScript
// shadow and the Python demo by default, and records both answers side by
// side. Signs in to each with the loopback OAuth flow (the authorization
// URLs are printed and written to <report>.urls.txt); tokens stay in memory.
// Usage: bun scripts/compare-facade.ts <report.json> [--only=tool,tool]
//   [--ts=<base url>] [--py=<base url>]
import { writeFile } from "node:fs/promises";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { cases, type Found, type Raw } from "./live-facade-cases.js";
import { signIn } from "./oauth-loopback.js";

const arg = (name: string) =>
  Bun.argv.find((a) => a.startsWith(`--${name}=`))?.slice(name.length + 3);
const reportPath = Bun.argv[2];
if (!reportPath || reportPath.startsWith("--"))
  throw new Error(
    "Usage: bun scripts/compare-facade.ts <report.json> [--only=a,b] [--ts=url] [--py=url]",
  );
const only = arg("only")?.split(",");
const servers = {
  ts: arg("ts") ?? "https://patent-mcp-ts-260633614954.us-central1.run.app",
  py: arg("py") ?? "https://mcp.patentclient.com",
};

type Side = keyof typeof servers;
const clients = {} as Record<Side, Client>;
for (const side of ["ts", "py"] as const) {
  const auth = await signIn(servers[side], async (url) => {
    await writeFile(`${reportPath}.urls.txt`, `${side}: ${url}\n`, {
      flag: "a",
    });
    console.log(`Open to sign in to ${side} (${servers[side]}):\n${url}\n`);
  });
  clients[side] = await Client.connect(`${servers[side]}/mcp`, {
    auth,
    versionNegotiation: { mode: "legacy" },
  });
  console.log(`${side}: connected`);
}

type ToolInfo = { name: string; inputSchema?: { properties?: object } };
const tools = {} as Record<Side, ToolInfo[]>;
for (const side of ["ts", "py"] as const)
  tools[side] = (await clients[side].listTools()) as ToolInfo[];
const names = (side: Side) => new Set(tools[side].map((t) => t.name));
const params = (t?: ToolInfo) => Object.keys(t?.inputSchema?.properties ?? {});
const toolDiff = [...new Set([...names("ts"), ...names("py")])]
  .sort()
  .map((name) => {
    const [t, p] = (["ts", "py"] as const).map((s) =>
      tools[s].find((x) => x.name === name),
    );
    const tp = params(t);
    const pp = params(p);
    return {
      name,
      ts: Boolean(t),
      py: Boolean(p),
      params_only_ts: tp.filter((x) => !pp.includes(x)),
      params_only_py: pp.filter((x) => !tp.includes(x)),
    };
  });

// Python returns some values raw; FastMCP wraps non-object results in
// { result }. Unwrap so both sides compare as the envelope or the value.
const body = (raw: Raw) => {
  const s = raw.structuredContent;
  if (s && Object.keys(s).length === 1 && "result" in s)
    return s.result as unknown;
  if (s) return s;
  const text = raw.content?.find((c) => c.type === "text")?.text;
  try {
    return text ? JSON.parse(text) : undefined;
  } catch {
    return text;
  }
};
const listOf = (value: unknown) =>
  Array.isArray(value)
    ? value
    : value && typeof value === "object"
      ? (Object.values(value).find(Array.isArray) as unknown[] | undefined)
      : undefined;
const keysOf = (value: unknown) =>
  value && typeof value === "object" && !Array.isArray(value)
    ? Object.keys(value).sort()
    : [];

async function call(side: Side, tool: string, args: Record<string, unknown>) {
  const started = performance.now();
  let raw: Raw;
  try {
    raw = (await clients[side].callToolRaw(tool, args)) as Raw;
  } catch (error) {
    raw = {
      isError: true,
      content: [
        {
          type: "text",
          text: error instanceof Error ? error.message : String(error),
        },
      ],
    };
  }
  const ms = Math.round(performance.now() - started);
  const ok = !raw.isError;
  const value = ok ? body(raw) : undefined;
  const list = listOf(value);
  const record = value as Record<string, unknown> | undefined;
  return {
    raw,
    ok,
    ms,
    keys: keysOf(value),
    items: list?.length,
    first_item_keys: keysOf(list?.[0]),
    summary:
      typeof record?.summary === "string"
        ? record.summary.slice(0, 240)
        : undefined,
    error: ok
      ? undefined
      : (raw.content?.find((c) => c.type === "text")?.text ?? "").slice(0, 400),
    sample: ok ? JSON.stringify(value).slice(0, 3000) : undefined,
  };
}

const found: Record<Side, Found> = { ts: {}, py: {} };
const results: Record<string, unknown>[] = [];
try {
  for (const entry of cases) {
    if (only && !only.includes(entry.tool) && !only.includes(entry.name))
      continue;
    const sides = {} as Record<
      Side,
      Omit<Awaited<ReturnType<typeof call>>, "raw"> | { skipped: true }
    >;
    for (const side of ["ts", "py"] as const) {
      const args =
        typeof entry.args === "function" ? entry.args(found[side]) : entry.args;
      if (!args) {
        sides[side] = { skipped: true };
        continue;
      }
      const { raw, ...result } = await call(side, entry.tool, args);
      if (result.ok)
        entry.harvest?.(
          (body(raw) ?? {}) as Record<string, unknown>,
          found[side],
        );
      sides[side] = { ...result, ...{ args } };
    }
    const t = sides.ts as { ok?: boolean; items?: number; skipped?: boolean };
    const p = sides.py as { ok?: boolean; items?: number; skipped?: boolean };
    const verdict =
      t.skipped || p.skipped
        ? "skipped"
        : t.ok && p.ok
          ? t.items === p.items
            ? "both ok"
            : "both ok, item counts differ"
          : !t.ok && !p.ok
            ? "both error"
            : t.ok
              ? "python error only"
              : "TS ERROR ONLY";
    results.push({
      name: entry.name,
      tool: entry.tool,
      expect: entry.expect ?? "ok",
      verdict,
      ...sides,
    });
    console.log(
      `${verdict.padEnd(28)} ${entry.name.padEnd(30)} ts ${String((sides.ts as { ms?: number }).ms ?? "-").padStart(6)}ms  py ${String((sides.py as { ms?: number }).ms ?? "-").padStart(6)}ms`,
    );
    await Bun.sleep(800);
  }
} finally {
  for (const client of Object.values(clients)) await client.close();
  await writeFile(
    reportPath,
    JSON.stringify(
      {
        ran_at: new Date().toISOString(),
        servers,
        tools: toolDiff,
        found,
        results,
      },
      null,
      2,
    ),
  );
}
