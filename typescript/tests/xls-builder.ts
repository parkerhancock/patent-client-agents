/**
 * Test-only writer for small BIFF8 .xls workbooks, so parser tests can use
 * exact rows (the Python test rows, edge cases) instead of fake book objects.
 * Strings go through the shared string table, split across CONTINUE records
 * every `sstChunk` bytes; numbers are NUMBER records; extra raw records can be
 * appended to a sheet to exercise other cell types.
 */
export type BuilderCell = string | number | null;
export interface BuilderSheet {
  name: string;
  rows: BuilderCell[][];
  /** Raw [type, payload] records written after the cells. */
  extra?: [number, Uint8Array][];
}

const le16 = (value: number) => [value & 0xff, (value >> 8) & 0xff];
const le32 = (value: number) => [
  value & 0xff,
  (value >> 8) & 0xff,
  (value >> 16) & 0xff,
  (value >>> 24) & 0xff,
];
const record = (type: number, payload: ArrayLike<number>) => [
  ...le16(type),
  ...le16(payload.length),
  ...Array.from(payload),
];
const f64 = (value: number) => {
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, value, true);
  return Array.from(new Uint8Array(view.buffer));
};
const wide = (text: string) => [...text].some((c) => c.charCodeAt(0) > 0xff);
const chars = (text: string, isWide: boolean) =>
  isWide
    ? [...text].flatMap((c) => le16(c.charCodeAt(0)))
    : [...text].map((c) => c.charCodeAt(0));

/** A LABEL record's payload (16-bit length XLUnicodeString). */
export function labelPayload(row: number, column: number, text: string) {
  const isWide = wide(text);
  return new Uint8Array([
    ...le16(row),
    ...le16(column),
    ...le16(0),
    ...le16(text.length),
    isWide ? 1 : 0,
    ...chars(text, isWide),
  ]);
}
/** An RK value holding an integer. */
export const rkInteger = (value: number) => ((value << 2) | 2) >>> 0;
export { f64, le16, le32 };

function sstRecords(strings: string[], chunk: number): number[] {
  const records: number[][] = [];
  let current: number[] = [...le32(strings.length), ...le32(strings.length)];
  const flush = () => {
    records.push(current);
    current = [];
  };
  for (const text of strings) {
    const isWide = wide(text);
    if (current.length + 3 > chunk) flush();
    current.push(...le16(text.length), isWide ? 1 : 0);
    let rest = [...text];
    while (rest.length) {
      const width = isWide ? 2 : 1;
      const room = Math.floor((chunk - current.length) / width);
      if (room <= 0) {
        flush();
        current.push(isWide ? 1 : 0);
        continue;
      }
      current.push(...chars(rest.slice(0, room).join(""), isWide));
      rest = rest.slice(room);
    }
  }
  flush();
  return records.flatMap((payload, i) =>
    record(i === 0 ? 0x00fc : 0x003c, payload),
  );
}

function workbookStream(
  sheets: BuilderSheet[],
  datemode: 0 | 1,
  sstChunk: number,
): Uint8Array {
  const strings: string[] = [];
  const index = new Map<string, number>();
  for (const sheet of sheets)
    for (const row of sheet.rows)
      for (const cell of row)
        if (typeof cell === "string" && !index.has(cell)) {
          index.set(cell, strings.length);
          strings.push(cell);
        }
  const bof = (type: number) =>
    record(0x0809, [...le16(0x0600), ...le16(type), ...new Array(12).fill(0)]);
  const sheetBodies = sheets.map((sheet) => {
    const body: number[] = [...bof(0x10)];
    sheet.rows.forEach((row, r) => {
      row.forEach((cell, c) => {
        if (typeof cell === "string")
          body.push(
            ...record(0x00fd, [
              ...le16(r),
              ...le16(c),
              ...le16(0),
              ...le32(index.get(cell) as number),
            ]),
          );
        else if (typeof cell === "number")
          body.push(
            ...record(0x0203, [
              ...le16(r),
              ...le16(c),
              ...le16(0),
              ...f64(cell),
            ]),
          );
      });
    });
    for (const [type, payload] of sheet.extra ?? [])
      body.push(...record(type, payload));
    body.push(...record(0x000a, []));
    return body;
  });
  const boundSheet = (name: string, position: number) => {
    const isWide = wide(name);
    return record(0x0085, [
      ...le32(position),
      0,
      0,
      name.length,
      isWide ? 1 : 0,
      ...chars(name, isWide),
    ]);
  };
  const head = [...bof(0x05), ...record(0x0022, le16(datemode))];
  const tail = [
    ...sstRecords(strings, sstChunk),
    // Padding keeps the stream above the 4096-byte mini-stream cutoff.
    ...record(0x00ef, new Array(4096).fill(0)),
    ...record(0x000a, []),
  ];
  const boundLength = sheets.reduce(
    (sum, sheet) => sum + boundSheet(sheet.name, 0).length,
    0,
  );
  let position = head.length + boundLength + tail.length;
  const bounds: number[] = [];
  for (const [i, sheet] of sheets.entries()) {
    bounds.push(...boundSheet(sheet.name, position));
    position += (sheetBodies[i] as number[]).length;
  }
  return new Uint8Array([...head, ...bounds, ...tail, ...sheetBodies.flat()]);
}

/** Wrap a Workbook stream in a minimal Compound File (512-byte sectors). */
function compoundFile(stream: Uint8Array): Uint8Array {
  const sectorCount = Math.ceil(stream.length / 512);
  if (sectorCount > 126) throw new Error("Test workbook too large.");
  const total = 512 * (3 + sectorCount);
  const out = new Uint8Array(total);
  const view = new DataView(out.buffer);
  out.set([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1]);
  view.setUint16(0x18, 0x3e, true);
  view.setUint16(0x1a, 3, true);
  view.setUint16(0x1c, 0xfffe, true);
  view.setUint16(0x1e, 9, true);
  view.setUint16(0x20, 6, true);
  view.setUint32(0x2c, 1, true);
  view.setUint32(0x30, 1, true);
  view.setUint32(0x38, 4096, true);
  view.setUint32(0x3c, 0xfffffffe, true);
  view.setUint32(0x44, 0xfffffffe, true);
  for (let i = 0; i < 109; i++)
    view.setUint32(0x4c + i * 4, i === 0 ? 0 : 0xffffffff, true);
  const fat = 512;
  for (let i = 0; i < 128; i++) view.setUint32(fat + i * 4, 0xffffffff, true);
  view.setUint32(fat, 0xfffffffd, true);
  view.setUint32(fat + 4, 0xfffffffe, true);
  for (let i = 0; i < sectorCount; i++)
    view.setUint32(
      fat + (2 + i) * 4,
      i === sectorCount - 1 ? 0xfffffffe : 3 + i,
      true,
    );
  const entry = (
    slot: number,
    name: string,
    type: number,
    start: number,
    size: number,
  ) => {
    const at = 1024 + slot * 128;
    [...name].forEach((c, i) => {
      view.setUint16(at + i * 2, c.charCodeAt(0), true);
    });
    view.setUint16(at + 0x40, (name.length + 1) * 2, true);
    out[at + 0x42] = type;
    view.setUint32(at + 0x44, 0xffffffff, true);
    view.setUint32(at + 0x48, 0xffffffff, true);
    view.setUint32(at + 0x4c, slot === 0 ? 1 : 0xffffffff, true);
    view.setUint32(at + 0x74, start, true);
    view.setUint32(at + 0x78, size, true);
  };
  entry(0, "Root Entry", 5, 0xfffffffe, 0);
  entry(1, "Workbook", 2, 2, stream.length);
  out.set(stream, 512 * 3);
  return out;
}

export function buildXls(
  sheets: BuilderSheet[],
  options: { datemode?: 0 | 1; sstChunk?: number } = {},
): Uint8Array {
  return compoundFile(
    workbookStream(sheets, options.datemode ?? 0, options.sstChunk ?? 8224),
  );
}
