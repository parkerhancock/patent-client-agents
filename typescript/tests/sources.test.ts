import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const directory = resolve(import.meta.dir, "../references/odp");

interface OpenApi {
  info: { version: string };
  paths: Record<string, Record<string, unknown>>;
}

function specification(text: string): OpenApi {
  return Bun.YAML.parse(text) as OpenApi;
}

test("official OpenAPI snapshots match their provenance receipts", async () => {
  const manifest = JSON.parse(
    await readFile(resolve(directory, "sources.json"), "utf8"),
  );
  for (const receipt of [
    manifest.current_main_spec,
    manifest.current_office_actions_spec,
  ]) {
    const bytes = await readFile(resolve(directory, receipt.archive));
    expect(createHash("sha256").update(bytes).digest("hex")).toBe(
      receipt.sha256,
    );
    expect(specification(bytes.toString()).info.version).toBe(
      receipt.info_version,
    );
  }
  expect(manifest.current_portal_release).toBe("5.0");
  // A current main file is not a resolved bundle of its external schemas.
  expect(manifest.current_schema_bundle_complete).toBe(false);
});

test("initial application routes and the new Office Actions surface exist in the current specifications", async () => {
  const main = specification(
    await readFile(resolve(directory, "swagger-2026-10-20.yaml"), "utf8"),
  );
  const paths = main.paths;
  expect(paths["/api/v1/patent/applications/search"]?.post).toBeDefined();
  expect(
    paths["/api/v1/patent/applications/{applicationNumberText}"]?.get,
  ).toBeDefined();
  const documents = paths[
    "/api/v1/patent/applications/{applicationNumberText}/documents"
  ]?.get as { parameters: { name?: string }[] };
  expect(
    documents.parameters.map((parameter: { name?: string }) => parameter.name),
  ).toContain("documentCodes");
  expect(
    paths[
      "/api/v1/patent/applications/{applicationNumberText}/associated-documents"
    ]?.get,
  ).toBeDefined();
  const actions = specification(
    await readFile(
      resolve(directory, "office-actions-2026-10-20.yaml"),
      "utf8",
    ),
  );
  expect(
    actions.paths["/api/v1/patent/office-action/search"]?.post,
  ).toBeDefined();
  expect(
    actions.paths[
      "/api/v1/patent/office-action/{officeActionRecordIdentifier}/download/officeActionText"
    ]?.get,
  ).toBeDefined();
});
