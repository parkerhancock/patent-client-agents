import { expect, test } from "bun:test";
import { OfficeActionAnalyticsClient } from "../packages/client/src/office-action-analytics.js";
import {
  OfficeActionsClient,
  STUB_OFFICE_ACTION_FIELDS,
} from "../packages/client/src/office-actions.js";
import {
  officeActionFeatureRecordings,
  officeActionRecording,
} from "./office-action-recordings.js";

test("all current office action operations and four legacy datasets replay real bounded responses", async () => {
  const results = await officeActionFeatureRecordings("none");
  expect(results).toHaveLength(15);
  expect(results.filter((result) => !result.verified)).toEqual([]);
  expect(
    results.find((result) => result.name === "office-actions-text")?.bytes,
  ).toBeGreaterThan(500);
  for (const result of results.filter((result) =>
    result.name.includes("export"),
  )) {
    expect(result.bytes).toBeGreaterThan(0);
    expect(result.count).toBe(1);
  }
  for (const result of results.filter(
    (result) =>
      result.name.endsWith("-records") || result.name.endsWith("-fields"),
  ))
    expect(result.count).toBeGreaterThan(0);
  for (const result of results.filter((result) =>
    result.name.endsWith("-records"),
  ))
    expect(result.returned).toBe(1);
});

test("real export failures document search-field projection drift instead of hiding rejected fields", async () => {
  // These are deliberately retained negative recordings from the pre-fix client.
  const search = await officeActionRecording(
    "office-actions-get-search",
    "none",
    (options) =>
      new OfficeActionsClient(options).search({
        method: "GET",
        query: "documentCode:CTNF",
        limit: 1,
      }),
  );
  const id = search.officeActionDataBag[0]?.officeActionRecordIdentifier;
  if (!id) throw new Error("Missing recorded office action identifier");
  for (const method of ["GET", "POST"] as const)
    for (const format of ["csv", "json"] as const)
      await expect(
        officeActionRecording(
          `office-actions-export-${method.toLowerCase()}-${format}-invalid-default-fields`,
          "none",
          (options) =>
            new OfficeActionsClient(options).download({
              method,
              format,
              query: `officeActionRecordIdentifier:${id}`,
              fields: [...STUB_OFFICE_ACTION_FIELDS],
              limit: 1,
            }),
        ),
      ).rejects.toMatchObject({ status: 400 });
});

// Form body matching must fail on drift rather than replaying an unrelated query.
test("legacy record cassettes reject changed Solr criteria and pagination", async () => {
  for (const [criteria, rows] of [
    ["id:changed", 1],
    ["*:*", 2],
  ] as const)
    await expect(
      officeActionRecording(
        "office-action-analytics-text-records",
        "none",
        (options) =>
          new OfficeActionAnalyticsClient(options).search("text", criteria, {
            rows,
          }),
      ),
    ).rejects.toMatchObject({ code: "NETWORK_ERROR" });
});
