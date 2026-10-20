import { expect, spyOn, test } from "bun:test";
import { access, readFile, unlink, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { DownloadStore } from "../packages/mcp/src/downloads.js";

const provenance = {
  source_url: "https://api.uspto.gov/test",
  source_name: "USPTO Open Data Portal",
  retrieved_at: new Date().toISOString(),
  cache_hit: false as const,
};
const bytes = new TextEncoder().encode("document");
async function put(store: DownloadStore) {
  const result = await store.put(bytes, "file.txt", "text/plain", provenance);
  if (!("file_path" in result)) throw new Error("Expected local file");
  return result.file_path;
}
test("close waits for already accepted writes, removes their files, and is idempotent", async () => {
  const store = new DownloadStore();
  const writing = put(store);
  const closing = store.close();
  const path = await writing;
  await closing;
  await expect(access(path)).rejects.toMatchObject({ code: "ENOENT" });
  await expect(access(dirname(path))).rejects.toMatchObject({ code: "ENOENT" });
  await store.close();
  await expect(put(store)).rejects.toThrow("closed");
});
test("concurrent writes enforce capacity before publishing excess files", async () => {
  const store = new DownloadStore({ maxBytes: bytes.length });
  try {
    const results = await Promise.allSettled([
      put(store),
      put(store),
      put(store),
    ]);
    expect(
      results.filter((result) => result.status === "fulfilled"),
    ).toHaveLength(1);
    expect(
      results.filter((result) => result.status === "rejected"),
    ).toHaveLength(2);
    const success = results.find((result) => result.status === "fulfilled");
    if (success?.status !== "fulfilled")
      throw new Error("Expected successful write");
    expect(new Uint8Array(await readFile(success.value))).toEqual(bytes);
  } finally {
    await store.close();
  }
});
test("periodic cleanup removes expired files while the store is idle", async () => {
  const store = new DownloadStore({ ttlSeconds: 1 });
  const path = await put(store);
  const time = Date.now();
  const clock = spyOn(Date, "now").mockReturnValue(time + 2000);
  try {
    await new Promise((resolve) => setTimeout(resolve, 1150));
    await expect(access(path)).rejects.toMatchObject({ code: "ENOENT" });
  } finally {
    clock.mockRestore();
    await store.close();
  }
});
test("close preserves unowned files and can retry after the directory is empty", async () => {
  const store = new DownloadStore();
  const owned = await put(store);
  const foreign = join(dirname(owned), "created-by-the-test.txt");
  await writeFile(foreign, "preserve me");
  try {
    await expect(store.close()).rejects.toMatchObject({ code: "ENOTEMPTY" });
    expect(await readFile(foreign, "utf8")).toBe("preserve me");
    await expect(access(owned)).rejects.toMatchObject({ code: "ENOENT" });
  } finally {
    await unlink(foreign);
    await store.close();
  }
});
