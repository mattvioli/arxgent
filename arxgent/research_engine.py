from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

os.environ["LITELLM_LOG"] = "ERROR"

import arxiv
import litellm

from arxgent.agents import Paper

SEARCH_ARXIV_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_arxiv",
        "description": "Search arxiv for papers matching a query. Returns a list of papers with title, authors, abstract snippet, and url.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Supports arxiv prefixes like all:, ti:, au:, cat:, abs:.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 10, max 50)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
}

GET_PAPER_DETAILS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_paper_details",
        "description": "Get full details for a specific arxiv paper including the complete abstract, all authors, and categories.",
        "parameters": {
            "type": "object",
            "properties": {
                "arxiv_id": {
                    "type": "string",
                    "description": "The arxiv ID of the paper (e.g. '1706.03762')",
                },
            },
            "required": ["arxiv_id"],
        },
    },
}

SUMMARIZE_PAPER_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "summarize_paper",
        "description": "Generate a structured summary of an arxiv paper including overview, key contribution, and relevance.",
        "parameters": {
            "type": "object",
            "properties": {
                "arxiv_id": {
                    "type": "string",
                    "description": "The arxiv ID of the paper to summarize",
                },
            },
            "required": ["arxiv_id"],
        },
    },
}

TOOLS: list[dict[str, Any]] = [
    SEARCH_ARXIV_TOOL,
    GET_PAPER_DETAILS_TOOL,
    SUMMARIZE_PAPER_TOOL,
]

SYSTEM_PROMPT = """You are a research assistant that helps users find and understand academic papers on arxiv.

You have access to tools to search for papers, get full details, and generate summaries.

Guidelines:
- Only use search_arxiv when the user explicitly asks to find or search for new papers (e.g. "find papers about X", "search for X", "what's new in X").
- If the user asks a question about papers already shown in the conversation, discusses research ideas, or gives feedback, just respond conversationally using what's already been discussed — do NOT search unless asked.
- Present results clearly with paper titles, authors, and a brief note on relevance.
- Include the arxiv URL for each paper so the user can click through.
- If the user asks about a specific paper already in the results, use get_paper_details to get the full abstract.
- If the user wants a summary, use summarize_paper to generate one.
- Ask clarifying questions when the user's request is vague.
- You can search multiple times to refine results based on user feedback, but only when the user has explicitly asked you to search."""

STATUS_LABELS: dict[str, str] = {
    "search_arxiv": "searching",
    "get_paper_details": "fetching",
    "summarize_paper": "summarizing",
}

TOOL_STATUS_MESSAGES: dict[str, str] = {
    "search_arxiv": "🔍 Searching arxiv...",
    "get_paper_details": "📄 Fetching paper details...",
    "summarize_paper": "📝 Summarizing paper...",
}


def _search_arxiv_impl(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=min(max_results, 50),
        sort_by=arxiv.SortCriterion.Relevance,
    )
    results: list[dict[str, Any]] = []
    for result in client.results(search):
        arxiv_id = result.entry_id.removeprefix("http://arxiv.org/abs/")
        arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
        results.append(
            {
                "arxiv_id": arxiv_id,
                "title": result.title,
                "authors": [a.name for a in result.authors],
                "published": result.published.strftime("%Y-%m-%d"),
                "abstract": result.summary,
                "abstract_snippet": result.summary[:300] + "...",
                "url": f"https://arxiv.org/abs/{arxiv_id}",
            }
        )
    return results


def _get_paper_details_impl(arxiv_id: str) -> dict[str, Any] | None:
    client = arxiv.Client()
    search = arxiv.Search(id_list=[arxiv_id])
    try:
        result = next(client.results(search))
    except StopIteration:
        return None
    return {
        "arxiv_id": arxiv_id,
        "title": result.title,
        "authors": [a.name for a in result.authors],
        "published": result.published.strftime("%Y-%m-%d"),
        "categories": list(result.categories),
        "abstract": result.summary,
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
    }


def _summarize_paper_impl(arxiv_id: str, model: str) -> str:
    paper_data = _get_paper_details_impl(arxiv_id)
    if paper_data is None:
        return "Paper not found."

    paper = Paper(
        arxiv_id=paper_data["arxiv_id"],
        title=paper_data["title"],
        authors=paper_data["authors"],
        published=paper_data["published"],
        categories=paper_data.get("categories", []),
        abstract=paper_data["abstract"],
        arxiv_url=paper_data["url"],
        pdf_url=paper_data["pdf_url"],
    )

    from arxgent.summarizer import SUMMARIZE_SYSTEM_PROMPT

    prompt = SUMMARIZE_SYSTEM_PROMPT.format(
        interest="the user's research interests"
    )

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


class ResearchEngine:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.papers: dict[str, dict[str, Any]] = {}

        self.on_status: Callable[[str], None] | None = None
        self.on_papers_updated: Callable[[], None] | None = None
        self.on_tool_start: Callable[[str, dict[str, Any]], None] | None = None
        self.on_tool_end: Callable[[str, dict[str, Any]], None] | None = None

    def process_message(
        self, user_msg: str, history: list[dict[str, Any]]
    ) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": user_msg})

        while True:
            if self.on_status:
                self.on_status("thinking")

            response = litellm.completion(
                model=self.model,
                messages=messages,
                tools=TOOLS,
                temperature=0.3,
            )

            msg = response.choices[0].message

            if not msg.tool_calls:
                if self.on_status:
                    self.on_status("ready")
                return msg.content or ""

            for tc in msg.tool_calls:
                tool_name = tc.function.name
                args = json.loads(tc.function.arguments)

                if self.on_tool_start:
                    self.on_tool_start(tool_name, args)

                if self.on_status:
                    self.on_status(
                        STATUS_LABELS.get(tool_name, "thinking")
                    )

                if tool_name == "search_arxiv":
                    result = _search_arxiv_impl(**args)
                    for p in result:
                        self.papers[p["arxiv_id"]] = p
                    if self.on_papers_updated:
                        self.on_papers_updated()
                elif tool_name == "get_paper_details":
                    result = _get_paper_details_impl(**args)
                    if result:
                        self.papers[result["arxiv_id"]] = result
                        if self.on_papers_updated:
                            self.on_papers_updated()
                elif tool_name == "summarize_paper":
                    result = _summarize_paper_impl(
                        arxiv_id=args["arxiv_id"], model=self.model
                    )
                else:
                    result = f"Unknown tool: {tool_name}"

                if self.on_tool_end:
                    self.on_tool_end(tool_name, args)

                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tc],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result)
                        if not isinstance(result, str)
                        else result,
                    }
                )
