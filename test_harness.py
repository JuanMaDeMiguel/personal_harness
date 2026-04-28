"""Smoke-test every major code path. Run with: python test_harness.py"""
import os
import sys
import json
import tempfile
import pathlib
import traceback

# ── helpers ──────────────────────────────────────────────────────────────────

PASS = 0
FAIL = 0


def check(name, fn):
    global PASS, FAIL
    try:
        fn()
        print(f"  PASS  {name}")
        PASS += 1
    except Exception as e:
        print(f"  FAIL  {name}: {e}")
        traceback.print_exc()
        FAIL += 1


def eq(a, b):
    assert a == b, f"{a!r} != {b!r}"


def ok(cond, msg=""):
    assert cond, msg or "assertion failed"


# ── imports ───────────────────────────────────────────────────────────────────

print("\n── Imports ──")
check("import config",   lambda: __import__("config"))
check("import prompts",  lambda: __import__("prompts"))
check("import ui.theme", lambda: __import__("ui.theme"))
check("import ui.display", lambda: __import__("ui.display"))
check("import ui.input", lambda: __import__("ui.input"))
check("import ui",       lambda: __import__("ui"))
check("import api",      lambda: __import__("api"))
check("import session",  lambda: __import__("session"))
check("import harness",  lambda: __import__("harness"))

import config
import session as sess
from ui import theme, console, format_args, print_result_preview, print_edit_diff

# ── theme ─────────────────────────────────────────────────────────────────────

print("\n── Theme ──")
check("detect()", lambda: theme.detect())
check("apply dark",  lambda: theme.apply("dark"))
check("apply light", lambda: theme.apply("light"))
check("apply dark",  lambda: theme.apply("dark"))
check("C.tool is hex string",   lambda: ok(theme.C.tool.startswith("#")))
check("C.rule is hex string",   lambda: ok(theme.C.rule.startswith("#")))
check("C.args is non-empty",    lambda: ok(len(theme.C.args) > 0))
check("C.diff_rm_bg non-empty", lambda: ok(len(theme.C.diff_rm_bg) > 0))
check("toolbar_ansi has ESC",   lambda: ok("\033" in theme.toolbar_ansi))
check("input_style not None",   lambda: ok(theme.input_style is not None))

# ── format_args ───────────────────────────────────────────────────────────────

print("\n── format_args ──")
check("simple str",   lambda: eq(format_args({"k": "v"}), 'k="v"'))
check("truncates >80 chars", lambda: ok("…" in format_args({"k": "x" * 100})))
check("int value",    lambda: eq(format_args({"n": 42}), "n=42"))
check("mixed",        lambda: ok('cmd="ls"' in format_args({"cmd": "ls", "n": 1})))

# ── session persistence ───────────────────────────────────────────────────────

print("\n── Session persistence ──")
tmp = pathlib.Path(tempfile.mktemp(suffix=".json"))
config.SESSIONS_FILE = tmp

sample = [
    {
        "started": "2024-01-01 10:00",
        "turns": [
            {
                "user": "list the files",
                "tool_calls": [
                    {
                        "name": "run_bash",
                        "args_str": 'command="ls"',
                        "reason": "Need to list files",
                        "result_preview_lines": ["harness.py", "tools.py"],
                        "result_total_lines": 5,
                        "result_context": "harness.py\ntools.py\nconfig.py",
                    }
                ],
                "answer": "The codebase contains harness.py and tools.py.",
            }
        ],
    }
]

check("save",         lambda: sess.save(sample))
check("file exists",  lambda: ok(tmp.exists()))

loaded = []

def _do_load():
    global loaded
    loaded = sess.load()

check("load",         _do_load)
check("load count",   lambda: eq(len(loaded), 1))
check("load content", lambda: eq(loaded[0]["turns"][0]["user"], "list the files"))

# ── build_context ─────────────────────────────────────────────────────────────

print("\n── build_context ──")
ctx = sess.build_context(sample[0]["turns"])
check("non-empty",       lambda: ok(len(ctx) > 0))
check("contains user",   lambda: ok("list the files" in ctx))
check("contains result", lambda: ok("harness.py" in ctx))
check("contains answer", lambda: ok("Answer given" in ctx))
check("empty turns",     lambda: eq(sess.build_context([]), ""))

# ── display_history ───────────────────────────────────────────────────────────

print("\n── display_history (Rich output) ──")
check("no crash", lambda: sess.display_history(sample[0]))
check("empty session no crash", lambda: sess.display_history({"turns": []}))

# ── print_result_preview ─────────────────────────────────────────────────────

print("\n── print_result_preview ──")
check("short output", lambda: print_result_preview("a\nb\nc"))
check("long output",  lambda: print_result_preview("\n".join(str(i) for i in range(20))))
check("empty",        lambda: print_result_preview(""))

# ── print_edit_diff ───────────────────────────────────────────────────────────

print("\n── print_edit_diff ──")
with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
    f.write("def hello():\n    pass\n")
    tmpf = f.name

check("basic diff", lambda: print_edit_diff({
    "filepath": tmpf,
    "old_string": "    pass",
    "new_string": "    return 42",
}))
check("nonexistent file", lambda: print_edit_diff({
    "filepath": "/nonexistent/path.py",
    "old_string": "old",
    "new_string": "new",
}))
check("empty strings", lambda: print_edit_diff({
    "filepath": tmpf,
    "old_string": "",
    "new_string": "",
}))

# ── api helpers ───────────────────────────────────────────────────────────────

print("\n── api helpers ──")
from api import _build_tool_signatures, plan_next_action, get_final_answer
from unittest.mock import patch

sig = _build_tool_signatures()
check("build_tool_signatures non-empty", lambda: ok(len(sig) > 0))
check("contains run_bash",              lambda: ok("run_bash" in sig))
check("contains edit_file",             lambda: ok("edit_file" in sig))

# plan_next_action parses JSON correctly and passes it through unchanged
def _test_plan_passthrough():
    with patch("api.call_api", return_value='{"action":"answer_directly","args":{},"reason":"done"}'):
        result = plan_next_action("x", observations=[])
    ok(result is not None)
    ok(result["action"] == "answer_directly")

check("plan_next_action passes through valid JSON", _test_plan_passthrough)

def _test_plan_extracts_json():
    raw = 'Sure! {"action":"run_bash","args":{"command":"ls"},"reason":"listing"} done.'
    with patch("api.call_api", return_value=raw):
        result = plan_next_action("x", observations=[])
    ok(result is not None)
    ok(result["action"] == "run_bash")

check("plan_next_action extracts JSON from noisy response", _test_plan_extracts_json)

# ── handle_resume ─────────────────────────────────────────────────────────────

print("\n── handle_resume ──")
from prompt_toolkit.history import InMemoryHistory

config.SESSIONS_FILE = pathlib.Path("/tmp/_harness_test_nonexistent.json")
h = InMemoryHistory()

check("empty sessions returns None", lambda: eq(sess.handle_resume([], h), None))
check("no-turns sessions returns None",
      lambda: eq(sess.handle_resume([{"started": "x", "turns": []}], h), None))

# ── tools ─────────────────────────────────────────────────────────────────────

print("\n── tools ──")
from tools import toolset

check("run_bash ls",    lambda: ok(toolset.execute("run_bash", {"command": "ls"})["ok"]))
check("run_bash echo",  lambda: eq(toolset.execute("run_bash", {"command": "echo hi"})["output"], "hi"))
check("run_bash blocked", lambda: ok(not toolset.execute("run_bash", {"command": "mkfs /dev/sda"})["ok"]))
check("unknown tool",   lambda: ok(not toolset.execute("nonexistent", {})["ok"]))

with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
    f.write("x = 1\ny = 2\n")
    edit_tmp = f.name

check("edit_file success", lambda: ok(
    toolset.execute("edit_file", {"filepath": edit_tmp, "old_string": "x = 1", "new_string": "x = 99"})["ok"]
))
check("edit_file verifies", lambda: ok("x = 99" in pathlib.Path(edit_tmp).read_text()))
check("edit_file not found", lambda: ok(
    not toolset.execute("edit_file", {"filepath": edit_tmp, "old_string": "NOTHERE", "new_string": "x"})["ok"]
))

# ── cleanup ───────────────────────────────────────────────────────────────────

tmp.unlink(missing_ok=True)
os.unlink(tmpf)
os.unlink(edit_tmp)

# ── summary ───────────────────────────────────────────────────────────────────

print(f"\n{'─'*50}")
print(f"  {PASS} passed, {FAIL} failed")
if FAIL:
    sys.exit(1)
