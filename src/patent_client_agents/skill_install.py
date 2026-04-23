"""Install the ``ip_research`` Claude Code skill into ``~/.claude/skills/``.

Entry point for the ``patent-client-agents-skill-install`` console script. Creates
a symlink pointing from ``~/.claude/skills/ip-research`` to the packaged
skill directory resolved via ``importlib.resources``, so Claude Code
picks up in-place edits during development and static copies in
wheel-install scenarios.

Usage::

    patent-client-agents-skill-install                    # interactive: asks before overwrite
    patent-client-agents-skill-install --force            # replace existing symlink/dir
    patent-client-agents-skill-install --target=PATH      # override ~/.claude/skills

The ``~/.claude/skills/ip-research`` target uses a hyphen to match the
skill-name convention used by other Claude Code skills, even though
the source directory is ``ip_research``.
"""

from __future__ import annotations

import argparse
import os
import sys
from importlib.resources import files
from pathlib import Path

_SKILL_LINK_NAME = "ip-research"


def _skill_source_dir() -> Path:
    """Resolve the packaged skill directory via ``importlib.resources``.

    Works for both editable installs (returns the source tree path) and
    wheel installs (returns the extracted site-packages path).
    """
    resource = files("patent_client_agents.skills.ip_research")
    # ``files()`` returns a Traversable; for on-disk installs this is a
    # PosixPath. Claude Code needs a real filesystem path to create the
    # symlink against.
    return Path(str(resource))


def _default_target_dir() -> Path:
    return Path(os.path.expanduser("~")) / ".claude" / "skills"


def _install(source: Path, target_dir: Path, force: bool) -> Path:
    """Create ``target_dir / ip-research`` → ``source`` symlink.

    Returns the link path.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    link = target_dir / _SKILL_LINK_NAME

    if link.is_symlink() or link.exists():
        existing = link.resolve() if link.is_symlink() else link
        if existing == source.resolve():
            print(f"Already installed: {link} -> {source}", file=sys.stderr)
            return link
        if not force:
            raise SystemExit(
                f"Refusing to overwrite {link} (currently -> {existing}). "
                f"Re-run with --force or move it aside."
            )
        if link.is_symlink() or link.is_file():
            link.unlink()
        else:
            # Directory — rename to a sibling so we don't lose user content.
            backup = target_dir / f"{_SKILL_LINK_NAME}.bak"
            link.rename(backup)
            print(f"Moved existing dir to {backup}", file=sys.stderr)

    link.symlink_to(source, target_is_directory=True)
    return link


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="patent-client-agents-skill-install",
        description="Install the ip_research Claude Code skill.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing skill link or directory without prompting.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=_default_target_dir(),
        help="Override the target directory (default: ~/.claude/skills).",
    )
    args = parser.parse_args(argv)

    source = _skill_source_dir()
    if not source.exists():
        print(f"Skill source dir not found at {source}", file=sys.stderr)
        return 1

    link = _install(source, args.target, force=args.force)
    print(f"Installed {link} -> {source}")
    print("Claude Code will pick up the skill on next session start.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
