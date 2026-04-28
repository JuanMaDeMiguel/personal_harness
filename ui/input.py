"""Public prompt entry point. Delegates to the custom Application in app.py."""

from .app import run_prompt


def prompt(completer=None, message=None, history=None, **_kwargs) -> str:
    """Drop-in replacement for pt_prompt(). Uses the custom Application layout."""
    msg = message
    # harness.py passes message as a list of (style, text) tuples from prompt_toolkit
    if isinstance(msg, list):
        msg = "".join(text for _, text in msg)
    if msg is None:
        msg = "> "
    return run_prompt(message=msg, completer=completer, history=history)
