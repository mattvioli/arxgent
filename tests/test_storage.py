from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from arxgent.agents import Paper
from arxgent.storage import save_paper_md, _slugify


class TestSlugify:
    def test_basic_slug(self) -> None:
        assert _slugify("Attention Is All You Need") == "attention-is-all-you-need"

    def test_special_chars_removed(self) -> None:
        assert _slugify("What's New? (Part 2)") == "whats-new-part-2"

    def test_truncates_long_titles(self) -> None:
        long = "A" * 100
        slug = _slugify(long)
        assert len(slug) <= 60

    def test_strips_trailing_hyphen(self) -> None:
        assert _slugify("Title -") == "title"


class TestSavePaperMd:
    def test_creates_file(self, tmp_path: Path) -> None:
        paper = Paper(
            arxiv_id="1706.03762",
            title="Attention Is All You Need",
            authors=["Vaswani"],
            published="2017-06-12",
            categories=["cs.LG", "cs.CL"],
            abstract="abstract",
            arxiv_url="https://arxiv.org/abs/1706.03762",
            pdf_url="https://arxiv.org/pdf/1706.03762",
        )
        summary = "**Overview:** A great paper."

        filepath = save_paper_md(paper, summary, str(tmp_path))
        assert filepath.exists()
        assert filepath.suffix == ".md"
        assert "2017-06-12" in filepath.name

    def test_frontmatter(self, tmp_path: Path) -> None:
        paper = Paper(
            arxiv_id="1706.03762",
            title="Attention",
            authors=["Vaswani"],
            published="2017-06-12",
            categories=["cs.LG"],
            abstract="abstract",
            arxiv_url="https://arxiv.org/abs/1706.03762",
            pdf_url="https://arxiv.org/pdf/1706.03762",
        )
        filepath = save_paper_md(paper, "summary", str(tmp_path))
        content = filepath.read_text()

        assert content.startswith("---")
        assert "title: Attention" in content
        assert "arxiv_id: '1706.03762'" in content or 'arxiv_id: "1706.03762"' in content
        assert "source: arxgent" in content

    def test_links_in_body(self, tmp_path: Path) -> None:
        paper = Paper(
            arxiv_id="1706.03762",
            title="Attention",
            authors=["Vaswani"],
            published="2017-06-12",
            categories=["cs.LG"],
            abstract="abstract",
            arxiv_url="https://arxiv.org/abs/1706.03762",
            pdf_url="https://arxiv.org/pdf/1706.03762",
        )
        summary = "Check the PDF at https://arxiv.org/pdf/1706.03762"
        filepath = save_paper_md(paper, summary, str(tmp_path))
        content = filepath.read_text()
        assert "arxiv.org/pdf/1706.03762" in content

    def test_output_dir_created(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b"
        paper = Paper(
            arxiv_id="1",
            title="Paper",
            authors=["A"],
            published="2026-01-01",
            categories=["cs.LG"],
            abstract="abstract",
            arxiv_url="https://arxiv.org/abs/1",
            pdf_url="https://arxiv.org/pdf/1",
        )
        filepath = save_paper_md(paper, "summary", str(nested))
        assert filepath.parent.exists()

    def test_frontmatter_parses_as_yaml(self, tmp_path: Path) -> None:
        paper = Paper(
            arxiv_id="1706.03762",
            title="Attention: A Study",
            authors=["Vaswani"],
            published="2017-06-12",
            categories=["cs.LG"],
            abstract="abstract",
            arxiv_url="https://arxiv.org/abs/1706.03762",
            pdf_url="https://arxiv.org/pdf/1706.03762",
        )
        filepath = save_paper_md(paper, "body", str(tmp_path))
        content = filepath.read_text()
        frontmatter_str = content.split("---")[1]
        data = yaml.safe_load(frontmatter_str)
        assert data["title"] == "Attention: A Study"
        assert data["arxiv_id"] == "1706.03762"
        assert data["categories"] == ["cs.LG"]
