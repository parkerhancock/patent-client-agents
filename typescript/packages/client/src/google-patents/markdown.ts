import { parseDocument } from "./dom.js";

/**
 * Google Patents description HTML to Markdown.
 *
 * A port of the Python `google_patents/markdown.py`, which runs markdownify
 * 1.2.2 with markitdown 0.1.5's overrides (ATX headings, links to non-web
 * schemes reduced to text, escaped link paths, truncated data-URI images,
 * checkbox inputs), then strips trailing spaces per line and collapses runs
 * of blank lines. The converter below mirrors markdownify's tree walk:
 * whitespace handling around block elements, newline collapsing between
 * children, `*`/`_` escaping, and its table, list and definition-list rules.
 * markitdown's heading override never runs under markdownify 1.2.2 (it is
 * named `convert_hn`), so headings use markdownify's own rule here too.
 */

interface Node {
  kind: "document" | "element" | "text" | "other";
  name: string;
  value: string;
  attrs: Record<string, string>;
  children: Node[];
  parent: Node | null;
  index: number;
}

/** Copy the linkedom tree into a bs4-like tree with parent and sibling links. */
function toTree(root: globalThis.Node, parent: Node | null): Node {
  const element = root.nodeType === 1 ? (root as Element) : null;
  const node: Node = {
    kind:
      root.nodeType === 9
        ? "document"
        : element
          ? "element"
          : root.nodeType === 3
            ? "text"
            : "other",
    name: element ? element.localName.toLowerCase() : "",
    value: root.nodeType === 3 ? (root.textContent ?? "") : "",
    attrs: element
      ? Object.fromEntries(
          Array.from(element.attributes).map((a) => [a.name, a.value]),
        )
      : {},
    children: [],
    parent,
    index: 0,
  };
  const children =
    element?.localName === "template"
      ? Array.from((element as HTMLTemplateElement).content?.childNodes ?? [])
      : Array.from(root.childNodes);
  node.children = children.map((child) => toTree(child, node));
  node.children.forEach((child, index) => {
    child.index = index;
  });
  return node;
}
const prev = (n: Node) =>
  n.parent && n.index > 0 ? (n.parent.children[n.index - 1] ?? null) : null;
const next = (n: Node) => n.parent?.children[n.index + 1] ?? null;
function findParent(n: Node, name: string) {
  for (let p = n.parent; p; p = p.parent) if (p.name === name) return p;
  return null;
}
function findAll(n: Node, names: string[]): Node[] {
  return n.children.flatMap((c) =>
    c.kind === "element"
      ? [...(names.includes(c.name) ? [c] : []), ...findAll(c, names)]
      : [],
  );
}
const isTag = (n: Node | null): n is Node => n?.kind === "element";

const HEADING = /^h(\d+)/;
const BLOCK_INSIDE = new Set([
  "p",
  "blockquote",
  "article",
  "div",
  "section",
  "ol",
  "ul",
  "li",
  "dl",
  "dt",
  "dd",
  "table",
  "thead",
  "tbody",
  "tfoot",
  "tr",
  "td",
  "th",
]);
function removeInside(n: Node | null) {
  if (!isTag(n)) return false;
  return HEADING.test(n.name) || BLOCK_INSIDE.has(n.name);
}
const removeOutside = (n: Node | null) =>
  removeInside(n) || (isTag(n) && n.name === "pre");
function isBlockContent(n: Node | null) {
  if (!n) return false;
  if (n.kind === "element") return true;
  if (n.kind === "text") return pyStrip(n.value) !== "";
  return false;
}
function nextBlockContentSibling(n: Node): Node | null {
  for (let s = next(n); s; s = next(s)) if (isBlockContent(s)) return s;
  return null;
}

// Python str.strip()/rstrip()/lstrip() with no argument strip Unicode whitespace.
const PY_WS = "\\s\\u001c-\\u001f\\u0085";
const pyStrip = (s: string) =>
  s.replace(new RegExp(`^[${PY_WS}]+|[${PY_WS}]+$`, "g"), "");
const pyRstrip = (s: string) => s.replace(new RegExp(`[${PY_WS}]+$`), "");
const stripChars = (s: string, chars: string, side: "both" | "l" | "r") => {
  let start = 0;
  let end = s.length;
  if (side !== "r")
    while (start < end && chars.includes(s[start] ?? "")) start++;
  if (side !== "l")
    while (end > start && chars.includes(s[end - 1] ?? "")) end--;
  return s.slice(start, end);
};
const WS = " \t\r\n";
const reAllWhitespace = /[\t \r\n]+/g;

function chomp(text: string): [string, string, string] {
  const prefix = text.startsWith(" ") ? " " : "";
  const suffix = text.endsWith(" ") ? " " : "";
  return [prefix, suffix, pyStrip(text)];
}
function inline(markup: string) {
  return (_n: Node, text: string, parents: Set<string>) => {
    if (parents.has("_noformat")) return text;
    const [prefix, suffix, body] = chomp(text);
    if (!body) return "";
    return `${prefix}${markup}${body}${markup}${suffix}`;
  };
}
/** Prefix every line that has content, like markdownify's re_line_with_content. */
const indentLines = (text: string, indent: string) =>
  text
    .split("\n")
    .map((line) => (line ? indent + line : ""))
    .join("\n");

/** Python urllib quote(unquote(path)) with the default safe='/'. */
function quotePath(path: string): string {
  let decoded: string;
  try {
    decoded = decodeURIComponent(path);
  } catch {
    decoded = path;
  }
  return Array.from(new TextEncoder().encode(decoded), (byte) => {
    const ch = String.fromCharCode(byte);
    return /[A-Za-z0-9_.\-~/]/.test(ch)
      ? ch
      : `%${byte.toString(16).toUpperCase().padStart(2, "0")}`;
  }).join("");
}
/** Python urlparse/urlunparse with the path re-quoted; null where urlparse would raise. */
function escapeHref(href: string): { scheme: string; href: string } | null {
  const scheme = /^([A-Za-z][A-Za-z0-9+.-]*):/.exec(href);
  let rest = href;
  let schemeName = "";
  if (scheme?.[1]) {
    schemeName = scheme[1].toLowerCase();
    rest = href.slice(scheme[0].length);
  }
  let netloc = "";
  if (rest.startsWith("//")) {
    const end = rest.slice(2).search(/[/?#]/);
    netloc = end < 0 ? rest.slice(2) : rest.slice(2, 2 + end);
    rest = end < 0 ? "" : rest.slice(2 + end);
    if (
      (netloc.includes("[") && !netloc.includes("]")) ||
      (netloc.includes("]") && !netloc.includes("["))
    )
      return null;
  }
  let fragment = "";
  const hash = rest.indexOf("#");
  if (hash >= 0) {
    fragment = rest.slice(hash + 1);
    rest = rest.slice(0, hash);
  }
  let query = "";
  const q = rest.indexOf("?");
  if (q >= 0) {
    query = rest.slice(q + 1);
    rest = rest.slice(0, q);
  }
  let params = "";
  const lastSlash = rest.lastIndexOf("/");
  const semi = rest.indexOf(";", lastSlash < 0 ? 0 : lastSlash);
  if (semi >= 0) {
    params = rest.slice(semi + 1);
    rest = rest.slice(0, semi);
  }
  let path = quotePath(rest);
  if (params) path = `${path};${params}`;
  let url = path;
  if (
    netloc ||
    (schemeName &&
      ["http", "https", "file", "ftp"].includes(schemeName) &&
      path.startsWith("/"))
  ) {
    if (path && !path.startsWith("/")) path = `/${path}`;
    url = `//${netloc}${path}`;
  }
  if (schemeName) url = `${schemeName}:${url}`;
  if (query) url = `${url}?${query}`;
  if (fragment) url = `${url}#${fragment}`;
  return { scheme: schemeName, href: url };
}

type Convert = (node: Node, text: string, parents: Set<string>) => string;

const convertDiv: Convert = (_n, text, parents) => {
  if (parents.has("_inline")) return ` ${pyStrip(text)} `;
  const body = pyStrip(text);
  return body ? `\n\n${body}\n\n` : "";
};
const convertList: Convert = (node, text, parents) => {
  const sibling = nextBlockContentSibling(node);
  const beforeParagraph = Boolean(
    sibling && !["ul", "ol"].includes(sibling.name),
  );
  if (parents.has("li")) return `\n${pyRstrip(text)}`;
  return `\n\n${text}${beforeParagraph ? "\n" : ""}`;
};
const colspan = (cell: Node) => {
  const value = cell.attrs.colspan;
  return value && /^\d+$/.test(value)
    ? Math.max(1, Math.min(1000, Number(value)))
    : 1;
};
const convertCell: Convert = (node, text) =>
  ` ${pyStrip(text).replaceAll("\n", " ")}${" |".repeat(colspan(node))}`;
const convertCode: Convert = (_n, text, parents) => {
  if (parents.has("_noformat")) return text;
  const [prefix, suffix, body] = chomp(text);
  if (!body) return "";
  const longest = Math.max(
    0,
    ...(body.match(/`+/g) ?? []).map((run) => run.length),
  );
  const fence = "`".repeat(longest + 1);
  const inner = longest > 0 ? ` ${body} ` : body;
  return `${prefix}${fence}${inner}${fence}${suffix}`;
};

const CONVERTERS: Record<string, Convert> = {
  "#document": (_n, text) => stripChars(text, "\n", "both"),
  a: (node, text) => {
    const [prefix, suffix, body] = chomp(text);
    if (!body) return "";
    if (findParent(node, "pre")) return body;
    let href = node.attrs.href;
    const title = node.attrs.title;
    if (href) {
      const parsed = escapeHref(href);
      if (!parsed) return `${prefix}${body}${suffix}`;
      if (parsed.scheme && !["http", "https", "file"].includes(parsed.scheme))
        return `${prefix}${body}${suffix}`;
      href = parsed.href;
    }
    if (body.replaceAll("\\_", "_") === href && !title) return `<${href}>`;
    const titlePart = title ? ` "${title.replaceAll('"', '\\"')}"` : "";
    return href ? `${prefix}[${body}](${href}${titlePart})${suffix}` : body;
  },
  b: inline("**"),
  strong: inline("**"),
  em: inline("*"),
  i: inline("*"),
  del: inline("~~"),
  s: inline("~~"),
  sub: inline(""),
  sup: inline(""),
  blockquote: (_n, text, parents) => {
    const body = stripChars(text, WS, "both");
    if (parents.has("_inline")) return ` ${body} `;
    if (!body) return "\n";
    return `\n${body
      .split("\n")
      .map((line) => (line ? `> ${line}` : ">"))
      .join("\n")}\n\n`;
  },
  br: (_n, _text, parents) => (parents.has("_inline") ? " " : "  \n"),
  code: convertCode,
  kbd: convertCode,
  samp: convertCode,
  div: convertDiv,
  article: convertDiv,
  section: convertDiv,
  dl: convertDiv,
  dd: (_n, text, parents) => {
    const body = pyStrip(text);
    if (parents.has("_inline")) return ` ${body} `;
    if (!body) return "\n";
    const indented = indentLines(body, "    ");
    return `:${indented.slice(1)}\n`;
  },
  dt: (_n, text, parents) => {
    const body = pyStrip(text).replace(reAllWhitespace, " ");
    if (parents.has("_inline")) return ` ${body} `;
    if (!body) return "\n";
    return `\n\n${body}\n`;
  },
  hr: () => "\n\n---\n\n",
  img: (node) => {
    const alt = (node.attrs.alt || "").replaceAll("\n", " ");
    let src = node.attrs.src || node.attrs["data-src"] || "";
    const title = node.attrs.title || "";
    const titlePart = title ? ` "${title.replaceAll('"', '\\"')}"` : "";
    if (src.startsWith("data:")) src = `${src.split(",")[0]}...`;
    return `![${alt}](${src}${titlePart})`;
  },
  input: (node) =>
    node.attrs.type === "checkbox"
      ? "checked" in node.attrs
        ? "[x] "
        : "[ ] "
      : "",
  ul: convertList,
  ol: convertList,
  li: (node, text) => {
    const body = pyStrip(text);
    if (!body) return "\n";
    let bullet: string;
    const parent = node.parent;
    if (parent?.name === "ol") {
      const start =
        parent.attrs.start && /^\d+$/.test(parent.attrs.start)
          ? Number(parent.attrs.start)
          : 1;
      const before = parent.children
        .slice(0, node.index)
        .filter((c) => isTag(c) && c.name === "li").length;
      bullet = `${start + before}.`;
    } else {
      let depth = -1;
      for (let n: Node | null = node; n; n = n.parent)
        if (n.name === "ul") depth++;
      bullet = "*+-"[((depth % 3) + 3) % 3] ?? "*";
    }
    bullet += " ";
    const indented = indentLines(body, " ".repeat(bullet.length));
    return `${bullet}${indented.slice(bullet.length)}\n`;
  },
  p: (_n, text, parents) => {
    if (parents.has("_inline")) return ` ${stripChars(text, WS, "both")} `;
    const body = stripChars(text, WS, "both");
    return body ? `\n\n${body}\n\n` : "";
  },
  pre: (_n, text) => {
    if (!text) return "";
    const body = text.replace(/^[ \n]*\n/, "").replace(/[ \n]*$/, "");
    return `\n\n\`\`\`\n${body}\n\`\`\`\n\n`;
  },
  q: (_n, text) => `"${text}"`,
  script: () => "",
  style: () => "",
  table: (_n, text) => `\n\n${pyStrip(text)}\n\n`,
  caption: (_n, text) => `${pyStrip(text)}\n\n`,
  figcaption: (_n, text) => `\n\n${pyStrip(text)}\n\n`,
  td: convertCell,
  th: convertCell,
};

function convertTr(node: Node, text: string): string {
  const cells = findAll(node, ["td", "th"]);
  const parent = node.parent;
  const isFirstRow = !parent?.children.slice(0, node.index).some(isTag);
  const isHeadRow =
    cells.every((c) => c.name === "th") ||
    (parent?.name === "thead" && findAll(parent, ["tr"]).length === 1);
  const isHeadRowMissing =
    (isFirstRow && parent?.name !== "tbody") ||
    (isFirstRow &&
      parent?.name === "tbody" &&
      findAll(parent.parent as Node, ["thead"]).length < 1);
  const full = cells.reduce((sum, cell) => sum + colspan(cell), 0);
  let overline = "";
  let underline = "";
  if (isHeadRow && isFirstRow)
    underline += `| ${Array(full).fill("---").join(" | ")} |\n`;
  else if (
    isHeadRowMissing ||
    (isFirstRow &&
      (parent?.name === "table" ||
        (parent?.name === "tbody" &&
          !parent.parent?.children.slice(0, parent.index).some(isTag))))
  ) {
    overline += `| ${Array(full).fill("").join(" | ")} |\n`;
    overline += `| ${Array(full).fill("---").join(" | ")} |\n`;
  }
  return `${overline}|${text}\n${underline}`;
}

function convertHeading(n: number, text: string, parents: Set<string>) {
  if (parents.has("_inline")) return text;
  const level = Math.max(1, Math.min(6, n));
  const body = pyStrip(text).replace(reAllWhitespace, " ");
  return `\n\n${"#".repeat(level)} ${body}\n\n`;
}

function escapeMarkdown(text: string): string {
  if (!text) return "";
  return text.replaceAll("*", "\\*").replaceAll("_", "\\_");
}

function processText(node: Node, parents: Set<string>): string {
  let text = node.value;
  if (!parents.has("pre"))
    text = text
      .replace(/[\t \r\n]*[\r\n][\t \r\n]*/g, "\n")
      .replace(/[\t ]+/g, " ");
  if (!parents.has("_noformat")) text = escapeMarkdown(text);
  const before = prev(node);
  const after = next(node);
  if (removeOutside(before) || (removeInside(node.parent) && !before))
    text = stripChars(text, WS, "l");
  if (removeOutside(after) || (removeInside(node.parent) && !after))
    text = pyRstrip(text);
  return text;
}

function processTag(node: Node, parents: Set<string>): string {
  const inside = removeInside(node);
  const canIgnore = (el: Node) => {
    if (el.kind === "element") return false;
    if (el.kind !== "text") return true;
    if (pyStrip(el.value) !== "") return false;
    if (inside && (!prev(el) || !next(el))) return true;
    return removeOutside(prev(el)) || removeOutside(next(el));
  };
  const childParents = new Set(parents);
  childParents.add(node.kind === "document" ? "[document]" : node.name);
  if (HEADING.test(node.name) || node.name === "td" || node.name === "th")
    childParents.add("_inline");
  if (["pre", "code", "kbd", "samp"].includes(node.name))
    childParents.add("_noformat");
  let strings = node.children
    .filter((child) => !canIgnore(child))
    .map((child) =>
      child.kind === "text"
        ? processText(child, childParents)
        : processTag(child, childParents),
    )
    .filter(Boolean);
  if (!(node.name === "pre" || findParent(node, "pre"))) {
    const updated = [""];
    for (const value of strings) {
      const match = /^(\n*)((?:[\s\S]*[^\n])?)(\n*)$/.exec(
        value,
      ) as RegExpExecArray;
      let leading = match[1] ?? "";
      const content = match[2] ?? "";
      const trailing = match[3] ?? "";
      if (updated[updated.length - 1] && leading) {
        const previous = updated.pop() ?? "";
        leading = "\n".repeat(
          Math.min(2, Math.max(previous.length, leading.length)),
        );
      }
      updated.push(leading, content, trailing);
    }
    strings = updated;
  }
  const text = strings.join("");
  if (node.kind === "document")
    return CONVERTERS["#document"]?.(node, text, parents) ?? text;
  if (node.name === "tr") return convertTr(node, text);
  const converter = CONVERTERS[node.name];
  if (converter) return converter(node, text, parents);
  const heading = HEADING.exec(node.name);
  if (heading) return convertHeading(Number(heading[1]), text, parents);
  return text;
}

// Python's _preprocess_patent_html: drop hidden mid-text paragraph numbers,
// then show <para-num> markers at paragraph starts.
const HIDDEN_PARA_SPAN =
  /<span\s+style="display:\s*none"\s*>\s*\[\d+\]\s*<\/span>/gi;
const PARA_NUM = /<para-num\s+num="(\[\d+\])"\s*>\s*<\/para-num>/g;

/** Markdown for Google Patents description HTML, or null for empty input. */
export function descriptionToMarkdown(
  html: string | null | undefined,
): string | null {
  if (!html) return null;
  const prepared = html.replace(HIDDEN_PARA_SPAN, "").replace(PARA_NUM, "$1 ");
  const document = parseDocument(prepared);
  const tree = toTree(document as unknown as globalThis.Node, null);
  for (const element of findAll(tree, ["script", "style"])) {
    element.parent?.children.splice(
      element.parent.children.indexOf(element),
      1,
    );
    element.parent?.children.forEach((child, index) => {
      child.index = index;
    });
  }
  const body = findAll(tree, ["body"])[0];
  const converted = pyStrip(processTag(body ?? tree, new Set()));
  return converted
    .split(/\r?\n/)
    .map((line) => pyRstrip(line))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n");
}
