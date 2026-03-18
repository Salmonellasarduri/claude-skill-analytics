---
description: Analyze Claude Code skill usage with dormancy detection and actionable recommendations
argument-hint: "[--days N] [--skill NAME] [--format json]"
allowed-tools: ["Bash", "Read"]
---

# Skill Usage Report

## Run the analytics script

```bash
PYTHONIOENCODING=utf-8 python3 scripts/skill_analytics.py --update-ts
```

Options:
- `--days 7` — last 7 days only
- `--days 30` — last 30 days only
- `--skill codex-analyst` — filter to a specific skill
- `--format json` — output as JSON (for automation)

If `python3` is not available, try `python` instead.

## Present the results

Show the script output and highlight:
- **Signals & Recommendations**: DORMANT / INVESTIGATE items need attention
- **Top skills**: Which skills are driving the most value
- **Uncategorized**: New skills that could benefit from category assignment

## Optional: Improvement actions

If asked to improve a low-usage skill:
1. Read the skill's SKILL.md
2. Compare with usage data
3. Suggest Trigger Conditions improvements
4. Edit SKILL.md after user approval
