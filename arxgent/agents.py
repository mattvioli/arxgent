from __future__ import annotations

import os
import re
from datetime import date, datetime
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
        parts.append(f"ANDNOT all:{kw}")

    return " AND ".join(parts)


def _arxiv_escape(term: str) -> str:
    return term.replace(" ", "_").replace("-", "_")


def _extract_terms(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]+", text)
    return [w.lower() for w in words if len(w) > 3]


def _score_keywords(profile: Profile, liked: bool) -> list[str]:
    scores: dict[str, int] = {}
    for entry in profile.history:
        match = entry.liked if liked else (entry.liked is False)
        if match and entry.feedback:
            for term in _extract_terms(entry.feedback):
                scores[term] = scores.get(term, 0) + 1
    sorted_terms = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return [term for term, _ in sorted_terms[:5]]


def _extract_liked_keywords(profile: Profile) -> list[str]:
    return _score_keywords(profile, liked=True)


def _extract_disliked_keywords(profile: Profile) -> list[str]:
    return _score_keywords(profile, liked=False)


def _extract_liked_authors(profile: Profile) -> list[str]:
    scores: dict[str, int] = {}
    for entry in profile.history:
        if entry.liked and entry.authors:
            for author in entry.authors:
                scores[author] = scores.get(author, 0) + 1
    sorted_authors = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return [author for author, _ in sorted_authors[:3]]


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


REFINE_INTEREST_PROMPT = """\
You are an expert research advisor helping a colleague refine their research interests.

Given their current interest statement, what they liked and disliked about recent papers, and extracted keywords and authors, produce a concise 1-3 sentence updated research interest paragraph.

The new interest should incorporate:
- Specific topics they liked
- Areas they want to avoid
- Authors whose work resonates with them

Return ONLY the new interest paragraph — no explanation, no prefix, no formatting."""


def refine_interest(profile: Profile, model: str, liked_papers: list[tuple[str, str]] | None = None) -> str:
    """Generate a refined interest paragraph based on feedback history.

    Args:
        profile: The user profile with history and current interest.
        model: The LLM model to use.
        liked_papers: Optional list of (title, feedback) tuples recently reviewed.
                      If None, derives from profile.history.

    Returns:
        The refined interest paragraph, or the current interest if no feedback exists.
    """
    liked_keywords = _extract_liked_keywords(profile)
    liked_authors = _extract_liked_authors(profile)
    disliked_keywords = _extract_disliked_keywords(profile)

    if liked_papers is None:
        liked_papers = [(e.title, e.feedback) for e in profile.history if e.liked and e.feedback]

    if not liked_keywords and not liked_papers:
        return profile.interest

    context_parts = [f"Current interest: {profile.interest}"]

    if liked_papers:
        context_parts.append("\nLiked papers:")
        for title, feedback in liked_papers:
            context_parts.append(f"  - {title}" + (f" (feedback: {feedback})" if feedback else ""))

    if liked_keywords:
        context_parts.append(f"\nPositive keywords: {', '.join(liked_keywords)}")

    if liked_authors:
        context_parts.append(f"Liked authors: {', '.join(liked_authors)}")

    if disliked_keywords:
        context_parts.append(f"Negative keywords: {', '.join(disliked_keywords)}")

    context = "\n".join(context_parts)

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": REFINE_INTEREST_PROMPT},
            {"role": "user", "content": context},
        ],
        max_tokens=300,
        temperature=0.5,
    )

    new_interest = (response.choices[0].message.content or "").strip()
    return new_interest if new_interest else profile.interest
