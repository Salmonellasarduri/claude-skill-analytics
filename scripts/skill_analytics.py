#!/usr/bin/env python3
"""
Skill Usage Analytics for Claude Code.

Reads logs/skill_usage.jsonl (populated by the PostToolUse hook) and reports
per-skill call counts, success rates, dormant detection, actionable
recommendations, and session patterns.

Usage:
    python3 scripts/skill_analytics.py
    python3 scripts/skill_analytics.py --days 7
    python3 scripts/skill_analytics.py --skill codex-analyst
    python3 scripts/skill_analytics.py --format json
    python3 scripts/skill_analytics.py --check-interval 5
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults -- users can override via categories.yaml
# ---------------------------------------------------------------------------
_DEFAULT_CATEGORIES: dict[str, set[str]] = {
    "workflow": {"plan", "save", "review", "implement", "debug", "restart",
                 "strategy", "strategy_deep"},
}

# Thresholds -- exposed here for transparency
DORMANT_AFTER_DAYS = 30       # skill unused for N days -> DORMANT
INVESTIGATE_FAIL_PCT = 0.25   # >25% failure rate -> INVESTIGATE
INVESTIGATE_MIN_CALLS = 3     # minimum calls before flagging


# ---------------------------------------------------------------------------
# Category management
# ---------------------------------------------------------------------------
def _load_categories(project_root: str) -> dict[str, set[str]]:
    """Load categories from categories.yaml if present, else use defaults."""
    cat_path = os.path.join(project_root, "categories.yaml")
    if os.path.isfile(cat_path):
        try:
            import yaml  # optional dependency
            with open(cat_path, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            return {k: set(v) for k, v in raw.items() if isinstance(v, list)}
        except ImportError:
            pass  # no PyYAML -> fall through to defaults
        except Exception:
            pass
    return dict(_DEFAULT_CATEGORIES)


def _build_reverse_lookup(categories: dict[str, set[str]]) -> dict[str, str]:
    lookup = {}
    for cat, skills in categories.items():
        for s in skills:
            lookup[s] = cat
    return lookup


def categorize(skill_name: str, lookup: dict[str, str]) -> str:
    """Categorize a skill. Auto-detect plugin skills by colon separator."""
    if skill_name in lookup:
        return lookup[skill_name]
    # Auto-detect: "plugin-name:command" -> category "plugin-name"
    if ":" in skill_name:
        return skill_name.split(":")[0]
    return "uncategorized"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_entries(path: Path, days: int | None = None,
                 skill_filter: str | None = None) -> list[dict]:
    entries = []
    cutoff = None
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    if not path.exists():
        return entries

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if cutoff:
                try:
                    ts = datetime.fromisoformat(entry.get("ts", ""))
                    # Normalize to UTC for comparison
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    else:
                        ts = ts.astimezone(timezone.utc)
                except (ValueError, TypeError):
                    continue
                if ts < cutoff:
                    continue

            if skill_filter and entry.get("skill") != skill_filter:
                continue

            entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
class SkillStats:
    __slots__ = ("total", "success", "fail", "sessions", "last_ts")

    def __init__(self):
        self.total = 0
        self.success = 0
        self.fail = 0
        self.sessions: set[str] = set()
        self.last_ts = ""


def analyze(entries: list[dict]):
    stats: dict[str, SkillStats] = {}
    daily: dict[str, int] = defaultdict(int)
    session_skills: dict[str, set[str]] = defaultdict(set)

    for e in entries:
        skill = e.get("skill", "unknown")
        if skill not in stats:
            stats[skill] = SkillStats()
        s = stats[skill]
        s.total += 1
        if e.get("success"):
            s.success += 1
        else:
            s.fail += 1

        sid = e.get("session_id", "")
        if sid:
            s.sessions.add(sid)
            session_skills[sid].add(skill)

        ts = e.get("ts", "")
        if ts > s.last_ts:
            s.last_ts = ts

        date_str = ts[:10]
        if date_str:
            daily[date_str] += 1

    return stats, daily, session_skills


# ---------------------------------------------------------------------------
# Report output (text)
# ---------------------------------------------------------------------------
def _local_date(iso_ts: str) -> str:
    """Convert ISO timestamp to local date string for display."""
    if not iso_ts:
        return "never"
    try:
        dt = datetime.fromisoformat(iso_ts)
        if dt.tzinfo:
            dt = dt.astimezone()  # convert to local
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return iso_ts[:10] if len(iso_ts) >= 10 else "?"


def print_report(stats: dict[str, SkillStats], daily: dict[str, int],
                 categories: dict[str, set[str]],
                 days_label: str = "all time"):
    if not stats:
        print("\nNo skill usage data found.")
        print("The PostToolUse(Skill) hook logs to logs/skill_usage.jsonl.")
        print("Use some skills and check back later.\n")
        return

    lookup = _build_reverse_lookup(categories)
    now_str = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    print()
    print(f"=== Skill Usage Report ({days_label}) -- {now_str} ===")

    # Group by category
    by_cat: dict[str, list[tuple[str, SkillStats]]] = defaultdict(list)
    for skill, s in stats.items():
        by_cat[categorize(skill, lookup)].append((skill, s))

    # Collect category names and sort: known first, then auto-detected, then uncategorized
    known_cats = list(categories.keys())
    all_cats = sorted(by_cat.keys(),
                      key=lambda c: (c == "uncategorized", c not in known_cats, c))

    for cat in all_cats:
        items = by_cat[cat]
        items.sort(key=lambda x: x[1].total, reverse=True)
        print()
        print(f"--- {cat} ---")
        print(f"  {'Skill':<40} {'Calls':>6} {'OK%':>5} {'Sessions':>9} {'Last Used':<12}")
        print(f"  {'-'*40} {'-'*6} {'-'*5} {'-'*9} {'-'*12}")

        for skill, s in items:
            ok_pct = f"{s.success / s.total * 100:.0f}%" if s.total else "--"
            sessions = len(s.sessions)
            last = _local_date(s.last_ts)
            print(f"  {skill:<40} {s.total:>6} {ok_pct:>5} {sessions:>9} {last:<12}")

    # Signals + Recommendations
    print()
    print("--- Signals & Recommendations ---")
    signals_found = False
    now = datetime.now(timezone.utc)

    for skill, s in sorted(stats.items()):
        # INVESTIGATE: high failure rate
        if s.total >= INVESTIGATE_MIN_CALLS and s.fail / s.total > INVESTIGATE_FAIL_PCT:
            fail_pct = s.fail / s.total * 100
            print(f"  [INVESTIGATE] {skill}: {fail_pct:.0f}% failure rate ({s.fail}/{s.total})")
            print(f"    -> Check if the skill is misconfigured or has known issues.")
            signals_found = True

        # DORMANT: not used recently
        if s.last_ts:
            try:
                last_dt = datetime.fromisoformat(s.last_ts)
                if last_dt.tzinfo:
                    last_dt = last_dt.astimezone(timezone.utc)
                else:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                if (now - last_dt).days >= DORMANT_AFTER_DAYS:
                    print(f"  [DORMANT] {skill}: last used {_local_date(s.last_ts)} "
                          f"({(now - last_dt).days}d ago)")
                    print(f"    -> Consider disabling to reduce context overhead.")
                    signals_found = True
            except (ValueError, TypeError):
                pass

    if not signals_found:
        print("  (none)")

    # Daily trend
    if daily:
        print()
        print("--- Daily Trend ---")
        for date in sorted(daily)[-14:]:
            bar = "#" * min(daily[date], 50)
            print(f"  {date}  {daily[date]:>3}  {bar}")

    print()


# ---------------------------------------------------------------------------
# Report output (JSON)
# ---------------------------------------------------------------------------
def json_report(stats: dict[str, SkillStats], daily: dict[str, int],
                categories: dict[str, set[str]],
                days_label: str = "all time") -> dict:
    lookup = _build_reverse_lookup(categories)
    skills = []
    for skill, s in sorted(stats.items(), key=lambda x: x[1].total, reverse=True):
        skills.append({
            "skill": skill,
            "category": categorize(skill, lookup),
            "calls": s.total,
            "success": s.success,
            "fail": s.fail,
            "success_rate": round(s.success / s.total, 3) if s.total else None,
            "sessions": len(s.sessions),
            "last_used": s.last_ts or None,
        })

    signals = []
    now = datetime.now(timezone.utc)
    for skill, s in stats.items():
        if s.total >= INVESTIGATE_MIN_CALLS and s.fail / s.total > INVESTIGATE_FAIL_PCT:
            signals.append({
                "type": "INVESTIGATE",
                "skill": skill,
                "detail": f"{s.fail / s.total * 100:.0f}% failure rate ({s.fail}/{s.total})",
            })
        if s.last_ts:
            try:
                last_dt = datetime.fromisoformat(s.last_ts)
                if last_dt.tzinfo:
                    last_dt = last_dt.astimezone(timezone.utc)
                else:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                if (now - last_dt).days >= DORMANT_AFTER_DAYS:
                    signals.append({
                        "type": "DORMANT",
                        "skill": skill,
                        "detail": f"last used {(now - last_dt).days}d ago",
                    })
            except (ValueError, TypeError):
                pass

    return {
        "report": "skill-analytics",
        "period": days_label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skills": skills,
        "signals": signals,
        "daily": dict(sorted(daily.items())),
    }


# ---------------------------------------------------------------------------
# Last-report timestamp (for periodic reminder)
# ---------------------------------------------------------------------------
def _state_dir(project_root: str) -> Path:
    d = Path(project_root) / "logs"
    d.mkdir(exist_ok=True)
    return d


def update_last_report_ts(project_root: str):
    ts_file = _state_dir(project_root) / ".last_skill_report"
    ts_file.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")


def days_since_last_report(project_root: str) -> int | None:
    ts_file = _state_dir(project_root) / ".last_skill_report"
    if not ts_file.exists():
        return None
    try:
        last = datetime.fromisoformat(ts_file.read_text(encoding="utf-8").strip())
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - last
        return delta.days
    except (ValueError, OSError):
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Skill Usage Analytics for Claude Code")
    parser.add_argument("--days", type=int, default=None,
                        help="Only analyze the last N days")
    parser.add_argument("--skill", type=str, default=None,
                        help="Filter to a specific skill")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--update-ts", action="store_true",
                        help="Update last-report timestamp after output")
    parser.add_argument("--check-interval", type=int, default=None,
                        help="Check if report is overdue (for hook use)")
    args = parser.parse_args()

    project_root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    logfile = Path(project_root) / "logs" / "skill_usage.jsonl"

    # --check-interval: silent check for hook integration
    if args.check_interval is not None:
        d = days_since_last_report(project_root)
        if d is None or d >= args.check_interval:
            entry_count = len(load_entries(logfile))
            if entry_count >= 10:
                print(f"[skill-analytics] {d or '?'}d since last report "
                      f"({entry_count} entries). Run /claude-skill-analytics:report")
        sys.exit(0)

    categories = _load_categories(project_root)
    days_label = f"last {args.days} days" if args.days else "all time"
    entries = load_entries(logfile, days=args.days, skill_filter=args.skill)
    stats, daily, _session_skills = analyze(entries)

    if args.format == "json":
        report = json_report(stats, daily, categories, days_label)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(stats, daily, categories, days_label)

    if args.update_ts:
        update_last_report_ts(project_root)
        if args.format == "text":
            print("(last-report timestamp updated)")


if __name__ == "__main__":
    main()
