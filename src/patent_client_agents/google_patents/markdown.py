"""Convert Google Patents description HTML to Markdown.

This reproduces markitdown 0.1.5's HTML path (``HtmlConverter`` with its
``_CustomMarkdownify`` subclass, plus ``MarkItDown``'s line clean-up) on top of
markdownify directly. Going through markitdown loaded magika, onnxruntime and
numpy and built a file-type model on every call, none of which HTML needs.

The ``_PatentMarkdownify`` overrides are adapted from markitdown
(https://github.com/microsoft/markitdown), Copyright (c) Microsoft
Corporation, MIT License.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, unquote, urlparse, urlunparse

import markdownify
from bs4 import BeautifulSoup


class _PatentMarkdownify(markdownify.MarkdownConverter):
    """markdownify with ATX headings, no javascript links, escaped URIs, and
    truncated data-URI images."""

    options: dict[str, Any]

    def __init__(self, **options: Any) -> None:
        options["heading_style"] = options.get("heading_style", markdownify.ATX)
        options["keep_data_uris"] = options.get("keep_data_uris", False)
        super().__init__(**options)

    def convert_hn(
        self, n: int, el: Any, text: str, convert_as_inline: bool | None = False, **kwargs: Any
    ) -> str:
        """Same as usual, but be sure to start with a new line."""
        if not convert_as_inline and not re.search(r"^\n", text):
            return "\n" + super().convert_hn(n, el, text, convert_as_inline)  # ty: ignore[unresolved-attribute]
        return super().convert_hn(n, el, text, convert_as_inline)  # ty: ignore[unresolved-attribute]

    def convert_a(
        self, el: Any, text: str, convert_as_inline: bool | None = False, **kwargs: Any
    ) -> str:
        """Same as usual, but drop javascript links and escape URIs."""
        prefix, suffix, text = markdownify.chomp(text)  # ty: ignore[unresolved-attribute]
        if not text:
            return ""
        if el.find_parent("pre") is not None:
            return text

        href = el.get("href")
        title = el.get("title")

        if href:
            try:
                parsed_url = urlparse(href)
                if parsed_url.scheme and parsed_url.scheme.lower() not in ["http", "https", "file"]:
                    return f"{prefix}{text}{suffix}"
                href = urlunparse(parsed_url._replace(path=quote(unquote(parsed_url.path))))
            except ValueError:
                return f"{prefix}{text}{suffix}"

        if (
            self.options["autolinks"]
            and text.replace(r"\_", "_") == href
            and not title
            and not self.options["default_title"]
        ):
            return f"<{href}>"
        if self.options["default_title"] and not title:
            title = href
        title_part = ' "{}"'.format(title.replace('"', r"\"")) if title else ""
        return f"{prefix}[{text}]({href}{title_part}){suffix}" if href else text

    def convert_img(
        self, el: Any, text: str, convert_as_inline: bool | None = False, **kwargs: Any
    ) -> str:
        """Same as usual, but truncate data URIs."""
        alt = el.attrs.get("alt", None) or ""
        src = el.attrs.get("src", None) or el.attrs.get("data-src", None) or ""
        title = el.attrs.get("title", None) or ""
        title_part = ' "{}"'.format(title.replace('"', r"\"")) if title else ""
        alt = alt.replace("\n", " ")
        if convert_as_inline and el.parent.name not in self.options["keep_inline_images_in"]:
            return alt
        if src.startswith("data:") and not self.options["keep_data_uris"]:
            src = src.split(",")[0] + "..."
        return f"![{alt}]({src}{title_part})"

    def convert_input(
        self, el: Any, text: str, convert_as_inline: bool | None = False, **kwargs: Any
    ) -> str:
        """Convert checkboxes to Markdown [x]/[ ] syntax."""
        if el.get("type") == "checkbox":
            return "[x] " if el.has_attr("checked") else "[ ] "
        return ""


def html_to_markdown(html: str) -> str:
    """Return Markdown for an HTML fragment or document."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style"]):
        element.extract()
    body = soup.find("body")
    text = _PatentMarkdownify().convert_soup(body if body else soup).strip()
    text = "\n".join(line.rstrip() for line in re.split(r"\r?\n", text))
    return re.sub(r"\n{3,}", "\n\n", text)
