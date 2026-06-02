#!/usr/bin/env bash
# AAEP website build script.

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/website/src"
DIST="$ROOT/website/dist"
export ROOT

log() { echo "[build] $1"; }
warn() { echo "[warn]  $1"; }
err() { echo "[err]   $1" >&2; }

CLEAN=0
for arg in "$@"; do
  case "$arg" in
    --clean) CLEAN=1 ;;
  esac
done

if ! python3 -c "import markdown" 2>/dev/null; then
  warn "python markdown package not found; installing..."
  python3 -m pip install markdown 2>/dev/null \
    || python3 -m pip install --user markdown 2>/dev/null \
    || python3 -m pip install --break-system-packages markdown 2>/dev/null \
    || { err "Could not install markdown package"; exit 1; }
fi

if [[ "$CLEAN" -eq 1 ]]; then
  log "Cleaning $DIST"
  rm -rf "$DIST"
fi

mkdir -p "$DIST"

log "Copying static assets"
mkdir -p "$DIST/styles"
cp "$SRC/styles/main.css" "$DIST/styles/main.css"
cp "$SRC/index.html" "$DIST/index.html"
cp "$SRC/404.html" "$DIST/404.html"

log "Writing CNAME for custom domain"
echo "aaep-protocol.org" > "$DIST/CNAME"

if [[ -d "$ROOT/schemas" ]]; then
  log "Copying JSON schemas"
  mkdir -p "$DIST/schemas/v1"
  cp -r "$ROOT/schemas/"* "$DIST/schemas/v1/"
fi

log "Rendering markdown content..."

python3 << 'PYEOF'
import os
import re
from pathlib import Path
import markdown

ROOT = Path(os.environ["ROOT"])
DIST = ROOT / "website" / "dist"
TEMPLATE_PATH = ROOT / "website" / "src" / "_template.html"

GITHUB_REPO_BASE = "https://github.com/Ramseyxlil/aaep/tree/main/"
GITHUB_BLOB_BASE = "https://github.com/Ramseyxlil/aaep/blob/main/"

NON_RENDERED_REPO_DIRS = [
    "examples",
    "conformance",
    "tools",
]

template = TEMPLATE_PATH.read_text(encoding="utf-8")

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

SOURCE_DIRS = {
    "spec": ROOT / "spec",
    "guides": ROOT / "guides",
    "governance": ROOT / "governance",
}

def file_title(path: Path) -> str:
    name = path.stem
    name = re.sub(r"^\d+[-_]", "", name)
    name = name.replace("-", " ").replace("_", " ")
    return name.title()

def rewrite_links(html: str) -> str:
    """Rewrite three classes of broken links in rendered HTML.

    1. Relative paths to non-rendered repo directories (examples/, conformance/,
       tools/) -> absolute GitHub tree/blob URLs.
    2. Markdown file references (.md) -> their HTML equivalents (.html).
    3. Absolute URLs to aaep-protocol.org that still end in .md -> .html.
    """
    # Pass 1: relative repo links to non-rendered dirs
    def replace_repo_link(match):
        href = match.group(1)
        stripped = re.sub(r"^(\.\./)+", "", href)
        for non_rendered in NON_RENDERED_REPO_DIRS:
            if stripped.startswith(non_rendered + "/") or stripped == non_rendered + "/" or stripped == non_rendered:
                if stripped.endswith("/") or "." not in stripped.split("/")[-1]:
                    return f'href="{GITHUB_REPO_BASE}{stripped}"'
                return f'href="{GITHUB_BLOB_BASE}{stripped}"'
        return match.group(0)

    html = re.sub(
        r'href="((?:\.\./)+(?:examples|conformance|tools)[^"]*)"',
        replace_repo_link,
        html,
    )

    # Pass 2: relative .md links -> .html links
    # Matches href="something.md" or href="something.md#anchor"
    # Doesn't touch absolute URLs that happen to contain .md
    def replace_md_link(match):
        href = match.group(1)
        anchor = match.group(2) or ""
        return f'href="{href}.html{anchor}"'

    html = re.sub(
        r'href="((?!https?://|mailto:|#)[^"]*?)\.md(#[^"]*)?"',
        replace_md_link,
        html,
    )

    # Pass 3: absolute aaep-protocol.org links that end in .md -> .html
    # (handles cases where source had a hardcoded full URL with .md)
    html = re.sub(
        r'href="(https?://aaep-protocol\.org/[^"]*?)\.md(#[^"]*)?"',
        lambda m: f'href="{m.group(1)}.html{m.group(2) or ""}"',
        html,
    )

    return html

def render_md(md_path: Path, out_path: Path, section: str, breadcrumb: str):
    md.reset()
    content_md = md_path.read_text(encoding="utf-8")
    first_h1 = re.search(r"^#\s+(.+)$", content_md, re.MULTILINE)
    page_title = first_h1.group(1).strip() if first_h1 else file_title(md_path)
    content_html = md.convert(content_md)
    content_html = rewrite_links(content_html)
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
section_pages = {}

for section_name, source_dir in SOURCE_DIRS.items():
    if not source_dir.exists():
        continue
    section_pages[section_name] = []
    out_section = DIST / section_name
    out_section.mkdir(parents=True, exist_ok=True)
    for md_path in sorted(source_dir.rglob("*.md")):
        rel = md_path.relative_to(source_dir)
        out_rel = rel.with_suffix(".html")
        out_path = out_section / out_rel
        content_md = md_path.read_text(encoding="utf-8")
        first_h1 = re.search(r"^#\s+(.+)$", content_md, re.MULTILINE)
        page_title = first_h1.group(1).strip() if first_h1 else file_title(md_path)
        breadcrumb = f'<a href="/">Home</a> / <a href="/{section_name}/">{section_name.title()}</a> / {page_title}'
        render_md(md_path, out_path, section_name, breadcrumb)
        rendered_count += 1
        rel_url = f"/{section_name}/{out_rel.as_posix()}"
        section_pages[section_name].append((page_title, rel_url, str(rel)))

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

print(f"  Rendered {rendered_count} HTML pages with link rewriting")
PYEOF

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
