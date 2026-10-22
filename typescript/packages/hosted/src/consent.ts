import { parseCookies, readForm, redirect, serializeCookie } from "./http.js";
import { htmlPage } from "./pages.js";

/**
 * Terms-of-use gate in front of /authorize, ported from the Python
 * consent.py: until the browser holds a cookie for the current terms
 * version, /authorize redirects to /consent, which replays the original
 * request after acceptance. Bumping TERMS_VERSION makes everyone re-accept.
 */
export const TERMS_COOKIE = "pca_terms_accepted";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

/** Same-origin relative paths only, so /consent cannot become an open redirect. */
export function isSafeNext(url: string): boolean {
  if (!url.startsWith("/") || url.startsWith("//") || url.includes("\\"))
    return false;
  try {
    const parsed = new URL(url, "http://placeholder.invalid");
    return parsed.origin === "http://placeholder.invalid";
  } catch {
    return false;
  }
}

/** Returns a redirect to /consent when the caller has not accepted the current terms. */
export function termsGate(
  request: Request,
  termsVersion: string,
): Response | undefined {
  const url = new URL(request.url);
  if (url.pathname !== "/authorize") return undefined;
  if (request.method !== "GET" && request.method !== "HEAD") return undefined;
  if (
    parseCookies(request.headers.get("cookie"))[TERMS_COOKIE] === termsVersion
  )
    return undefined;
  const next = `/authorize${url.search}`;
  return redirect(`/consent?next=${encodeURIComponent(next)}`, 302);
}

export function consentForm(request: Request, termsVersion: string): Response {
  const requested = new URL(request.url).searchParams.get("next") ?? "/";
  return htmlPage("consent.html", {
    next_url: isSafeNext(requested) ? requested : "/",
    terms_version: termsVersion,
  });
}

export async function consentAccept(
  request: Request,
  options: { termsVersion: string; publicUrl: string },
): Promise<Response> {
  // The Python form had no CSRF check. Refuse cross-site posts when the
  // browser says where the form came from.
  const origin = request.headers.get("origin");
  if (
    origin &&
    origin !== "null" &&
    origin !== new URL(options.publicUrl).origin
  )
    return new Response("Forbidden", {
      status: 403,
      headers: { "content-type": "text/plain" },
    });
  const form = await readForm(request);
  const requested = form.get("next") ?? "/";
  const next = isSafeNext(requested) ? requested : "/";
  if (form.get("agree") !== "on")
    return redirect(`/consent?next=${encodeURIComponent(next)}`, 303);
  return redirect(next, 303, {
    "set-cookie": serializeCookie(TERMS_COOKIE, options.termsVersion, {
      maxAge: COOKIE_MAX_AGE,
      secure: options.publicUrl.startsWith("https://"),
      sameSite: "Lax",
    }),
  });
}
