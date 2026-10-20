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
    ...manifest.additional_current_specs,
    ...manifest.current_companion_specs,
  ]) {
    const bytes = await readFile(resolve(directory, receipt.archive));
    expect(createHash("sha256").update(bytes).digest("hex")).toBe(
      receipt.sha256,
    );
    if (receipt.info_version !== undefined)
      expect(specification(bytes.toString()).info.version).toBe(
        receipt.info_version,
      );
  }
  expect(manifest.current_portal_release).toBe("5.0");
  expect(manifest.current_companion_specs).toHaveLength(7);
  expect(manifest.current_schema_bundle_archived).toBe(true);
  // All files are archived; two upstream main-index pointers remain dangling.
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

test("all archived original schema references resolve except the two recorded upstream defects", async () => {
  const manifest = JSON.parse(
    await readFile(resolve(directory, "sources.json"), "utf8"),
  );
  const receipts = [
    manifest.current_main_spec,
    manifest.current_office_actions_spec,
    ...manifest.additional_current_specs,
    ...manifest.current_companion_specs,
  ] as { archive: string }[];
  const documents = new Map<string, unknown>();
  for (const receipt of receipts)
    documents.set(
      receipt.archive.replace("-2026-10-20", ""),
      Bun.YAML.parse(
        await readFile(resolve(directory, receipt.archive), "utf8"),
      ),
    );
  expect(documents.size).toBe(15);
  const unresolved: string[] = [];
  let referenceCount = 0;
  function walk(value: unknown, filename: string) {
    if (!value || typeof value !== "object") return;
    for (const [key, item] of Object.entries(value)) {
      if (key !== "$ref" || typeof item !== "string") {
        walk(item, filename);
        continue;
      }
      referenceCount++;
      const [targetFile, fragment = ""] = item.split("#");
      const targetName = targetFile
        ? targetFile.replace(/^\.\//, "")
        : filename;
      expect(documents.has(targetName)).toBe(true);
      let target: unknown = documents.get(targetName);
      for (const part of fragment.split("/").slice(1)) {
        const decoded = part.replaceAll("~1", "/").replaceAll("~0", "~");
        target =
          target && typeof target === "object"
            ? (target as Record<string, unknown>)[decoded]
            : undefined;
      }
      if (target === undefined) unresolved.push(`${filename}: ${item}`);
    }
  }
  for (const [filename, document] of documents) walk(document, filename);
  expect(referenceCount).toBe(1039);
  expect(unresolved.sort()).toEqual([
    "swagger.yaml: ./odp-common-base.yaml#/components/schemas/PetitionDecisionIdentifierResponseBag",
    "swagger.yaml: ./odp-common-base.yaml#/components/schemas/PetitionDecisionResponseBag",
  ]);
  expect(manifest.current_schema_bundle_resolved).toBe(false);
});
