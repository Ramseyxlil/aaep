#!/usr/bin/env bash
#
# AAEP Website Build Script
#
# Copies sources from src/ to dist/, syncs schemas from ../schemas/v1/,
# renders the markdown spec/guides/governance docs to HTML, and validates
# the output structure.
#
# Requires:
#   - bash 4+
#   - python3.10+ with the `markdown` package (auto-installed if missing)
#
# Usage:
#   ./build.sh             # Standard build
#   ./build.sh --watch     # Continuous rebuild (requires `entr` or `fswatch`)
#   ./build.sh --clean     # Remove dist/ and rebuild from scratch
#   ./build.sh --validate  # Validate output structure only

set -euo pipefail

# === Configuration ===

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC_DIR="${SCRIPT_DIR}/src"
DIST_DIR="${SCRIPT_DIR}/dist"
SCHEMAS_DIR="${REPO_ROOT}/schemas/v1"
SPEC_DIR="${REPO_ROOT}/spec"
GUIDES_DIR="${REPO_ROOT}/guides"
GOVERNANCE_DIR="${REPO_ROOT}/governance"
CUSTOM_DOMAIN="aaep-protocol.org"

# Colors (only when stdout is a terminal)
if [[ -t 1 ]]; then
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  RED='\033[0;31m'
  RESET='\033[0m'
else
  GREEN='' YELLOW='' RED='' RESET=''
fi

log()  { echo -e "${GREEN}[build]${RESET} $*"; }
warn() { echo -e "${YELLOW}[warn]${RESET}  $*"; }
err()  { echo -e "${RED}[err]${RESET}   $*" >&2; }

# === Argument parsing ===

CLEAN=0
WATCH=0
VALIDATE_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean)    CLEAN=1; shift ;;
    --watch)    WATCH=1; shift ;;
    --validate) VALIDATE_ONLY=1; shift ;;
    -h|--help)
      sed -n '2,/^set -e/p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) err "Unknown argument: $1"; exit 2 ;;
  esac
done

# === Dependency check ===

if ! command -v python3 >/dev/null 2>&1; then
  err "python3 not found in PATH"
  exit 1
fi

if ! python3 -c "import markdown" 2>/dev/null; then
  warn "python markdown package not found; installing..."
  # Try venv-aware install first, then --user, then --break-system-packages
  python3 -m pip install markdown 2>/dev/null \
    || python3 -m pip install --user markdown 2>/dev/null \
    || python3 -m pip install --break-system-packages markdown 2>/dev/null \
    || { err "Could not install markdown package"; exit 1; }
fi

# === Build steps ===

clean_dist() {
  log "Cleaning ${DIST_DIR}"
  rm -rf "${DIST_DIR}"
}

copy_static() {
  log "Copying static assets from src/"
  mkdir -p "${DIST_DIR}"
  cp -r "${SRC_DIR}/index.html" "${DIST_DIR}/"
  cp -r "${SRC_DIR}/404.html" "${DIST_DIR}/" 2>/dev/null || true
  cp -r "${SRC_DIR}/styles" "${DIST_DIR}/"
}

sync_schemas() {
  log "Syncing JSON schemas from ${SCHEMAS_DIR}"
  if [[ ! -d "${SCHEMAS_DIR}" ]]; then
    warn "Schema source not found: ${SCHEMAS_DIR}"
    return
  fi
  mkdir -p "${DIST_DIR}/schemas/v1"
  cp -r "${SCHEMAS_DIR}/." "${DIST_DIR}/schemas/v1/"
  local count
  count=$(find "${DIST_DIR}/schemas/v1" -name '*.json' | wc -l | tr -d ' ')
  log "  ${count} schema files synced"
}

render_markdown() {
  local source_dir="$1"
  local output_subpath="$2"
  local title_prefix="$3"
  if [[ ! -d "${source_dir}" ]]; then
    warn "Source not found: ${source_dir}"
    return
  fi
  log "Rendering markdown from ${source_dir} → ${DIST_DIR}/${output_subpath}/"
  mkdir -p "${DIST_DIR}/${output_subpath}"

  python3 - <<PY
import os
import sys
from pathlib import Path

try:
    import markdown
except ImportError:
    print("markdown package missing", file=sys.stderr)
    sys.exit(1)

source = Path("${source_dir}")
output = Path("${DIST_DIR}/${output_subpath}")
title_prefix = "${title_prefix}"

count = 0
for md_path in sorted(source.glob("**/*.md")):
    rel = md_path.relative_to(source)
    out_path = output / rel.with_suffix(".html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = markdown.markdown(
        md_path.read_text(encoding="utf-8"),
        extensions=["fenced_code", "tables", "toc", "sane_lists"],
        output_format="html5",
    )
    title = md_path.stem.replace("-", " ").replace("_", " ").title()
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title_prefix}: {title} — AAEP</title>
  <link rel="stylesheet" href="/styles/main.css">
</head>
<body>
<a class="skip-link" href="#main">Skip to main content</a>
<header role="banner">
  <div class="header-inner">
    <a href="/" class="brand">
      <span class="brand-mark">AAEP</span>
      <span class="brand-full">{title_prefix}</span>
    </a>
    <nav aria-label="Primary">
      <ul>
        <li><a href="/spec/">Spec</a></li>
        <li><a href="/guides/">Guides</a></li>
        <li><a href="https://github.com/Ramseyxlil/aaep">GitHub</a></li>
      </ul>
    </nav>
  </div>
</header>
<main id="main">
  <article class="content" style="padding: 2rem 1.5rem; max-width: 48rem; margin: 0 auto;">
{body}
  </article>
</main>
<footer role="contentinfo">
  <div class="footer-meta" style="text-align:center;">
    <p>AAEP {title_prefix} — <a href="/">back to home</a></p>
  </div>
</footer>
</body>
</html>"""
    out_path.write_text(html, encoding="utf-8")
    count += 1

print(f"  Rendered {count} markdown files")
PY
}

write_cname() {
  log "Writing CNAME for custom domain"
  echo "${CUSTOM_DOMAIN}" > "${DIST_DIR}/CNAME"
}

validate_output() {
  log "Validating output structure"
  local errors=0

  local required=(
    "index.html"
    "404.html"
    "styles/main.css"
    "CNAME"
  )

  for path in "${required[@]}"; do
    if [[ -f "${DIST_DIR}/${path}" ]]; then
      log "  ✓ ${path}"
    else
      err "  ✗ Missing: ${path}"
      errors=$((errors + 1))
    fi
  done

  if [[ -d "${DIST_DIR}/schemas/v1" ]]; then
    local schema_count
    schema_count=$(find "${DIST_DIR}/schemas/v1" -name '*.json' | wc -l | tr -d ' ')
    log "  ✓ schemas/v1/ (${schema_count} files)"
  else
    warn "  ○ schemas/v1/ not present (will be missing at deploy)"
  fi

  if [[ "${errors}" -gt 0 ]]; then
    err "Validation failed with ${errors} error(s)"
    return 1
  fi

  log "All required outputs present"
}

# === Watch mode ===

run_watch() {
  if command -v entr >/dev/null 2>&1; then
    log "Watching with entr (Ctrl+C to stop)"
    find "${SRC_DIR}" "${SCHEMAS_DIR}" "${SPEC_DIR}" "${GUIDES_DIR}" "${GOVERNANCE_DIR}" \
      2>/dev/null | entr -d "${SCRIPT_DIR}/build.sh"
  elif command -v fswatch >/dev/null 2>&1; then
    log "Watching with fswatch (Ctrl+C to stop)"
    fswatch -o "${SRC_DIR}" "${SCHEMAS_DIR}" "${SPEC_DIR}" "${GUIDES_DIR}" "${GOVERNANCE_DIR}" \
      2>/dev/null | xargs -n1 "${SCRIPT_DIR}/build.sh"
  else
    err "Watch mode requires either entr or fswatch"
    err "  brew install entr  (macOS)"
    err "  apt install entr   (Debian/Ubuntu)"
    exit 1
  fi
}

# === Main ===

if [[ "${VALIDATE_ONLY}" -eq 1 ]]; then
  validate_output
  exit $?
fi

if [[ "${WATCH}" -eq 1 ]]; then
  run_watch
  exit 0
fi

if [[ "${CLEAN}" -eq 1 ]]; then
  clean_dist
fi

log "Building AAEP website → ${DIST_DIR}"

copy_static
sync_schemas
render_markdown "${SPEC_DIR}" "spec" "Specification"
render_markdown "${GUIDES_DIR}" "guides" "Guides"
render_markdown "${GOVERNANCE_DIR}" "governance" "Governance"
write_cname
validate_output

log "Build complete."
log "Preview: open ${DIST_DIR}/index.html"
