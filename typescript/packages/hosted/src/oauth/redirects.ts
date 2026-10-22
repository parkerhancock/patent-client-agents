/**
 * Redirect URI patterns MCP clients may register, and the matcher. Ported
 * from mcp_data_core's _DEFAULT_MCP_REDIRECT_URIS and FastMCP's
 * redirect_validation.matches_allowed_pattern.
 */
export const DEFAULT_REDIRECT_PATTERNS = [
  "https://claude.ai/*",
  "https://*.anthropic.com/*",
  // Claude Desktop's Code tab.
  "claude://claude.ai/mcp-auth-callback/sdk",
  // ChatGPT connectors and Apps SDK.
  "https://chatgpt.com/*",
  "https://chat.openai.com/*",
  // RFC 8252 loopback redirects from native clients such as Claude Code.
  "http://localhost:*",
  "http://127.0.0.1:*",
] as const;

const LOOPBACK = new Set(["localhost", "127.0.0.1", "::1"]);

interface Parts {
  scheme: string;
  userinfo: boolean;
  host: string;
  port: string | undefined;
  path: string;
}

/** Split without WHATWG URL normalization, which would drop "*" ports and rewrite custom schemes. */
function split(value: string): Parts | undefined {
  const match = /^([A-Za-z][A-Za-z0-9+.-]*):\/\/([^/?#]*)([^?#]*)/.exec(value);
  if (!match) return undefined;
  const [, scheme = "", authority = "", path = ""] = match;
  const at = authority.lastIndexOf("@");
  const hostPort = at >= 0 ? authority.slice(at + 1) : authority;
  let host = hostPort;
  let port: string | undefined;
  if (hostPort.startsWith("[")) {
    const end = hostPort.indexOf("]");
    host = hostPort.slice(1, end);
    const rest = hostPort.slice(end + 1);
    if (rest.startsWith(":")) port = rest.slice(1);
  } else {
    const colon = hostPort.lastIndexOf(":");
    if (colon >= 0) {
      host = hostPort.slice(0, colon);
      port = hostPort.slice(colon + 1);
    }
  }
  return {
    scheme: scheme.toLowerCase(),
    userinfo: at >= 0,
    host: host.toLowerCase(),
    port: port === "" ? undefined : port,
    path: path || "/",
  };
}

function globToRegExp(glob: string): RegExp {
  const source = glob
    .split("*")
    .map((part) =>
      part
        .split("?")
        .map((piece) => piece.replace(/[.+^${}()|[\]\\]/g, "\\$&"))
        .join("."),
    )
    .join(".*");
  return new RegExp(`^${source}$`, "s");
}

export function matchesRedirectPattern(uri: string, pattern: string): boolean {
  const candidate = split(uri);
  const allowed = split(pattern);
  if (!candidate || !allowed) return false;
  // Reject userinfo: http://localhost@evil.example would otherwise pass.
  if (candidate.userinfo) return false;
  if (candidate.scheme !== allowed.scheme) return false;
  if (allowed.host.startsWith("*.")) {
    const suffix = allowed.host.slice(1);
    if (
      !candidate.host.endsWith(suffix) ||
      candidate.host === allowed.host.slice(2)
    )
      return false;
  } else if (candidate.host !== allowed.host) return false;
  if (!(LOOPBACK.has(allowed.host) && allowed.port === undefined)) {
    if (allowed.port !== "*") {
      const fallback = candidate.scheme === "https" ? "443" : "80";
      if ((candidate.port ?? fallback) !== (allowed.port ?? fallback))
        return false;
    }
  }
  if (allowed.path === "/") return true;
  return globToRegExp(allowed.path).test(candidate.path);
}

export function redirectAllowed(
  uri: string,
  patterns: readonly string[] = DEFAULT_REDIRECT_PATTERNS,
): boolean {
  if (uri.includes("#")) return false;
  return patterns.some((pattern) => matchesRedirectPattern(uri, pattern));
}
