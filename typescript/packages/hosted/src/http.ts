/** Small HTTP helpers shared by the hosted routes. */

/** The fetch signature the hosted code calls; narrower than Bun's `typeof fetch`. */
export type FetchLike = (
  input: string | URL | Request,
  init?: RequestInit,
) => Promise<Response>;

export function parseCookies(header: string | null): Record<string, string> {
  const cookies: Record<string, string> = {};
  for (const part of (header ?? "").split(";")) {
    const index = part.indexOf("=");
    if (index < 0) continue;
    const name = part.slice(0, index).trim();
    let value = part.slice(index + 1).trim();
    if (value.startsWith('"') && value.endsWith('"'))
      value = value.slice(1, -1);
    if (!name || name in cookies) continue;
    try {
      cookies[name] = decodeURIComponent(value);
    } catch {
      cookies[name] = value;
    }
  }
  return cookies;
}

export interface CookieOptions {
  maxAge: number;
  path?: string;
  secure: boolean;
  httpOnly?: boolean;
  sameSite?: "Lax" | "Strict" | "None";
}

export function serializeCookie(
  name: string,
  value: string,
  options: CookieOptions,
): string {
  return [
    `${name}=${encodeURIComponent(value)}`,
    `Max-Age=${options.maxAge}`,
    `Path=${options.path ?? "/"}`,
    `SameSite=${options.sameSite ?? "Lax"}`,
    ...(options.httpOnly === false ? [] : ["HttpOnly"]),
    ...(options.secure ? ["Secure"] : []),
  ].join("; ");
}

export function json(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

export function redirect(
  location: string,
  status = 302,
  headers: HeadersInit = {},
): Response {
  const result = new Headers(headers);
  result.set("location", location);
  return new Response(null, { status, headers: result });
}

/** Read a request body with a byte limit. */
export async function readBody(
  request: Request,
  limit: number,
): Promise<string> {
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (declared > limit) throw new BodyTooLarge();
  const text = await request.text();
  if (new TextEncoder().encode(text).length > limit) throw new BodyTooLarge();
  return text;
}

export class BodyTooLarge extends Error {
  override name = "BodyTooLarge";
}

/** application/x-www-form-urlencoded body, or empty when the type differs. */
export async function readForm(
  request: Request,
  limit = 64 * 1024,
): Promise<URLSearchParams> {
  const type = request.headers.get("content-type") ?? "";
  const text = await readBody(request, limit);
  if (!type.toLowerCase().startsWith("application/x-www-form-urlencoded"))
    return new URLSearchParams();
  return new URLSearchParams(text);
}
