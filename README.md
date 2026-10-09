# tommasozeri.github.io

Personal research site, built with [Quarto](https://quarto.org) and published on GitHub Pages.

## Structure

```
research/<slug>/index.qmd   papers (abstract, PDF, code, BibTeX)
notes/<slug>/index.qmd      course notes and expository write-ups
blog/<slug>/index.qmd       shorter posts
about.qmd, index.qmd        static pages
styles/                     theme (SCSS) and custom CSS
scripts/                    WordPress import tools
```

## Add a new paper

1. Create `research/my-paper/` and put `index.qmd` and `my-paper.pdf` inside.
2. Copy the front matter from an existing paper and edit it:

```yaml
---
title: "Paper title"
author: Tommaso Zeri
date: 2026-10-09
lang: en
idioma: English
categories: [Statistical Arbitrage]
description: "One- or two-sentence summary shown in the listings."
citation:
  type: report
  pdf-url: https://tommasozeri.github.io/research/my-paper/my-paper.pdf
google-scholar: true
---
```

3. Push to `main`. The site rebuilds in about a minute.

Math works as in LaTeX: `$x_t$` inline, `$$ ... $$` display.

## Preview locally

```bash
quarto preview
```

## WordPress import

`scripts/wp2quarto.py` converted the WordPress export into these pages (the post mapping is in `scripts/posts.py`).
The PDFs initially still point at wordpress.com. Run the **Import WordPress files** workflow once (Actions tab → Run workflow): it downloads every file next to its page, rewrites the links and redeploys.
