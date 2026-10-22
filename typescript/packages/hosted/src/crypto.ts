const encoder = new TextEncoder();

export function base64url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

export function fromBase64url(value: string): Uint8Array<ArrayBuffer> {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let index = 0; index < binary.length; index++)
    bytes[index] = binary.charCodeAt(index);
  return bytes;
}

/** 256 random bits, base64url: identifiers, codes and refresh tokens. */
export function randomToken(): string {
  return base64url(crypto.getRandomValues(new Uint8Array(32)));
}

export async function sha256(value: string): Promise<Uint8Array> {
  return new Uint8Array(
    await crypto.subtle.digest("SHA-256", encoder.encode(value)),
  );
}

export async function sha256Hex(value: string): Promise<string> {
  return Buffer.from(await sha256(value)).toString("hex");
}

/** RFC 7636 S256: BASE64URL(SHA256(ASCII(code_verifier))). */
export async function pkceChallenge(verifier: string): Promise<string> {
  return base64url(await sha256(verifier));
}

export function constantTimeEqual(a: string, b: string): boolean {
  const left = encoder.encode(a);
  const right = encoder.encode(b);
  let difference = left.length ^ right.length;
  for (let index = 0; index < Math.max(left.length, right.length); index++)
    difference |= (left[index] ?? 0) ^ (right[index] ?? 0);
  return difference === 0;
}

/** Derive an independent 256-bit key from SESSION_SECRET for one purpose. */
export async function deriveKey(secret: string, purpose: string) {
  const material = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    "HKDF",
    false,
    ["deriveBits"],
  );
  return new Uint8Array(
    await crypto.subtle.deriveBits(
      {
        name: "HKDF",
        hash: "SHA-256",
        salt: encoder.encode("patent-client-agents/hosted"),
        info: encoder.encode(purpose),
      },
      material,
      256,
    ),
  );
}

/** AES-256-GCM for upstream Google tokens at rest, bound to the record id. */
export class Sealer {
  private constructor(private readonly key: CryptoKey) {}

  static async fromSecret(secret: string): Promise<Sealer> {
    const raw = await deriveKey(secret, "seal/v1");
    return new Sealer(
      await crypto.subtle.importKey("raw", raw, "AES-GCM", false, [
        "encrypt",
        "decrypt",
      ]),
    );
  }

  async seal(value: unknown, context: string): Promise<string> {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ciphertext = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv, additionalData: encoder.encode(context) },
      this.key,
      encoder.encode(JSON.stringify(value)),
    );
    return `v1.${base64url(iv)}.${base64url(new Uint8Array(ciphertext))}`;
  }

  async open<T>(sealed: string, context: string): Promise<T> {
    const [version, iv, ciphertext] = sealed.split(".");
    if (version !== "v1" || !iv || !ciphertext)
      throw new Error("Unsupported sealed value.");
    const plaintext = await crypto.subtle.decrypt(
      {
        name: "AES-GCM",
        iv: fromBase64url(iv),
        additionalData: encoder.encode(context),
      },
      this.key,
      fromBase64url(ciphertext),
    );
    return JSON.parse(new TextDecoder().decode(plaintext)) as T;
  }
}

/**
 * Deployment-scoped pseudonymous actor id: the first 32 hex characters of
 * HMAC-SHA256(ACTOR_HASH_KEY, lowercased email). Identical to the Python
 * observability.pseudonymous_actor_id, so ids line up across both services.
 */
export async function actorId(
  email: string,
  key: string,
): Promise<string | undefined> {
  const normalized = email.trim().toLowerCase();
  if (!key || !normalized || normalized === "unauthenticated") return undefined;
  const hmacKey = await crypto.subtle.importKey(
    "raw",
    encoder.encode(key),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const digest = await crypto.subtle.sign(
    "HMAC",
    hmacKey,
    encoder.encode(normalized),
  );
  return Buffer.from(digest).toString("hex").slice(0, 32);
}
