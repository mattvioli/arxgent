# arxgent — arxiv research agent that learns your interests

A CLI tool that searches arxiv by your chosen categories, summarizes papers via any [litellm](https://github.com/BerriAI/litellm)-supported LLM, saves Obsidian-ready markdown files, and refines future searches from your feedback.

## Features

- **Category-based search** — pick from 8 arxiv groups (CS, Physics, Math, Statistics, etc.)
- **Any LLM** — model-agnostic via litellm (`gpt-4o-mini`, `claude-sonnet-4-20250514`, `ollama/qwen2.5`, etc.)
- **Smart summaries** — structured markdown with overview, key contribution, and relevance to your interest
- **Preference learning** — keywords and liked authors from your feedback refine future arxiv queries
- **Interest evolution** — LLM-generated interest paragraph updates based on what you liked/disliked
- **Obsidian-ready output** — YAML frontmatter with arxiv/PDF links, saved as `Title_Author_YYYY-MM.md`
- **Interactive CLI** — questionary-powered setup and review wizards

## Quick start

```bash
uv tool install arxgent
# or: pip install arxgent (not yet published)

arxgent setup              # interactive wizard: pick categories, write interest
arxgent run                # search → summarize → save → review
arxgent review             # re-review unread papers
arxgent status             # show profile, stats, config
```

## Configuration

Config at `~/.config/arxgent/config.json`:

```json
{
  "llm": {
    "model": "gpt-4o-mini",
    "max_tokens": 1024,
    "temperature": 0.3
  },
  "output_dir": "~/research/papers",
  "num_papers": 3,
  "skip_review": false
}
```

API keys are resolved from `$VAR_NAME` syntax — set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. in your environment.

## Profile

Saved at `~/.config/arxgent/profile.json` — contains your categories, interest paragraph, paper history, and feedback. Automatically updated by `setup`, `run`, and `review`.

## Usage

```bash
arxgent run                          # last 7 days
arxgent run --date today
arxgent run --date custom --start 2026-05-01 --end 2026-05-24
arxgent run --skip-review            # skip the post-run review prompt

arxgent setup --model claude-sonnet-4-20250514   # setup + set LLM

arxgent review                       # review unread papers
arxgent status                       # check stats
```

## Development

```bash
git clone <repo> && cd arxgent
uv sync
uv run pytest tests/
uv run ruff check .
```

## How it works

1. **`setup`**: Pick arxiv categories → write a research interest paragraph → profile saved
2. **`run`**: Build arxiv query (categories + dates + learned keywords/authors) → fetch papers → summarize each via LLM (prompted with your interest) → save `.md` files → optionally review
3. **`review`**: For each unread paper → mark read/unread, liked/disliked/neutral, add feedback → keywords/authors extracted → interest paragraph refined via LLM → profile updated
4. Next `run` uses the refined keywords, authors, and interest

## Project structure

```
arxgent/
├── arxgent/
│   ├── agents.py       # paper model, query builder, arxiv search, summarizer, interest refiner
│   ├── categories.py   # 8 arxiv groups with subcategory IDs and names
│   ├── cli.py          # click commands: setup, run, review, status
│   ├── config.py       # Pydantic config model, save/load/resolve env vars
│   ├── profile.py      # Pydantic profile model, save/load, setup wizard
│   └── storage.py      # markdown writer with YAML frontmatter
└── tests/
    ├── test_agents.py
    ├── test_categories.py
    ├── test_cli.py
    ├── test_config.py
    ├── test_profile.py
    └── test_storage.py
```

## License

MIT
