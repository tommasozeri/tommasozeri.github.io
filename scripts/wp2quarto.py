#!/usr/bin/env python3
"""Convert a WordPress WXR export into Quarto .qmd pages.

Usage: python scripts/wp2quarto.py export.xml [--out .]

Re-running overwrites research/, notes/, blog/ pages generated from the export.
"""
import argparse
import html
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from posts import POSTS  # noqa: E402

NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}
AUTHOR = "Tommaso Zeri"
BLOCK_RE = re.compile(r"<!-- wp:([a-z0-9\-/]+)(\s+\{.*?\})?\s*(/)?-->", re.S)


def pandoc_md(fragment: str) -> str:
    fragment = re.sub(r"(<br\s*/?>\s*){2,}", "</p><p>", fragment)
    out = subprocess.run(
        ["pandoc", "-f", "html", "-t",
         "markdown-raw_html-native_divs-native_spans-header_attributes"
         "-link_attributes-bracketed_spans-fenced_divs+pipe_tables",
         "--wrap=none"],
        input=fragment, capture_output=True, text=True, check=True,
    ).stdout
    return out.strip()


def top_blocks(body: str):
    """Yield (name, attrs, inner_html) for top-level Gutenberg blocks."""
    pos = 0
    while True:
        m = BLOCK_RE.search(body, pos)
        if not m:
            break
        between = re.sub(r"<!-- /wp:[^>]*-->", "", body[pos:m.start()]).strip()
        if between:
            yield ("raw", {}, between)
        name, attrs, selfclose = m.group(1), m.group(2), m.group(3)
        attrs = json.loads(attrs) if attrs else {}
        if selfclose:
            yield (name, attrs, "")
            pos = m.end()
            continue
        close = f"<!-- /wp:{name} -->"
        open_pat = re.compile(rf"<!-- wp:{re.escape(name)}[\s>]")
        level, i = 1, m.end()
        while level:
            c = body.find(close, i)
            if c < 0:
                c = len(body)
                level = 0
                i = c
                break
            o = open_pat.search(body, i)
            if o and o.start() < c:
                level += 1
                i = o.end()
            else:
                level -= 1
                i = c + len(close)
        yield (name, attrs, body[m.end():i - len(close)])
        pos = i
    tail = re.sub(r"<!-- /wp:[^>]*-->", "", body[pos:]).strip()
    if tail:
        yield ("raw", {}, tail)


def text_of(fragment: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(fragment, "html.parser").get_text(" ")).strip()


def clean_html_block(fragment: str) -> str:
    soup = BeautifulSoup(fragment, "html.parser")
    for tag in soup.find_all(True):
        for a in ("style", "class", "id"):
            tag.attrs.pop(a, None)
    return str(soup)


def img_url(u: str) -> str:
    return re.sub(r"\?.*$", "", u)


def convert_post(item):
    body = item.find("content:encoded", NS).text or ""
    pdfs, code_urls, chunks, texts = [], [], [], []
    skip_next_code_heading = False
    byline = []
    blocks = list(top_blocks(body))

    # drop malformed duplicate paragraphs (WordPress editor leftovers)
    ptexts = [text_of(b[2]) if b[0] == "paragraph" else None for b in blocks]
    drop = set()
    for i, t in enumerate(ptexts):
        if not t:
            continue
        nxt = next((ptexts[j] for j in range(i + 1, len(blocks)) if ptexts[j]), None)
        prv = next((ptexts[j] for j in range(i - 1, -1, -1) if ptexts[j] and j not in drop), None)
        if nxt and t.startswith(nxt) and len(t) > 3 * len(nxt):
            drop.add(i)  # truncated copy of the whole post
        elif prv and t in prv and len(t) < len(prv):
            drop.add(i)  # sentence repeated from previous paragraph

    for i, (name, attrs, inner) in enumerate(blocks):
        if i in drop:
            continue
        if name in ("post-terms", "group", "columns", "column", "details", "raw"):
            if name == "raw" and text_of(inner):
                chunks.append(pandoc_md(inner))
            continue
        if name == "file":
            href = attrs.get("href") or ""
            if href.lower().endswith(".pdf"):
                pdfs.append(href)
            continue
        if name == "embed":
            url = attrs.get("url", "")
            if "github.com" in url:
                code_urls.append(url)
            elif "codepen.io" in url:
                chunks.append(codepen(url))
            else:
                url = html.unescape(url).split("?")[0]
                chunks.append(f"<{url}>")
            continue
        if name == "shortcode":
            m = re.search(r"\[embed\](.*?)\[/embed\]", inner)
            if m and "codepen.io" in m.group(1):
                chunks.append(codepen(m.group(1)))
            continue
        if name == "math":
            chunks.append("$$\n" + attrs["latex"] + "\n$$")
            continue
        if name in ("code", "syntaxhighlighter/code"):
            code = BeautifulSoup(inner, "html.parser").get_text()
            if not code.strip():
                continue
            lang = "vb" if re.search(r"\bDim\b|\bFunction\b.*\bAs\b", code) else ""
            chunks.append(f"```{lang}\n{code.rstrip()}\n```")
            continue
        if name == "image":
            soup = BeautifulSoup(inner, "html.parser")
            img = soup.find("img")
            if img:
                cap = soup.find("figcaption")
                alt = cap.get_text(" ").strip() if cap else (img.get("alt") or "")
                chunks.append(f"![{alt}]({img_url(img['src'])})")
            continue
        if name == "html":
            md = pandoc_md(clean_html_block(inner))
            if md:
                chunks.append(md)
            continue
        if name in ("paragraph", "heading", "list", "quote", "table", "separator"):
            t = text_of(inner)
            m = re.match(r"^Tommaso Zeri\s*[—–-]\s*(.+)$", t)
            if name == "paragraph" and m and len(t) < 120:
                byline.append(m.group(1).replace(" | ", ", "))
                continue
            if name == "heading" and t.lower() in ("code repository", "code", "repository"):
                skip_next_code_heading = True
                continue
            gh = re.findall(r"https://github\.com/[^\s\"<]+", inner)
            if gh and len(re.sub(r"https?://\S+|[.\s]", "", t)) == 0:
                code_urls += gh
                continue
            if not t and name != "separator":
                continue
            md = pandoc_md(inner)
            if name == "heading":
                md = re.sub(r"^#+", lambda m: "#" * max(2, len(m.group(0))), md)
            chunks.append(md)
            if name == "paragraph":
                texts.append(t)
            continue
        # unknown block: best effort
        if text_of(inner):
            chunks.append(pandoc_md(inner))
    return chunks, pdfs, list(dict.fromkeys(code_urls)), texts, byline


def codepen(url: str) -> str:
    m = re.search(r"codepen\.io/([^/]+)/pen/([^/?#]+)", url)
    user, pen = m.group(1), m.group(2)
    src = f"https://codepen.io/{user}/embed/{pen}?default-tab=result"
    return (f'```{{=html}}\n<iframe class="embed" height="520" style="width:100%" '
            f'src="{src}" title="Interactive visualization" loading="lazy" '
            f'allowfullscreen></iframe>\n```')


def description(texts):
    for t in texts:
        if len(t) > 80 and "Riot Investment Society |" not in t:
            s = re.split(r"(?<=[.!?])\s", t)
            d = ""
            for sent in s:
                if len(d) + len(sent) > 380 and len(d) > 140:
                    break
                d += (" " if d else "") + sent
            return d
    return ""


def yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xml")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    out = Path(a.out)
    root = ET.parse(a.xml).getroot()
    attachments = {
        it.find("wp:post_id", NS).text: it.find("wp:attachment_url", NS).text
        for it in root.iter("item")
        if it.find("wp:post_type", NS).text == "attachment"
    }
    seen = set()
    for item in root.iter("item"):
        if item.find("wp:post_type", NS).text != "post":
            continue
        if item.find("wp:status", NS).text != "publish":
            continue
        wpname = item.find("wp:post_name", NS).text
        if wpname not in POSTS:
            print("UNMAPPED:", wpname, file=sys.stderr)
            continue
        seen.add(wpname)
        section, slug, lang, cats = POSTS[wpname]
        title = re.sub(r"\s+", " ", html.unescape(item.find("title").text)).strip()
        date = item.find("wp:post_date", NS).text[:10]
        chunks, pdfs, codes, texts, byline = convert_post(item)
        thumb = None
        for m in item.findall("wp:postmeta", NS):
            if m.find("wp:meta_key", NS).text == "_thumbnail_id":
                thumb = attachments.get(m.find("wp:meta_value", NS).text)
        desc = description(texts)

        fm = [
            "---",
            f"title: {yaml_str(title)}",
        ] + ([f"subtitle: {yaml_str(byline[0])}"] if byline else []) + [
            f"author: {AUTHOR}",
            f"date: {date}",
        ] + ([f"image: {img_url(thumb)}"] if thumb else []) + [
            f"lang: {lang}",
            f"idioma: {'Italiano' if lang == 'it' else 'English'}",
            "categories: [" + ", ".join(cats) + "]",
        ]
        if desc:
            fm.append(f"description: {yaml_str(desc)}")
        if pdfs:
            fm.append(f"pdf: {pdfs[0]}")
        if codes:
            fm.append(f"code: {codes[0]}")
        if section == "research":
            fm += ["citation:", "  type: report"]
            if pdfs:
                fm.append(f"  pdf-url: {pdfs[0]}")
            fm.append("google-scholar: true")
        fm.append(f"wordpress: {item.find('link').text}")
        fm.append("---")

        links = []
        if pdfs:
            links.append(f'<a class="btn-paper" href="{pdfs[0]}">PDF</a>')
        for c in codes:
            links.append(f'<a class="btn-paper" href="{c}">Code</a>')
        if section == "research":
            links.append('<a class="btn-paper" href="#quarto-citation">Cite</a>')
        head = []
        if links:
            head = ["```{=html}", '<p class="paper-links">' + " ".join(links) + "</p>", "```"]
        tail = []
        if pdfs:
            tail = ["", "## Full text" if lang == "en" else "## Testo completo", "",
                    "```{=html}",
                    f'<object class="pdf-viewer" data="{pdfs[0]}" type="application/pdf">'
                    f'<p><a href="{pdfs[0]}">Download PDF</a></p></object>',
                    "```"]
        doc = "\n".join(fm) + "\n\n" + "\n".join(head) + "\n\n" + "\n\n".join(chunks) + "\n" + "\n".join(tail) + "\n"
        dest = out / section / slug / "index.qmd"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(doc, encoding="utf-8")
        print(f"{section:9s} {slug}")
    missing = set(POSTS) - seen
    if missing:
        print("MISSING in export:", missing, file=sys.stderr)


if __name__ == "__main__":
    main()
