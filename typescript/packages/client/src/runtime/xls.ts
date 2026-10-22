/**
 * Minimal reader for legacy Excel 97-2003 (.xls, BIFF8) workbooks: the
 * Compound File container, the shared string table and the cell records that
 * carry values (numbers, RK numbers, strings, booleans and cached formula
 * results). Formatting is ignored. Cells read as numbers, strings or booleans;
 * blank and missing cells read as "". Runs in Bun, Node and browsers.
 */

export type XlsCell = string | number | boolean;
export interface XlsSheet {
  name: string;
  /** Rows padded to the sheet's widest row, as xlrd's row_values returns them. */
  rows: XlsCell[][];
}
export interface XlsWorkbook {
  /** 0: dates count from 1900 (Windows); 1: from 1904 (Mac). */
  datemode: 0 | 1;
  sheets: XlsSheet[];
}

export class XlsError extends Error {
  override name = "XlsError";
}

const CFB_MAGIC = [0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1];
const END_OF_CHAIN = 0xfffffffe;
const FREE = 0xffffffff;
const MAX_SECTORS = 1 << 22;

/** Read one named stream out of a Compound File Binary container. */
function cfbStream(data: Uint8Array, names: readonly string[]): Uint8Array {
  if (data.length < 512 || CFB_MAGIC.some((byte, i) => data[i] !== byte))
    throw new XlsError("Not a legacy Excel (Compound File) workbook.");
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const sectorSize = 1 << view.getUint16(0x1e, true);
  const miniSectorSize = 1 << view.getUint16(0x20, true);
  if (sectorSize !== 512 && sectorSize !== 4096)
    throw new XlsError("Unsupported Compound File sector size.");
  const fatSectors = view.getUint32(0x2c, true);
  const directoryStart = view.getUint32(0x30, true);
  const miniCutoff = view.getUint32(0x38, true);
  const miniFatStart = view.getUint32(0x3c, true);
  let difatSector = view.getUint32(0x44, true);
  const sector = (index: number) => {
    const offset = (index + 1) * sectorSize;
    if (offset >= data.length)
      throw new XlsError("Compound File sector lies outside the file.");
    return data.subarray(offset, Math.min(offset + sectorSize, data.length));
  };
  const u32 = (bytes: Uint8Array, offset: number) =>
    new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(
      offset,
      true,
    );

  const fatIndexes: number[] = [];
  for (let i = 0; i < 109 && fatIndexes.length < fatSectors; i++)
    fatIndexes.push(view.getUint32(0x4c + i * 4, true));
  const perSector = sectorSize / 4;
  let guard = 0;
  while (
    fatIndexes.length < fatSectors &&
    difatSector !== END_OF_CHAIN &&
    difatSector !== FREE
  ) {
    if (guard++ > MAX_SECTORS) throw new XlsError("Compound File DIFAT loops.");
    const bytes = sector(difatSector);
    for (let i = 0; i < perSector - 1 && fatIndexes.length < fatSectors; i++)
      fatIndexes.push(u32(bytes, i * 4));
    difatSector = u32(bytes, (perSector - 1) * 4);
  }
  const fat: number[] = [];
  for (const index of fatIndexes) {
    const bytes = sector(index);
    for (let i = 0; i < perSector; i++) fat.push(u32(bytes, i * 4));
  }
  const chain = (start: number, table: number[]) => {
    const out: number[] = [];
    for (let at = start; at !== END_OF_CHAIN; at = table[at] ?? END_OF_CHAIN) {
      if (at === FREE || at >= table.length || out.length > table.length)
        throw new XlsError("Compound File sector chain is broken.");
      out.push(at);
    }
    return out;
  };
  const read = (start: number, size?: number) => {
    const sectors = chain(start, fat);
    const out = new Uint8Array(sectors.length * sectorSize);
    sectors.forEach((index, i) => {
      out.set(sector(index), i * sectorSize);
    });
    return size === undefined ? out : out.subarray(0, size);
  };

  const directory = read(directoryStart);
  const entries: {
    name: string;
    type: number;
    start: number;
    size: number;
  }[] = [];
  for (let offset = 0; offset + 128 <= directory.length; offset += 128) {
    const entry = directory.subarray(offset, offset + 128);
    const nameBytes = Math.min(
      new DataView(entry.buffer, entry.byteOffset).getUint16(0x40, true),
      64,
    );
    const name = new TextDecoder("utf-16le")
      .decode(entry.subarray(0, Math.max(nameBytes - 2, 0)))
      .replace(/\0+$/, "");
    entries.push({
      name,
      type: entry[0x42] ?? 0,
      start: u32(entry, 0x74),
      size: u32(entry, 0x78),
    });
  }
  const root = entries.find((entry) => entry.type === 5);
  const stream = names
    .map((wanted) =>
      entries.find(
        (entry) =>
          entry.type === 2 && entry.name.toLowerCase() === wanted.toLowerCase(),
      ),
    )
    .find(Boolean);
  if (!stream)
    throw new XlsError("The workbook has no Workbook stream (not BIFF8).");
  if (stream.size >= miniCutoff) return read(stream.start, stream.size);
  if (!root) throw new XlsError("Compound File has no root entry.");
  const miniStream = read(root.start, root.size);
  const miniFat: number[] = [];
  if (miniFatStart !== END_OF_CHAIN) {
    const bytes = read(miniFatStart);
    for (let i = 0; i + 4 <= bytes.length; i += 4) miniFat.push(u32(bytes, i));
  }
  const sectors = chain(stream.start, miniFat);
  const out = new Uint8Array(sectors.length * miniSectorSize);
  sectors.forEach((index, i) => {
    out.set(
      miniStream.subarray(index * miniSectorSize, (index + 1) * miniSectorSize),
      i * miniSectorSize,
    );
  });
  return out.subarray(0, stream.size);
}

interface BiffRecord {
  type: number;
  offset: number;
  data: Uint8Array;
}

function records(stream: Uint8Array, start: number): BiffRecord[] {
  const out: BiffRecord[] = [];
  const view = new DataView(
    stream.buffer,
    stream.byteOffset,
    stream.byteLength,
  );
  let offset = start;
  while (offset + 4 <= stream.length) {
    const type = view.getUint16(offset, true);
    const length = view.getUint16(offset + 2, true);
    if (offset + 4 + length > stream.length)
      throw new XlsError("BIFF record runs past the end of the stream.");
    out.push({
      type,
      offset,
      data: stream.subarray(offset + 4, offset + 4 + length),
    });
    offset += 4 + length;
    if (type === 0x000a) break; // EOF
  }
  return out;
}

const latin1 = new TextDecoder("latin1");
const utf16 = new TextDecoder("utf-16le");

/**
 * Reads strings that may continue across CONTINUE records. At each record
 * boundary inside a string's characters, a fresh option byte says whether
 * the rest is compressed (one byte per character) or UTF-16LE.
 */
class SegmentReader {
  private segment = 0;
  private position = 0;
  constructor(private readonly segments: Uint8Array[]) {}
  private current() {
    while (
      this.segment < this.segments.length &&
      this.position >= (this.segments[this.segment]?.length ?? 0)
    ) {
      this.segment++;
      this.position = 0;
    }
    const bytes = this.segments[this.segment];
    if (!bytes) throw new XlsError("Shared string table is truncated.");
    return bytes;
  }
  done() {
    return (
      this.segment >= this.segments.length ||
      (this.segment === this.segments.length - 1 &&
        this.position >= (this.segments[this.segment]?.length ?? 0))
    );
  }
  u8() {
    const bytes = this.current();
    return bytes[this.position++] as number;
  }
  u16() {
    return this.u8() | (this.u8() << 8);
  }
  u32() {
    return (this.u16() | (this.u16() << 16)) >>> 0;
  }
  skip(count: number) {
    let left = count;
    while (left > 0) {
      const bytes = this.current();
      const take = Math.min(left, bytes.length - this.position);
      this.position += take;
      left -= take;
    }
  }
  characters(count: number, wide: boolean) {
    let text = "";
    let left = count;
    let isWide = wide;
    while (left > 0) {
      let bytes = this.segments[this.segment];
      if (!bytes || this.position >= bytes.length) {
        // A string continued into the next record restates its width.
        this.segment++;
        this.position = 0;
        bytes = this.segments[this.segment];
        if (!bytes) throw new XlsError("Shared string table is truncated.");
        isWide = ((bytes[this.position++] ?? 0) & 1) === 1;
      }
      const width = isWide ? 2 : 1;
      const take = Math.min(
        left,
        Math.floor((bytes.length - this.position) / width),
      );
      if (take <= 0) throw new XlsError("Malformed string continuation.");
      const slice = bytes.subarray(this.position, this.position + take * width);
      text += isWide ? utf16.decode(slice) : latin1.decode(slice);
      this.position += take * width;
      left -= take;
    }
    return text;
  }
  /** XLUnicodeRichExtendedString, as stored in the SST. */
  richString() {
    const count = this.u16();
    const flags = this.u8();
    const runs = flags & 0x08 ? this.u16() : 0;
    const ext = flags & 0x04 ? this.u32() : 0;
    const text = this.characters(count, (flags & 1) === 1);
    this.skip(runs * 4 + ext);
    return text;
  }
}

/** Unicode string with an 8- or 16-bit length, inside one record. */
function unicodeString(bytes: Uint8Array, offset: number, lengthBytes: 1 | 2) {
  const count =
    lengthBytes === 1
      ? (bytes[offset] ?? 0)
      : (bytes[offset] ?? 0) | ((bytes[offset + 1] ?? 0) << 8);
  const flags = bytes[offset + lengthBytes] ?? 0;
  let at = offset + lengthBytes + 1;
  if (flags & 0x08) at += 2;
  if (flags & 0x04) at += 4;
  const wide = (flags & 1) === 1;
  const slice = bytes.subarray(at, at + count * (wide ? 2 : 1));
  return wide ? utf16.decode(slice) : latin1.decode(slice);
}

function rkNumber(value: number): number {
  const scaled = (value & 1) === 1;
  let number: number;
  if (value & 2) number = value >> 2;
  else {
    const buffer = new DataView(new ArrayBuffer(8));
    buffer.setUint32(4, value & 0xfffffffc, true);
    number = buffer.getFloat64(0, true);
  }
  return scaled ? number / 100 : number;
}

/** Parse a BIFF8 .xls workbook into sheets of cell values. */
export function readXls(data: Uint8Array): XlsWorkbook {
  const stream = cfbStream(data, ["Workbook", "Book"]);
  const globals = records(stream, 0);
  const bof = globals[0];
  if (bof?.type !== 0x0809 || bof.data.length < 2)
    throw new XlsError("Workbook stream does not begin with a BIFF BOF.");
  if ((bof.data[0] ?? 0) + ((bof.data[1] ?? 0) << 8) !== 0x0600)
    throw new XlsError("Only BIFF8 (Excel 97-2003) workbooks are supported.");
  let datemode: 0 | 1 = 0;
  const boundSheets: { name: string; position: number }[] = [];
  let strings: string[] = [];
  for (let i = 0; i < globals.length; i++) {
    const record = globals[i] as BiffRecord;
    const view = new DataView(record.data.buffer, record.data.byteOffset);
    switch (record.type) {
      case 0x002f:
        throw new XlsError("The workbook is encrypted.");
      case 0x0022:
        datemode = view.getUint16(0, true) === 1 ? 1 : 0;
        break;
      case 0x0085:
        if ((record.data[5] ?? 0) === 0)
          boundSheets.push({
            position: view.getUint32(0, true),
            name: unicodeString(record.data, 6, 1),
          });
        break;
      case 0x00fc: {
        const segments = [record.data];
        while (globals[i + 1]?.type === 0x003c)
          segments.push((globals[++i] as BiffRecord).data);
        const reader = new SegmentReader(segments);
        reader.u32();
        const unique = reader.u32();
        strings = [];
        for (let n = 0; n < unique && !reader.done(); n++)
          strings.push(reader.richString());
        if (strings.length !== unique)
          throw new XlsError("Shared string table is truncated.");
        break;
      }
    }
  }
  const sheets = boundSheets.map(({ name, position }) => {
    if (position >= stream.length)
      throw new XlsError(`Sheet ${name} lies outside the workbook stream.`);
    const cells = new Map<number, Map<number, XlsCell>>();
    let width = 0;
    let height = 0;
    const put = (row: number, column: number, value: XlsCell) => {
      let line = cells.get(row);
      if (!line) {
        line = new Map();
        cells.set(row, line);
      }
      line.set(column, value);
      width = Math.max(width, column + 1);
      height = Math.max(height, row + 1);
    };
    const sheetRecords = records(stream, position);
    for (let i = 0; i < sheetRecords.length; i++) {
      const { type, data: bytes } = sheetRecords[i] as BiffRecord;
      const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.length);
      const at = () => [view.getUint16(0, true), view.getUint16(2, true)];
      switch (type) {
        case 0x0203: {
          const [row, column] = at() as [number, number];
          put(row, column, view.getFloat64(6, true));
          break;
        }
        case 0x027e: {
          const [row, column] = at() as [number, number];
          put(row, column, rkNumber(view.getUint32(6, true)));
          break;
        }
        case 0x00bd: {
          const [row, first] = at() as [number, number];
          const count = (bytes.length - 6) / 6;
          for (let n = 0; n < count; n++)
            put(row, first + n, rkNumber(view.getUint32(4 + n * 6 + 2, true)));
          break;
        }
        case 0x00fd: {
          const [row, column] = at() as [number, number];
          const index = view.getUint32(6, true);
          const text = strings[index];
          if (text === undefined)
            throw new XlsError("Cell refers to a missing shared string.");
          put(row, column, text);
          break;
        }
        case 0x0204:
        case 0x00d6: {
          const [row, column] = at() as [number, number];
          put(row, column, unicodeString(bytes, 6, 2));
          break;
        }
        case 0x0205: {
          const [row, column] = at() as [number, number];
          if (bytes[7] === 0) put(row, column, bytes[6] === 1);
          break;
        }
        case 0x0006: {
          const [row, column] = at() as [number, number];
          if (bytes[12] !== 0xff || bytes[13] !== 0xff)
            put(row, column, view.getFloat64(6, true));
          else if (bytes[6] === 1) put(row, column, bytes[8] === 1);
          else if (bytes[6] === 0) {
            const next = sheetRecords.findIndex(
              (record, n) => n > i && record.type === 0x0207,
            );
            const record = sheetRecords[next];
            if (record) put(row, column, unicodeString(record.data, 0, 2));
          }
          break;
        }
      }
    }
    const rows: XlsCell[][] = [];
    for (let row = 0; row < height; row++) {
      const line = cells.get(row);
      rows.push(
        Array.from({ length: width }, (_, column) => line?.get(column) ?? ""),
      );
    }
    return { name, rows };
  });
  return { datemode, sheets };
}

/**
 * An Excel serial date as YYYY-MM-DD (time of day dropped), following
 * xlrd's xldate_as_datetime, including the 1900 leap-year quirk.
 */
export function xlsSerialDate(serial: number, datemode: 0 | 1): string {
  if (!Number.isFinite(serial) || serial < 0)
    throw new XlsError(`Invalid Excel serial date: ${serial}`);
  const epoch =
    datemode === 1
      ? Date.UTC(1904, 0, 1)
      : serial < 60
        ? Date.UTC(1899, 11, 31)
        : Date.UTC(1899, 11, 30);
  return new Date(epoch + Math.floor(serial) * 86_400_000)
    .toISOString()
    .slice(0, 10);
}
