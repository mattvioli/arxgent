from __future__ import annotations

import os

os.environ["LITELLM_LOG"] = "ERROR"

import litellm

from arxgent.feedback import _extract_disliked_keywords, _extract_liked_authors, _extract_liked_keywords
from arxgent.profile import Profile


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
