#!/usr/bin/env python3
"""Turn a LaTeX paper into the full-text body of a Quarto page on the site.

    tex2page.py MAIN.tex PAGE_DIR [--lang en|it] [--pandoc PATH]

PAGE_DIR/index.qmd keeps its front matter (title, date, categories, image, pdf,
code, citation ...); the body is replaced by the full text of the paper, with
figures copied into PAGE_DIR/figures, TikZ drawn as SVG, the bibliography
copied next to the page, and the PDF download block at the end.
"""
import argparse
from html import unescape as html_unescape
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("main")
ap.add_argument("page")
ap.add_argument("--pandoc", default="pandoc")
a = ap.parse_args()
MAIN = Path(a.main).resolve()
SRC = MAIN.parent
PAGE = Path(a.page).resolve()
FIG = PAGE / "figures"
import tempfile
WORK = Path(tempfile.mkdtemp(prefix="tex2page_"))
if FIG.exists():
    shutil.rmtree(FIG)
FIG.mkdir(parents=True)
log = []


# ---------------------------------------------------------------- read source
def strip_comments(t):
    return re.sub(r"(?<!\\)%.*", "", t)


def expand(t, base, depth=0):
    def inc(m):
        name = m.group(2).strip()
        for cand in (base / name, base / (name + ".tex")):
            if cand.is_file():
                return expand(strip_comments(cand.read_text(errors="ignore")), base, depth + 1)
        log.append(f"missing input {name}")
        return ""
    if depth > 5:
        return t
    return re.sub(r"\\(input|include)\{([^}]+)\}", inc, t)


raw = expand(strip_comments(MAIN.read_text(errors="ignore")), SRC)
i0 = raw.index("\\begin{document}")
pre, body = raw[:i0], raw[i0 + len("\\begin{document}"):]
body = body.split("\\end{document}")[0]

# abstract -> front matter
abstract = ""
m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", body, re.S)
if m:
    abstract = m.group(1)
    body = body.replace(m.group(0), "")
else:  # "\section*{Abstract} ..." up to the next section
    m = re.search(r"\\(?:section|subsection|paragraph)\*?\{\s*(?:Abstract|Sommario)\s*\}(.*?)(?=\\(?:section|chapter)|\\tableofcontents|\\newpage|\\clearpage)", body, re.S | re.I)
    if m:
        abstract = m.group(1)
        body = body.replace(m.group(0), "")

# title page material that does not belong in the web body
for pat in [r"\\maketitle", r"\\tableofcontents", r"\\listoffigures", r"\\listoftables",
            r"\\begin\{titlepage\}.*?\\end\{titlepage\}", r"\\begin\{frontmatter\}.*?\\end\{frontmatter\}",
            r"\\(?:newpage|clearpage|cleardoublepage|pagebreak|thispagestyle\{[^}]*\}|pagenumbering\{[^}]*\})",
            r"\\addcontentsline\{[^}]*\}\{[^}]*\}\{[^}]*\}", r"\\phantomsection",
            r"\\bibliographystyle\{[^}]*\}", r"\\vspace\*?\{[^}]*\}", r"\\hspace\*?\{[^}]*\}",
            r"\\(?:noindent|centering|raggedright|small|footnotesize|scriptsize|normalsize|large|Large|LARGE|huge|Huge)\b",
            r"\\FloatBarrier", r"\\appendix"]:
    body = re.sub(pat, "", body, flags=re.S)
# a title block hand-made with \begin{center}...\end{center} before the first section
first = re.search(r"\\(chapter|section)\*?\{", body)
if first:
    head = body[:first.start()]
    if re.search(r"\\begin\{center\}", head) and len(re.sub(r"\\[a-zA-Z]+|[{}\s]", "", head)) < 1500:
        body = body[first.start():]

# --------------------------------------------------------------- bibliography
bibs = []
for m in re.finditer(r"\\(?:bibliography|addbibresource)\{([^}]+)\}", raw):
    for name in m.group(1).split(","):
        name = name.strip()
        for cand in (SRC / name, SRC / (name + ".bib")):
            if cand.is_file() and (cand.suffix == ".bib" or cand.read_text(errors="ignore").lstrip().startswith("@")):
                bibs.append(cand)
                break
if not bibs and re.search(r"\\(?:bibliography|addbibresource)\{", raw):
    # the .bib named in the source is missing: use any BibTeX-looking file in the project
    bibs = [f for f in SRC.iterdir() if f.is_file() and f.suffix in (".bib", ".tex", ".txt")
            and f.read_text(errors="ignore").lstrip().startswith("@")]
body = re.sub(r"\\(?:bibliography|printbibliography|addbibresource)(\[[^\]]*\])?\{?[^}\n]*\}?", "", body)
bib_names = []
for k, b in enumerate(dict.fromkeys(bibs)):
    nm = "references.bib" if k == 0 else f"references{k}.bib"
    shutil.copy(b, PAGE / nm)
    bib_names.append(nm)

# ----------------------------------------------------------------- figures
gpaths = [SRC] + [SRC / g for g in re.findall(r"\{([^{}]+/)\}", " ".join(re.findall(r"\\graphicspath\{(.*?)\}\s*$", pre, re.M)))]
EXTS = ["", ".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg", ".PNG", ".JPG", ".PDF"]


def find_img(name):
    p = _find_img(name)
    if p and p.suffix.lower() in (".pdf", ".eps"):
        for e in (".png", ".jpg", ".jpeg"):
            if p.with_suffix(e).is_file():
                return p.with_suffix(e)
    return p


def _find_img(name):
    noext = re.sub(r"\.(pdf|png|jpe?g|eps|svg)$", "", name, flags=re.I)
    for g in gpaths:
        for nm in (name, noext):
            for e in EXTS:
                p = g / (nm + e)
                if p.is_file():
                    return p
    stem = Path(noext).name.lower()
    hits = [p for p in SRC.rglob("*") if p.is_file() and p.stem.lower() == stem
            and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg")]
    hits.sort(key=lambda p: (p.suffix.lower() not in (".png", ".jpg", ".jpeg"), len(str(p))))
    return hits[0] if hits else None


n_img = 0


def img(m):
    global n_img
    name = m.group(2).strip()
    p = find_img(name)
    if not p:
        log.append(f"missing figure {name}")
        return ""
    n_img += 1
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", p.stem).strip("-").lower() or f"fig{n_img}"
    if p.suffix.lower() == ".pdf":
        out = FIG / f"{slug}.png"
        if not out.exists():
            subprocess.run(["pdftocairo", "-png", "-r", "160", "-singlefile", "-f", "1", "-l", "1",
                            str(p), str(out.with_suffix(""))], check=False, capture_output=True)
    elif p.suffix.lower() == ".eps":
        out = FIG / f"{slug}.png"
        subprocess.run(["gs", "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=png16m", "-r160", "-dEPSCrop",
                        f"-sOutputFile={out}", str(p)], check=False, capture_output=True)
    else:
        out = FIG / f"{slug}{p.suffix.lower()}"
        shutil.copy(p, out)
    if not out.exists():
        log.append(f"could not convert {p.name}")
        return ""
    return f"\\includegraphics{{figures/{out.name}}}"


body = re.sub(r"\\includegraphics(\[[^\]]*\])?\{([^}]+)\}", img, body)

# TikZ / pgfplots -> SVG
tikz_pre = "\n".join(l for l in pre.splitlines()
                     if re.match(r"\s*\\(usetikzlibrary|usepgfplotslibrary|definecolor|pgfplotsset|tikzset|colorlet|newcommand|DeclareMathOperator|renewcommand)", l))
pkgs = "\\usepackage{amsmath,amssymb,amsfonts,bm,xcolor}\n\\usepackage{tikz}\n"
if "pgfplots" in pre:
    pkgs += "\\usepackage{pgfplots}\n"
if "circuitikz" in pre:
    pkgs += "\\usepackage{circuitikz}\n"
n_tikz = 0


def tikz(m):
    global n_tikz
    n_tikz += 1
    d = WORK / "tikz"
    d.mkdir(exist_ok=True)
    doc = ("\\documentclass[border=4pt]{standalone}\n" + pkgs + tikz_pre +
           "\n\\begin{document}\n" + m.group(0) + "\n\\end{document}\n")
    (d / f"t{n_tikz}.tex").write_text(doc)
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"t{n_tikz}.tex"],
                   cwd=d, capture_output=True, timeout=120)
    pdf = d / f"t{n_tikz}.pdf"
    if not pdf.exists():
        log.append(f"tikz {n_tikz} failed to compile")
        return ""
    out = FIG / f"diagram-{n_tikz}.svg"
    subprocess.run(["pdftocairo", "-svg", str(pdf), str(out)], check=False)
    return f"\\includegraphics{{figures/{out.name}}}"


body = re.sub(r"\\begin\{(tikzpicture|circuitikz)\}.*?\\end\{\1\}", tikz, body, flags=re.S)

# --------------------------------------------------------- cross references
# drop the word in front of \ref, Quarto writes "Figure 1" / "Figura 1" itself
words = r"(?:Figures?|Figs?\.|Tables?|Tabs?\.|Sections?|Secs?\.|Equations?|Eqs?\.|Appendix|Appendices|Chapters?|Figur[ae]|Tabell[ae]|Sezion[ei]|Capitol[oi]|Equazion[ei]|Appendice)"
body = re.sub(words + r"(?:~|\s)*\\(ref|eqref|autoref|cref|Cref)\{", r"\\ref{", body)
body = re.sub(r"\\(autoref|cref|Cref)\{", r"\\ref{", body)
body = re.sub(r"\(\s*\\eqref\{([^}]+)\}\s*\)", r"\\eqref{\1}", body)
body = re.sub(r"\(\s*\\ref\{(eq[^}]+)\}\s*\)", r"\\eqref{\1}", body)

# longtable: keep the first header only
body = re.sub(r"\\endfirsthead.*?\\endhead", "", body, flags=re.S)
body = re.sub(r"(\\(?:bottomrule|hline|midrule)\s*)?\\endfoot.*?(\\endlastfoot)?", "", body)
body = re.sub(r"\\endlastfoot|\\endhead|\\endfirsthead", "", body)

# custom column types pandoc does not know (L{..}, X, C{..}); width arg of tabularx / tabular*
def group_end(t, i):
    depth = 0
    for j in range(i, len(t)):
        if t[j] == "{" and (j == 0 or t[j - 1] != "\\"):
            depth += 1
        elif t[j] == "}" and t[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return j
    return -1


def fix_tabulars(t):
    out, pos = [], 0
    for m in re.finditer(r"\\begin\{(tabularx|tabular\*|tabular)\}", t):
        if m.start() < pos:
            continue
        i = m.end()
        out.append(t[pos:m.start()])
        if m.group(1) != "tabular":          # skip the width argument
            e = group_end(t, i)
            i = e + 1 if e >= 0 else i
        e = group_end(t, i)
        if e < 0:
            out.append(t[m.start():i])
            pos = i
            continue
        spec = t[i + 1:e]
        spec = re.sub(r"[@!<>]\{(?:[^{}]|\{[^{}]*\})*\}", "", spec)
        spec = re.sub(r"[LCRY]\{([^}]*)\}", r"p{\1}", spec)
        spec = re.sub(r"(?<![a-zA-Z\\])X", "l", spec)
        out.append("\\begin{tabular}{" + spec + "}")
        pos = e + 1
    out.append(t[pos:])
    t = "".join(out)
    return t.replace("\\end{tabularx}", "\\end{tabular}").replace("\\end{tabular*}", "\\end{tabular}")


body = fix_tabulars(body)
body = re.sub(r"\\(?:shortstack|makecell|thead)(?:\[[^\]]*\])?\{((?:[^{}]|\{[^{}]*\})*)\}",
              lambda m: m.group(1).replace("\\\\", " "), body)
body = re.sub(r"(\\multicolumn\{[^}]*\}\{)((?:[^{}]|\{[^{}]*\})*)\}",
              lambda m: m.group(1) + re.sub(r"[@!<>]\{(?:[^{}]|\{[^{}]*\})*\}", "", m.group(2)) + "}", body)
body = re.sub(r"\\resizebox\{[^}]*\}\{[^}]*\}\{", "{", body)
body = re.sub(r"\\adjustbox\{[^}]*\}\{", "{", body)

# thebibliography -> plain paragraphs with an anchor token per entry
def thebib(m):
    ents = re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}(.*?)(?=\\bibitem|$)", m.group(1), re.S)
    is_it = re.search(r"^lang:\s*it", (PAGE / "index.qmd").read_text(), re.M)
    head = "\\section*{" + ("Bibliografia" if is_it else "References") + "}\n\n"
    return head + "\n\n".join(f"ZZBIBREF{re.sub(r'[^a-zA-Z0-9]+', '-', k.strip()).strip('-').lower()}ZZ {t.strip()}" for k, t in ents) + "\n\n"


body = re.sub(r"\\begin\{thebibliography\}(?:\{[^}]*\})?(.*?)\\end\{thebibliography\}", thebib, body, flags=re.S)

# keep the preamble so pandoc can expand \newcommand macros
doc = pre + "\\begin{document}\n" + body + "\n\\end{document}\n"
# Overleaf compiles through small errors (a stray brace, an extra \end{itemize});
# pandoc does not, so drop the offending token and try again.
MAXFIX = int(os.environ.get("MAXFIX", "12"))
for attempt in range(MAXFIX):
    (WORK / "doc.tex").write_text(doc)
    res = subprocess.run([*a.pandoc.split(), "-f", "latex", "-t", "markdown-raw_tex-raw_attribute+tex_math_dollars",
                          "--wrap=none", "--mathjax", str(WORK / "doc.tex")], capture_output=True, text=True, cwd=WORK)
    if res.returncode == 0:
        break
    em = re.search(r"line (\d+), column (\d+)\):\s*\n(.*?)\n", res.stderr)
    if not em:
        sys.exit("pandoc failed: " + res.stderr[:3000])
    ln, col, what = int(em.group(1)), int(em.group(2)), em.group(3)
    lines = doc.split("\n")
    if "end of input" in res.stderr:  # unexpected end of input: an environment or brace was never closed
        envs = re.findall(r"\\(begin|end)\{([^}]+)\}", doc)
        stack = []
        for kind, env in envs:
            if kind == "begin":
                stack.append(env)
            elif stack and stack[-1] == env:
                stack.pop()
        closer = "".join(f"\\end{{{e}}}" for e in reversed([e for e in stack if e != "document"]))
        if closer:
            doc = doc.replace("\\end{document}", closer + "\n\\end{document}")
            log.append(f"closed {closer} at end of input")
            continue
        # an unclosed group such as "{\small" that LaTeX forgives: drop its opening brace
        opens, k = [], 0
        while k < len(doc):
            c = doc[k]
            if c == "\\":
                k += 2
                continue
            if c == "%":
                k = doc.find("\n", k)
                k = len(doc) if k < 0 else k
                continue
            if c == "{":
                opens.append(k)
            elif c == "}" and opens:
                opens.pop()
            k += 1
        if not opens:
            sys.exit("pandoc failed: " + res.stderr[:1500])
        bstart = doc.find("\\begin{document}")
        k = next((o for o in opens if o > bstart), opens[-1])
        log.append(f"removed unclosed '{{' : ...{doc[max(0, k-40):k+20].strip()!r}")
        doc = doc[:k] + doc[k + 1:]
        continue
    line = lines[ln - 1]
    pos = min(col - 1, len(line))
    exp = re.search(r"expecting \\end\{([^}]+)\}", res.stderr)
    if "end{document}" in line and exp and exp.group(1) != "document":
        lines[ln - 1] = line.replace("\\end{document}", f"\\end{{{exp.group(1)}}}\n\\end{{document}}")
        doc = "\n".join(lines)
        log.append(f"closed unterminated {exp.group(1)} at the end")
        continue
    cut = None
    if pos < len(line) and line[pos] == "}":
        cut = (pos, pos + 1)
    elif re.search(r"\\end\{[^}]*\}\s*$", line[:pos]):
        mm = re.search(r"\\end\{[^}]*\}\s*$", line[:pos])
        cut = (mm.start(), pos)
    elif re.match(r"\\end\{[^}]*\}", line[pos:]):
        mm = re.match(r"\\end\{[^}]*\}", line[pos:])
        cut = (pos, pos + mm.end())
    elif pos > 0 and line[pos - 1] == "}":
        cut = (pos - 1, pos)
    elif pos < len(line) and not line[pos].isalnum() and attempt < 60:
        cut = (pos, pos + 1)
    if cut is None:              # last resort: drop the line, and say so
        cut = (0, len(line))
    t = line[cut[0]:cut[1]]
    lines[ln - 1] = line[:cut[0]] + line[cut[1]:]
    log.append(f"removed stray {t!r}: ...{line[max(0, cut[0]-60):cut[0]].strip()}")
    doc = "\n".join(lines)
else:
    sys.exit("pandoc failed after repairs: " + res.stderr[:2000])
md = res.stdout
if res.stderr.strip():
    log.append("pandoc: " + " | ".join(res.stderr.strip().splitlines()[:8]))
ab = ""
if abstract.strip():
    ab = subprocess.run([*a.pandoc.split(), "-f", "latex", "-t", "markdown-raw_tex+tex_math_dollars", "--wrap=none"],
                        input=pre + "\\begin{document}\n" + abstract + "\n\\end{document}", capture_output=True, text=True).stdout.strip()

# -------------------------------------------------------- post-processing
# math inside raw-HTML figures comes out as \( \) spans: back to $ $
md = re.sub(r'<span class="math inline">\\\((.*?)\\\)</span>', lambda m: "$" + html_unescape(m.group(1)) + "$", md, flags=re.S)
md = re.sub(r'<span class="math display">\\\[(.*?)\\\]</span>', lambda m: "$$" + html_unescape(m.group(1)) + "$$", md, flags=re.S)
md = re.sub(r'<a href="#([^"]+)" data-reference-type="[^"]*" data-reference="[^"]*">[^<]*</a>',
            lambda m: "[](#" + m.group(1) + "){reference-type=\"ref\" reference=\"" + m.group(1) + "\"}", md)
md = re.sub(r"</?em>", "*", md)
# figures written as HTML -> markdown figures
md = re.sub(r'<figure(?: id="([^"]*)")?[^>]*>\s*(?:<img src="([^"]+)"[^>]*/>\s*)+(?:<figcaption>(.*?)</figcaption>\s*)?</figure>',
            lambda m: "![" + re.sub(r"\s+", " ", (m.group(3) or "")).strip() + "](" + m.group(2) + ")" +
            ("{#" + m.group(1) + "}" if m.group(1) else ""), md, flags=re.S)
# figures with several panels -> Quarto figure div with a column layout
seen_ids = set()


def multi_fig(m):
    fid, inner = m.group(1), m.group(2)
    imgs = re.findall(r'!\[([^\]]*)\]\(([^)\s]+)\)', inner) + [("", u) for u in re.findall(r'<img src="([^"]+)"', inner)]
    if not imgs:
        return m.group(0)
    cap = re.search(r"<figcaption>(.*?)</figcaption>", inner, re.S)
    cap = re.sub(r"\s+", " ", cap.group(1)).strip() if cap else ""
    attrs = f"layout-ncol={min(len(imgs), 3)}"
    if fid and fid not in seen_ids:
        seen_ids.add(fid)
        attrs = f"#{fid} " + attrs
    body_ = "\n\n".join(f"![{c}]({u})" for c, u in imgs)
    return f"::: {{{attrs}}}\n\n{body_}\n\n{cap}\n\n:::"


md = re.sub(r'^[ \t]*<figure(?: id="([^"]*)")?[^>]*>(.*?)</figure>', lambda m: "\n" + multi_fig(m) + "\n", md, flags=re.S | re.M)
md = re.sub(r'\{width="[^"]*"\}', "", md)
md = re.sub(r'(\{#[^}\s]+) width="[^"]*"', r"\1", md)
md = re.sub(r'(\{#[^}]*?)\s*data-latex-placement="[^"]*"', r"\1", md)

# map every label to a Quarto id
idmap = {}


def newid(old, kind):
    base = re.sub(r"^(fig|figure|tab|table|tbl|eq|eqn|sec|section|chap|ch|app|subsec)[:_\-.]", "", old, flags=re.I)
    base = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower() or "x"
    nid = f"{kind}-{base}"
    while nid in idmap.values():
        nid += "x"
    idmap[old] = nid
    return nid


md = re.sub(r"\]\(([^)\s]+)\)\{#([^}\s]+)\}", lambda m: f"]({m.group(1)}){{#{newid(m.group(2), 'fig')}}}", md)
md = re.sub(r"^(\s*: .*)\{#([^}\s]+)\}[ \t]*$", lambda m: f"{m.group(1)}{{#{newid(m.group(2), 'tbl')}}}", md, flags=re.M)
md = re.sub(r"^(#+ .*)\{#([^}\s]+)((?: \.[a-z]+)*)\}[ \t]*$",
            lambda m: f"{m.group(1)}{{#{newid(m.group(2), 'sec')}{m.group(3)}}}", md, flags=re.M)


def div_id(m):
    colons, old = m.group(1), m.group(2)
    low = old.lower()
    if re.match(r"(tab|table|tbl)[:_\-.]", low):
        kind = "tbl"
    elif re.match(r"(fig|figure)[:_\-.]", low):
        kind = "fig"
    else:
        nxt = md[m.end():m.end() + 600]
        kind = "fig" if "![" in nxt.split(":::")[0] else "tbl" if re.search(r"^\s*[-+|]{3,}", nxt, re.M) else None
    if kind is None:
        return m.group(0)
    return f"{colons} {{#{newid(old, kind)}{m.group(3)}}}"


md = re.sub(r"^([ \t]*:::+) \{#([^}\s]+)([^}]*)\}[ \t]*$", div_id, md, flags=re.M)


def eq(m):
    inner = m.group(1)
    labs = re.findall(r"\\label\{([^}]+)\}", inner)
    inner = re.sub(r"\\label\{[^}]+\}", "", inner)
    inner = re.sub(r"\\begin\{(equation|multline|gather)\*?\}(.*?)\\end\{\1\*?\}", r"\2", inner, flags=re.S)
    inner = re.sub(r"\\begin\{(align|eqnarray|flalign)\*?\}(.*?)\\end\{\1\*?\}", r"\\begin{aligned}\2\\end{aligned}", inner, flags=re.S)
    inner = inner.replace("\\nonumber", "").replace("\\notag", "")
    if "\\begin{" in inner and not re.search(r"^(:::|#|- |\*\*)", inner, re.M):
        inner = re.sub(r"\n[ \t]*(?=\n)", "", inner)
    if "aligned" in inner and "\\tag" in inner:   # MathJax: no \tag inside aligned
        tags = re.findall(r"\\tag\*?\{([^}]*)\}", inner)
        inner = re.sub(r"\\tag\*?\{[^}]*\}", "", inner)
        if tags and not labs:
            inner += "\\tag{" + tags[0] + "}"
    if not labs:
        return "$$" + inner + "$$"
    nid = newid(labs[0], "eq")
    for extra in labs[1:]:
        idmap[extra] = nid
    return "\n\n$$" + inner.rstrip() + "\n$$ {#" + nid + "}\n\n"


# park cross-reference links first: their text "\[label\]" looks like display math
md = re.sub(r"\[((?:\\\]|[^\]$\n])*)\]\(#([^)\s]+)\)\{reference-type=\"[^\"]*\"[^}]*\}",
            lambda m: "ZZREF" + m.group(2).replace(":", "ZZC") + "ZZEND", md)
md = re.sub(r"\$\$(.*?)\$\$", eq, md, flags=re.S)
# ids pandoc put on raw divs / spans for labels inside theorems etc.
md = re.sub(r'\[\]\{#([^}\s]+)(?: label="[^"]*")?\}', "", md)


lang_it = re.search(r"^lang:\s*it", (PAGE / "index.qmd").read_text(), re.M)


def ref(m):
    text, target = m.group(1), m.group(2)
    if target in idmap:
        return "@" + idmap[target]
    log.append(f"unresolved ref {target}")
    return "(see the PDF)" if lang_it is None else "(vedi il PDF)"


md = re.sub(r"ZZREF(.*?)ZZEND", lambda m: ref(type("R", (), {"group": lambda self, k: ("", m.group(1).replace("ZZC", ":"))[k - 1]})()), md)
# hand-written thebibliography: resolve @key citations to author-year links
items = re.findall(r"\\bibitem(?:\[([^\]]*)\])?\{([^}]+)\}(.*?)(?=\\bibitem|\\end\{thebibliography\})", raw, re.S)
if items and not bib_names:
    labels = {}
    for opt, key, txt in items:
        key = key.strip()
        flat = re.sub(r"\\[a-zA-Z]+\*?|[{}~]", " ", txt)
        flat = re.sub(r"\s+", " ", flat).strip()
        yr = re.search(r"\(?((?:1[89]|20)\d\d[a-z]?)\)?", flat)
        seg = flat[:yr.start()] if yr else flat[:80]
        names = re.findall(r"([A-ZÀ-Ý][A-Za-zÀ-ÿ'\-]+),", seg) or re.findall(r"([A-ZÀ-Ý][A-Za-zÀ-ÿ'\-]{2,})", seg)
        if opt and opt.strip():
            name, year = re.sub(r"\s*\(?\d{4}[a-z]?\)?\s*$", "", opt).strip(), (yr.group(1) if yr else "")
        elif names:
            name = names[0] if len(names) == 1 else f"{names[0]} and {names[1]}" if len(names) == 2 else f"{names[0]} et al."
            year = yr.group(1) if yr else ""
        else:
            name, year = key, ""
        labels[key] = (name, year)
    rid = lambda k: "ref-" + re.sub(r"[^a-zA-Z0-9]+", "-", k).strip("-").lower()

    def cite_group(m):
        keys = re.findall(r"@([\w:.\-/]+)", m.group(1))
        if not keys or any(k not in labels for k in keys):
            return m.group(0)
        return "(" + "; ".join(f"[{labels[k][0]} {labels[k][1]}](#{rid(k)})".replace("  ", " ") for k in keys) + ")"

    md = re.sub(r"\[((?:-?@[\w:.\-/]+(?:,[^;\]]*)?;?\s*)+)\]", cite_group, md)
    md = re.sub(r"(?<![\w\[])@([\w:.\-/]*\w)",
                lambda m: f"[{labels[m.group(1)][0]} ({labels[m.group(1)][1]})](#{rid(m.group(1))})"
                if m.group(1) in labels else m.group(0), md)

md = re.sub(r"ZZBIBREF([a-z0-9-]+)ZZ\s*", lambda m: "[]{#ref-" + m.group(1) + "}", md)
md = re.sub(r"^(#+ (?:References|Bibliografia)) \{#[^}]*\}", r"\1 {.unnumbered}", md, flags=re.M)

# citations with no bibliography anywhere in the project: print them as plain author-year text
if not bib_names:
    def keylabel(k):
        m = re.match(r"([A-Za-z]+?)[_\-]?((?:19|20)\d\d)", k)
        return (m.group(1).capitalize(), m.group(2)) if m else (k, "")

    def plain_group(m):
        keys = re.findall(r"@([\w:.\-/]+)", m.group(1))
        if not keys or any(re.match(r"(fig|tbl|sec|eq)-", k) for k in keys):
            return m.group(0)
        return "(" + "; ".join(" ".join(x for x in keylabel(k) if x) for k in keys) + ")"

    def plain_cites(t):
        t = re.sub(r"\[((?:-?@[\w:.\-/]+(?:,[^;\]]*)?;?\s*)+)\]", plain_group, t)
        return re.sub(r"(?<![\w\[`/])@([A-Za-z][\w:.\-/]*\w)",
                      lambda m: m.group(0) if re.match(r"(fig|tbl|sec|eq)-", m.group(1))
                      else (lambda n, y: f"{n} ({y})" if y else n)(*keylabel(m.group(1))), t)

    md, ab = plain_cites(md), plain_cites(ab)

# code blocks: "``` {fontsize=...}" would be taken by Quarto as an executable chunk
def fence(m):
    cls = re.search(r"\.([A-Za-z0-9_+-]+)", m.group(2))
    cap = re.search(r'caption="([^"]*)"', m.group(2))
    lead = f"*{cap.group(1)}*\n\n" if cap else ""
    return lead + m.group(1) + (cls.group(1).lower() if cls else "")


md = re.sub(r"^(`{3,})[ \t]*\{([^}\n]*)\}[ \t]*$", fence, md, flags=re.M)
# packages MathJax does not have: bm, dsfont, bbm
for a_, b_ in [(r"\\bm(?![a-zA-Z])", r"\\boldsymbol"), (r"\\mathds(?![a-zA-Z])", r"\\mathbb"), (r"\\mathbbm(?![a-zA-Z])", r"\\mathbb")]:
    md, ab = re.sub(a_, b_, md), re.sub(a_, b_, ab)
md = re.sub(r"\n{3,}", "\n\n", md).strip("\n")

# ---------------------------------------------------------------- the page
qmd = PAGE / "index.qmd"
old = qmd.read_text()
fm = old.split("---", 2)[1]
lang = re.search(r"^lang:\s*(\w+)", fm, re.M).group(1) if re.search(r"^lang:", fm, re.M) else "en"
fm = re.sub(r"^(abstract|bibliography|number-sections|number-depth):.*(\n  .*)*\n?", "", fm, flags=re.M)
if ab:
    fm += "abstract: |\n" + "\n".join("  " + l for l in ab.splitlines()) + "\n"
if bib_names:
    fm += "bibliography: " + (bib_names[0] if len(bib_names) == 1 else "[" + ", ".join(bib_names) + "]") + "\n"
fm += "number-sections: true\nnumber-depth: 3\n"
pdf = re.search(r"^pdf:\s*(\S+)", fm, re.M)
code = re.search(r"^code:\s*(\S+)", fm, re.M)
btn = []
if pdf:
    btn.append(f"[{'Scarica il PDF' if lang == 'it' else 'Download PDF'}]({pdf.group(1)}){{.btn-paper download=\"\"}}")
if code:
    btn.append(f"[{'Codice' if lang == 'it' else 'Code'}]({code.group(1)}){{.btn-paper}}")
tail = "\n\n::: {.paper-download}\n" + " ".join(btn) + "\n:::\n" if btn else ""
refs = ""
if bib_names and not re.search(r"^#+ (References|Bibliografia|Riferimenti)", md, re.M):
    refs = f"\n\n# {'Bibliografia' if lang == 'it' else 'References'} {{.unnumbered}}\n\n::: {{#refs}}\n:::\n"
qmd.write_text("---" + fm.rstrip("\n") + "\n---\n\n" + md + "\n" + refs + tail)
import os
if not os.environ.get("KEEP"):
    shutil.rmtree(WORK)
else:
    print("work:", WORK)
print(f"OK {PAGE.name}: {len(md)//1000}k chars, {n_img} figures, {n_tikz} tikz, {len(idmap)} labels, bib={bib_names}")
for l in log:
    print("  !", l)
