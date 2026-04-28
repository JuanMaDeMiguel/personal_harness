import argparse
from datetime import datetime

from prompt_toolkit.history import InMemoryHistory
from rich.markdown import Markdown

import config
import session as sess
from tools import toolset
from ui import theme, apply_theme, detect_theme
from ui import console, format_args, print_result_preview, print_edit_diff, prompt as harness_prompt
from ui import SlashCompleter, COMMANDS
from api import plan_next_action, get_final_answer

MAX_ITERATIONS = 20

EFFORT_LEVELS = ["low", "medium", "high", "xhigh"]


def _handle_command(user_input: str, all_sessions: list, history: InMemoryHistory) -> str | bool | None:
    """Handle slash commands.
    Returns: new context str (from /resume), True (continue), False (exit), None (not a command).
    """
    parts = user_input.split()
    cmd   = parts[0].lower()

    if cmd == "/theme":
        t = parts[1].lower() if len(parts) > 1 else ""
        if t in ("dark", "light"):
            apply_theme(t)
            console.print(f"[{theme.C.dim}]theme: {t}[/{theme.C.dim}]\n")
        else:
            console.print(f"[{theme.C.dim}]usage: /theme dark|light[/{theme.C.dim}]\n")
        return True

    if cmd == "/model":
        if len(parts) < 2:
            opts = " | ".join(COMMANDS["/model"]["options"])
            console.print(f"[{theme.C.dim}]usage: /model <{opts}>[/{theme.C.dim}]\n")
        else:
            config.active_model = parts[1]
            console.print(f"[{theme.C.dim}]model: {config.active_model}[/{theme.C.dim}]\n")
        return True

    if cmd == "/effort":
        if len(parts) < 2:
            opts = " | ".join(EFFORT_LEVELS)
            console.print(f"[{theme.C.dim}]usage: /effort <{opts}>[/{theme.C.dim}]\n")
        elif parts[1].lower() not in EFFORT_LEVELS:
            console.print(f"[{theme.C.error}]unknown effort '{parts[1]}' — choose: {', '.join(EFFORT_LEVELS)}[/{theme.C.error}]\n")
        else:
            config.reasoning_effort = parts[1].lower()
            console.print(f"[{theme.C.dim}]effort: {config.reasoning_effort}[/{theme.C.dim}]\n")
        return True

    if cmd == "/resume":
        return sess.handle_resume(all_sessions, history)

    if cmd in ("/exit", "/bye", "/quit"):
        return False

    # Unknown slash command — show available commands
    console.print(f"[{theme.C.dim}]Unknown command. Available:[/{theme.C.dim}]")
    for name, info in COMMANDS.items():
        opts = f"  [{' | '.join(info['options'])}]" if info["options"] else ""
        console.print(f"  [{theme.C.tool}]{name}[/{theme.C.tool}] [{theme.C.dim}]{info['description']}{opts}[/{theme.C.dim}]")
    console.print()
    return True


def main():
    parser = argparse.ArgumentParser(description="Harness — local AI coding agent")
    parser.add_argument("--debug", action="store_true", help="Print raw API payloads")
    args_cli = parser.parse_args()
    config.debug = args_cli.debug

    all_sessions = sess.load()
    completer    = SlashCompleter()

    console.print(
        f"[{theme.C.header}]Harness[/{theme.C.header}]  "
        f"[{theme.C.dim}]type / for commands · ctrl+c to exit[/{theme.C.dim}]\n"
    )

    current_session = {
        "started": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "turns": [],
    }
    accumulated_context = ""
    history = InMemoryHistory()
    _active_theme = detect_theme()

    while True:
        # Hot-reload theme on every prompt
        detected = detect_theme()
        if detected != _active_theme:
            _active_theme = detected
            apply_theme(detected)

        console.rule(style=theme.C.rule)
        try:
            user_input = harness_prompt(
                message=[("class:prompt", "> ")],
                history=history,
                completer=completer,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.rule(style=theme.C.rule)
            console.print(f"[{theme.C.dim}]bye[/{theme.C.dim}]")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            result = _handle_command(user_input, all_sessions, history)
            if result is False:
                console.rule(style=theme.C.rule)
                console.print(f"[{theme.C.dim}]bye[/{theme.C.dim}]")
                break
            if isinstance(result, str):
                accumulated_context = result
            continue

        console.rule(style=theme.C.rule)

        observations: list[tuple[str, str, str]] = []
        turn_tool_calls = []

        for _ in range(MAX_ITERATIONS):
            with console.status(
                f"[{theme.C.dim}]Thinking...[/{theme.C.dim}]",
                spinner="dots",
                spinner_style=theme.C.tool,
            ):
                plan = plan_next_action(user_input, observations, accumulated_context)

            if not plan:
                console.print(f"[{theme.C.error}]Planner returned no valid plan.[/{theme.C.error}]")
                break

            action = plan.get("action", "answer_directly")
            args   = plan.get("args", {})
            reason = plan.get("reason", "")

            if action == "answer_directly" or action not in toolset.tools:
                break

            display_args = (
                {"filepath": args["filepath"]}
                if action == "edit_file" and "filepath" in args
                else args
            )
            arg_str = format_args(display_args)

            if reason:
                console.print(f"[{theme.C.reason}]{reason}[/{theme.C.reason}]")
            console.print(
                f"[{theme.C.tool}]●[/{theme.C.tool}] "
                f"[{theme.C.tool}]{action}[/{theme.C.tool}]"
                f"([{theme.C.args}]{arg_str}[/{theme.C.args}])"
            )

            with console.status("", spinner="dots", spinner_style=theme.C.dim):
                raw = toolset.execute(action, args)

            if not raw.get("ok"):
                console.print(f"  [{theme.C.error}]{raw['error']}[/{theme.C.error}]")
                result_str = f"Error: {raw['error']}"
            else:
                result_str = raw["output"]
                if action == "edit_file":
                    print_edit_diff(args)
                else:
                    print_result_preview(result_str)

            console.print()
            observations.append((action, str(args), result_str))
            turn_tool_calls.append({
                "name":                 action,
                "args_str":             arg_str,
                "reason":               reason,
                "result_preview_lines": result_str.splitlines()[:3],
                "result_total_lines":   len(result_str.splitlines()),
                "result_context":       result_str[:1500],
            })

        with console.status(
            f"[{theme.C.dim}]Thinking...[/{theme.C.dim}]",
            spinner="dots",
            spinner_style=theme.C.tool,
        ):
            answer = get_final_answer(user_input, observations, accumulated_context)

        if answer:
            console.print(Markdown(answer))

        turn = {
            "user":       user_input,
            "tool_calls": turn_tool_calls,
            "answer":     answer or "",
        }
        current_session["turns"].append(turn)
        sess.save(all_sessions + [current_session])
        accumulated_context = sess.build_context(current_session["turns"])


if __name__ == "__main__":
    main()
