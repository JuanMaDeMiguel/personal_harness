import os
import re
import json
import subprocess


# Commands that are unconditionally blocked regardless of context.
# shell=True is intentional — this is a local dev tool for personal use.
_BLOCKED = re.compile(
    r"\brm\s+-[^\s]*r[^\s]*\s+/(?!\w)"  # rm -rf /
    r"|\bdd\b.*\bof=/dev/"              # dd to raw disk
    r"|\bmkfs\b"                        # format filesystem
    r"|\b:\(\)\s*\{.*\|.*&",            # fork bomb
    re.IGNORECASE,
)


class Toolset:
    def __init__(self):
        self.tools = {}

    def tool(self, func):
        self.tools[func.__name__] = func
        return func

    def execute(self, name: str, args) -> dict:
        """Returns {"ok": True, "output": str} or {"ok": False, "error": str}.
        Tools must raise exceptions on errors — return values are always success."""
        if name not in self.tools:
            return {"ok": False, "error": f"Tool '{name}' not found."}
        try:
            if isinstance(args, str):
                args = json.loads(args)
            output = self.tools[name](**args)
            return {"ok": True, "output": str(output)}
        except Exception as e:
            return {"ok": False, "error": str(e)}


toolset = Toolset()


@toolset.tool
def run_bash(command):
    """Run any bash command (ls, cat, grep, find, python, git, etc.). PREFERRED for reading files and listing directories."""
    if _BLOCKED.search(command):
        raise RuntimeError("command blocked (matches destructive pattern)")
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=os.getcwd(),
    )
    out = result.stdout
    if result.returncode != 0 and result.stderr:
        out += result.stderr
    return out.strip() or "(no output)"


@toolset.tool
def edit_file(filepath, old_string, new_string):
    """Replace old_string with new_string in a file. Use run_bash('cat filepath') first to get the exact text."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    count = content.count(old_string)
    if count == 0:
        raise ValueError(
            f"old_string not found in {filepath}. Read the file first to get the exact content."
        )
    if count > 1:
        raise ValueError(
            f"old_string appears {count} times in {filepath}. Make it more specific."
        )
    new_content = content.replace(old_string, new_string, 1)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    return f"Done: replaced text in {filepath}."


@toolset.tool
def list_files(directory="."):
    """List files in a directory. Prefer using the bash tool instead."""
    return "\n".join(os.listdir(directory))


@toolset.tool
def read_file(filepath):
    """Read a text file. Prefer using the bash tool instead."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()
