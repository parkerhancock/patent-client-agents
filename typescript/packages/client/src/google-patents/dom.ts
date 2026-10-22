import { parseHTML } from "linkedom";

/**
 * DOM helpers for Google Patents pages, mirroring the Python lxml helpers.
 * linkedom is a pure-JavaScript DOM, so the same parsers run in Bun, Node
 * and browsers. Google Patents marks data with schema.org microdata, so
 * nearly every lookup is an `[itemprop=…]` CSS selector.
 */
export type Root = Document | Element;

export function parseDocument(html: string): Document {
  return parseHTML(html).document as unknown as Document;
}
/** lxml text_content().strip(): all descendant text, trimmed. */
export function text(element: Element | null | undefined): string {
  return element?.textContent?.trim() ?? "";
}
/** Collapse internal whitespace. */
export const squash = (value: string) => value.replace(/\s+/g, " ").trim();
export function all(
  root: Root | null | undefined,
  selector: string,
): Element[] {
  return root ? Array.from(root.querySelectorAll(selector)) : [];
}
export function first(
  root: Root | null | undefined,
  selector: string,
): Element | null {
  return root?.querySelector(selector) ?? null;
}
/** Trimmed text of the first match, or "". */
export function firstText(
  root: Root | null | undefined,
  selector: string,
): string {
  return text(first(root, selector));
}
/** Trimmed, non-empty attribute of the first match, or null. */
export function firstAttr(
  root: Root | null | undefined,
  selector: string,
  attribute: string,
): string | null {
  return first(root, selector)?.getAttribute(attribute)?.trim() || null;
}
/** XPath text(): the element's own text nodes, joined and trimmed. */
export function ownText(element: Element | null | undefined): string {
  if (!element) return "";
  return Array.from(element.childNodes)
    .filter((node) => node.nodeType === 3)
    .map((node) => node.textContent ?? "")
    .join("")
    .trim();
}
/** First own-text of matches, like XPath `.//x/text()` taking the first non-empty value. */
export function firstOwnText(
  root: Root | null | undefined,
  selector: string,
): string {
  for (const element of all(root, selector)) {
    const value = ownText(element);
    if (value) return value;
  }
  return "";
}
/** The next element sibling matching `selector`, like following-sibling::x[1]. */
export function nextSibling(
  element: Element | null | undefined,
  selector: string,
): Element | null {
  let sibling = element?.nextElementSibling ?? null;
  while (sibling && !sibling.matches(selector))
    sibling = sibling.nextElementSibling;
  return sibling;
}
/** First <dt> whose text matches the pattern. */
export function findDt(root: Root, pattern: RegExp): Element | null {
  return all(root, "dt").find((dt) => pattern.test(text(dt))) ?? null;
}
/** Text of the next <dd> after a <dt>. */
export function ddText(dt: Element | null): string {
  return text(nextSibling(dt, "dd"));
}
/** Serialized outer HTML of an element. */
export function outerHtml(element: Element | null | undefined): string | null {
  return element ? element.outerHTML : null;
}
