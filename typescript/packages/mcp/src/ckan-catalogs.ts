import type {
  CkanCatalogClient,
  CkanDataset,
  CkanResource,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailEnvelope,
  detailToolOptions,
  listEnvelope,
  listToolOptions,
} from "./shared.js";

/** Python's resource projection, under the id key each tool family uses. */
function project(resource: CkanResource, idKey: string) {
  return {
    [idKey]: resource.id,
    name: resource.name ?? null,
    description: resource.description ?? null,
    format: resource.format ?? null,
    mimetype: resource.mimetype ?? null,
    size_bytes: resource.size ?? null,
    last_modified: resource.last_modified ?? null,
    download_url: resource.url ?? null,
  };
}
const licence = (dataset: CkanDataset) =>
  dataset.license_title ?? dataset.license_id ?? "unknown licence";

interface Family {
  label: string;
  listTool: string;
  downloadTool: string;
  idKey: string;
  listDescription: string;
  downloadDescription: string;
  datasetDescription: string;
}

/** A catalog's two Python tools: list a dataset's resources, and resolve one to its download URL. */
function registerCatalog(
  server: FastMCP,
  client: CkanCatalogClient,
  family: Family,
  auth?: AuthCheck,
) {
  const datasetId = z
    .string()
    .regex(/^[A-Za-z0-9_-]{1,100}$/)
    .default(client.catalog.defaultDatasetId)
    .describe(family.datasetDescription);
  server.tool(
    {
      ...listToolOptions(auth),
      name: family.listTool,
      description: family.listDescription,
      input: z.object({ dataset_id: datasetId }),
    },
    async ({ dataset_id }) => {
      const { data, provenance } = await client.getDataset(dataset_id);
      const items = data.resources.map((r) => project(r, family.idKey));
      return listEnvelope(
        `${family.label} — \`${dataset_id}\` (${licence(data)}): ${items.length} downloadable resource(s).`,
        items,
        provenance,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: family.downloadTool,
      description: family.downloadDescription,
      input: z.object({
        [family.idKey]: z
          .string()
          .trim()
          .min(1)
          .max(100)
          .describe(`CKAN resource id from ${family.listTool}.`),
        dataset_id: datasetId.describe("Parent dataset id."),
      }),
    },
    async (input: Record<string, string>) => {
      const id = input[family.idKey] as string;
      const dataset = input.dataset_id as string;
      const {
        data,
        dataset: parent,
        provenance,
      } = await client.getResource(id, dataset);
      const size =
        typeof data.size === "number"
          ? ` (${(data.size / 1_000_000).toLocaleString("en-US", { maximumFractionDigits: 1 })} MB)`
          : "";
      return detailEnvelope(
        `${family.label} — ${data.name ?? id}${size}: fetch download_url directly; it is public and unauthenticated.`,
        {
          ...project(data, family.idKey),
          dataset_id: dataset,
          license: parent.license_title ?? parent.license_id ?? null,
        },
        provenance,
      );
    },
  );
}

/** list_ilpo_tm_releases and download_ilpo_tm. */
export function registerIlpoTmTools(
  server: FastMCP,
  client: CkanCatalogClient,
  auth?: AuthCheck,
) {
  registerCatalog(
    server,
    client,
    {
      label: "ILPO Israel TM feed",
      listTool: "list_ilpo_tm_releases",
      downloadTool: "download_ilpo_tm",
      idKey: "resource_id",
      datasetDescription:
        "data.gov.il CKAN dataset id. Defaults to 'simaneymisahr' (the ILPO trade-mark register). 'trademarks_nice' holds the Nice and Vienna classification tables.",
      listDescription:
        "List downloadable ILPO Israel trade-mark releases on data.gov.il.\n\nEach item carries the CKAN resource id (use it as `resource_id` in `download_ilpo_tm`), the name, the file format and size, the last-modified timestamp, and the data.gov.il download URL. The register dataset holds the trade-mark database plus priority claims, change log, holders and licensees, marks based on foreign registrations, and conditions or disclaimers, each a CSV refreshed daily.\n\nRelated tools: download_ilpo_tm, search_ilpo_statutes.",
      downloadDescription:
        "Resolve an ILPO Israel TM release id to a direct data.gov.il download URL.\n\nReturns the upstream URL plus the resource metadata (format, size, last-modified) and the dataset licence. The URL is public and unauthenticated — fetch it with any HTTP client; the bytes are not proxied because the register CSV is about 390 MB.\n\nRelated tools: list_ilpo_tm_releases.",
    },
    auth,
  );
}
/** list_ipa_bulk_releases and download_ipa_bulk. */
export function registerIpaBulkTools(
  server: FastMCP,
  client: CkanCatalogClient,
  auth?: AuthCheck,
) {
  registerCatalog(
    server,
    client,
    {
      label: "IP Australia bulk",
      listTool: "list_ipa_bulk_releases",
      downloadTool: "download_ipa_bulk",
      idKey: "release_id",
      datasetDescription:
        "data.gov.au CKAN dataset id. Defaults to 'iprapid' (the weekly snapshot). Pass an alternate id (e.g. an annual 'ipgod' release) to enumerate that dataset's resources instead.",
      listDescription:
        "List downloadable IP RAPID (Australian bulk IP register) releases on data.gov.au.\n\nEach item carries the CKAN resource id (use it as `release_id` in `download_ipa_bulk`), the name, the file format and size, the last-modified timestamp, and the data.gov.au download URL. IP RAPID is currently two resources: the data dictionary PDF and the full ~1.35 GB CSV zip of patents, trade marks, designs and plant breeder's rights, refreshed weekly (CC BY 4.0).\n\nRelated tools: download_ipa_bulk.",
      downloadDescription:
        "Resolve an IP RAPID release id to a direct data.gov.au download URL.\n\nReturns the upstream URL plus the resource metadata (format, size, last-modified) and the dataset licence. The URL is public and unauthenticated — fetch it with any HTTP client; the ~1.35 GB zip is not proxied.\n\nRelated tools: list_ipa_bulk_releases.",
    },
    auth,
  );
}
