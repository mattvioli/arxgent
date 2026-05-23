from __future__ import annotations

import re
from pathlib import Path

import yaml

from arxgent.agents import Paper


def _slugify(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s-]+", "-", s)
    return s[:60].rstrip("-")


def _frontmatter(paper: Paper) -> str:
    data = {
        "title": paper.title,
        "date": paper.published,
        "arxiv_id": paper.arxiv_id,
        "categories": paper.categories,
        "source": "arxgent",
    }
    return "---\n" + yaml.dump(data, default_style=None, allow_unicode=True, sort_keys=False).strip() + "\n---"


def save_paper_md(paper: Paper, summary: str, output_dir: str) -> Path:
    dir_path = Path(output_dir).expanduser().resolve()
    dir_path.mkdir(parents=True, exist_ok=True)

    filename = f"{paper.published}_{_slugify(paper.title)}.md"
    filepath = dir_path / filename

    content = _frontmatter(paper) + "\n\n" + summary + "\n"
    filepath.write_text(content)

    return filepath
