# claude-skill-analytics

A Claude Code plugin that automatically tracks skill usage and generates ranked reports with actionable recommendations.

Know which skills drive your workflow, which ones are dormant, and which ones are failing silently.

## Quick Start

**1. Clone into your plugins directory:**

```bash
cd ~/.claude/plugins/local-curated/
git clone https://github.com/Salmonellasarduri/claude-skill-analytics.git
```

Or download and extract into `~/.claude/plugins/local-curated/claude-skill-analytics/`.

**2. Enable the plugin in your project:**

Open `.claude/settings.json` in your project and add:

```json
{
  "enabledPlugins": {
    "claude-skill-analytics@local-curated": true
  }
}
```

That's it. The plugin starts logging skill usage automatically.

## Usage

After a few days of normal Claude Code usage, run:

```
/claude-skill-analytics:report
```

Options:
- `/claude-skill-analytics:report --days 7` — last 7 days
- `/claude-skill-analytics:report --skill codex-analyst` — specific skill
- `/claude-skill-analytics:report --format json` — JSON output for automation

## Example Output

```
=== Skill Usage Report (last 30 days) -- 2026-03-18 21:50 ===

--- workflow ---
  Skill                                    Calls   OK%  Sessions Last Used
  ---------------------------------------- ------ ----- --------- ------------
  plan                                        12   100%        10 2026-03-18
  save                                        10   100%         9 2026-03-18
  review                                       8   100%         8 2026-03-17

--- hookify ---
  hookify:configure                            3   100%         2 2026-03-15
  hookify:list                                 2   100%         2 2026-03-14

--- uncategorized ---
  my-custom-skill                              1   100%         1 2026-03-16

--- Signals & Recommendations ---
  [INVESTIGATE] codex-analyst: 40% failure rate (2/5)
    -> Check if the skill is misconfigured or has known issues.
  [DORMANT] doc-updater: last used 2026-02-10 (36d ago)
    -> Consider disabling to reduce context overhead.

--- Daily Trend ---
  2026-03-15    5  #####
  2026-03-16    8  ########
  2026-03-17   12  ############
  2026-03-18    6  ######
```

## Features

- **Automatic logging** — PostToolUse(Skill) hook records every skill invocation
- **Category-based ranking** — Skills grouped by workflow, plugin, or custom categories
- **Dormant detection** — Skills unused for 30+ days are flagged
- **Failure alerts** — Skills with >25% failure rate (3+ calls) are flagged
- **Actionable recommendations** — Each signal includes a suggested action
- **JSON export** — `--format json` for CI/automation integration
- **Zero config** — Works out of the box with sensible defaults

## Configuration

### Custom categories

Create `categories.yaml` in your project root to override the default grouping:

```yaml
workflow:
  - plan
  - save
  - review
  - implement
  - debug

utility:
  - codex-analyst
  - gemini-researcher
  - doc-updater

task_specific:
  - enqueue-book
  - create-note-header
```

Skills with `:` in the name (e.g., `hookify:configure`) are auto-categorized by their plugin name.

Skills not matched by any rule appear under `uncategorized`.

### Thresholds

Edit `scripts/skill_analytics.py` to adjust:

```python
DORMANT_AFTER_DAYS = 30       # days unused before DORMANT signal
INVESTIGATE_FAIL_PCT = 0.25   # failure rate threshold (25%)
INVESTIGATE_MIN_CALLS = 3     # minimum calls before flagging
```

## How It Works

```
  Skill invocation
       |
       v
  PostToolUse(Skill) hook
       |
       v
  skill_usage_logger.py  -->  logs/skill_usage.jsonl
       |
       v
  /claude-skill-analytics:report
       |
       v
  skill_analytics.py  -->  Ranked report + Signals
```

1. Every time Claude Code invokes a skill, the hook appends a log entry
2. When you run the report command, the analytics script reads the log and generates insights

## Privacy

This plugin records **only** the following fields per skill invocation:

| Field | Example | Purpose |
|-------|---------|---------|
| `ts` | `2026-03-18T12:00:00+00:00` | When the skill was called |
| `v` | `1` | Log schema version |
| `skill` | `plan` | Which skill was invoked |
| `command_name` | `plan` | Command name returned by Claude Code |
| `session_id` | `uuid` | Groups calls within a session |
| `success` | `true` | Whether the invocation succeeded |

**Not recorded:** project paths, file names, code snippets, skill arguments, or any other content.

Log files are stored in `logs/skill_usage.jsonl` within your project directory. Add `logs/` to your `.gitignore` to prevent accidental commits.

## Uninstall

**1.** Remove from `.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "claude-skill-analytics@local-curated": false
  }
}
```

**2.** Delete the plugin directory:

```bash
rm -rf ~/.claude/plugins/local-curated/claude-skill-analytics
```

**3.** Optionally delete log data:

```bash
rm logs/skill_usage.jsonl logs/.last_skill_report
```

## Known Limitations

- **`python3` on Windows**: The hook uses `python3` which may not be available on all Windows setups. If the hook doesn't work, ensure `python3` is on your PATH (e.g., via Git Bash, `py -3`, or a symlink). This is a limitation shared by all Claude Code plugins that use Python.
- **Hook API stability**: Claude Code's hook system is evolving. If a future update changes the PostToolUse format, the logger may need updating. The defensive parser handles missing fields gracefully.
- **PostToolUse matcher**: The `"Skill"` matcher in `hooks.json` works in project settings but is unverified for plugin-installed hooks. If skills aren't being logged, check your Claude Code version.

## Requirements

- Claude Code (with plugin support)
- Python 3.10+

## License

MIT
