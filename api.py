import re
import json
import inspect

import requests

import config
from ui import theme, console
from prompts import PLANNER_TEMPLATE, ANSWER_TEMPLATE
from tools import toolset


def call_api(prompt_text: str) -> str | None:
    headers = {"Authorization": f"Bearer {config.API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": config.active_model,
        "input": prompt_text,
        "reasoning_effort": config.reasoning_effort,
    }

    if config.debug:
        console.print(f"\n[{theme.C.dim}]── DEBUG payload ──[/{theme.C.dim}]")
        console.print_json(json.dumps(payload))

    try:
        resp = requests.post(config.ENDPOINT, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if config.debug:
            console.print(f"\n[{theme.C.dim}]── DEBUG response ──[/{theme.C.dim}]")
            console.print_json(json.dumps(data))
        return data["output"][0]["content"][0]["text"]
    except Exception as e:
        console.print(f"[{theme.C.error}]API error: {e}[/{theme.C.error}]")
        return None


def _build_tool_signatures() -> str:
    lines = []
    for name, func in toolset.tools.items():
        sig = inspect.signature(func)
        params = ", ".join(
            p if v.default is inspect.Parameter.empty else f'{p}="{v.default}"'
            for p, v in sig.parameters.items()
        )
        doc = (func.__doc__ or "").strip().split("\n")[0]
        lines.append(f"- {name}({params}): {doc}")
    return "\n".join(lines)


def plan_next_action(
    user_request: str,
    observations: list,
    session_context: str = "",
) -> dict | None:
    obs_block = ""
    if observations:
        obs_block = "Observations this turn:\n" + "\n".join(
            f"- [{name}({args})] -> {result}" for name, args, result in observations
        )
    ctx_block = f"{session_context}\n" if session_context else ""
    prompt_text = PLANNER_TEMPLATE.format(
        tool_signatures=_build_tool_signatures(),
        session_context_block=ctx_block,
        user_request=user_request,
        observations_block=obs_block,
    )
    text = call_api(prompt_text)
    if not text:
        return None
    text = text.strip().strip("```json").strip("```").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        if config.debug:
            console.print(f"[{theme.C.dim}]Bad planner JSON: {text!r}[/{theme.C.dim}]")
        return None


def get_final_answer(
    user_request: str,
    observations: list,
    session_context: str = "",
) -> str | None:
    parts = []
    if session_context:
        parts.append(session_context)
    if observations:
        parts.append("\n".join(
            f"[{name}({args})] -> {result}" for name, args, result in observations
        ))
    obs_block = "\n\n".join(parts) if parts else "(no information gathered)"

    prompt_text = ANSWER_TEMPLATE.format(
        user_request=user_request,
        observations_block=obs_block,
    )
    return call_api(prompt_text)
