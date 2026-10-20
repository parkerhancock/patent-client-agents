import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import {
  applicationDatasets,
  applicationFeatureRecordings,
} from "./application-recordings.js";

test("real application dataset and PDF/XML/DOCX/granted-claim recordings replay offline", async () => {
  const result = await applicationFeatureRecordings("none");
  expect(Object.keys(result.datasets)).toEqual([...applicationDatasets]);
  for (const dataset of applicationDatasets) {
    expect(result.datasets[dataset]?.count).toBe(1);
    expect(result.datasets[dataset]?.patentFileWrapperDataBag).toBeArray();
  }
  expect(result.status.data.statusCodeBag).toBeArray();
  expect(result.artifacts).toEqual({
    pdf: {
      documentIdentifier: "LAQYXZN3XBLUEX4",
      size: 25164,
      sha256:
        "8c981ea8d799e10c45e774c1c64d5a17364982540031cb398e223252f4be1b4e",
    },
    xml: {
      documentIdentifier: "KDF4GVODRXEAPX5",
      size: 3851,
      sha256:
        "8c02298421d8fa1acd699f287ec7a2bc543cce7a0bf729e81c6a54a187f43197",
    },
    docx: {
      documentIdentifier: "KBAWAOALRXEAPX0",
      size: 21517,
      sha256:
        "d94c4a6f6e96f17ea3d71a00fb9464e7df2289e4db51ffd39cbfaea87bf7de15",
    },
  });
  expect(result.claims?.claims).toHaveLength(32);
  expect(result.claims?.claims?.[0]?.claim_number).toBe(1);
  expect(
    result.claims?.claims?.some((claim) => claim.claim_type === "dependent"),
  ).toBe(true);
});
test("new real application recordings contain no API key or authentication headers", async () => {
  const files = [
    ...applicationDatasets,
    "status-codes",
    "pdf",
    "xml",
    "docx",
    "granted-claims",
  ];
  for (const name of files) {
    const content = await readFile(
      new URL(`./cassettes/odp-application-${name}.yaml`, import.meta.url),
      "utf8",
    );
    expect(content).not.toMatch(
      /(?:^|\n)\s*(?:x-api-key|authorization|cookie|set-cookie):/i,
    );
    if (Bun.env.USPTO_ODP_API_KEY)
      expect(content).not.toContain(Bun.env.USPTO_ODP_API_KEY);
  }
});
