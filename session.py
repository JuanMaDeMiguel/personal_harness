import json

from rich.markdown import Markdown

import config
from ui import theme, console, prompt as harness_prompt


def load() -> list[dict]:
    if config.SESSIONS_FILE.exists():
        try:
            data = json.loads(config.SESSIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            if config.debug:
                console.print(
                    f"[{theme.C.dim}]Warning: sessions file has unexpected format, "
                    f"starting fresh.[/{theme.C.dim}]"
                )
        except Exception as e:
            if config.debug:
                console.print(
                    f"[{theme.C.dim}]Warning: could not load sessions ({e}), "
                    f"starting fresh.[/{theme.C.dim}]"
                )
    return []


def save(sessions: list[dict]):
    """Atomic write via .tmp + replace to prevent corruption on crash."""
    tmp = config.SESSIONS_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(sessions[-config.MAX_SESSIONS:], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(config.SESSIONS_FILE)
    except Exception as e:
        if config.debug:
            console.print(
                f"[{theme.C.dim}]Warning: could not save sessions ({e}).[/{theme.C.dim}]"
            )
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def build_context(turns: list[dict]) -> str:
    """Serialise previous tool results into [tool(args)] -> result format."""
    if not turns:
        return ""
    lines = []
    for t in turns:
        lines.append(f"# Earlier turn: {t['user']}")
        for tc in t.get("tool_calls", []):
            ctx = tc.get("result_context", "")
            if ctx:
                lines.append(f"[{tc['name']}({tc['args_str']})] -> {ctx}")
        if t.get("answer"):
            lines.append(f"# Answer given: {t['answer'][:400]}")
    return "\n".join(lines)


def display_history(session: dict):
    if not session.get("turns"):
        return
    started = session.get("started", "previous session")
    for turn in session["turns"]:
        console.rule(style=theme.C.rule)
        console.print(f"[bold {theme.C.tool}]>[/bold {theme.C.tool}] {turn['user']}")
        console.rule(style=theme.C.rule)
        for tc in turn.get("tool_calls", []):
            if tc.get("reason"):
                console.print(f"[{theme.C.reason}]{tc['reason']}[/{theme.C.reason}]")
            console.print(
                f"[{theme.C.tool}]●[/{theme.C.tool}] "
                f"[{theme.C.tool}]{tc['name']}[/{theme.C.tool}]"
                f"([{theme.C.args}]{tc.get('args_str', '')}[/{theme.C.args}])"
            )
            lines = tc.get("result_preview_lines", [])
            total = tc.get("result_total_lines", len(lines))
            for line in lines:
                console.print(f"  [{theme.C.result}]{line[:110]}[/{theme.C.result}]")
            if total > len(lines):
                console.print(f"  [{theme.C.dim}]... ({total} lines total)[/{theme.C.dim}]")
            console.print()
        if turn.get("answer"):
            console.print(Markdown(turn["answer"]))
    console.rule(f"[{theme.C.hist}]{started}[/{theme.C.hist}]", style=theme.C.hist)
    console.print()


def handle_resume(all_sessions: list[dict], history) -> str | None:
    """Show session picker, replay chosen session, return its context string."""
    candidates = [s for s in all_sessions if s.get("turns")]
    if not candidates:
        console.print(f"[{theme.C.dim}]No previous sessions found.[/{theme.C.dim}]\n")
        return None

    ordered = list(reversed(candidates))
    console.print(f"\n[{theme.C.header}]Sessions[/{theme.C.header}]\n")
    for i, s in enumerate(ordered, 1):
        started = s.get("started", "unknown")
        turns   = s.get("turns", [])
        preview = turns[0]["user"][:60] if turns else ""
        n       = len(turns)
        label   = f"{n} turn{'s' if n != 1 else ''}"
        console.print(
            f"  [{theme.C.dim}]{i:>2}.[/{theme.C.dim}]  [{theme.C.args}]{started}[/{theme.C.args}]"
            f"  [{theme.C.dim}]{preview}  ({label})[/{theme.C.dim}]"
        )

    console.print()
    console.rule(style=theme.C.rule)
    try:
        choice = harness_prompt(
            message=[("class:prompt", "Session > ")],
            history=history,
        ).strip()
    except (KeyboardInterrupt, EOFError):
        console.rule(style=theme.C.rule)
        return None

    console.rule(style=theme.C.rule)
    console.print()

    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(ordered)):
            raise ValueError
    except ValueError:
        console.print(f"[{theme.C.error}]Invalid selection.[/{theme.C.error}]\n")
        return None

    display_history(ordered[idx])
    return build_context(ordered[idx].get("turns", []))
