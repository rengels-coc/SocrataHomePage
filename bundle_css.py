#!/usr/bin/env python3
"""
CSS Bundler Script

Purpose:
  Concatenate the large set of extracted CSS fragments (generated from the MHTML
  snapshot) into a single, human-readable, well‑commented stylesheet
  (assets/combined.css) while:
    * Preserving original load order (to keep cascade behavior the same)
    * Removing duplicate identical blocks when safe
    * De‑duplicating @charset declarations (keep only first)
    * Annotating each source file with a banner comment so you can trace origins
    * Optionally skipping obviously empty or whitespace‑only files

Usage:
  python bundle_css.py [--minify] [--no-dedupe]

Outputs:
  assets/combined.css   (Pretty, commented)
  assets/combined.min.css (Optional, if --minify provided)

Why not just delete the many files?
  The original portal splits CSS for lazy loading / feature flag isolation.
  After snapshotting, they all became first-class <link> tags. Merging reduces
  HTTP requests and cognitive overhead while documentation inside the combined
  file preserves traceability.

Limitations:
  * This is a static concatenator; it does not resolve url(...) paths or inline
    assets beyond preserving them verbatim.
  * If two files redefine the same selector later, the *later* one will still
    win. That's why we retain source order exactly.

"""
from __future__ import annotations
import re
import argparse
from pathlib import Path
import hashlib

INDEX_FILE = Path('index.html')
ASSETS_DIR = Path('assets')
OUTPUT = ASSETS_DIR / 'combined.css'              # legacy name (uuid fragments originally)
FULL_OUTPUT = ASSETS_DIR / 'combined_all.css'      # new comprehensive bundle
MIN_OUTPUT = ASSETS_DIR / 'combined.min.css'
MANIFEST_JSON = ASSETS_DIR / 'css-manifest.json'

# Regex helpers to capture every local stylesheet link with order + media.
LINK_TAG_RE = re.compile(r'<link[^>]*?>', re.IGNORECASE)
REL_RE = re.compile(r'rel\s*=\s*"stylesheet"', re.IGNORECASE)
HREF_RE = re.compile(r'href\s*=\s*"(assets/[^" >]+\.css(?:\.css)?)"', re.IGNORECASE)
MEDIA_RE = re.compile(r'media\s*=\s*"([^"]+)"', re.IGNORECASE)
CHARSET_RE = re.compile(r'@charset\s+"[^"]+";')
COMMENT_BANNER = """/*====================================================================\n Source: {path}\n SHA256: {sha}\n Size: {size} bytes\n====================================================================*/\n"""

CSS_COMMENT_CLEAN_RE = re.compile(r'/\*![\s\S]*?\*/')  # preserve important comments starting with /*! if desired later


def extract_links(index_html: str):
    """Return ordered list of dicts {href, media, order} for every local stylesheet.
    Includes platform & uuid files. Order is head order to preserve cascade."""
    out = []
    order = 0
    for tag in LINK_TAG_RE.findall(index_html):
        if not REL_RE.search(tag):
            continue
        href_m = HREF_RE.search(tag)
        if not href_m:
            continue
        href = href_m.group(1)
        media_m = MEDIA_RE.search(tag)
        media = media_m.group(1).strip() if media_m else None
        out.append({'href': href, 'media': media, 'order': order})
        order += 1
    return out


def load_css(path: str) -> str:
    p = Path(path)
    try:
        text = p.read_text(encoding='utf-8', errors='replace')
    except FileNotFoundError:
        return f"/* Missing file referenced in HTML: {path} */\n"
    return text


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def dedupe_blocks(chunks: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Very conservative dedupe: if entire file content (post trivial trim)
    matches a previous file, drop it (leave a reference comment instead)."""
    seen = {}
    result = []
    for path, content in chunks:
        key = hash_text(content.strip())
        if key in seen:
            result.append((path, f"/* Skipped duplicate content: identical to {seen[key]} */\n"))
        else:
            seen[key] = path
            result.append((path, content))
    return result


def strip_redundant_charsets(css: str) -> str:
    first = True
    pieces = []
    for token in CHARSET_RE.split(css):
        # CHARSET_RE.split removes the matches; we need a different approach.
        pass
    # Simpler approach: iterate matches and rebuild
    out = []
    idx = 0
    for m in CHARSET_RE.finditer(css):
        if m.start() > idx:
            out.append(css[idx:m.start()])
        if first:
            out.append(m.group(0))
            first = False
        else:
            out.append(f"/* removed duplicate {m.group(0).strip()} */")
        idx = m.end()
    out.append(css[idx:])
    return ''.join(out)


def maybe_minify(css: str) -> str:
    # Very light minification: remove comments (non-important) & collapse whitespace
    css_no_comments = re.sub(r'/\*[^!][\s\S]*?\*/', '', css)
    css_no_ws = re.sub(r'\s+', ' ', css_no_comments)
    css_no_ws = re.sub(r' ?([{};:,]) ?', r'\1', css_no_ws)
    return css_no_ws.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--minify', action='store_true', help='Also produce a minified combined.min.css')
    ap.add_argument('--no-dedupe', action='store_true', help='Do not skip duplicate full-file contents')
    args = ap.parse_args()

    html = INDEX_FILE.read_text(encoding='utf-8', errors='replace')
    links = extract_links(html)
    if not links:
        print('No CSS <link rel="stylesheet"> tags found.')
        return

    chunks: list[tuple[str, str, str | None]] = []  # path, content, media
    manifest = []
    for link in links:
        path = link['href']
        media = link['media']
        content = load_css(path)
        chunks.append((path, content, media))
        manifest.append({'href': path, 'media': media, 'order': link['order'], 'bytes': len(content.encode('utf-8'))})

    if not args.no_dedupe:
        base_pairs = [(p, c) for (p, c, _m) in chunks]
        deduped = dedupe_blocks(base_pairs)
        rebuilt = []
        for (orig_p, _orig_c, media), (new_p, new_c) in zip(chunks, deduped):
            rebuilt.append((orig_p, new_c, media))
        chunks = rebuilt

    assembled_parts = []
    emitted_charset = False
    for path, content, media in chunks:
        # Normalize CRLF -> LF
        content = content.replace('\r\n', '\n')
        # Extract and manage @charset declarations
        charsets = CHARSET_RE.findall(content)
        if charsets:
            # Remove them all, then add the first if we haven't yet
            content_wo = CHARSET_RE.sub('', content)
            if not emitted_charset:
                assembled_parts.append(charsets[0])
                emitted_charset = True
            else:
                # record removal
                assembled_parts.append(f"/* Duplicate {charsets[0].strip()} removed */")
            content = content_wo
        banner = COMMENT_BANNER.format(path=path + (f" (media={media})" if media else ''), sha=hash_text(content), size=len(content.encode('utf-8')))
        if media and media.lower() not in (None, 'all', 'screen'):
            wrapped = f"@media {media} {{\n{content.strip()}\n}}"
            assembled_parts.append(banner + wrapped + '\n')
        else:
            assembled_parts.append(banner + content.strip() + '\n')

    combined = '\n'.join(assembled_parts)
    combined = strip_redundant_charsets(combined)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(combined, encoding='utf-8')  # maintain legacy name
    FULL_OUTPUT.write_text(combined, encoding='utf-8')
    print(f'Wrote {FULL_OUTPUT} ({FULL_OUTPUT.stat().st_size} bytes) from {len(chunks)} source files.')
    print(f'Also updated legacy {OUTPUT}.')

    # Manifest JSON
    import json
    MANIFEST_JSON.write_text(json.dumps({'files': manifest}, indent=2), encoding='utf-8')
    print(f'Wrote manifest {MANIFEST_JSON}')

    if args.minify:
        MIN_OUTPUT.write_text(maybe_minify(combined), encoding='utf-8')
        print(f'Wrote {MIN_OUTPUT} ({MIN_OUTPUT.stat().st_size} bytes)')

if __name__ == '__main__':
    main()
