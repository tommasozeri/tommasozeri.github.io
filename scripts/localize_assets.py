#!/usr/bin/env python3
"""Download files still hosted on wordpress.com and point pages at the local copy.

Each file is saved next to the page that uses it (research/<slug>/paper.pdf),
so PDFs are served from the same domain as the page, which Google Scholar
expects. Safe to re-run: already-local links are left alone.

Usage: python scripts/localize_assets.py [--dry-run]
"""
import argparse
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WP_URL = re.compile(r"https://[a-z0-9\-]+\.wordpress\.com/wp-content/uploads/[^\s\"')>\]]+")


def save_cover(data: bytes, dest: Path, width: int = 800):
    """Shrink cover images (WordPress originals are several MB) to a light JPEG."""
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(dest, "JPEG", quality=82, optimize=True, progressive=True)


def site_url() -> str:
    m = re.search(r"^\s*site-url:\s*(\S+)", (ROOT / "_quarto.yml").read_text(), re.M)
    return m.group(1).rstrip("/") if m else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    failures = 0
    for qmd in sorted(ROOT.glob("*/*/index.qmd")):
        text = qmd.read_text(encoding="utf-8")
        urls = sorted(set(WP_URL.findall(text)))
        if not urls:
            continue
        cover_m = re.search(r"^image:\s*(\S+)$", text, re.M)
        cover_url = cover_m.group(1) if cover_m else None
        for url in urls:
            name = url.rsplit("/", 1)[-1]
            if url == cover_url:
                name = "cover.jpg"
            dest = qmd.parent / name
            print(f"{qmd.parent.relative_to(ROOT)}: {name}")
            if a.dry_run:
                text = text.replace(url, name)
                continue
            if not dest.exists():
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=120) as r:
                        data = r.read()
                    if name == "cover.jpg":
                        save_cover(data, dest)
                    else:
                        dest.write_bytes(data)
                except Exception as e:  # keep the remote link if download fails
                    print(f"  FAILED: {e}", file=sys.stderr)
                    failures += 1
                    continue
            text = text.replace(url, name)
        # Google Scholar wants an absolute citation_pdf_url
        page_url = f"{site_url()}/{qmd.parent.relative_to(ROOT).as_posix()}/"
        text = re.sub(r"^(  pdf-url: )(?!https?://)(\S+)$",
                      lambda m: m.group(1) + page_url + m.group(2), text, flags=re.M)
        if not a.dry_run:
            qmd.write_text(text, encoding="utf-8")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
