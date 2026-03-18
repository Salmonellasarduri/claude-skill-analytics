#!/usr/bin/env python3
"""
PostToolUse(Skill) hook -- logs every skill invocation to JSONL.

stdin JSON from Claude Code:
{
  "session_id": "...",
  "tool_input": {"skill": "plan", "args": "..."},
  "tool_response": {"success": true, "commandName": "plan"},
  ...
}

Privacy: Only records ts, skill, command_name, session_id, success.
No project paths, file names, or code snippets are stored.
"""
import json
import os
import sys
from datetime import datetime, timezone


# Schema version -- increment when log format changes
_SCHEMA_VERSION = 1


def _parse_event(raw: str) -> dict | None:
    """Parse hook stdin into a skill event. Returns None if not a skill call."""
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None

    tool_input = data.get("tool_input") or {}
    skill = tool_input.get("skill")
    if not skill:
        return None

    tool_response = data.get("tool_response") or {}
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "v": _SCHEMA_VERSION,
        "skill": skill,
        "command_name": tool_response.get("commandName"),
        "session_id": data.get("session_id"),
        "success": tool_response.get("success", False),
    }


def main():
    raw = sys.stdin.read()
    event = _parse_event(raw)
    if event is None:
        return

    # Resolve log directory: CLAUDE_PROJECT_DIR > cwd
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    logfile = os.path.join(root, "logs", "skill_usage.jsonl")
    os.makedirs(os.path.dirname(logfile), exist_ok=True)

    try:
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[skill_usage_logger] write error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
