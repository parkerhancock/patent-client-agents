import {
  createDCtx,
  decompress,
  decompressUsingDict,
  init,
} from "@bokuweb/zstd-wasm";
import { wasmLocations } from "./wasm.js";

let ready: Promise<void> | undefined;
/** libzstd's dstSize_tooSmall error code, as reported by the binding. */
const OUTPUT_TOO_SMALL = /code -70\b/;

export class ZstdOutputTooLarge extends Error {
  override name = "ZstdOutputTooLarge";
}

/** libzstd compiled to WebAssembly: one decoder for every runtime, with dictionary support and checksum verification. */
export async function zstd() {
  ready ??= (() => {
    const { zstd: location } = wasmLocations();
    // The web build's init accepts a wasm URL; the Node typings omit it.
    return location
      ? (init as (path?: string) => Promise<void>)(String(location))
      : init();
  })();
  await ready;
  return {
    /**
     * Decode one frame. A declared content size sizes the output exactly;
     * otherwise the output buffer starts small and doubles up to maxBytes,
     * failing with ZstdOutputTooLarge beyond it.
     */
    decompress(
      bytes: Uint8Array,
      maxBytes: number,
      declaredSize: number | null,
    ) {
      if (declaredSize !== null) return decompress(bytes);
      for (
        let size = Math.min(Math.max(bytes.length * 4, 1024 * 1024), maxBytes);
        ;
        size = Math.min(size * 2, maxBytes)
      ) {
        try {
          return decompress(bytes, { defaultHeapSize: size });
        } catch (error) {
          if (!OUTPUT_TOO_SMALL.test(String(error))) throw error;
          if (size >= maxBytes) throw new ZstdOutputTooLarge();
        }
      }
    },
    decompressWithDictionary: (bytes: Uint8Array, dictionary: Uint8Array) =>
      decompressUsingDict(createDCtx(), bytes, dictionary),
  };
}
