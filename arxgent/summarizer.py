from __future__ import annotations

import os

os.environ["LITELLM_LOG"] = "ERROR"

import litellm

from arxgent.agents import Paper
from arxgent.profile import Profile


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
