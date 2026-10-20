---
description: token-lab report - publishes cost per active hour, context, subagents, implementer quality and guardrails as an Artifact page
argument-hint: "[normalised|sessions|subagents|quality|bulk-reader|gate|routing] [--no-git]"
---

# token-lab report

Arguments: `$ARGUMENTS`

The report reads every transcript under `~/.claude/projects`. Give each Bash call below a 600000 ms timeout.

## Full report (no section named)

1. Build the page: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" report --html $ARGUMENTS`. It prints the path of a self-contained HTML file in `~/.claude/token-lab/reports/`. Its charts and tables use the page's own CSS; the only external load is Google Fonts. Pass the file as it is, without rewriting it.
2. Publish it with the Artifact tool.
   - If `~/.claude/token-lab/artifact-url.txt` exists, update that artifact: read it first with `action: "read"`, then publish the new file with `url` set to it. One URL then always shows the latest report.
   - Otherwise publish it as new with `icon: "chart"` and the description "Claude Code cost per active hour, context, subagent spend and implementer quality across the baseline and each experiment." Then save the returned URL to `~/.claude/token-lab/artifact-url.txt`.
   - If this session has no Artifact tool, open the file locally instead (`open` on macOS, `xdg-open` on Linux) and say so.
3. In chat, give the link and a 3-5 bullet conclusion. Don't paste the tables.
   - **Headline:** $ per active hour, period against period. This is the common ground across busy and quiet weeks; $ per wall-clock hour rises whenever someone simply works more.
   - **What moved it:** context per turn and compactions for main sessions, and subagent spend by role and model.
   - **Quality,** if SDD runs exist: compare each model with itself across periods.
   - **One recommended next experiment.** Change one variable at a time.
   - Call out samples that are too small (under ~20 active hours or ~20 tasks).

## One section

For a quick look in chat with no page, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" section $ARGUMENTS`, or `lab.py routing` for routing. Summarise it in the same style.
