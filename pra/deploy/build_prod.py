#!/usr/bin/env python3
"""Build the production copy of the site from the review copy.

    python3 pra/deploy/build_prod.py pra/site pra/_prod

The review copy carries a noindex tag, a "Design concept for review" footer label, a review note on
the policies page and a robots.txt that blocks everything. The production copy drops all four and
adds a sitemap.
"""
import shutil
import sys
from pathlib import Path

ORIGIN = "https://www.pacificriskadvisors.com"
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(src, dst)

REMOVE = [
    '<meta name="robots" content="noindex, nofollow">\n',
    '    <span class="sp mono">Design concept for review</span>\n',
]
pages = []
for page in sorted(dst.glob("*.html")):
    html = page.read_text(encoding="utf-8")
    for fragment in REMOVE:
        if fragment not in html:
            sys.exit(f"{page.name}: expected review marker not found: {fragment.strip()}")
        html = html.replace(fragment, "")
    if page.name == "legal.html":
        start = html.index('<p class="review-note">')
        end = html.index("</p>", start) + len("</p>")
        html = html[:start] + html[end:]
        html = html.replace("Draft added November 2026", "Added November 2026")
    html = html.replace('content="assets/og.png"', f'content="{ORIGIN}/assets/og.png"')
    if "noindex" in html or "for review" in html.lower():
        sys.exit(f"{page.name}: review wording still present")
    page.write_text(html, encoding="utf-8")
    pages.append("" if page.name == "index.html" else page.name)

(dst / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {ORIGIN}/sitemap.xml\n", encoding="utf-8")
urls = "".join(f"  <url><loc>{ORIGIN}/{p}</loc></url>\n" for p in pages)
(dst / "sitemap.xml").write_text(
    f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n',
    encoding="utf-8")
print(f"production copy written to {dst}: {len(pages)} pages")
