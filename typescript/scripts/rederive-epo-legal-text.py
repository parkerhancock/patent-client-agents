"""Re-derive EPO legal corpus text from the stored HTML with word breaks.

The May 14, 2026 EPO corpora were built with lxml ``text_content()``, which
joins adjacent text nodes with nothing between them: EPC Article 54's heading
became "Article 5442, 43Novelty" and an FTS search for "novelty" missed it.
Each row stores the ``<main>`` fragment its text came from, so this script
recomputes ``text`` (and ``title``, where it came from the page's first H1)
with the fixed extraction from ``fix/epo-legal-heading-whitespace``
(deb55e73), then rebuilds the FTS index. The snapshot is otherwise unchanged.

It refuses to write unless the old extraction, run over the stored HTML,
reproduces every stored text exactly, which shows the stored fragment is the
extraction input.

Usage: python rederive-epo-legal-text.py IN.db OUT.db
"""

from __future__ import annotations

import re
import shutil
import sqlite3
import sys
from copy import deepcopy

import zstandard as zstd
from lxml import html

# Copied from deb55e73 (patent_client_agents/shared/corpus/epo_legal.py).
_WORD_BREAK_TAGS = frozenset(
    {
        "address", "article", "aside", "blockquote", "br", "caption", "dd", "div",
        "dl", "dt", "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5",
        "h6", "header", "hr", "li", "ol", "p", "pre", "section", "sub", "sup",
        "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
    }
)  # fmt: skip
FIX_COMMIT = "deb55e73"


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def element_text(element: html.HtmlElement) -> str:
    copy = deepcopy(element)
    for node in copy.iter():
        if isinstance(node.tag, str) and node.tag.lower() in _WORD_BREAK_TAGS:
            node.text = " " + (node.text or "")
            node.tail = " " + (node.tail or "")
    return normalize_whitespace(copy.text_content())


def main(source: str, target: str) -> None:
    shutil.copyfile(source, target)
    db = sqlite3.connect(target)
    dicts = {
        name: zstd.ZstdDecompressor(dict_data=zstd.ZstdCompressionDict(bytes(raw)))
        for name, raw in db.execute(
            "SELECT column_name, dict_bytes FROM compression_dict"
        )
    }
    if set(dicts) - {"html"}:
        sys.exit(f"unexpected compressed columns: {sorted(dicts)}")
    rows = db.execute("SELECT rowid, html, text, title FROM sections").fetchall()
    updates = []
    mismatched = []
    for rowid, stored_html, text, title in rows:
        fragment = (
            dicts["html"].decompress(stored_html).decode()
            if "html" in dicts and isinstance(stored_html, bytes)
            else stored_html
        )
        if not fragment:
            if text:
                mismatched.append(rowid)
            continue
        main_el = html.fromstring(fragment)
        if normalize_whitespace(main_el.text_content()) != text:
            mismatched.append(rowid)
            continue
        h1s = main_el.xpath(".//h1")
        old_title = normalize_whitespace(h1s[0].text_content()) if h1s else None
        new_title = title
        if h1s and title == (old_title or None):
            new_title = element_text(h1s[0]) or None
        new_text = element_text(main_el)
        if new_text != text or new_title != title:
            updates.append((new_text, new_title, rowid))
    if mismatched:
        sys.exit(
            f"{len(mismatched)} of {len(rows)} rows don't round-trip "
            f"(first rowids {mismatched[:5]}); not writing"
        )
    db.executemany("UPDATE sections SET text = ?, title = ? WHERE rowid = ?", updates)
    db.execute("INSERT INTO sections_fts(sections_fts) VALUES ('rebuild')")
    db.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('text_extraction', ?)",
        (f"element_text {FIX_COMMIT}",),
    )
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(f"{target}: {len(updates)} of {len(rows)} rows changed")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
