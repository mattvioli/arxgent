from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import List

os.environ["LITELLM_LOG"] = "ERROR"

import arxiv
from pydantic import BaseModel

from arxgent.feedback import _extract_disliked_keywords, _extract_liked_authors, _extract_liked_keywords
from arxgent.profile import Profile


class Paper(BaseModel):
    arxiv_id: str
    title: str
    authors: List[str]
    published: str
    categories: List[str]
    abstract: str
    arxiv_url: str
    pdf_url: str


def _dates_to_arxiv(start: date, end: date) -> str:
    fmt = "%Y%m%d%H%M%S"
    return f"[{start.strftime(fmt)} TO {end.strftime(fmt)}]"


def _build_query(profile: Profile, start_date: str, end_date: str) -> str:
    parts: list[str] = []

    all_cats: list[str] = []
    for subs in profile.topics.values():
        all_cats.extend(subs)
    if all_cats:
        cat_parts = [f"cat:{c}" for c in all_cats]
        if len(cat_parts) == 1:
            parts.append(cat_parts[0])
        else:
            parts.append("(" + " OR ".join(cat_parts) + ")")

    date_filter = "submittedDate:" + _dates_to_arxiv(
        datetime.strptime(start_date, "%Y-%m-%d").date(),
        datetime.strptime(end_date, "%Y-%m-%d").date(),
    )
    parts.append(date_filter)

    liked_keywords = _extract_liked_keywords(profile)
    for kw in liked_keywords:
        parts.append(f"all:{kw}")

    liked_authors = _extract_liked_authors(profile)
    for author in liked_authors:
        parts.append(f"au:{_arxiv_escape(author)}")

    disliked_keywords = _extract_disliked_keywords(profile)
    for kw in disliked_keywords:
        parts.append(f"NOT all:{kw}")

    return " AND ".join(parts)


def _arxiv_escape(term: str) -> str:
    return term.replace(" ", "_").replace("-", "_")


def research_papers(
    profile: Profile,
    start_date: str,
    end_date: str,
    fetch_count: int = 50,
) -> list[Paper]:
    query = _build_query(profile, start_date, end_date)

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=fetch_count,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    papers: list[Paper] = []
    for result in client.results(search):
        arxiv_id = result.entry_id.removeprefix("http://arxiv.org/abs/")
        arxiv_id = re.sub(r"v\d+$", "", arxiv_id)

        papers.append(
            Paper(
                arxiv_id=arxiv_id,
                title=result.title,
                authors=[a.name for a in result.authors],
                published=result.published.strftime("%Y-%m-%d"),
                categories=list(result.categories),
                abstract=result.summary,
                arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
            )
        )

    return papers
