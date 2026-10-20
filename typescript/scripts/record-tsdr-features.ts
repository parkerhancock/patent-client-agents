import { tsdrFeatureRecordings } from "../tests/tsdr-live-recordings.js";

const record = Bun.argv.includes("--record"),
  replay = Bun.argv.includes("--replay");
if (record === replay) throw new Error("Choose --record or --replay.");
let key: string | undefined = record
  ? Bun.env.USPTO_TSDR_API_KEY?.trim() || undefined
  : undefined;
const deployedSecret = Bun.argv.includes("--deployed-secret");
if (deployedSecret && !record)
  throw new Error("--deployed-secret requires --record.");
if (record && !key && !deployedSecret)
  throw new Error(
    "Configure USPTO_TSDR_API_KEY or explicitly select --deployed-secret.",
  );
if (record && !key && deployedSecret) {
  // Capture directly in memory. Never print subprocess output or persist the key.
  const child = Bun.spawn(
    [
      "gcloud",
      "secrets",
      "versions",
      "access",
      "latest",
      "--secret=uspto-tsdr-api-key",
      "--project=patentclient-mcp",
      "--account=parker.d.hancock@gmail.com",
    ],
    { stdout: "pipe", stderr: "pipe" },
  );
  const [output, errorOutput, code] = await Promise.all([
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
    child.exited,
  ]);
  void errorOutput;
  if (code !== 0 || !output.trim() || output.length > 4096)
    throw new Error(
      "Existing TSDR secret access failed; no credential was exposed.",
    );
  key = output.trim();
}
try {
  const outcomes = await tsdrFeatureRecordings(key, (value) =>
    console.log(JSON.stringify(value)),
  );
  if (outcomes.some((value) => !value.verified)) process.exitCode = 1;
} catch {
  console.log(
    JSON.stringify({
      stopped: true,
      reason: "Bounded TSDR recording stopped; inspect safe outcomes above.",
    }),
  );
  process.exitCode = 1;
} finally {
  key = undefined;
}
