// Tests replay cassettes and must never read or write a response cache: a
// cached hit would bypass the cassette and hide a missing recording. Tests
// that exercise the cache opt in with `useCache: true` and their own storage.
process.env.PATENT_CLIENT_AGENTS_CACHE = "off";
