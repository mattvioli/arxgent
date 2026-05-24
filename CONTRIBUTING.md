# Contributing to Arxgent

## Architecture

### Module overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   cli.py    │────▶│  agents.py   │────▶│ storage.py  │
│  (click)    │     │ (arxiv+LLM)  │     │   (YAML md) │
└─────┬───────┘     └──────┬───────┘     └─────────────┘
      │                    │
      │     ┌──────────────┴──────────┐
      │     │                         │
      ▼     ▼                         ▼
┌──────────────┐          ┌──────────────────┐
│   config.py  │          │   profile.py     │
│ (Pydantic)   │          │ (Pydantic+setup) │
└──────────────┘          └────────┬─────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │  categories.py   │
                          │  (arxiv groups)  │
                          └──────────────────┘
```

### CLI command flow

```mermaid
flowchart TD
    A[arxgent setup] --> B[Choose groups]
    B --> C[Choose subcategories]
    C --> D[Write interest paragraph]
    D --> E[Save profile.json]

    F[arxgent run] --> G[Load profile + config]
    G --> H[_build_query: categories + dates + keywords + authors]
    H --> I[arxiv.Search API]
    I --> J[For each paper: summarize_paper via litellm]
    J --> K[save_paper_md: YAML frontmatter .md file]
    K --> L[Append PaperEntry to profile history]
    L --> M[Save profile.json]

    N[arxgent review] --> O[Load profile]
    O --> P[Iterate unread PaperEntry]
    P --> Q[Mark read/liked/feedback]
    Q --> R[_extract_liked_keywords, _extract_liked_authors]
    R --> S[refine_interest via litellm]
    S --> T[Offer to update interest paragraph]
    T --> U[Save profile.json]

    O --> V{All reviewed?}
    V -- yes --> W["All caught up!"]
    V -- no --> X["N remaining"]
```

### Run data flow

```mermaid
sequenceDiagram
    participant User
    participant CLI as cli.py
    participant Agents as agents.py
    participant ArXiv as arxiv API
    participant LLM as litellm
    participant Disk as storage.py

    User->>CLI: arxgent run
    CLI->>CLI: load_profile() + load_config()
    CLI->>Agents: research_papers(profile, dates, N)
    Agents->>Agents: _build_query(cats + dates + keywords + authors)
    Agents->>ArXiv: arxiv.Search(query, max_results=N)
    ArXiv-->>Agents: List[arxiv.Result]
    Agents-->>CLI: List[Paper]

    loop Each paper
        CLI->>Agents: summarize_paper(paper, profile, model)
        Agents->>LLM: litellm.completion(system=prompt, user=title+abstract)
        LLM-->>Agents: Markdown summary
        Agents-->>CLI: str summary
        CLI->>Disk: save_paper_md(paper, summary, output_dir)
        Disk-->>CLI: Path to .md file
    end

    CLI->>CLI: Append PaperEntry to history
    CLI->>CLI: save_profile()
    User-->>CLI: (user runs arxgent review later)
```

### Preference learning loop

```mermaid
flowchart LR
    A[Feedback] --> B[_extract_terms]
    B --> C[_score_keywords: dedup + frequency]
    C --> D[liked_keywords: all:term]
    C --> E[disliked_keywords: ANDNOT all:term]

    F[Liked papers] --> G[_extract_liked_authors]
    G --> H[liked_authors: au:Name]

    D --> I[_build_query]
    E --> I
    H --> I
    I --> J[arxiv query]
    J --> K[Next run]

    L[refine_interest via LLM] --> M[Updated interest paragraph]
    M --> N[Used in summarizer prompts]
```

### Module responsibilities

| Module | Responsibility | Key exports |
|---|---|---|
| `cli.py` | Click command group, user interaction, orchestration | `cli`, `setup`, `run`, `review`, `status` |
| `agents.py` | Arxiv query building, search, LLM summarization, interest refinement | `research_papers`, `summarize_paper`, `refine_interest`, `Paper` |
| `config.py` | Config model, persistence, env var resolution | `ArxgentConfig`, `LLMConfig`, `load_config`, `save_config` |
| `profile.py` | Profile model, persistence, setup wizard | `Profile`, `PaperEntry`, `load_profile`, `run_setup_wizard` |
| `categories.py` | Arxiv category hierarchy (8 groups, ~200 subcategories) | `GROUPS`, `get_category_name`, `get_group_for_category` |
| `storage.py` | Markdown file output with YAML frontmatter | `save_paper_md`, `_slugify` |

## Setup for development

```bash
git clone <repo> && cd arxgent
uv sync
```

## Running tests

```bash
uv run pytest tests/          # all tests
uv run pytest tests/ -v       # verbose
uv run pytest tests/ -k test_query  # filter by name
uv run pytest tests/ --cov=arxgent  # coverage
```

## Code style

- **Python 3.11+** with `from __future__ import annotations`
- **Line length**: 100
- **Formatter**: Ruff (`uv run ruff check .`)
- **Models**: Pydantic v2 (`BaseModel`, `Field`, `model_validate`, `model_dump`)
- **Types**: Use `list[str]` not `List[str]` in signatures (3.9+ style), `Optional[X]` for nullable
- **Imports**: stdlib → third-party → local, separated by blank lines
- **Tests**: pytest with `CliRunner` for CLI, monkeypatch for dependencies, `MagicMock` + `patch` for external APIs

## Key design decisions

- **No AutoGen**: Sequential research→summarize is simpler as functions; can be added later
- **Query built programmatically**: Categories + dates + feedback keywords/authors constructed in Python rather than LLM-generated — deterministic, zero extra API cost
- **Keyword extraction via regex + frequency**: Not LLM — keeps latency low for v1
- **Spaces in arxiv queries**: Use actual spaces (not `+`) in query strings so the `arxiv` library's `urlencode` encodes them correctly (spaces → `+` rather than `+` → `%2B`)

## Adding a new feature

1. Add the logic in the appropriate module (`agents.py`, `profile.py`, etc.)
2. Wire up the CLI command in `cli.py`
3. Add tests in the corresponding `tests/test_*.py` file
4. Run `uv run pytest tests/` to verify
5. Run `uv run ruff check .` for style

## Pull request process

1. Ensure all tests pass
2. Add tests for new functionality
3. Update README if changing user-facing behavior
4. Open a PR with a concise description of the change
