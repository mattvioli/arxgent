from __future__ import annotations

from typing import Any

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Input, Label, RichLog, Static

from arxgent.config import LLMConfig
from arxgent.research_engine import (
    TOOL_STATUS_MESSAGES,
    ResearchEngine,
)


class PaperCard(Static):
    class SummarizePaper(Message):
        def __init__(self, arxiv_id: str, title: str) -> None:
            super().__init__()
            self.arxiv_id = arxiv_id
            self.title = title

    def __init__(self, paper: dict[str, Any], index: int) -> None:
        super().__init__()
        self.paper = paper
        self.index = index

    def compose(self) -> ComposeResult:
        with Vertical(classes="paper-card"):
            yield Label(
                f"#{self.index} {self.paper['title']}",
                classes="paper-title",
            )
            authors = ", ".join(self.paper["authors"][:2])
            if len(self.paper["authors"]) > 2:
                authors += " et al."
            yield Label(authors, classes="paper-authors")
            yield Label(self.paper["published"], classes="paper-date")
            arxiv_id = self.paper["arxiv_id"]
            yield Label(
                f'[link="https://arxiv.org/abs/{arxiv_id}"]arxiv.org/abs/{arxiv_id}[/link]',
                classes="paper-link",
            )
            yield Button(
                "Summarize", id=f"summarize-{arxiv_id.replace('.', '-')}"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.post_message(
            self.SummarizePaper(self.paper["arxiv_id"], self.paper["title"])
        )


class PaperPanel(VerticalScroll):
    papers: reactive[dict[str, dict[str, Any]]] = reactive({})

    def watch_papers(
        self, papers: dict[str, dict[str, Any]]
    ) -> None:
        self.remove_children()
        if not papers:
            self.mount(
                Label(
                    "No papers found yet.\nSearch for a topic to get started.",
                    classes="paper-placeholder",
                )
            )
            return
        for i, (arxiv_id, paper) in enumerate(papers.items(), 1):
            self.mount(PaperCard(paper, i))


class ChatLog(RichLog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, wrap=True, **kwargs)
    
    def on_mount(self) -> None:
        self.write(
            Text(
                "Welcome! I can help you find papers on arxiv. "
                "Tell me what you're researching.",
                style="italic",
            )
        )


class ChatInput(Input):
    BINDINGS = [
        Binding("escape", "clear", "Clear input"),
    ]

    def action_clear(self) -> None:
        self.value = ""


class StatusBar(Static):
    status: reactive[str] = reactive("ready")

    def watch_status(self, status: str) -> None:
        labels = {
            "ready": "Ready",
            "thinking": "💭 Thinking...",
            "searching": "🔍 Searching arxiv...",
            "fetching": "📄 Fetching paper details...",
            "summarizing": "📝 Summarizing paper...",
        }
        self.update(f"Status: {labels.get(status, status)}")


class ChatScreen(Screen[None]):
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self, llm_config: LLMConfig) -> None:
        super().__init__()
        self.llm_config = llm_config
        self.engine = ResearchEngine(llm_config=llm_config)
        self.history: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Horizontal(classes="top-area"):
            yield ChatLog(id="chat-log")
            yield Vertical(
                Label("📄 Papers", classes="panel-header"),
                PaperPanel(id="paper-panel"),
                classes="right-panel",
            )
        yield ChatInput(
            id="chat-input",
            placeholder="Ask about a research topic...",
        )
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self.engine.on_status = self._on_status
        self.engine.on_papers_updated = self._on_papers_updated
        self.engine.on_tool_start = self._on_tool_start
        self.engine.on_tool_end = self._on_tool_end
        self.query_one(ChatInput).focus()

    def _call_from_thread_safe(self, method, *args, **kwargs):
        try:
            self.app.call_from_thread(method, *args, **kwargs)
        except RuntimeError:
            method(*args, **kwargs)

    def _on_status(self, status: str) -> None:
        self._call_from_thread_safe(
            self.query_one(StatusBar).__setattr__, "status", status
        )

    def _on_papers_updated(self) -> None:
        self._call_from_thread_safe(
            self.query_one(PaperPanel).__setattr__,
            "papers",
            dict(self.engine.papers),
        )

    def _on_tool_start(
        self, tool_name: str, args: dict[str, Any]
    ) -> None:
        msg = TOOL_STATUS_MESSAGES.get(tool_name, f"Running {tool_name}...")
        self._call_from_thread_safe(
            self.query_one(ChatLog).write, Text(msg, style="dim italic")
        )

    def _on_tool_end(
        self, tool_name: str, args: dict[str, Any]
    ) -> None:
        pass

    def on_paper_card_summarize_paper(
        self, event: PaperCard.SummarizePaper
    ) -> None:
        msg = f"Summarize paper {event.arxiv_id}: {event.title}"
        self.query_one(ChatInput).value = msg
        self._submit_message(msg)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        msg = event.value.strip()
        if not msg:
            return
        self.query_one(ChatInput).clear()
        self._submit_message(msg)

    def _submit_message(self, msg: str) -> None:
        self.query_one(ChatLog).write(
            Text(f"> {msg}", style="bold")
        )
        self.history.append({"role": "user", "content": msg})
        self._process_with_engine(msg)

    @work(exclusive=True, thread=True)
    def _process_with_engine(self, msg: str) -> None:
        try:
            response = self.engine.process_message(msg, self.history)
            self.app.call_from_thread(self._append_response, response)
        except Exception as e:
            self.app.call_from_thread(
                self._show_error, str(e)
            )

    def _append_response(self, response: str) -> None:
        self.query_one(ChatLog).write(Text(response))
        self.history.append({"role": "assistant", "content": response})
        self._on_status("ready")

    def _show_error(self, error: str) -> None:
        self.query_one(ChatLog).write(
            Text(f"Error: {error}", style="bold red")
        )
        self._on_status("ready")


class ResearchApp(App[None]):
    TITLE = "arxgent research"
    CSS = """
    Screen {
        layout: vertical;
    }

    .top-area {
        layout: horizontal;
        height: 1fr;
    }

    #chat-log {
        width: 2fr;
        border: solid $primary;
        padding: 0 1;
        overflow-x: hidden;
    }

    .right-panel {
        width: 1fr;
        height: 1fr;
        border: solid $secondary;
        padding: 0 1;
    }

    .panel-header {
        text-style: bold;
        padding: 1 0;
    }

    #paper-panel {
        height: 1fr;
    }

    .paper-card {
        border: solid $surface;
        padding: 0 1;
        margin: 1 0;
        height: auto;
    }

    .paper-title {
        text-style: bold;
    }

    .paper-authors {
        color: $text-muted;
    }

    .paper-date {
        color: $text-muted;
    }

    .paper-link {
        color: $accent;
    }

    .paper-placeholder {
        color: $text-muted;
        padding: 1 0;
    }

    #chat-input {
        height: 3;
        margin: 1 0;
    }

    #status-bar {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(self, llm_config: LLMConfig) -> None:
        super().__init__()
        self.llm_config = llm_config

    def on_mount(self) -> None:
        self.push_screen(ChatScreen(llm_config=self.llm_config))

def run_research(llm_config: LLMConfig) -> None:
    app = ResearchApp(llm_config=llm_config)
    app.run()
