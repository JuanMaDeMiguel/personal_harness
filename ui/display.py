import shutil
from pathlib import Path

from rich.console import Console

from . import theme

console = Console()


def format_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        if isinstance(v, str):
            display = v[:80] + ("…" if len(v) > 80 else "")
            parts.append(f'{k}="{display}"')
        else:
            parts.append(f"{k}={v!r}")
    return ", ".join(parts)


def print_result_preview(result: str, max_lines: int = 3, max_width: int = 110):
    lines = result.splitlines()
    for line in lines[:max_lines]:
        console.print(f"  [{theme.C.result}]{line[:max_width]}[/{theme.C.result}]")
    if len(lines) > max_lines:
        console.print(f"  [{theme.C.dim}]... ({len(lines)} lines total)[/{theme.C.dim}]")


def print_edit_diff(args: dict):
    """Claude Code-style diff: context lines above/below + red/green changed lines."""
    CONTEXT = 3   # lines of context above and below
    MAX_CHANGE = 8  # max changed lines to show before truncating

    filepath  = args.get("filepath", "?")
    old_str   = args.get("old_string", "")
    new_str   = args.get("new_string", "")
    old_lines = old_str.splitlines() or [""]
    new_lines = new_str.splitlines() or [""]

    # Read file to get context lines and the line number of the change.
    all_lines: list[str] = []
    start_ln = 1
    try:
        content = Path(filepath).read_text(encoding="utf-8")
        all_lines = content.splitlines()
        idx = content.find(new_str)
        if idx >= 0:
            start_ln = content[:idx].count("\n") + 1
    except Exception:
        pass

    w = shutil.get_terminal_size((80, 20)).columns

    def _row(ln: int, sign: str, text: str, bg: str | None, fg: str):
        ln_str = f"{ln:>4}" if ln > 0 else "    "
        prefix = f"{ln_str} {sign} "
        avail  = max(w - len(prefix) - 1, 20)
        padded = text[:avail].ljust(avail)
        if bg:
            console.print(f"[{fg} on {bg}]{prefix}{padded}[/{fg} on {bg}]")
        else:
            console.print(f"[{fg}]{prefix}{text[:avail]}[/{fg}]")

    # Context lines before the change (from the current file state)
    ctx_start = max(0, start_ln - 1 - CONTEXT)  # 0-indexed
    for i in range(ctx_start, start_ln - 1):
        if i < len(all_lines):
            _row(i + 1, " ", all_lines[i], None, theme.C.dim)

    # Removed lines
    for i, line in enumerate(old_lines[:MAX_CHANGE]):
        _row(start_ln + i, "-", line, theme.C.diff_rm_bg, theme.C.diff_rm_fg)
    if len(old_lines) > MAX_CHANGE:
        console.print(f"  [{theme.C.dim}]  … ({len(old_lines)} lines)[/{theme.C.dim}]")

    # Added lines
    for i, line in enumerate(new_lines[:MAX_CHANGE]):
        _row(start_ln + i, "+", line, theme.C.diff_add_bg, theme.C.diff_add_fg)
    if len(new_lines) > MAX_CHANGE:
        console.print(f"  [{theme.C.dim}]  … ({len(new_lines)} lines)[/{theme.C.dim}]")

    # Context lines after the change
    ctx_end_start = start_ln - 1 + len(new_lines)  # 0-indexed
    for i in range(ctx_end_start, min(ctx_end_start + CONTEXT, len(all_lines))):
        _row(i + 1, " ", all_lines[i], None, theme.C.dim)
