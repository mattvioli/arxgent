from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from typing import List

os.environ["LITELLM_LOG"] = "ERROR"

import arxiv
import litellm
from pydantic import BaseModel

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
    return f"[{start.strftime(fmt)}+TO+{end.strftime(fmt)}]"


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
            parts.append("(" + "+OR+".join(cat_parts) + ")")

    date_filter = "submittedDate:" + _dates_to_arxiv(
        datetime.strptime(start_date, "%Y-%m-%d").date(),
        datetime.strptime(end_date, "%Y-%m-%d").date(),
    )
    parts.append(date_filter)

    liked_keywords = _extract_liked_keywords(profile)
    for kw in liked_keywords:
        parts.append(f"+AND+all:{kw}")

    disliked_keywords = _extract_disliked_keywords(profile)
    for kw in disliked_keywords:
        parts.append(f"+ANDNOT+all:{kw}")

    return "+AND+".join(parts)


def _extract_liked_keywords(profile: Profile) -> list[str]:
    keywords: list[str] = []
    for entry in profile.history:
        if entry.liked and entry.feedback:
            words = re.findall(r"[A-Za-z][A-Za-z0-9_-]+", entry.feedback)
            keywords.extend(w.lower() for w in words if len(w) > 3)
    return keywords[:5]


def _extract_disliked_keywords(profile: Profile) -> list[str]:
    keywords: list[str] = []
    for entry in profile.history:
        if entry.liked is False and entry.feedback:
            words = re.findall(r"[A-Za-z][A-Za-z0-9_-]+", entry.feedback)
            keywords.extend(w.lower() for w in words if len(w) > 3)
    return keywords[:5]


def research_papers(
    profile: Profile,
    start_date: str,
    end_date: str,
    num_papers: int = 3,
) -> list[Paper]:
    query = _build_query(profile, start_date, end_date)

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=num_papers,
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


SUMMARIZE_SYSTEM_PROMPT = """\
You are an expert researcher helping a colleague find relevant papers.

Given a paper and the reader's research interests, write a concise \
markdown summary.

Structure your summary as:
1. **Overview** — one sentence describing what the paper does
2. **Key contribution** — what novel method, finding, or idea does it introduce?
3. **Relevance** — why this matters for someone interested in: {interest}

Then include these metadata lines at the end:
- **Link:** {{arxiv_url}}
- **PDF:** {{pdf_url}}"""


def summarize_paper(paper: Paper, profile: Profile, model: str) -> str:
    prompt = SUMMARIZE_SYSTEM_PROMPT.format(interest=profile.interest)

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Title: {paper.title}\n\n"
                    f"Authors: {', '.join(paper.authors)}\n\n"
                    f"Abstract: {paper.abstract}"
                ),
            },
        ],
        max_tokens=1024,
        temperature=0.3,
    )

    summary = response.choices[0].message.content or ""

    summary = summary.replace("{arxiv_url}", paper.arxiv_url)
    summary = summary.replace("{pdf_url}", paper.pdf_url)

    return summary
