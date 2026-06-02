#!/usr/bin/env bash
# AAEP website build script.
# Renders all markdown content into a complete static website.

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/website/src"
DIST="$ROOT/website/dist"

log() { echo "[build] $1"; }
warn() { echo "[warn]  $1"; }
err() { echo "[err]   $1" >&2; }

# Parse args
CLEAN=0
for arg in "$@"; do
  case "$arg" in
    --clean) CLEAN=1 ;;
  esac
done

# Ensure markdown package is available
if ! python3 -c "import markdown" 2>/dev/null; then
  warn "python markdown package not found; installing..."
  python3 -m pip install markdown 2>/dev/null \
    || python3 -m pip install --user markdown 2>/dev/null \
    || python3 -m pip install --break-system-packages markdown 2>/dev/null \
    || { err "Could not install markdown package"; exit 1; }
fi

# Clean dist if requested
if [[ "$CLEAN" -eq 1 ]]; then
  log "Cleaning $DIST"
  rm -rf "$DIST"
fi

mkdir -p "$DIST"

# Copy static assets
log "Copying static assets"
mkdir -p "$DIST/styles"
cp "$SRC/styles/main.css" "$DIST/styles/main.css"

# Copy raw HTML files (index, 404)
cp "$SRC/index.html" "$DIST/index.html"
cp "$SRC/404.html" "$DIST/404.html"

# Write CNAME
log "Writing CNAME for custom domain"
echo "aaep-protocol.org" > "$DIST/CNAME"

# Copy JSON schemas directly (they're served as-is, not rendered)
if [[ -d "$ROOT/schemas" ]]; then
  log "Copying JSON schemas"
  mkdir -p "$DIST/schemas/v1"
  cp -r "$ROOT/schemas/"* "$DIST/schemas/v1/"
fi

# Now render every markdown file
log "Rendering markdown content..."

python3 << 'PYEOF'
import os
import re
from pathlib import Path
import markdown

ROOT = Path(os.environ.get("ROOT", Path.cwd().parent))
DIST = ROOT / "website" / "dist"
TEMPLATE_PATH = ROOT / "website" / "src" / "_template.html"

# Read the template
template = TEMPLATE_PATH.read_text(encoding="utf-8")

# Markdown extensions for tables, code blocks, table of contents
md = markdown.Markdown(
    extensions=[
        "fenced_code",
        "tables",
        "toc",
        "attr_list",
        "def_list",
        "abbr",
        "footnotes",
        "codehilite",
    ],
    extension_configs={
        "codehilite": {"css_class": "code", "guess_lang": False},
        "toc": {"permalink": False},
    },
)

# Source directories to render
SOURCE_DIRS = {
    "spec": ROOT / "spec",
    "guides": ROOT / "guides",
    "governance": ROOT / "governance",
}

# Pretty titles for navigation
def file_title(path: Path) -> str:
    """Derive a human title from a path."""
    name = path.stem
    # Remove leading numbers like "01-" 
    name = re.sub(r"^\d+[-_]", "", name)
    # Replace dashes and underscores with spaces
    name = name.replace("-", " ").replace("_", " ")
    # Title case
    return name.title()

def render_md(md_path: Path, out_path: Path, section: str, breadcrumb: str):
    """Render a markdown file to HTML using the template."""
    md.reset()
    content_md = md_path.read_text(encoding="utf-8")
    # Extract first H1 as page title, fall back to filename
    first_h1 = re.search(r"^#\s+(.+)$", content_md, re.MULTILINE)
    page_title = first_h1.group(1).strip() if first_h1 else file_title(md_path)
    content_html = md.convert(content_md)
    # Substitute into template
    output = (
        template
        .replace("{{PAGE_TITLE}}", page_title)
        .replace("{{SECTION}}", section)
        .replace("{{BREADCRUMB}}", breadcrumb)
        .replace("{{CONTENT}}", content_html)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")

rendered_count = 0
section_pages = {}  # section name -> [(title, relative_url)]

for section_name, source_dir in SOURCE_DIRS.items():
    if not source_dir.exists():
        continue
    section_pages[section_name] = []
    out_section = DIST / section_name
    out_section.mkdir(parents=True, exist_ok=True)
    for md_path in sorted(source_dir.rglob("*.md")):
        # Compute relative output path
        rel = md_path.relative_to(source_dir)
        # Convert .md → .html
        out_rel = rel.with_suffix(".html")
        out_path = out_section / out_rel
        # Compute page title from first H1
        content_md = md_path.read_text(encoding="utf-8")
        first_h1 = re.search(r"^#\s+(.+)$", content_md, re.MULTILINE)
        page_title = first_h1.group(1).strip() if first_h1 else file_title(md_path)
        # Breadcrumb
        breadcrumb = f'<a href="/">Home</a> / <a href="/{section_name}/">{section_name.title()}</a> / {page_title}'
        # Render
        render_md(md_path, out_path, section_name, breadcrumb)
        rendered_count += 1
        # Add to section index
        rel_url = f"/{section_name}/{out_rel.as_posix()}"
        section_pages[section_name].append((page_title, rel_url, str(rel)))

# Generate an index.html for each section
for section_name, pages in section_pages.items():
    if not pages:
        continue
    out_index = DIST / section_name / "index.html"
    section_title = section_name.title()
    items_html = "\n".join(
        f'<li><a href="{url}">{title}</a> <span class="path">{path}</span></li>'
        for title, url, path in pages
    )
    content_html = f"""
<h1>{section_title}</h1>
<p>The following {section_title.lower()} pages are available:</p>
<ul class="page-index">
{items_html}
</ul>
"""
    breadcrumb = f'<a href="/">Home</a> / {section_title}'
    output = (
        template
        .replace("{{PAGE_TITLE}}", section_title)
        .replace("{{SECTION}}", section_name)
        .replace("{{BREADCRUMB}}", breadcrumb)
        .replace("{{CONTENT}}", content_html)
    )
    out_index.write_text(output, encoding="utf-8")
    rendered_count += 1

# Generate schemas index
schemas_dir = DIST / "schemas" / "v1"
if schemas_dir.exists():
    schema_files = sorted(schemas_dir.rglob("*.json"))
    items = []
    for sf in schema_files:
        rel = sf.relative_to(schemas_dir)
        items.append(f'<li><a href="/schemas/v1/{rel.as_posix()}">{rel.as_posix()}</a></li>')
    items_html = "\n".join(items)
    content_html = f"""
<h1>JSON Schemas (v1)</h1>
<p>Canonical AAEP v1 JSON Schemas. Each schema's <code>$id</code> matches its URL on this site.</p>
<ul class="page-index">
{items_html}
</ul>
"""
    breadcrumb = '<a href="/">Home</a> / Schemas v1'
    output = (
        template
        .replace("{{PAGE_TITLE}}", "JSON Schemas v1")
        .replace("{{SECTION}}", "schemas")
        .replace("{{BREADCRUMB}}", breadcrumb)
        .replace("{{CONTENT}}", content_html)
    )
    (schemas_dir / "index.html").write_text(output, encoding="utf-8")
    rendered_count += 1

print(f"  Rendered {rendered_count} HTML pages")
PYEOF

# Validate output structure
log "Validating output structure"
for f in index.html 404.html styles/main.css CNAME; do
  if [[ -f "$DIST/$f" ]]; then
    log "  ✓ $f"
  else
    err "  MISSING: $f"
    exit 1
  fi
done

log "Build complete."
log "Preview: open $DIST/index.html"
