---
description: Set up token-lab - check dependencies, start your first experiment, optionally tune settings and schedule a weekly report
---

# token-lab setup

Work through these steps in order. Report each result in one line.

1. **Dependencies.** Run `command -v python3 jq git`. python3 (3.9+) and jq are required: without jq the hooks do nothing, and without python3 no reports run. git is optional; without it, commits and lines are left out of the report. If something is missing, tell the user how to install it (macOS: `brew install jq`) and stop.

2. **State folder.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" config` once. It prints the defaults, and everything token-lab writes goes to `~/.claude/token-lab/`.

3. **Mark the install as an experiment.** The hooks and agents start working now, so mark it. The baseline is then the 7 days before this point, read from the user's existing transcripts:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" start token-lab --note "gate, bulk-reader, model routing, ship checklist"`
   If `list` shows a `token-lab` experiment already, skip this step.

4. **First look.** Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" compare`. Summarise in 3-5 bullets how the user's last week compares with the pretrained reference: $ per active hour, mean context, Opus share of subagent spend, and implementer quality if they use superpowers SDD.

5. **Optional settings, each with its own yes.** These can't live in a plugin; they are env vars in `~/.claude/settings.json`. Offer each one separately with its trade-off. Change only what the user agrees to, after copying settings.json to `settings.json.bak-<timestamp>`, and keep the file valid JSON.
   - `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50`: on 1M-context models this was the biggest saving in the reference data, cutting mean context per turn by about half. The trade-off is that detail from early in a long session can be lost when it compacts.
   - `CLAUDE_CODE_SUBAGENT_MODEL=sonnet`: the default model for subagent calls that name no model. It had little effect for the reference user, because their skills always name a model.
   Don't mark the setting change as a separate experiment at the same time as step 3. If the user wants to measure it on its own, tell them to wait a few days and run `/token-lab:experiment start autocompact-50`.

6. **Optional weekly report.** Ask first, then run `"${CLAUDE_PLUGIN_ROOT}/scripts/schedule-weekly.sh"`. It uses launchd on macOS and cron elsewhere, and reports land in `~/.claude/token-lab/reports/`.

7. Tell the user that hooks and agents load when a session starts. Sessions already running need a restart.
