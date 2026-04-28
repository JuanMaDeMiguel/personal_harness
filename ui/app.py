"""Custom prompt Application.

Layout (top → bottom, no blank space):
  [input area  — grows/shrinks with text]
  [rule        — 1 row, always visible]
  [completions — 0 rows when empty, N rows when active]
  [status      — 1 row, model · effort]
"""

import shutil

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import to_formatted_text, to_plain_text
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.key_binding.bindings.emacs import load_emacs_bindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import ConditionalContainer, HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.output import ColorDepth

from . import theme
import config


# ── formatted-text generators ─────────────────────────────────────────────────

def _rule_text():
    w = shutil.get_terminal_size((80, 20)).columns
    return [(theme.C.rule, "─" * w)]


def _status_text():
    w = shutil.get_terminal_size((80, 20)).columns
    text = f" {config.active_model} · {config.reasoning_effort} "
    return [(theme.C.tool, text.rjust(w))]


def _completion_text():
    """Render the current completion list as FormattedText tuples."""
    try:
        cs = get_app().current_buffer.complete_state
    except Exception:
        return []
    if not cs or not cs.completions:
        return []

    w       = shutil.get_terminal_size((80, 20)).columns
    bg      = theme.C.menu_bg
    sel_fg  = theme.C.menu_sel_fg
    norm_fg = theme.C.args
    dim_fg  = theme.C.dim

    result = []
    for i, c in enumerate(cs.completions[:10]):
        is_sel  = (i == cs.complete_index)
        display = to_plain_text(c.display)
        meta    = to_plain_text(c.display_meta)

        # Two columns: command (left, padded) + description (right)
        left  = display.ljust(14)
        line  = f"  {left}   {meta}"
        line  = line[:w].ljust(w)

        if is_sel:
            result.append((f"bg:{theme.C.tool} bold {sel_fg}", line))
        else:
            result.append((f"bg:{bg} {norm_fg}", left[:14+2+2]))
            result.append((f"bg:{bg} {dim_fg}",  line[len(left[:14+2+2]):]))
        result.append(("", "\n"))

    if result and result[-1] == ("", "\n"):
        result.pop()
    return result


@Condition
def _has_completions():
    try:
        cs = get_app().current_buffer.complete_state
        return bool(cs and cs.completions)
    except Exception:
        return False


# ── main entry point ───────────────────────────────────────────────────────────

def run_prompt(message: str = "> ", completer=None, history=None) -> str:
    """Run one prompt turn with the custom layout. Returns the submitted text.
    Raises KeyboardInterrupt or EOFError on ctrl+c / ctrl+d."""

    buf = Buffer(
        completer=completer,
        history=history,
        complete_while_typing=completer is not None,
        name="default",
    )

    kb = KeyBindings()

    @kb.add("enter", eager=True)
    def _(event):
        event.app.exit(result=buf.text)

    @kb.add("c-c", eager=True)
    def _(event):
        event.app.exit(exception=KeyboardInterrupt())

    @kb.add("c-d", eager=True)
    def _(event):
        if not event.app.current_buffer.text:
            event.app.exit(exception=EOFError())

    @kb.add("escape", eager=True)
    def _(event):
        b = event.app.current_buffer
        if b.complete_state:
            b.cancel_completion()

    @kb.add("up", eager=True)
    def _(event):
        b = event.app.current_buffer
        if b.complete_state:
            b.complete_previous()
        else:
            b.history_backward()

    @kb.add("down", eager=True)
    def _(event):
        b = event.app.current_buffer
        if b.complete_state:
            b.complete_next()
        else:
            b.history_forward()

    def get_prefix(lineno, wrap_count):
        if lineno == 0 and wrap_count == 0:
            return to_formatted_text([("class:prompt", message)])
        return to_formatted_text([("", " " * len(message))])

    layout = Layout(
        HSplit([
            # 1. Input: grows/shrinks with content
            Window(
                BufferControl(buf, include_default_input_processors=True),
                get_line_prefix=get_prefix,
                wrap_lines=True,
            ),
            # 2. Rule: always 1 row
            Window(FormattedTextControl(_rule_text), height=1),
            # 3. Completions: 0 rows when empty, expands when active
            ConditionalContainer(
                Window(
                    FormattedTextControl(_completion_text),
                    dont_extend_height=True,
                ),
                filter=_has_completions,
            ),
            # 4. Status: always 1 row
            Window(FormattedTextControl(_status_text), height=1),
        ]),
        focused_element=buf,
    )

    app = Application(
        layout=layout,
        key_bindings=merge_key_bindings([load_emacs_bindings(), kb]),
        style=theme.input_style,
        color_depth=ColorDepth.DEPTH_24_BIT,
        full_screen=False,
        mouse_support=False,
    )

    try:
        result = app.run()
        if isinstance(result, Exception):
            raise result
        return result or ""
    except (KeyboardInterrupt, EOFError):
        raise
