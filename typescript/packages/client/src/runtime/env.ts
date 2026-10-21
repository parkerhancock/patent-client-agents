/** Web-standard helpers so the client runs in Bun, Node, Deno and browsers. */

/** An environment variable where the runtime has one; always undefined in browsers. */
export function env(name: string): string | undefined {
  const process = (
    globalThis as { process?: { env?: Record<string, string | undefined> } }
  ).process;
  return process?.env?.[name];
}
const encoder = new TextEncoder();
/** UTF-8 byte length of a string. */
export function byteLength(text: string): number {
  return encoder.encode(text).byteLength;
}
/** Base64 of raw bytes. */
export function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000)
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}
/** Base64 of a string's UTF-8 bytes. */
export function textToBase64(text: string): string {
  return bytesToBase64(encoder.encode(text));
}
/** Lowercase hex SHA-256 using Web Crypto. */
export async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    bytes as Uint8Array<ArrayBuffer>,
  );
  return Array.from(new Uint8Array(digest), (b) =>
    b.toString(16).padStart(2, "0"),
  ).join("");
}
