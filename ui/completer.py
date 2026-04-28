import config
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML

# Registry of all slash commands.
COMMANDS: dict[str, dict] = {
    "/model":  {"description": "set model",        "options": ["gpt-5.4", "gpt-5.5"],              "config_attr": "active_model"},
    "/effort": {"description": "reasoning effort", "options": ["low", "medium", "high", "xhigh"],  "config_attr": "reasoning_effort"},
    "/theme":  {"description": "ui theme",         "options": ["dark", "light"],                   "config_attr": None},
    "/resume": {"description": "resume a session", "options": [],                                   "config_attr": None},
    "/exit":   {"description": "quit",             "options": [],                                   "config_attr": None},
}

# Max completions to show — drives reserve_space_for_menu
MAX_COMPLETIONS = max(len(info["options"]) or len(COMMANDS) for info in COMMANDS.values())


class SlashCompleter(Completer):
    """Shows completions only when input starts with '/'. Safe to enable always."""

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return

        parts = text.split(maxsplit=1)
        if not parts:
            return

        if not text.endswith(" ") and len(parts) == 1:
            # Completing the command name
            partial = parts[0]
            # Width of the longest command — used to align meta column
            max_cmd = max(len(c) for c in COMMANDS)
            for cmd, info in COMMANDS.items():
                if not cmd.startswith(partial):
                    continue
                hint = (
                    f"  <ansibrightblack>[{'|'.join(info['options'])}]</ansibrightblack>"
                    if info["options"] else ""
                )
                # Pad cmd to align descriptions in a clean second column
                padded = cmd.ljust(max_cmd + 3)
                yield Completion(
                    cmd,
                    start_position=-len(partial),
                    display=HTML(f"<b>{padded}</b>"),
                    display_meta=HTML(f"<ansibrightblack>{info['description']}{hint}</ansibrightblack>"),
                )
        else:
            # Completing a sub-option after the command
            cmd = parts[0]
            if cmd not in COMMANDS:
                return
            info    = COMMANDS[cmd]
            options = info.get("options", [])
            if not options:
                return
            partial  = parts[1] if len(parts) > 1 and not text.endswith(" ") else ""
            attr     = info.get("config_attr")
            current  = getattr(config, attr, None) if attr else None

            for opt in options:
                if not opt.startswith(partial):
                    continue
                meta_str = " current" if opt == current else ""
                yield Completion(
                    opt,
                    start_position=-len(partial),
                    display=HTML(f"<b>{opt}</b>" if opt == current else opt),
                    display_meta=HTML(f"<ansibrightblack>{meta_str}</ansibrightblack>") if meta_str else "",
                )
