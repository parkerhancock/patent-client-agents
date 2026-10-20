import { randomUUID } from "node:crypto";
import { constants } from "node:fs";
import { lstat, open, rename, unlink } from "node:fs/promises";
import { resolve } from "node:path";
import {
  decodeWafSession,
  encodeWafSession,
  MAX_SESSION_BYTES,
  WafSessionError,
  type WafSessionStore,
} from "./session.js";

export function createFileWafSessionStore(filename: string): WafSessionStore {
  if (process.platform === "win32")
    throw new WafSessionError(
      "Protected WAF session files require POSIX permissions.",
    );
  if (!filename.trim())
    throw new WafSessionError("A WAF session file is required.");
  const path = resolve(filename);
  return {
    async read() {
      try {
        const handle = await open(
          path,
          constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK,
        );
        try {
          const stat = await handle.stat();
          if (
            !stat.isFile() ||
            stat.size > MAX_SESSION_BYTES ||
            (stat.mode & 0o077) !== 0
          )
            throw new Error();
          const buffer = Buffer.alloc(MAX_SESSION_BYTES + 1);
          let length = 0;
          while (length < buffer.byteLength) {
            const { bytesRead } = await handle.read(
              buffer,
              length,
              buffer.byteLength - length,
              null,
            );
            if (!bytesRead) break;
            length += bytesRead;
          }
          return decodeWafSession(buffer.subarray(0, length));
        } finally {
          await handle.close();
        }
      } catch {
        throw new WafSessionError(
          "Unable to read a protected current WAF session file.",
        );
      }
    },
    async write(value, options = {}) {
      const bytes = encodeWafSession(value);
      const temporary = `${path}.${randomUUID()}.tmp`;
      let created = false;
      try {
        options.signal?.throwIfAborted();
        const previous = await lstat(path).catch(
          (error: NodeJS.ErrnoException) => {
            if (error.code === "ENOENT") return undefined;
            throw error;
          },
        );
        if (previous && (!previous.isFile() || previous.isSymbolicLink()))
          throw new Error();
        options.signal?.throwIfAborted();
        const handle = await open(
          temporary,
          constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL,
          0o600,
        );
        created = true;
        try {
          options.signal?.throwIfAborted();
          await handle.chmod(0o600);
          options.signal?.throwIfAborted();
          await handle.writeFile(bytes);
          options.signal?.throwIfAborted();
          await handle.sync();
        } finally {
          await handle.close();
        }
        options.signal?.throwIfAborted();
        await rename(temporary, path);
        created = false;
      } catch {
        throw new WafSessionError(
          "Unable to publish the protected WAF session file.",
        );
      } finally {
        if (created) await unlink(temporary).catch(() => {});
      }
    },
  };
}
