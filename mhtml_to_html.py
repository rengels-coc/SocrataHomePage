#!/usr/bin/env python3
"""
Convert an MHTML (MIME HTML) file into a standalone HTML file with local assets.
- Extracts the first text/html part as the main HTML.
- Saves related parts (images, css, js, etc.) to an assets/ folder.
- Rewrites references in the HTML from cid: and Content-Location URLs to local asset paths when present in the archive.
- Also rewrites root-relative references (e.g., /views/...) to absolute URLs on the original host to avoid missing backgrounds.
- Additionally rewrites CSS file contents to point to local assets or absolute URLs; prefers local when available.

Usage:
  python mhtml_to_html.py "City of Seattle Open Data portal.mhtml" portal.html assets
"""

from __future__ import annotations
import os
import re
import sys
import pathlib
import mimetypes
from email import policy
from email.parser import BytesParser
from urllib.parse import urlparse


ORIGIN = "https://data.seattle.gov"  # Used for root-relative URL rewriting


def safe_name(name: str) -> str:
    # Keep simple safe characters
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    name = re.sub(r"_+", "_", name).strip("._")
    return name or "file"


def ext_for_mime(mime: str) -> str:
    # Prefer known, else guess
    known = {
        'text/css': '.css',
        'application/javascript': '.js',
        'text/javascript': '.js',
        'image/png': '.png',
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/gif': '.gif',
        'image/svg+xml': '.svg',
        'font/woff2': '.woff2',
        'font/woff': '.woff',
        'font/ttf': '.ttf',
        'application/font-woff2': '.woff2',
        'application/font-woff': '.woff',
    }
    if mime in known:
        return known[mime]
    guess = mimetypes.guess_extension(mime or '')
    return guess or ''


def pick_filename(part, used: set[str]) -> str:
    # Use Content-Location basename if present
    loc = part.get('Content-Location')
    cid = part.get('Content-ID')
    ctype = part.get_content_type()

    base = None
    if loc:
        parsed = urlparse(loc)
        base_candidate = os.path.basename(parsed.path) or safe_name(parsed.netloc)
        base = safe_name(base_candidate)
    if not base and cid:
        cid_clean = cid.strip('<>')
        base = safe_name(cid_clean)

    if not base:
        base = 'asset'

    ext = ext_for_mime(ctype)
    filename = base + ext
    i = 1
    while filename in used:
        filename = f"{base}_{i}{ext}"
        i += 1
    used.add(filename)
    return filename


def build_replacements(parts_info):
    # Map both cid: and Content-Location URLs to local asset paths
    # Also add path-only variant for entries under the same origin
    repl = {}
    for info in parts_info:
        local = info['local_path']
        cid = info.get('cid')
        loc = info.get('location')
        if cid:
            repl[f"cid:{cid}"] = local
        if loc:
            repl[loc] = local
            try:
                parsed = urlparse(loc)
                if parsed.scheme in ("http", "https") and parsed.netloc == urlparse(ORIGIN).netloc:
                    path_key = parsed.path
                    if path_key:
                        repl[path_key] = local
            except Exception:
                pass
    # Sort keys by length desc to avoid partial overlaps when replacing
    keys = sorted(repl.keys(), key=len, reverse=True)
    return keys, repl


def rewrite_root_relative_urls_in_html(html: str, origin: str) -> str:
    # Attribute-based root-relative URLs: href="/...", src="/...", action="/..."
    def repl_attr(m):
        attr = m.group(1)
        quote = m.group(2)
        path = m.group(3)
        if path.startswith('/') and not path.startswith('//'):
            return f"{attr}={quote}{origin}{path}{quote}"
        return m.group(0)

    html = re.sub(r"\b(href|src|action)=(['\"])\/(?!\/)([^'\"]*)\2",
                  lambda m: repl_attr(m), html)

    # Inline CSS url(/...) where quotes are literal or HTML-entity encoded
    def repl_css(m):
        openp = m.group(1)
        path = m.group(2)
        closep = m.group(3)
        if path.startswith('/') and not path.startswith('//'):
            return f"url({openp}{origin}{path}{closep})"
        return m.group(0)

    html = re.sub(r"url\((['\"]?)(\/[^'\")]+)(['\"]?)\)", lambda m: repl_css(m), html)
    # Handle entity-encoded quotes inside style attributes: url(&quot;/...&quot;)
    html = re.sub(r"url\((&quot;)(\/[^&]+)(&quot;)\)", lambda m: f"url(&quot;{origin}{m.group(2)}&quot;)", html)
    return html


def rewrite_urls_in_css(css_text: str, keys, repl_map, origin: str) -> str:
    # First, map known absolute and path keys to local paths
    for k in keys:
        if k in css_text:
            css_text = css_text.replace(k, repl_map[k])
    # Then, rewrite any remaining root-relative url(/...) to absolute origin
    def repl_css(m):
        openp = m.group(1)
        path = m.group(2)
        closep = m.group(3)
        if path.startswith('/') and not path.startswith('//'):
            return f"url({openp}{origin}{path}{closep})"
        return m.group(0)
    css_text = re.sub(r"url\((['\"]?)(\/[^'\")]+)(['\"]?)\)", lambda m: repl_css(m), css_text)
    return css_text


def convert(mhtml_path: str, out_html_path: str, assets_dir: str):
    mhtml_path = os.path.abspath(mhtml_path)
    out_html_path = os.path.abspath(out_html_path)
    assets_dir = os.path.abspath(assets_dir)

    os.makedirs(os.path.dirname(out_html_path), exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)

    with open(mhtml_path, 'rb') as f:
        msg = BytesParser(policy=policy.default).parse(f)

    if msg.is_multipart():
        parts = list(msg.walk())
    else:
        parts = [msg]

    html_text = None
    assets = []
    used_names = set()

    css_assets_indices = []

    for idx, part in enumerate(parts):
        ctype = part.get_content_type()
        if ctype == 'text/html' and html_text is None:
            payload = part.get_payload(decode=True) or b''
            charset = part.get_content_charset() or 'utf-8'
            try:
                html_text = payload.decode(charset, errors='replace')
            except LookupError:
                html_text = payload.decode('utf-8', errors='replace')
            continue

        if part.is_multipart():
            continue

        # Skip the container message itself (has no Content-Type or irrelevant)
        if not ctype or ctype in ('text/plain',):
            continue

        payload = part.get_payload(decode=True)
        if payload is None:
            continue

        filename = pick_filename(part, used_names)
        local_path = os.path.join(assets_dir, filename)
        with open(local_path, 'wb') as outf:
            outf.write(payload)

        asset_info = {
            'content_type': ctype,
            'local_path': os.path.relpath(local_path, os.path.dirname(out_html_path)).replace('\\', '/'),
            'cid': (part.get('Content-ID') or '').strip('<>') or None,
            'location': part.get('Content-Location') or None,
        }
        assets.append(asset_info)
        if ctype == 'text/css':
            css_assets_indices.append(len(assets) - 1)

    if html_text is None:
        raise SystemExit('No text/html part found in MHTML file')

    # Build replacement map (includes origin path variants)
    keys, repl = build_replacements(assets)

    # Replace references to embedded parts in HTML
    rewritten = html_text
    for k in keys:
        rewritten = rewritten.replace(k, repl[k])

    # Rewrite root-relative references to absolute origin for any remaining resources
    rewritten = rewrite_root_relative_urls_in_html(rewritten, ORIGIN)

    # Post-process CSS files to fix their internal url() references
    for i in css_assets_indices:
        css_local_path = os.path.join(os.path.dirname(out_html_path), assets[i]['local_path'])
        try:
            raw = pathlib.Path(css_local_path).read_bytes()
            try:
                css_text = raw.decode('utf-8')
            except UnicodeDecodeError:
                css_text = raw.decode('latin-1', errors='replace')
            css_text = rewrite_urls_in_css(css_text, keys, repl, ORIGIN)
            pathlib.Path(css_local_path).write_text(css_text, encoding='utf-8')
        except Exception:
            # Best-effort: skip on failure
            pass

    # Write HTML out
    with open(out_html_path, 'w', encoding='utf-8') as outf:
        outf.write(rewritten)

    return out_html_path, assets_dir


def main(argv: list[str]):
    if len(argv) < 2 or len(argv) > 4:
        print("Usage: python mhtml_to_html.py <input.mhtml> [output.html] [assets_dir]", file=sys.stderr)
        return 2
    mhtml = argv[1]
    out_html = argv[2] if len(argv) >= 3 else os.path.splitext(mhtml)[0] + '.html'
    assets_dir = argv[3] if len(argv) >= 4 else 'assets'

    out_html_path, assets_dir_path = convert(mhtml, out_html, assets_dir)
    print(f"Wrote {out_html_path}\nAssets in {assets_dir_path}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
