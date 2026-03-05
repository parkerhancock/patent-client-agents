#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MARKER_FILE="$REPO_ROOT/.install-marker"

if [[ -f "$REPO_ROOT/pyproject.toml" ]]; then
    # Dev repo: editable install with dependency tracking
    CURRENT_HASH=$(md5 -q "$REPO_ROOT/pyproject.toml" 2>/dev/null || md5sum "$REPO_ROOT/pyproject.toml" 2>/dev/null | cut -d' ' -f1 || echo "none")
    STORED_HASH=$(cat "$MARKER_FILE" 2>/dev/null || echo "")

    # Fast path: already installed and pyproject.toml unchanged
    if [[ "$CURRENT_HASH" == "$STORED_HASH" ]] && python3 -c "import ip_tools" 2>/dev/null; then
        exit 0
    fi

    # Install/upgrade (editable install for dev - code changes auto-picked up)
    pip install --quiet --user -e "$REPO_ROOT"

    # Store marker for next run
    echo "$CURRENT_HASH" > "$MARKER_FILE"
else
    # Not in repo - check if already installed
    python3 -c "import ip_tools" 2>/dev/null && exit 0

    # Install from GitHub
    pip install --quiet --user git+https://github.com/parkerhancock/ip_tools.git
fi

# Verify
python3 -c "import ip_tools" || {
    echo "Error: Failed to install ip_tools" >&2
    exit 1
}
