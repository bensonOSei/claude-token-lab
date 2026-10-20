---
description: token-lab report - publishes cost per active hour, context, subagents, implementer quality and guardrails as an Artifact page
argument-hint: "[normalised|sessions|subagents|quality|bulk-reader|gate|routing] [--no-git]"
---

# token-lab report

Arguments: `$ARGUMENTS`

The report reads every transcript under `~/.claude/projects`. Give each Bash call below a 600000 ms timeout.

## Full report (no section named)

1. Build the page: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" report --html $ARGUMENTS`. It prints the path of a self-contained HTML file in `~/.claude/token-lab/reports/`. Its charts and tables use the page's own CSS; the only external load is Google Fonts. Pass the file as it is, without rewriting it.
2. **Check the "In conclusion" section.** The page always opens with it: a plain-English reading of the numbers, generated from rules, covering cost, per reply, context, subagents, code quality, bugs that slipped through, guardrails, what to do next and how sure it is. Read it in the HTML (the `<section class="conclusion">` block) next to the tables.
   - Keep it if it is accurate.
   - If it misses something the numbers clearly show, or reads wrong, write your own version: one `Topic: sentence` per line, in plain English a non-specialist can follow, with no jargon and with the numbers that back each claim. Save it to `~/.claude/token-lab/reports/conclusion.txt` and rebuild with `--conclusion ~/.claude/token-lab/reports/conclusion.txt` added to the step 1 command. Keep the same topics, and always end with "What to do next" and "How sure is this".
3. Publish it with the Artifact tool.
   - If `~/.claude/token-lab/artifact-url.txt` exists, update that artifact: read it first with `action: "read"`, then publish the new file with `url` set to it. One URL then always shows the latest report.
   - Otherwise publish it as new with `icon: "chart"` and the description "Claude Code cost per active hour, context, subagent spend and implementer quality across the baseline and each experiment." Then save the returned URL to `~/.claude/token-lab/artifact-url.txt`.
   - If this session has no Artifact tool, open the file locally instead (`open` on macOS, `xdg-open` on Linux) and say so.
4. In chat, give the link and the conclusion's key points in 3-5 bullets. Don't paste the tables.
   - **Headline:** $ per active hour, period against period. This is the common ground across busy and quiet weeks; $ per wall-clock hour rises whenever someone simply works more.
   - **What moved it:** context per turn and compactions for main sessions, and subagent spend by role and model.
   - **Quality,** if SDD runs exist: compare each model with itself across periods.
   - **One recommended next experiment.** Change one variable at a time.
   - Call out samples that are too small (under ~20 active hours or ~20 tasks).

## One section

For a quick look in chat with no page, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" section $ARGUMENTS`, or `lab.py routing` for routing. Summarise it in the same style.
