"""MkDocs hook for the Patent Client Index.

Working name (per Parker, 2026-05-18) — a published, opinionated atlas of
patent + IP data sources. Sources of truth live under ``research/`` and are
*virtual-mounted* into the mkdocs docs tree at ``patent-client-index/{layer}/``,
then transformed at render time for an external reader.

What this hook does, in order:

1. ``on_files`` — registers every research synopsis as a virtual file under
   ``patent-client-index/{multilateral|regional|national}/<basename>.md``. No
   on-disk copy. Also writes the overview matrix to
   ``docs/patent-client-index/index.md`` (gitignored) from ``research/STATE.yaml``.
2. ``on_nav`` — injects the per-layer nav structure so each synopsis appears
   under the ``Patent Client Index`` tab without manual mkdocs.yml edits.
3. ``on_page_markdown`` — transforms each synopsis for an external audience:
   - prepends a rating callout
   - renames §5 to "Access via patent-client-agents"
   - renames §6 to "Known unknowns"
   - collapses §8 change log to a single "Last updated" footer line
   - rewrites cross-references to research/ neighbors as GitHub URLs

Only synopsis files are mounted. Detail surveys (``connectors/``) and
waves (``waves/``) stay GitHub-only.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path
from typing import Any

import yaml
from mkdocs.structure.files import File, Files
from mkdocs.structure.nav import Navigation

REPO_ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = REPO_ROOT / "research"
STATE_YAML = RESEARCH_DIR / "STATE.yaml"
INDEX_OUTPUT = REPO_ROOT / "docs" / "patent-client-index" / "index.md"
GITHUB_REPO_URL = "https://github.com/parkerhancock/patent-client-agents/blob/main"
GITHUB_RESEARCH_URL = f"{GITHUB_REPO_URL}/research"
ATLAS_URL = "https://patentclient.com/atlas"

LAYERS = ("multilateral", "regional", "national")

# Rating vocabulary. Mirrored in scripts/build_coverage.py — keep both in
# sync until lifted into a shared module.
RATING_BADGES = {
    "green": ("🟢", "Green", "Live API, queryable, ToS-clean."),
    "yellow_byok": (
        "🟡",
        "Yellow — BYOK",
        "Live API but per-user keys required (terms of use forbid shared-key proxy).",
    ),
    "yellow_paid": (
        "🟡",
        "Yellow — Paid",
        "Programmatic access exists but only behind a paid contract or subscription.",
    ),
    "red_tos": ("🔴", "Red — ToS", "Terms of use prohibit programmatic / automated access."),
    "red_no_api": (
        "🔴",
        "Red — No API",
        "No queryable API surface; HTML-only or bulk-dump access.",
    ),
    "red_bulk_only": ("🔴", "Red — Bulk only", "Bulk download exists but no per-query API."),
    "red_contract": (
        "🔴",
        "Red — Contract",
        "Access requires a paper / wet-signature contract not accessible to indie developers.",
    ),
    "red_blocked": (
        "🔴",
        "Red — Blocked",
        "Access path exists but is currently blocked (egress filter, geofence, etc.).",
    ),
    "watch": ("⚪", "Watch", "Monitoring for changes; no decision yet."),
    "tbd": ("⚪", "TBD", "Research pending."),
}

CONNECTOR_STATUS_BADGES = {
    "shipped": "✅ shipped",
    "in_progress": "🔨 in progress",
    "spec_ready": "📋 spec ready",
    "planned": "📝 planned",
    "skipped": "❌ skipped",
    "blocked": "⛔ blocked",
    "none": "—",
}


# ─── on_pre_build ──────────────────────────────────────────────────────────


def on_pre_build(config: dict[str, Any]) -> None:
    """Write the overview matrix BEFORE mkdocs validates the nav against
    the docs directory. mkdocs.yml references ``patent-client-index/index.md``
    as the placeholder for the Patent Client Index tab; if the file
    doesn't physically exist when nav validation runs, --strict aborts
    with a warning. CI does a fresh clone where the gitignored
    generated file doesn't exist yet, so we generate it on every build.
    """
    INDEX_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    INDEX_OUTPUT.write_text(_render_overview())


# ─── on_files ──────────────────────────────────────────────────────────────


def on_files(files: Files, config: dict[str, Any]) -> Files:
    """Virtual-mount synopses AND inject the per-layer sub-nav into
    ``config["nav"]`` so the synopses appear in the Material sidebar
    (not as orphan pages).
    """
    # 1) Virtual-mount each synopsis (and collect them for the nav build)
    by_layer: dict[str, list[tuple[str, str]]] = {lyr: [] for lyr in LAYERS}
    for layer in LAYERS:
        layer_dir = RESEARCH_DIR / layer
        if not layer_dir.is_dir():
            continue
        for source in sorted(layer_dir.glob("*.md")):
            if source.name == "README.md":
                continue
            virtual = f"patent-client-index/{layer}/{source.name}"
            f = File(
                path=virtual,
                src_dir=str(source.parent),
                dest_dir=config["site_dir"],
                use_directory_urls=config["use_directory_urls"],
            )
            f.abs_src_path = str(source)
            f.src_path = virtual
            f.src_uri = virtual
            files.append(f)
            by_layer[layer].append((_title_from_synopsis(source), virtual))

    # 3) Inject the sub-nav into config["nav"]. The mkdocs.yml entry is
    #    a placeholder (single page); replace it with a section that has
    #    "Overview" + per-layer groups of synopsis pages.
    nav = config.get("nav") or []
    for i, item in enumerate(nav):
        if isinstance(item, dict) and "Patent Client Index" in item:
            section: list[dict[str, str]] = [
                {"Overview": "patent-client-index/index.md"},
            ]
            for layer in LAYERS:
                entries = by_layer.get(layer, [])
                if not entries:
                    continue
                section.append(
                    {
                        layer.capitalize(): [{title: path} for title, path in entries],
                    }
                )
            nav[i] = {"Patent Client Index": section}
            break
    config["nav"] = nav

    return files


# ─── on_page_markdown ──────────────────────────────────────────────────────


def on_page_markdown(markdown: str, page, config, files) -> str:
    src = getattr(page.file, "src_uri", "") or getattr(page.file, "src_path", "")
    src = src.replace("\\", "/")
    if not src.startswith("patent-client-index/"):
        return markdown
    if src == "patent-client-index/index.md":
        return markdown  # already-generated overview, no transformation

    layer = src.split("/")[1]
    entity = _find_state_row_by_synopsis(f"{layer}/{Path(src).name}")
    return _transform_synopsis(markdown, layer, entity)


# ─── helpers ───────────────────────────────────────────────────────────────


def _find_page(nav: Navigation, src_uri: str):
    """Walk nav and find a Page whose file.src_uri matches."""
    stack = list(nav.items)
    while stack:
        item = stack.pop()
        if hasattr(item, "file") and item.file is not None:
            if getattr(item.file, "src_uri", None) == src_uri:
                return item
        if hasattr(item, "children") and item.children:
            stack.extend(item.children)
    return None


def _title_from_synopsis(path: Path) -> str:
    """Pull the first H1 from a synopsis file; fall back to filename.

    Cleanup applied:
    - ``KIPO Korea (KR) — national`` → ``KIPO Korea``
    - ``WIPO PATENTSCOPE — multilateral`` → ``WIPO PATENTSCOPE``
    - ``WIPO Hague System (WO/WIPO/Hague)`` → ``WIPO Hague System``
    """
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                # Strip "— layer-name" suffix
                title = re.sub(r"\s*—\s*(multilateral|regional|national)\s*$", "", title)
                # Strip trailing parenthetical (CODE / IDs)
                title = re.sub(r"\s*\([^)]+\)\s*$", "", title)
                return title.strip()
        return path.stem
    except OSError:
        return path.stem


def _load_state() -> dict[str, Any]:
    return yaml.safe_load(STATE_YAML.read_text(encoding="utf-8"))


def _find_state_row_by_synopsis(synopsis_path: str) -> dict[str, Any] | None:
    state = _load_state()
    for row in state.get("entities", []):
        if (row.get("synopsis") or "").replace("\\", "/") == synopsis_path:
            return row
    return None


def _render_overview() -> str:
    """Render docs/patent-client-index/index.md from STATE.yaml."""
    state = _load_state()
    entities = state.get("entities", [])
    stats = state.get("stats", {})
    last_updated = state.get("last_updated", "")

    lines: list[str] = []
    lines.append("# Patent Client Index")
    lines.append("")
    lines.append(
        "_An opinionated atlas of patent and IP data sources. "
        f"{len(entities)} offices surveyed, with ratings on what's queryable._"
    )
    lines.append("")
    lines.append(
        f"**At a glance:** {stats.get('synopses_filled', 0)} synopses · "
        f"{stats.get('connectors_shipped', 0)} connectors shipped · "
        f"{stats.get('connectors_in_progress', 0)} in progress · "
        f"last updated **{last_updated}**."
    )
    lines.append("")
    lines.append("## What this is")
    lines.append("")
    lines.append(
        "For each office we track: what programmatic surfaces it exposes "
        "(REST, OAuth, paid contract, none), whether the terms of use permit "
        "live querying, fee schedules, and whether **patent-client-agents** "
        "ships a connector for it today. Ratings:"
    )
    lines.append("")
    for code, (emoji, label, desc) in RATING_BADGES.items():
        if code in ("watch", "tbd"):
            continue
        lines.append(f"- {emoji} **{label}** — {desc}")
    lines.append("")
    lines.append("## Coverage matrix")
    lines.append("")
    lines.append("| Office | ISO | Rights | Rating | Connector | Last verified |")
    lines.append("|---|---|---|---|---|---|")

    layer_order = {"multilateral": 0, "regional": 1, "national": 2}
    sorted_entities = sorted(
        entities,
        key=lambda r: (layer_order.get(r.get("layer", ""), 99), r.get("name", "")),
    )

    for row in sorted_entities:
        name = row.get("name", "—")
        synopsis = row.get("synopsis")
        if synopsis:
            name_cell = f"[{name}]({synopsis})"
        else:
            name_cell = name
        iso = row.get("iso2") or "—"
        if iso == "n/a":
            iso = "—"
        rights = ", ".join(_short_rights(row.get("rights", [])))
        rating_code = row.get("rating", "tbd")
        emoji, label, _ = RATING_BADGES.get(rating_code, RATING_BADGES["tbd"])
        rating_cell = f"{emoji} {label}"
        connector_cell = CONNECTOR_STATUS_BADGES.get(row.get("connector_status", "none"), "—")
        last_verified = row.get("last_verified", "—")
        lines.append(
            f"| {name_cell} | {iso} | {rights} | {rating_cell} | {connector_cell} | {last_verified} |"
        )

    lines.append("")
    lines.append("## Layers")
    lines.append("")
    lines.append(
        "- **Multilateral** — WIPO systems (PATENTSCOPE, Madrid, Hague, Lex, Global Brand DB, Global Design DB)"
    )
    lines.append("- **Regional** — multi-state offices (EPO, EUIPO, UPC, EAPO, ARIPO, OAPI, GCC)")
    lines.append(
        "- **National** — single-state offices (US, JP, KR, CN, DE, GB, FR, CA, AU, IN, …)"
    )
    lines.append("")
    lines.append(f"_Source of truth: [`research/STATE.yaml`]({GITHUB_RESEARCH_URL}/STATE.yaml)._")
    lines.append("")
    return "\n".join(lines)


_RIGHTS_SHORT = {
    "patent": "pat",
    "utility_model": "um",
    "trademark": "tm",
    "design": "des",
    "copyright": "©",
    "plant_variety": "pv",
    "gi": "gi",
    "trade_secret": "ts",
}


def _short_rights(rights: list[str]) -> list[str]:
    return [_RIGHTS_SHORT.get(r, r) for r in rights]


# ─── synopsis transformation ───────────────────────────────────────────────

_SECTION_RENAMES = [
    # Preserve §-prefixes so the rendered ToC reads continuously §1..§7.
    ("## §5 Connector strategy", "## §5 Access via patent-client-agents"),
    ("## §6 Open questions", "## §6 Known unknowns"),
]


def _atlas_focus_token(entity: dict[str, Any]) -> str:
    """For national entities use iso2; otherwise the first id segment.

    ``KR/KIPO``  → ``KR`` (iso2)
    ``EP/EPO``   → ``EP``
    ``WO/WIPO/Madrid`` → ``WO``
    """
    iso = entity.get("iso2")
    if iso and iso != "n/a":
        return iso
    eid = entity.get("id", "")
    return eid.split("/")[0] if eid else ""


def _transform_synopsis(markdown: str, layer: str, entity: dict[str, Any] | None) -> str:
    # 1) Prepend a rating callout (if we have entity state)
    callout = ""
    if entity:
        emoji, label, desc = RATING_BADGES.get(entity.get("rating", "tbd"), RATING_BADGES["tbd"])
        basis = entity.get("rating_basis", "").strip() or desc
        focus = _atlas_focus_token(entity)
        atlas_link = f"    [View on the atlas →]({ATLAS_URL}?focus={focus})\n" if focus else ""
        callout = (
            f"!!! {'success' if emoji == '🟢' else 'warning' if emoji == '🟡' else 'danger' if emoji == '🔴' else 'note'}"
            f' "Rating: {emoji} {label}"\n'
            f"    {basis}\n"
            f"    [Jump to access details →](#5-access-via-patent-client-agents)\n"
            f"{atlas_link}\n"
        )

    # 2) Rename sections
    for old, new in _SECTION_RENAMES:
        markdown = markdown.replace(old, new)

    # 3) Collapse §8 change log to a footer line
    markdown = _collapse_change_log(markdown)

    # 4) Drop the "What we should NOT add" subsection
    markdown = _drop_should_not_add(markdown)

    # 5) Restructure the synopsis frontmatter block (the **Label:** value
    #    lines under the H1). Without this, mkdocs collapses them into a
    #    single mushy <p> because there are no blank lines between them.
    markdown = _restructure_frontmatter(markdown)

    # 6) Ensure a blank line between `**Label:**` headers and the bullet
    #    list that follows (same issue, throughout the body — §7
    #    References is the typical offender).
    markdown = _separate_label_bullet_blocks(markdown)

    # 7) Rewrite cross-references to non-mounted neighbors (connectors/, waves/, BACKLOG, etc.)
    markdown = _rewrite_research_links(markdown, layer)

    # 8) Insert callout right after the first H1 (and its header lines that follow)
    if callout:
        markdown = _insert_after_header_block(markdown, callout)

    return markdown


def _separate_label_bullet_blocks(markdown: str) -> str:
    """Insert a blank line between any ``**Label:**``-only line and the
    bullet list directly under it. mkdocs treats the run of lines as a
    single paragraph otherwise.

    Also: insert a blank line between two consecutive non-blank lines
    where one starts with ``**`` (bold key) and the next starts with a
    different inline element (e.g. plain text or another bold) when
    they're inside what looks like a free-form k:v dump — but **only**
    after we've already restructured the frontmatter, so this won't
    fire on already-tabled metadata.
    """
    # Pattern: a line that's just `**Word(s):**` (possibly with trailing
    # whitespace), immediately followed by a `- ` bullet on the next
    # line. Insert a blank line between them.
    return re.sub(
        r"^(\*\*[^*\n]+:\*\*[ \t]*)\n(- )",
        r"\1\n\n\2",
        markdown,
        flags=re.MULTILINE,
    )


_INLINE_KV_RE = re.compile(r"^\*\*([^*][^:]*?):\*\*\s+(.+?)\s*$")
_LABEL_ONLY_RE = re.compile(r"^\*\*([^*][^:]*?):\*\*\s*$")


def _restructure_frontmatter(markdown: str) -> str:
    """Rewrite the H1-to-`---` (or H1-to-first-`## §`) preamble.

    The synopses use a wall of ``**Label:** value`` lines with no blank
    lines between them, which markdown collapses into one <p>. We split
    the block into:
    - **Inline pairs** (``**X:** value`` on one line) → emit as one HTML
      ``<dl>`` so each row gets its own <dt>/<dd>.
    - **Label-only headers** (``**X:**`` followed by a bullet list) →
      keep, but insert a blank line before each so they render as a
      bold header followed by a <ul>.
    """
    # Identify the preamble: from line after H1 to first `---` or `## `
    lines = markdown.splitlines()
    h1_idx = next((i for i, line in enumerate(lines) if line.startswith("# ")), -1)
    if h1_idx == -1:
        return markdown
    end_idx = None
    for j in range(h1_idx + 1, len(lines)):
        if lines[j].strip() == "---" or lines[j].startswith("## "):
            end_idx = j
            break
    if end_idx is None:
        return markdown
    preamble = lines[h1_idx + 1 : end_idx]

    inline_pairs: list[tuple[str, str]] = []
    tail_blocks: list[list[str]] = []  # each block = [label line, *bullet lines]
    current_block: list[str] | None = None
    in_inline_run = True
    for line in preamble:
        if in_inline_run:
            m = _INLINE_KV_RE.match(line)
            if m:
                inline_pairs.append((m.group(1).strip(), m.group(2).strip()))
                continue
            if not line.strip():
                continue
            in_inline_run = False
        # Tail: label-only blocks followed by bullet lists
        if _LABEL_ONLY_RE.match(line):
            if current_block is not None:
                tail_blocks.append(current_block)
            current_block = [line]
        elif current_block is not None:
            if line.strip() or current_block[-1].strip():
                # Keep the line. Drop only consecutive blanks.
                current_block.append(line)
        elif line.strip():
            # Stray content before any label-only header — keep as its own block
            current_block = [line]
    if current_block is not None:
        tail_blocks.append(current_block)

    if not inline_pairs and not tail_blocks:
        return markdown  # nothing to restructure

    rebuilt: list[str] = [lines[h1_idx], ""]

    # Inline k:v pairs → markdown table (more robust than <dl> against
    # python-markdown's paragraph injection).
    if inline_pairs:
        rebuilt.append("| | |")
        rebuilt.append("|---|---|")
        for k, v in inline_pairs:
            rebuilt.append(f"| **{k}** | {_escape_pipes(v)} |")
        rebuilt.append("")  # blank after table

    # Tail blocks: each becomes "**Label:**\n\n- bullet…" with proper
    # blank-line separation so markdown renders bold heading + list.
    for block in tail_blocks:
        label = block[0]
        body = block[1:]
        rebuilt.append(label)
        rebuilt.append("")  # blank line so list parses
        rebuilt.extend(body)
        rebuilt.append("")  # blank after block

    rebuilt.append(lines[end_idx])
    rebuilt.extend(lines[end_idx + 1 :])
    return "\n".join(rebuilt)


def _escape_pipes(s: str) -> str:
    """Escape `|` inside markdown table cells."""
    return s.replace("|", "\\|")


def _insert_after_header_block(markdown: str, snippet: str) -> str:
    """Insert snippet after the first H1 + its immediately-following header lines.

    Synopsis files start with:

        # KIPO Korea (KR) — national

        **Layer:** national
        **Jurisdiction:** KR ...
        ...

        ---

        ## §1 Mission

    We want the callout after the `---` (or before the first `## §1`).
    """
    parts = markdown.split("\n## ", 1)
    if len(parts) != 2:
        return snippet + markdown
    return parts[0].rstrip() + "\n\n" + snippet + "## " + parts[1]


def _collapse_change_log(markdown: str) -> str:
    """Replace the §8 change log table with a single 'Last updated <date>' footer."""
    pattern = re.compile(r"## §8 Change log\s*\n.*?(?=\n## |\Z)", flags=re.DOTALL)
    match = pattern.search(markdown)
    if not match:
        return markdown
    # Find the most-recent date inside the change log table
    dates = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", match.group(0))
    latest = max(dates) if dates else ""
    footer = f"---\n\n*Last updated {latest}.*\n" if latest else ""
    return markdown[: match.start()] + footer + markdown[match.end() :]


def _drop_should_not_add(markdown: str) -> str:
    """Strip the '### What we should NOT add' subsection (and its body)."""
    pattern = re.compile(r"### What we should NOT add\s*\n.*?(?=\n### |\n## |\Z)", flags=re.DOTALL)
    return pattern.sub("", markdown)


_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def _rewrite_research_links(markdown: str, layer: str) -> str:
    """Rewrite relative links in synopsis files to GitHub URLs.

    The synopsis lives at ``research/<layer>/<basename>.md`` in the repo.
    A relative target like ``../../coverage/sources.yaml`` should resolve
    to the repo-root path and be rewritten to its GitHub URL — *not* a
    URL with a literal ``..`` segment in it.

    Co-mounted sibling synopses (``../<layer>/Y.md`` where Y is also
    rendered into the docs) stay relative so mkdocs handles them.
    """
    co_mounted_by_layer = {
        lyr: {p.name for p in (RESEARCH_DIR / lyr).glob("*.md")} for lyr in LAYERS
    }
    synopsis_dir_repo_relative = f"research/{layer}"  # repo-root-relative

    def replace(match: re.Match) -> str:
        text, target = match.group(1), match.group(2)
        if target.startswith("#") or "://" in target or target.startswith("mailto:"):
            return match.group(0)
        target_path, _, anchor = target.partition("#")

        # Co-mounted sibling synopsis (cross-layer) — keep relative
        for lyr in LAYERS:
            prefix = f"../{lyr}/"
            if target_path.startswith(prefix):
                rest = target_path[len(prefix) :]
                if rest in co_mounted_by_layer[lyr]:
                    return match.group(0)
                break

        # Co-mounted intra-layer sibling — keep relative
        if (
            "/" not in target_path
            and target_path.endswith(".md")
            and target_path in co_mounted_by_layer[layer]
        ):
            return match.group(0)

        # Resolve everything else to a repo-root path
        resolved = posixpath.normpath(posixpath.join(synopsis_dir_repo_relative, target_path))
        if resolved.startswith("../"):
            return match.group(0)  # escapes the repo — leave alone
        url = f"{GITHUB_REPO_URL}/{resolved}"
        if anchor:
            url = f"{url}#{anchor}"
        return f"[{text}]({url})"

    return _LINK_RE.sub(replace, markdown)
