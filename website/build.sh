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
  log "Copying JSON schemas to /schemas/v1/"
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
    ".github",
]

NON_RENDERED_REPO_FILES = [
    "README.md", "README.html",
    "CHANGELOG.md", "CHANGELOG.html",
    "LICENSE", "LICENSE.md",
    "LICENSE-MIT", "LICENSE-MIT.md",
    "LICENSE-CC-BY-4.0", "LICENSE-CC-BY-4.0.md",
    "NOTICE", "NOTICE.md",
    "CITATION.cff",
    "DEPLOYMENT.md", "DEPLOYMENT.html",
]

RELOCATED_REPO_DIRS = {
    "schemas/core": "/schemas/v1/core",
    "schemas/handshake": "/schemas/v1/handshake",
    "schemas/context": "/schemas/v1/context",
    "schemas": "/schemas/v1",
}

RENDERED_SECTIONS = {"spec", "guides", "governance"}

template = TEMPLATE_PATH.read_text(encoding="utf-8")

md = markdown.Markdown(
    extensions=[
        "fenced_code", "tables", "toc", "attr_list",
        "def_list", "abbr", "footnotes", "codehilite",
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

unresolved_links = []

def rewrite_links(html: str, source_section: str) -> str:
    def replace_non_rendered(match):
        href = match.group(1)
        stripped = re.sub(r"^(\.\./)+", "", href)
        for non_rendered in NON_RENDERED_REPO_DIRS:
            if stripped == non_rendered or stripped.startswith(non_rendered + "/"):
                if stripped.endswith("/") or "." not in stripped.split("/")[-1]:
                    return f'href="{GITHUB_REPO_BASE}{stripped}"'
                return f'href="{GITHUB_BLOB_BASE}{stripped}"'
        return match.group(0)

    html = re.sub(
        r'href="((?:\.\./)+(?:' + "|".join(NON_RENDERED_REPO_DIRS) + r')[^"]*)"',
        replace_non_rendered, html,
    )

    def replace_relocated(match):
        href = match.group(1)
        stripped = re.sub(r"^(\.\./)+", "", href)
        for src, dst in sorted(RELOCATED_REPO_DIRS.items(), key=lambda kv: -len(kv[0])):
            if stripped == src:
                return f'href="{dst}/"'
            if stripped.startswith(src + "/"):
                tail = stripped[len(src):]
                return f'href="{dst}{tail}"'
        return match.group(0)

    if RELOCATED_REPO_DIRS:
        relocated_pattern = (
            r'href="((?:\.\./)+(?:'
            + "|".join(re.escape(k) for k in RELOCATED_REPO_DIRS.keys())
            + r')[^"]*)"'
        )
        html = re.sub(relocated_pattern, replace_relocated, html)

    def replace_cross_section(match):
        href = match.group(1)
        stripped = re.sub(r"^(\.\./)+", "", href)
        for section in RENDERED_SECTIONS:
            if stripped == section or stripped.startswith(section + "/"):
                return f'href="/{stripped}"'
        return match.group(0)

    html = re.sub(
        r'href="((?:\.\./)+(?:' + "|".join(RENDERED_SECTIONS) + r')[^"]*)"',
        replace_cross_section, html,
    )

    def replace_root_file(match):
        href = match.group(1)
        stripped = re.sub(r"^(\.\./)+", "", href)
        base = re.split(r'[#?]', stripped)[0]
        github_path = base.replace(".html", ".md") if base.endswith(".html") else base
        if base in NON_RENDERED_REPO_FILES or github_path in NON_RENDERED_REPO_FILES:
            return f'href="{GITHUB_BLOB_BASE}{github_path}"'
        return match.group(0)

    html = re.sub(
        r'href="((?:\.\./)+(?:README|CHANGELOG|LICENSE|NOTICE|CITATION|DEPLOYMENT)[^"]*)"',
        replace_root_file, html,
    )

    html = re.sub(
        r'href="((?!https?://|mailto:|#)[^"]*?)\.md(#[^"]*)?"',
        lambda m: f'href="{m.group(1)}.html{m.group(2) or ""}"',
        html,
    )
    html = re.sub(
        r'href="(https?://aaep-protocol\.org/[^"]*?)\.md(#[^"]*)?"',
        lambda m: f'href="{m.group(1)}.html{m.group(2) or ""}"',
        html,
    )

    suspicious = re.findall(r'href="((?:\.\./)+[^"]+)"', html)
    for s in suspicious:
        unresolved_links.append((source_section, s))

    return html

def render_md(md_path: Path, out_path: Path, section: str, breadcrumb: str):
    md.reset()
    content_md = md_path.read_text(encoding="utf-8")
    first_h1 = re.search(r"^#\s+(.+)$", content_md, re.MULTILINE)
    page_title = first_h1.group(1).strip() if first_h1 else file_title(md_path)
    content_html = md.convert(content_md)
    content_html = rewrite_links(content_html, f"{section}/{md_path.name}")
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
    # Main /schemas/v1/ index listing every schema
    schema_files = sorted(list(schemas_dir.rglob("*.json")) + list(schemas_dir.rglob("*.jsonld")))
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

    # Per-subdirectory indexes for /schemas/v1/core/, /handshake/, /context/, etc.
    for subdir in sorted([d for d in schemas_dir.iterdir() if d.is_dir()]):
        sub_files = sorted(list(subdir.rglob("*.json")) + list(subdir.rglob("*.jsonld")))
        if not sub_files:
            continue
        sub_name = subdir.name
        sub_items = []
        for sf in sub_files:
            rel = sf.relative_to(subdir)
            sub_items.append(f'<li><a href="/schemas/v1/{sub_name}/{rel.as_posix()}">{rel.as_posix()}</a></li>')
        sub_items_html = "\n".join(sub_items)
        sub_content = f"""
<h1>JSON Schemas — {sub_name}</h1>
<p>AAEP v1 JSON Schemas in the <code>{sub_name}</code> category. Each schema's <code>$id</code> matches its URL on this site.</p>
<ul class="page-index">
{sub_items_html}
</ul>
<p><a href="/schemas/v1/">← Back to all schemas</a></p>
"""
        sub_breadcrumb = f'<a href="/">Home</a> / <a href="/schemas/v1/">Schemas v1</a> / {sub_name}'
        sub_output = (
            template
            .replace("{{PAGE_TITLE}}", f"Schemas v1: {sub_name}")
            .replace("{{SECTION}}", "schemas")
            .replace("{{BREADCRUMB}}", sub_breadcrumb)
            .replace("{{CONTENT}}", sub_content)
        )
        (subdir / "index.html").write_text(sub_output, encoding="utf-8")
        rendered_count += 1

redirect_count = 0
for src, dst in RELOCATED_REPO_DIRS.items():
    src_dir = DIST / src
    if (src_dir / "index.html").exists():
        continue
    src_dir.mkdir(parents=True, exist_ok=True)
    stub = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Redirecting to {dst}/ — AAEP</title>
<meta http-equiv="refresh" content="0; url={dst}/">
<link rel="canonical" href="{dst}/">
</head>
<body>
<main>
<p>This page has moved to <a href="{dst}/">{dst}/</a>.</p>
</main>
</body>
</html>"""
    (src_dir / "index.html").write_text(stub, encoding="utf-8")
    redirect_count += 1

print(f"  Rendered {rendered_count} HTML pages")
print(f"  Generated {redirect_count} redirect stubs")

if unresolved_links:
    print(f"\n  ⚠ {len(unresolved_links)} suspicious link(s) remain:")
    for section, link in unresolved_links[:20]:
        print(f"      {section}: {link}")
    if len(unresolved_links) > 20:
        print(f"      ... and {len(unresolved_links) - 20} more")
else:
    print("  ✓ All internal links resolved")
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