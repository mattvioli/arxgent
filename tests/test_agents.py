from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from arxgent.agents import (
    Paper,
    _build_query,
    _dates_to_arxiv,
    _extract_disliked_keywords,
    _extract_liked_keywords,
    research_papers,
    summarize_paper,
)
from arxgent.profile import PaperEntry, Profile


class TestDateConversion:
    def test_arxiv_format(self) -> None:
        result = _dates_to_arxiv(datetime(2026, 5, 17).date(), datetime(2026, 5, 24).date())
        assert result == "[20260517000000+TO+20260524000000]"


class TestQueryBuilder:
    def test_single_category(self) -> None:
        profile = Profile(topics={"CS": ["cs.LG"]})
        query = _build_query(profile, "2026-05-17", "2026-05-24")
        assert "cat:cs.LG" in query
        assert "submittedDate:" in query

    def test_multiple_categories_ored(self) -> None:
        profile = Profile(topics={"CS": ["cs.LG", "cs.AI"]})
        query = _build_query(profile, "2026-05-17", "2026-05-24")
        assert "cat:cs.LG+OR+cat:cs.AI" in query

    def test_no_categories(self) -> None:
        profile = Profile()
        query = _build_query(profile, "2026-05-17", "2026-05-24")
        assert "cat:" not in query
        assert "submittedDate:" in query

    def test_groups_from_multiple_areas(self) -> None:
        profile = Profile(topics={"CS": ["cs.LG"], "Math": ["math.ST"]})
        query = _build_query(profile, "2026-05-17", "2026-05-24")
        assert "cat:cs.LG" in query
        assert "cat:math.ST" in query

    def test_date_range_in_query(self) -> None:
        profile = Profile(topics={"CS": ["cs.LG"]})
        query = _build_query(profile, "2026-05-17", "2026-05-24")
        assert "submittedDate:[20260517000000+TO+20260524000000]" in query


class TestFeedbackExtraction:
    def test_liked_keywords(self) -> None:
        profile = Profile(history=[
            PaperEntry(arxiv_id="1", title="A", date_delivered="2026-05-23", read=True, liked=True, feedback="great paper about transformers"),
        ])
        keywords = _extract_liked_keywords(profile)
        assert "transformers" in keywords

    def test_disliked_keywords(self) -> None:
        profile = Profile(history=[
            PaperEntry(arxiv_id="1", title="A", date_delivered="2026-05-23", read=True, liked=False, feedback="too much reinforcement learning"),
        ])
        keywords = _extract_disliked_keywords(profile)
        assert "reinforcement" in keywords

    def test_no_feedback_returns_empty(self) -> None:
        profile = Profile()
        assert _extract_liked_keywords(profile) == []
        assert _extract_disliked_keywords(profile) == []

    def test_liked_keywords_appear_in_query(self) -> None:
        profile = Profile(
            topics={"CS": ["cs.LG"]},
            history=[
                PaperEntry(arxiv_id="1", title="A", date_delivered="2026-05-23", read=True, liked=True, feedback="transformers"),
            ],
        )
        query = _build_query(profile, "2026-05-17", "2026-05-24")
        assert "all:transformers" in query

    def test_disliked_keywords_appear_as_andnot(self) -> None:
        profile = Profile(
            topics={"CS": ["cs.LG"]},
            history=[
                PaperEntry(arxiv_id="1", title="A", date_delivered="2026-05-23", read=True, liked=False, feedback="reinforcement"),
            ],
        )
        query = _build_query(profile, "2026-05-17", "2026-05-24")
        assert "ANDNOT+all:reinforcement" in query


class TestPaperModel:
    def test_arxiv_url_format(self) -> None:
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
        assert paper.arxiv_url == "https://arxiv.org/abs/1706.03762"
        assert paper.pdf_url == "https://arxiv.org/pdf/1706.03762"


class FakeArxivResult:
    def __init__(self, title, arxiv_id, authors, published, summary, categories):
        self.title = title
        self.entry_id = f"http://arxiv.org/abs/{arxiv_id}"
        self.authors = [FakeAuthor(a) for a in authors]
        self.published = datetime.strptime(published, "%Y-%m-%d")
        self.summary = summary
        self.categories = categories
        self.pdf_url = f"http://arxiv.org/pdf/{arxiv_id}"


class FakeAuthor:
    def __init__(self, name):
        self.name = name


class TestResearchPapers:
    def test_returns_papers(self) -> None:
        fake_results = [
            FakeArxivResult(
                title="Paper One",
                arxiv_id="1706.03762",
                authors=["Author A"],
                published="2026-05-20",
                summary="Abstract one",
                categories=["cs.LG"],
            ),
            FakeArxivResult(
                title="Paper Two",
                arxiv_id="1706.03763",
                authors=["Author B"],
                published="2026-05-21",
                summary="Abstract two",
                categories=["cs.AI"],
            ),
        ]

        fake_client = MagicMock()
        fake_client.results.return_value = fake_results

        with patch("arxgent.agents.arxiv.Client", return_value=fake_client):
            papers = research_papers(
                profile=Profile(topics={"CS": ["cs.LG"]}),
                start_date="2026-05-17",
                end_date="2026-05-24",
                num_papers=2,
            )

        assert len(papers) == 2
        assert papers[0].arxiv_id == "1706.03762"
        assert papers[0].title == "Paper One"
        assert papers[1].arxiv_id == "1706.03763"

    def test_empty_results(self) -> None:
        fake_client = MagicMock()
        fake_client.results.return_value = []

        with patch("arxgent.agents.arxiv.Client", return_value=fake_client):
            papers = research_papers(
                profile=Profile(topics={"CS": ["cs.LG"]}),
                start_date="2026-05-17",
                end_date="2026-05-24",
                num_papers=5,
            )

        assert papers == []


class TestSummarizer:
    def test_calls_litellm(self) -> None:
        paper = Paper(
            arxiv_id="1706.03762",
            title="Attention Is All You Need",
            authors=["Vaswani"],
            published="2017-06-12",
            categories=["cs.LG"],
            abstract="A novel architecture",
            arxiv_url="https://arxiv.org/abs/1706.03762",
            pdf_url="https://arxiv.org/pdf/1706.03762",
        )
        profile = Profile(interest="deep learning")

        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            "**Overview:** Great paper\n"
            "**Key contribution:** Transformers\n"
            "- **Link:** {arxiv_url}\n"
            "- **PDF:** {pdf_url}"
        )

        with patch("arxgent.agents.litellm.completion", return_value=mock_response):
            summary = summarize_paper(paper, profile, model="gpt-4o-mini")

        assert "**Overview:**" in summary
        assert "**Key contribution:**" in summary
        assert "arxiv.org/abs/1706.03762" in summary
        assert "arxiv.org/pdf/1706.03762" in summary

    def test_handles_empty_response(self) -> None:
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
        profile = Profile(interest="ML")

        mock_response = MagicMock()
        mock_response.choices[0].message.content = None

        with patch("arxgent.agents.litellm.completion", return_value=mock_response):
            summary = summarize_paper(paper, profile, model="gpt-4o-mini")

        assert summary == ""
