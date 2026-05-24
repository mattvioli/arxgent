from __future__ import annotations

import json
import os
import re

os.environ["LITELLM_LOG"] = "ERROR"

import litellm

from arxgent.agents import Paper


RANKER_SYSTEM_PROMPT = """\
You are an expert research advisor selecting the most relevant papers for a colleague.

Given a research interest and a numbered list of papers (title + abstract excerpt), \
return a JSON array of objects for the top {top_k} papers that best match the interest.

Each object must have:
- "index": the 0-based index of the paper
- "reason": a one-sentence explanation of why this paper is relevant

Consider:
- Direct topical relevance to the stated interest
- Methodological overlap
- Potential impact on the reader's work

Return ONLY a valid JSON array — no explanation, no markdown, no prefix.
Example: [{{"index": 3, "reason": "Directly addresses transformer architectures for coding tasks."}}]"""


def _build_ranker_context(papers: list[Paper]) -> str:
    lines: list[str] = []
    for i, p in enumerate(papers):
        abstract_short = p.abstract[:150].strip()
        lines.append(f"{i}. {p.title} — {abstract_short}")
    return "\n".join(lines)


def _extract_json(text: str) -> str:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    start = text.find("[")
    if start == -1:
        start = text.find("{")
    if start != -1:
        text = text[start:]
    end = text.rfind("]")
    if end == -1:
        end = text.rfind("}")
    if end != -1:
        text = text[: end + 1]
    return text


def rank_papers_by_interest(
    papers: list[Paper],
    interest: str,
    model: str,
    top_k: int = 3,
) -> list[tuple[Paper, str]]:
    if not interest or not papers:
        return [(p, "") for p in papers[:top_k]]

    if len(papers) <= top_k:
        return [(p, "") for p in papers]

    context = _build_ranker_context(papers)
    prompt = f"Research interest: {interest}\n\nPapers:\n{context}"

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": RANKER_SYSTEM_PROMPT.format(top_k=top_k)},
            {"role": "user", "content": prompt},
        ],
        max_tokens=top_k * 128,
        temperature=0.3,
    )

    content = (response.choices[0].message.content or "").strip()

    content = _extract_json(content)

    try:
        parsed = json.loads(content)
        if not isinstance(parsed, list):
            return [(p, "") for p in papers[:top_k]]

        # support both [{"index": i, "reason": "..."}] and plain [i, j, k]
        if parsed and isinstance(parsed[0], dict):
            indices = [item["index"] for item in parsed if isinstance(item.get("index"), int) and 0 <= item["index"] < len(papers)]
            reasons = {item["index"]: item.get("reason", "") for item in parsed if isinstance(item.get("index"), int)}
        else:
            indices = [i for i in parsed if isinstance(i, int) and 0 <= i < len(papers)]
            reasons = {}

        ranked = [(papers[i], reasons.get(i, "")) for i in indices]
        if len(ranked) == top_k:
            return ranked
        ranked_indices = set(indices)
        for p in papers:
            if len(ranked) >= top_k:
                break
            if p not in [r[0] for r in ranked]:
                ranked.append((p, ""))
        return ranked
    except (json.JSONDecodeError, ValueError, KeyError):
        print(f"  Ranker: could not parse response:\n    {content[:300]}")
        return [(p, "") for p in papers[:top_k]]
