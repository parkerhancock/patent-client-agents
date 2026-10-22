import { readFileSync } from "node:fs";

/**
 * The Python demo's Jinja templates, copied verbatim into assets/templates,
 * rendered with the small subset they use: `{% extends %}`, named blocks and
 * autoescaped `{{ variable }}` substitution.
 */
const TEMPLATES = new URL("../assets/templates/", import.meta.url);
const STATIC = new URL("../assets/static/", import.meta.url);

const BLOCK = /{%\s*block\s+(\w+)\s*%}([\s\S]*?){%\s*endblock\s*%}/g;
const EXTENDS = /^\s*{%\s*extends\s+"([^"]+)"\s*%}/;
const VARIABLE = /{{\s*(\w+)\s*}}/g;

const cache = new Map<string, string>();

function source(name: string): string {
  let text = cache.get(name);
  if (text === undefined) {
    text = readFileSync(new URL(name, TEMPLATES), "utf8");
    cache.set(name, text);
  }
  return text;
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&#34;")
    .replace(/'/g, "&#39;");
}

export function render(
  name: string,
  context: Record<string, string> = {},
): string {
  let text = source(name);
  const parent = EXTENDS.exec(text)?.[1];
  if (parent) {
    const blocks = new Map<string, string>();
    for (const match of text.matchAll(BLOCK))
      blocks.set(match[1] ?? "", match[2] ?? "");
    text = source(parent).replace(
      BLOCK,
      (_whole, block: string, fallback: string) =>
        blocks.get(block) ?? fallback,
    );
  } else text = text.replace(BLOCK, (_whole, _block, body: string) => body);
  return text.replace(VARIABLE, (_whole, variable: string) => {
    const value = context[variable];
    if (value === undefined)
      throw new Error(`Template ${name} needs ${variable}.`);
    return escapeHtml(value);
  });
}

export function htmlPage(
  name: string,
  context: Record<string, string> = {},
  status = 200,
): Response {
  return new Response(render(name, context), {
    status,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

export function errorPage(status: number, title: string, message: string) {
  return htmlPage(
    "error.html",
    { error_title: title, error_message: message },
    status,
  );
}

const STATIC_FILES: Record<string, string> = {
  "icon.png": "image/png",
  "icon.svg": "image/svg+xml",
  "wordmark.png": "image/png",
};

const staticBytes = new Map<string, Uint8Array<ArrayBuffer>>();

/** Serve a fixed set of files; request paths never reach the filesystem. */
export function staticFile(name: string): Response | undefined {
  const type = STATIC_FILES[name];
  if (!type) return undefined;
  let bytes = staticBytes.get(name);
  if (!bytes) {
    bytes = new Uint8Array(
      readFileSync(new URL(name, STATIC)),
    ) as Uint8Array<ArrayBuffer>;
    staticBytes.set(name, bytes);
  }
  return new Response(bytes, {
    headers: {
      "content-type": type,
      "cache-control": "public, max-age=3600",
    },
  });
}

export const ROBOTS_TXT =
  "User-agent: *\n" +
  "Disallow: /authorize\n" +
  "Disallow: /token\n" +
  "Disallow: /register\n" +
  "Disallow: /consent\n" +
  "Disallow: /auth/\n" +
  "Disallow: /mcp\n";
