// Reflected Castagnoli polynomial used by Secret Manager's dataCrc32c field.
export function crc32c(bytes: Uint8Array): number {
  let checksum = 0xffffffff;
  for (const byte of bytes) {
    checksum ^= byte;
    for (let bit = 0; bit < 8; bit++)
      checksum = (checksum >>> 1) ^ (checksum & 1 ? 0x82f63b78 : 0);
  }
  return (checksum ^ 0xffffffff) >>> 0;
}
