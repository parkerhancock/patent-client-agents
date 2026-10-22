import { all, first, type Root } from "./dom.js";

export interface FigureCallout {
  figure_page: number | null;
  reference_id: string | null;
  label: string | null;
  bounds: {
    left: number | null;
    top: number | null;
    right: number | null;
    bottom: number | null;
  };
}
export interface GoogleFigure {
  index: number;
  page_number: number | null;
  image_id: string | null;
  thumbnail_url: string | null;
  full_image_url: string | null;
  callouts: FigureCallout[];
}

function absolute(url: string | null | undefined): string | null {
  const cleaned = url?.trim();
  if (!cleaned) return null;
  if (cleaned.startsWith("//")) return `https:${cleaned}`;
  if (cleaned.startsWith("/")) return `https://patents.google.com${cleaned}`;
  return cleaned;
}
function integer(value: string | null | undefined): number | null {
  const cleaned = value?.trim();
  return cleaned && /^-?\d+$/.test(cleaned) ? Number(cleaned) : null;
}
const imageId = (url: string | null) =>
  url ? (url.replace(/\/+$/, "").split("/").at(-1) ?? null) : null;
const meta = (node: Element, name: string) =>
  node
    .querySelector(`:scope > meta[itemprop='${name}']`)
    ?.getAttribute("content") ?? null;

/** Figure images and their numbered callouts. */
export function extractFigures(root: Root): GoogleFigure[] {
  return all(root, "li[itemprop='images']").flatMap((node, index) => {
    const thumbnail = absolute(
      first(node, "img[itemprop='thumbnail']")?.getAttribute("src"),
    );
    const full = absolute(
      first(node, "meta[itemprop='full']")?.getAttribute("content"),
    );
    if (!thumbnail && !full) return [];
    const url = full ?? thumbnail;
    const pageMeta = all(node, "meta[itemprop='figurePage']")
      .map((item) => integer(item.getAttribute("content")))
      .find((value) => value !== null);
    const fromId = /-D0*([0-9]+)/.exec(imageId(url) ?? "")?.[1];
    return [
      {
        index,
        page_number: pageMeta ?? integer(fromId),
        image_id: imageId(url),
        thumbnail_url: thumbnail,
        full_image_url: url,
        callouts: all(node, "li[itemprop='callouts']").map((callout) => {
          const bounds = first(callout, "span[itemprop='bounds']");
          const edge = (key: string) =>
            bounds ? integer(meta(bounds, key)) : null;
          return {
            figure_page: integer(meta(callout, "figurePage")),
            reference_id: meta(callout, "id")?.trim() || null,
            label: meta(callout, "label")?.trim() || null,
            bounds: {
              left: edge("left"),
              top: edge("top"),
              right: edge("right"),
              bottom: edge("bottom"),
            },
          };
        }),
      },
    ];
  });
}
