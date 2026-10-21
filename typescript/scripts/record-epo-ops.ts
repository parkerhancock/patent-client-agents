import { epoRecording, operations } from "../tests/epo-ops-recordings.js";

/**
 * Record EPO OPS cassettes. Credentials come from EPO_OPS_API_KEY/SECRET or,
 * with --deployed-secret, from the existing Secret Manager entries read into
 * memory only. Never print credentials or raw responses.
 */
const only = Bun.argv.find((value) => value.startsWith("--only="))?.slice(7);
const names = only ? only.split(",") : Object.keys(operations);
for (const name of names)
  if (!operations[name]) throw new Error(`Unknown operation: ${name}`);

async function secret(name: string) {
  const child = Bun.spawn(
    [
      "gcloud",
      "secrets",
      "versions",
      "access",
      "latest",
      `--secret=${name}`,
      "--project=patentclient-mcp",
      "--account=parker.d.hancock@gmail.com",
    ],
    {
      stdout: "pipe",
      stderr: "ignore",
      env: {
        ...process.env,
        CLOUDSDK_BILLING_QUOTA_PROJECT: "patentclient-mcp",
      },
    },
  );
  const [output, code] = await Promise.all([
    new Response(child.stdout).text(),
    child.exited,
  ]);
  if (code !== 0 || !output.trim() || output.length > 4096)
    throw new Error(
      `Secret ${name} was unavailable; no credential was exposed.`,
    );
  return output.trim();
}

let apiKey = Bun.env.EPO_OPS_API_KEY?.trim();
let apiSecret = Bun.env.EPO_OPS_API_SECRET?.trim();
if (Bun.argv.includes("--deployed-secret")) {
  apiKey = await secret("epo-ops-api-key");
  apiSecret = await secret("epo-ops-api-secret");
}
if (!apiKey || !apiSecret)
  throw new Error(
    "Configure EPO_OPS_API_KEY/EPO_OPS_API_SECRET or pass --deployed-secret.",
  );

let failures = 0;
for (const name of names) {
  try {
    const result = await epoRecording(name, { apiKey, apiSecret });
    const data = (result as { data?: unknown }).data ?? result;
    console.log(
      JSON.stringify({
        name,
        verified: true,
        ...(data instanceof Uint8Array
          ? { bytes: data.byteLength }
          : { keys: Object.keys(data ?? {}).slice(0, 8) }),
      }),
    );
  } catch (error) {
    failures++;
    console.log(
      JSON.stringify({
        name,
        verified: false,
        error: error instanceof Error ? error.message : "unknown",
        code: (error as { code?: string }).code,
        status: (error as { status?: number }).status,
      }),
    );
  }
  await Bun.sleep(1500);
}
if (failures) process.exitCode = 1;
