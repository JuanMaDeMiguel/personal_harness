"""Terminal theme detection and color palette (matches Claude Code's actual colors)."""
import os
import re
import sys
import time

from prompt_toolkit.styles import Style as PTStyle


class Colors:
    """Mutable palette — apply() updates in place so all importers see live values.
    All values are hex strings (Rich + prompt_toolkit both accept #rrggbb)."""
    # Claude Code 'permission' color (tool ● indicator)
    tool:    str = "#b1b9f9"   # rgb(177,185,249) permission dark
    args:    str = "#d4d4d4"   # soft white on dark bg; updated by apply()
    reason:  str = "italic #999999"
    result:  str = "#999999"
    error:   str = "#ff6b80"   # rgb(255,107,128) error dark
    # 'subtle' — very dim background text
    dim:     str = "#505050"
    # 'inactive' — secondary UI text
    header:  str = "#999999"
    # 'promptBorder' — horizontal rules
    rule:    str = "#888888"
    rule_rgb: tuple = (136, 136, 136)
    hist:    str = "#505050"
    diff_rm_bg:  str = "#7a2936"
    diff_rm_fg:  str = "#b3596b"
    diff_add_bg: str = "#225c2b"
    diff_add_fg: str = "#38a660"
    menu_bg:     str = "#1e1e1e"   # completion menu background
    menu_sel_fg: str = "#1a1a1a"   # text on selected completion item


C = Colors()

# Module-level vars updated by apply(); access via `theme.toolbar_ansi` etc.
toolbar_ansi: str = "\033[38;2;136;136;136m"
input_style: PTStyle = PTStyle.from_dict({
    "":               "",            # terminal default
    "prompt":         "bold #b1b9f9",
    "bottom-toolbar": "noreverse bg:default",
})

# Cache whether OSC 11 is supported; avoids 150ms timeout on every prompt after
# the first failed query.
_osc11_works: bool | None = None


def _osc11_query() -> float | None:
    """Query terminal background via OSC 11. Returns BT.709 luminance 0–1 or None."""
    global _osc11_works
    if _osc11_works is False:
        return None
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        _osc11_works = False
        return None
    try:
        import termios, tty, select
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        result = None
        try:
            tty.setraw(fd)
            sys.stdout.write("\033]11;?\033\\")
            sys.stdout.flush()
            if not select.select([sys.stdin], [], [], 0.15)[0]:
                _osc11_works = False
                return None
            buf, t0 = "", time.monotonic()
            while time.monotonic() - t0 < 0.15:
                if not select.select([sys.stdin], [], [], 0.05)[0]:
                    break
                buf += os.read(fd, 1).decode("latin-1", errors="replace")
                if buf.endswith("\\") or buf.endswith("\007"):
                    break
            m = re.search(r"rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)", buf)
            if m:
                def norm(s): return int(s, 16) / (65535.0 if len(s) > 2 else 255.0)
                r, g, b = norm(m.group(1)), norm(m.group(2)), norm(m.group(3))
                result = 0.2126 * r + 0.7152 * g + 0.0722 * b
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        _osc11_works = result is not None
        return result
    except Exception:
        _osc11_works = False
        return None


def detect() -> str:
    override = os.getenv("HARNESS_THEME", "").strip().lower()
    if override in {"dark", "light"}:
        return override
    lum = _osc11_query()
    if lum is not None:
        return "light" if lum > 0.5 else "dark"
    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg:
        try:
            bg = int(colorfgbg.split(";")[-1])
            return "light" if bg in {7, 8, 15} else "dark"
        except (ValueError, IndexError):
            pass
    return "dark"


def _palette(theme: str) -> dict:
    """Real Claude Code color tokens extracted from the 2.1.119 binary."""
    if theme == "light":
        return {
            "tool":        "#5769f7",
            "args":        "#1a1a1a",
            "reason":      "italic #666666",
            "result":      "#666666",
            "error":       "#ab2b3f",
            "dim":         "#afafaf",
            "header":      "#666666",
            "rule":        "#999999",
            "rule_rgb":    (153, 153, 153),
            "hist":        "#afafaf",
            "diff_rm_bg":  "#fdd2d8",
            "diff_rm_fg":  "#d1454b",
            "diff_add_bg": "#c7e1cb",
            "diff_add_fg": "#2f9d44",
            # completion menu
            "menu_bg":     "#f0f0f0",
            "menu_sel_fg": "#ffffff",
        }
    return {
        "tool":        "#b1b9f9",
        "args":        "#d4d4d4",
        "reason":      "italic #999999",
        "result":      "#999999",
        "error":       "#ff6b80",
        "dim":         "#505050",
        "header":      "#999999",
        "rule":        "#888888",
        "rule_rgb":    (136, 136, 136),
        "hist":        "#505050",
        "diff_rm_bg":  "#7a2936",
        "diff_rm_fg":  "#b3596b",
        "diff_add_bg": "#225c2b",
        "diff_add_fg": "#38a660",
        # completion menu
        "menu_bg":     "#1e1e1e",
        "menu_sel_fg": "#1a1a1a",
    }


def apply(theme: str):
    """Mutate C and module-level style vars so all importers pick up the new theme."""
    global toolbar_ansi, input_style

    p = _palette(theme)
    C.tool        = p["tool"]
    C.args        = p["args"]
    C.reason      = p["reason"]
    C.result      = p["result"]
    C.error       = p["error"]
    C.dim         = p["dim"]
    C.header      = p["header"]
    C.rule        = p["rule"]
    C.rule_rgb    = p["rule_rgb"]
    C.hist        = p["hist"]
    C.diff_rm_bg  = p["diff_rm_bg"]
    C.diff_rm_fg  = p["diff_rm_fg"]
    C.diff_add_bg = p["diff_add_bg"]
    C.diff_add_fg = p["diff_add_fg"]
    C.menu_bg     = p["menu_bg"]
    C.menu_sel_fg = p["menu_sel_fg"]

    r, g, b = p["rule_rgb"]
    toolbar_ansi = f"\033[38;2;{r};{g};{b}m"

    menu_bg     = p["menu_bg"]
    menu_sel_fg = p["menu_sel_fg"]
    input_style = PTStyle.from_dict({
        "":               "",
        "prompt":         f"bold {p['tool']}",
        "bottom-toolbar": "noreverse bg:default",
        # completion menu
        "completion-menu":                         f"bg:{menu_bg} {p['args']}",
        "completion-menu.completion":              f"bg:{menu_bg} {p['args']}",
        "completion-menu.completion.current":      f"bg:{p['tool']} {menu_sel_fg} bold",
        "completion-menu.meta.completion":         f"bg:{menu_bg} {p['dim']}",
        "completion-menu.meta.completion.current": f"bg:{p['tool']} {menu_sel_fg}",
        # hide the scrollbar entirely
        "scrollbar":                               "bg:default",
        "scrollbar.background":                    "bg:default",
        "scrollbar.button":                        "bg:default",
        "scrollbar.arrow":                         "bg:default",
        "scrollbar.start":                         "bg:default",
        "scrollbar.end":                           "bg:default",
    })


# Apply detected theme at import time
apply(detect())
