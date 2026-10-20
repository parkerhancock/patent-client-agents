import { createHash } from "node:crypto";
import { readFile, stat } from "node:fs/promises";
import { MpepClient } from "@patent-client-agents/client";
import { Client } from "@prefecthq/fastmcp-ts/client";
import { createServer } from "../packages/mcp/src/index.js";

let stage = "configuration";
let verified = false;
let artifact: string | undefined;
try {
  const args = Bun.argv.slice(2);
  if (
    args.length !== 4 ||
    args[0] !== "--corpus" ||
    args[2] !== "--sha256" ||
    !args[1] ||
    !/^[a-f\d]{64}$/i.test(args[3] ?? "")
  )
    throw new Error();
  const corpusPath = args[1];
  const expectedSha256 = args[3] as string;
  const library = new MpepClient({ corpusPath, expectedSha256 });
  let contentHash: string;
  let version: string;
  try {
    stage = "corpus";
    const status = await library.getCorpusStatus();
    if (!status.available || status.artifact_sha256 !== expectedSha256)
      throw new Error();
    version = status.corpus_version;
    stage = "library";
    const result = await library.search({ query: "patent", limit: 1 });
    const section = await library.getSection("2106");
    if (result.hits.length !== 1 || !section.text.length) throw new Error();
    contentHash = section.content_sha256;
  } finally {
    library.close();
  }
  // Exercise default server wiring rather than an injected corpus client.
  process.env.MPEP_CORPUS_PATH = corpusPath;
  process.env.MPEP_CORPUS_SHA256 = expectedSha256;
  const server = createServer();
  try {
    stage = "mcp";
    const client = await Client.connect(server, {
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const search = await client.callTool<{ items: unknown[] }>(
        "search_mpep",
        {
          query: "patent",
          limit: 1,
        },
      );
      if (search.structuredContent?.items.length !== 1) throw new Error();
      const result = await client.callTool<{
        items: { document: { file_path: string } }[];
      }>("get_mpep_section", { section: "2106", format: "html" });
      artifact = result.structuredContent?.items[0]?.document.file_path;
      if (!artifact) throw new Error();
      const actual = createHash("sha256")
        .update(await readFile(artifact))
        .digest("hex");
      if (actual !== contentHash) throw new Error();
    } finally {
      await client.close();
    }
  } finally {
    await server.close();
  }
  stage = "cleanup";
  if (!artifact) throw new Error();
  const retained = await stat(artifact).catch(
    (error: NodeJS.ErrnoException) => {
      if (error.code === "ENOENT") return undefined;
      throw error;
    },
  );
  if (retained) throw new Error();
  verified = true;
  console.log(
    JSON.stringify({
      verified,
      stage,
      corpus_version: version,
      section_html_sha256: contentHash,
    }),
  );
} catch {
  console.error(JSON.stringify({ verified, stage }));
  process.exitCode = 1;
}
