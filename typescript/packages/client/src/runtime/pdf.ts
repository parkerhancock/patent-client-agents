/**
 * Plain text of each PDF page, for connectors that parse published PDFs
 * (the fee schedules that Python reads with pypdf). pdfjs-dist is loaded on
 * first use, so callers that never parse a PDF don't pay for it.
 *
 * Text items are grouped into lines by baseline, ordered left to right, and
 * joined with single spaces; lines are joined with "\n". This approximates
 * pypdf's `extract_text()` closely enough for row-oriented fee tables. Use
 * `pdfPageItems` when a parser needs positions or font sizes.
 */
export interface PdfTextItem {
  str: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

type PdfJs = typeof import("pdfjs-dist/legacy/build/pdf.mjs");
let pdfjs: Promise<PdfJs> | undefined;
const loadPdfJs = () => {
  pdfjs ??= import("pdfjs-dist/legacy/build/pdf.mjs");
  return pdfjs;
};

/** Positioned text items of each page, in content-stream order. */
export async function pdfPageItems(
  bytes: Uint8Array,
): Promise<PdfTextItem[][]> {
  const { getDocument } = await loadPdfJs();
  const document = await getDocument({
    // pdfjs takes ownership of the buffer; keep the caller's bytes intact.
    data: bytes.slice(),
    isEvalSupported: false,
    disableFontFace: true,
    useSystemFonts: false,
    // Errors only: font-rendering warnings don't affect extracted text.
    verbosity: 0,
  }).promise;
  try {
    const pages: PdfTextItem[][] = [];
    for (let number = 1; number <= document.numPages; number++) {
      const page = await document.getPage(number);
      const content = await page.getTextContent();
      const items: PdfTextItem[] = [];
      for (const item of content.items) {
        if (!("str" in item)) continue;
        items.push({
          str: item.str,
          x: item.transform[4],
          y: item.transform[5],
          width: item.width,
          height: item.height,
        });
      }
      pages.push(items);
      page.cleanup();
    }
    return pages;
  } finally {
    await document.destroy();
  }
}

/** Line-ordered plain text of each page. */
export async function pdfPageTexts(bytes: Uint8Array): Promise<string[]> {
  return (await pdfPageItems(bytes)).map(pageText);
}

function pageText(items: PdfTextItem[]): string {
  const lines: { y: number; items: PdfTextItem[] }[] = [];
  for (const item of items) {
    if (!item.str.trim()) continue;
    const tolerance = Math.max(2, item.height * 0.4);
    const line = lines.find((l) => Math.abs(l.y - item.y) <= tolerance);
    if (line) line.items.push(item);
    else lines.push({ y: item.y, items: [item] });
  }
  return lines
    .sort((a, b) => b.y - a.y)
    .map((line) =>
      line.items
        .sort((a, b) => a.x - b.x)
        .map((item) => item.str.trim())
        .join(" ")
        .replace(/\s+/g, " "),
    )
    .join("\n");
}
