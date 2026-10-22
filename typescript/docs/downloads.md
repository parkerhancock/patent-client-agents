# Document downloads

October 22, 2026. Download tools (file wrappers, PTAB papers, court and
USITC documents, legal-reference PDFs) never return base64. They call
`downloadResult` ([source](../packages/mcp/src/downloads.ts)), which returns
the artifact envelope with either a `download_url` and `expires_at`, or a
`file_path` over stdio.

## Where the bytes go

`createServer({ downloads })` takes `DownloadOptions`. There are three
outcomes:

| Configuration | Result | Survives the process |
| --- | --- | --- |
| Nothing (stdio) | `file_path` in a private temp directory | No |
| `publicBaseUrl` | `download_url` on this server's `/downloads` route: single-use HMAC links (`mode: "signed"`, the default) or bearer-token links bound to the caller (`mode: "authenticated"`); 900 s TTL, 256 MB in-process cap | No |
| `blobStore` | `download_url` from the store, for example a GCS V4 signed URL | Yes, until it expires |

A blob store is any object with one method:

```ts
interface BlobStore {
  put(object: { bytes: Uint8Array; filename: string; contentType: string }):
    Promise<{ url: string; expiresAt: Date }>;
}
```

The download layer sanitizes the filename and content type and rejects empty
documents before calling `put`, then reports `expiresAt` as `expires_at`.
Blob URLs are bearer links, so a blob store cannot be combined with
`mode: "authenticated"`; the server refuses that configuration. Uploads run
concurrently, and `maxBytes` becomes a per-document limit.

The TypeScript server has no MCP-resource route for downloads. Python's
`resource_link` copy, which helps clients like Claude CoWork whose outbound
allowlist blocks external hosts, is not ported, so a client that cannot reach
`storage.googleapis.com` cannot fetch a GCS link.

## GCS

`GcsBlobStore` ([source](../packages/mcp/src/gcs-blob-store.ts), exported as
`@patent-client-agents/mcp/gcs-blob-store`) is server-only and uses `fetch`
with no Google SDK. It mirrors the Python deploy's `blob_store.py`:

- Objects are named `downloads/<uuid>/<filename>` and uploaded with the JSON
  API's multipart upload, with `contentDisposition` set to
  `attachment; filename="…"` (plus an RFC 5987 `filename*` when the name has
  characters that cannot be quoted) and `Cache-Control: private, no-store`.
  The upload uses `ifGenerationMatch=0`, so it only ever creates objects.
- URLs are V4 signed GETs on `https://storage.googleapis.com/<bucket>/<object>`.
  The string to sign goes to the IAM Credentials `signBlob` API, because
  Cloud Run's identity has no private key. With the same key and timestamp
  the URL is byte-identical to `google-cloud-storage`'s
  `generate_signed_url_v4`.
- Credentials follow google-auth's order: `GOOGLE_APPLICATION_CREDENTIALS`,
  then gcloud's `application_default_credentials.json`, then the metadata
  server. Only user ADC (`gcloud auth application-default login`) and the
  metadata server are supported; service-account key files are refused.
  The signer is the metadata server's default service account, or
  `DOWNLOAD_SIGNER_EMAIL`, which local user ADC requires.

`bun packages/mcp/src/cli.ts` reads:

| Variable | Python name also accepted | Default |
| --- | --- | --- |
| `DOWNLOAD_BUCKET` | `LAW_TOOLS_CORE_GCS_BUCKET` | unset (no GCS) |
| `DOWNLOAD_TTL_SECONDS` | `LAW_TOOLS_CORE_DOWNLOAD_TTL_SECONDS` | 86400 (max 604800) |
| `DOWNLOAD_PREFIX` | none | `downloads` |
| `DOWNLOAD_SIGNER_EMAIL` | none | metadata server account |

With a bucket set, HTTP transport no longer needs `MCP_PUBLIC_BASE_URL`. A
hosted app constructs the store itself:

```ts
import { GcsBlobStore, gcsBlobStoreOptionsFromEnv } from "@patent-client-agents/mcp/gcs-blob-store";
const gcs = gcsBlobStoreOptionsFromEnv(process.env);
createServer({ downloads: gcs ? { blobStore: new GcsBlobStore(gcs) } : {} });
```

### IAM and bucket setup

For runtime service account `SA`:

- `roles/iam.serviceAccountTokenCreator` on `SA` itself, granted to `SA`
  (for `signBlob`). A 403 from `signBlob` names this role.
- `roles/storage.objectCreator` on the bucket (upload) and
  `roles/storage.objectViewer` on the bucket (the signed GET is evaluated as
  `SA`). `roles/storage.objectUser` covers both.
- Locally, the user needs `serviceAccountTokenCreator` on the signer account
  and the same bucket roles.

The bucket should use uniform bucket-level access with public access
prevention, and a lifecycle rule that deletes download objects after the TTL:

```json
{ "rule": [{ "action": { "type": "Delete" },
             "condition": { "age": 2, "matchesPrefix": ["downloads/"] } }] }
```

`age` counts whole days, so 2 days covers the 24-hour default TTL. Objects
whose signing failed after upload are removed by the same rule.

### Differences from Python

- Python names objects by a stable resource path and overwrites; TypeScript
  uses a random UUID per call and creates only.
- Python's `read_object` read-through cache tier has no TypeScript
  counterpart.
- When `LAW_TOOLS_CORE_DOWNLOAD_BASE_URL` is set, Python keeps the bytes in
  GCS but still hands out its own HMAC `/downloads` URL so every download
  comes from one host. TypeScript always returns the GCS URL.
- Python accepts a downloaded service-account key for local signing;
  TypeScript always signs through `signBlob`.
- Local single-use links become reusable-until-expiry links on GCS, as in
  Python.
