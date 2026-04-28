# Harness

A local CLI AI agent built in pure Python. Harness implements a **ReAct (Reasoning + Acting)** loop against a custom OpenAI-compatible API, with a polished terminal UI that mirrors the aesthetics of Claude Code.

```
────────────────────────────────────────────────────────────────
> what does this codebase do?

  Exploring project structure to answer the question
● run_bash(command="ls -la && cat README.md 2>/dev/null | head -60")
  total 208
  -rw-r--r-- api.py
  -rw-r--r-- harness.py
  ... (12 lines total)

A local CLI AI coding agent built in Python...
────────────────────────────────────────────────────────────────
>
──────────────────────────────────────── gpt-5.5 · medium
```

---

## Features

- **ReAct loop** — the model plans tool calls, executes them locally, feeds observations back, and generates a final answer
- **Tool calling** — `run_bash`, `edit_file`, `read_file`, `list_files`; easily extensible with a single decorator
- **Session persistence** — conversations are saved across restarts; `/resume` replays any past session
- **Slash commands** — `/model`, `/effort`, `/theme`, `/resume`, `/exit` with FZF-style autocomplete
- **Live theme detection** — queries OSC 11 on every prompt; switches between dark/light palette automatically when the terminal theme changes
- **Claude Code color palette** — colors extracted directly from the Claude Code 2.1.119 binary (`permission`, `diffAdded`, `diffRemoved`, etc.)
- **Clean diff display** — `edit_file` shows a context diff (3 lines above/below) with exact Claude Code diff colors
- **Configurable reasoning effort** — `low` / `medium` / `high` / `xhigh` passed directly to the model

---

## Architecture

```
User input
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  ReAct Loop  (harness.py, up to 20 iterations)          │
│                                                         │
│  ┌──────────┐    JSON plan     ┌──────────────────────┐ │
│  │ Planner  │ ──────────────▶  │  Tool Executor       │ │
│  │  (api.py)│ ◀─────────────── │  (tools.py)          │ │
│  └──────────┘   observation    └──────────────────────┘ │
│       │                                                  │
│       │ answer_directly / max iterations                │
│       ▼                                                  │
│  ┌──────────┐                                            │
│  │  Answer  │                                            │
│  │  (api.py)│                                            │
│  └──────────┘                                            │
└─────────────────────────────────────────────────────────┘
    │
    ▼
Rich Markdown output
```

### Two-prompt design

The proxy API has pre-configured agent behavior and strips system prompts. Harness works around this with **two separate calls per iteration**:

1. **Planner call** — receives the tool signatures and current observations; returns a single JSON object: `{"action": "run_bash", "args": {...}, "reason": "..."}`
2. **Answer call** — receives all accumulated observations; generates the final Markdown response

### Planner guardrails

The planner prompt is written so the model:
- Uses tools when it needs information it doesn't already have
- Chooses `answer_directly` only when the answer is already present in the context
- Respects session context from previous turns (tool results are serialised as `[tool(args)] -> result`)

---

## Project structure

```
harness/
├── harness.py          # Entry point + main ReAct loop
├── tools.py            # Tool registry (@toolset.tool decorator)
├── config.py           # API endpoint, model, session file, runtime flags
├── prompts.py          # PLANNER_TEMPLATE and ANSWER_TEMPLATE
├── api.py              # call_api(), plan_next_action(), get_final_answer()
├── session.py          # load/save/build_context/handle_resume
├── test_harness.py     # Smoke-test suite (55 tests, no network calls)
└── ui/
    ├── __init__.py     # Re-exports
    ├── app.py          # Custom prompt_toolkit Application (the core input widget)
    ├── theme.py        # OSC 11 detection, Colors palette, apply()
    ├── display.py      # Rich console, print_result_preview, print_edit_diff
    ├── input.py        # prompt() wrapper
    └── completer.py    # SlashCompleter (FZF-style slash command autocomplete)
```

---

## Installation

```bash
git clone https://github.com/<you>/harness.git
cd harness
python -m venv venv
source venv/bin/activate
pip install requests python-dotenv rich prompt_toolkit
```

Create a `.env` file with your API key:

```
OPENAI_API_KEY=your_key_here
```

---

## Usage

```bash
source venv/bin/activate
python harness.py

# Verbose API logging
python harness.py --debug
```

### Slash commands

| Command | Description |
|---------|-------------|
| `/model <name>` | Switch model at runtime (`gpt-5.4`, `gpt-5.5`, …) |
| `/effort <level>` | Set reasoning effort: `low` `medium` `high` `xhigh` |
| `/theme dark\|light` | Override terminal theme |
| `/resume` | Pick and replay a previous session |
| `/exit` | Quit |

Type `/` at the prompt and use arrow keys to navigate the autocomplete menu. The current model and effort level are always shown in the status bar.

### Adding tools

Add a decorated function to `tools.py`:

```python
@toolset.tool
def my_tool(param1: str, param2: str = "default"):
    """One-line description shown to the model."""
    # your implementation
    return result  # raise exceptions on error, don't return error strings
```

That's it — the tool is auto-discovered and its signature is injected into the planner prompt.

---

## Configuration

All runtime configuration lives in `config.py`. Key values:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENDPOINT` | `https://…/v1/responses` | API endpoint |
| `MODEL` | `gpt-5.5` | Default model |
| `active_model` | `MODEL` | Mutable; changed by `/model` |
| `reasoning_effort` | `"medium"` | Mutable; changed by `/effort` |
| `MAX_SESSIONS` | `50` | Sessions kept in the history file |

---

## Running the tests

```bash
source venv/bin/activate
python test_harness.py
```

The suite mocks network calls and covers imports, theme switching, session persistence, diff rendering, tool execution, slash command completion, and the planner's JSON passthrough.

---

## Technical notes

### Terminal theme hot-reload

On every prompt the UI queries OSC 11 (terminal background colour via escape sequence). If the result changes (e.g. the user switched from dark to light mode in their terminal), `apply_theme()` is called and all colour globals update in-place. The first query that fails (tmux, headless, etc.) sets a flag so subsequent prompts skip the 150 ms timeout.

### Custom prompt layout

The input widget is a hand-rolled `prompt_toolkit.Application` rather than the built-in `pt_prompt()`. This lets the layout be:

```
[input — grows/shrinks as text wraps]
[─── rule ───────────────────────────]
[completions — 0 rows when empty    ]
[model · effort ─ right-aligned ─── ]
```

A `ConditionalContainer` makes the completion area literally 0 rows when the menu is closed, so there is no reserved blank space.

### Session context

Each session turn stores up to 1 500 chars of tool output. On `/resume` (or across turns in the same session), previous results are injected into both the planner and answer prompts as `[tool(args)] -> result` lines — the same format the model was trained to parse from its own outputs.
