from __future__ import annotations

import os

os.environ["LITELLM_LOG"] = "ERROR"

import litellm

from arxgent.agents import Paper
from arxgent.config import LLMConfig
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


def summarize_paper(paper: Paper, profile: Profile, llm_config: LLMConfig) -> str:
    prompt = SUMMARIZE_SYSTEM_PROMPT.format(interest=profile.interest)

    kwargs: dict = dict(
        model=llm_config.model,
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
        max_tokens=llm_config.max_tokens,
        temperature=llm_config.temperature,
    )
    if llm_config.api_base:
        kwargs["api_base"] = llm_config.api_base
    if llm_config.api_key:
        kwargs["api_key"] = llm_config.api_key

    response = litellm.completion(**kwargs)

    summary = response.choices[0].message.content or ""

    summary = summary.replace("{arxiv_url}", paper.arxiv_url)
    summary = summary.replace("{pdf_url}", paper.pdf_url)

    return summary
