from __future__ import annotations

import re

from arxgent.profile import Profile


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
