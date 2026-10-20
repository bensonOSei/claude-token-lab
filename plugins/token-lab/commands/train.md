---
description: Train token-lab on your own history - calibrate the model router, turn your reviewers' findings into your ship checklist, tune the file-size gate
argument-hint: "[days, default 28]"
---

# token-lab train

The plugin ships trained on one heavy user's data: the router patterns, the 7-point ship checklist and the 350-line gate. This command fits all three to the current user's own transcripts. Nothing leaves the machine.

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" train --days ${ARGUMENTS:-28}` with a 600000 ms timeout.

2. **Router.** Read `~/.claude/token-lab/train/classifier.txt`. Look for two kinds of mistake:
   - in `untouched`: descriptions that are clearly implementation work;
   - in `implementer`: ones that are judgment work (design, debugging, security, plans).
   Propose regexes to fix them. Lowercase ERE, matched against the lowercased description. Show the user the exact JSON, then on their yes:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" config --set 'routing_implementer_patterns=["..."]'` and/or `--set 'routing_allow_patterns=["..."]'`.
   Re-run the train step and confirm the counts moved as intended.

3. **Ship checklist.** Read `~/.claude/token-lab/train/findings.md`, the Critical and Important findings reviewers raised on Sonnet- and Haiku-built tasks.
   - Group them into the 5-8 failure classes that recur most, each with a count and one example.
   - Compare those with `${CLAUDE_PLUGIN_ROOT}/hooks/implementer-checklist.md`.
   - Draft a personal checklist. Keep the shipped items that match this user's failures, drop the ones that never occur, and add their own top classes. Each item must be a concrete action the implementer can carry out and prove, not advice.
   - Show the draft. On a yes, write it to `~/.claude/token-lab/checklist.md`. Keep the first heading line exactly as `## Ship checklist (added by token-lab; do all of it before you report DONE)`, and start the file with two blank lines. The hook prefers this file over the shipped one.
   - If findings.md has fewer than ~15 findings, say so and keep the shipped checklist.

4. **Gate.** Use the gate section of the output:
   - Mostly "targeted read of the same file" after blocks: the gate is working.
   - Many blocks on files the user had to edit anyway: suggest raising the threshold, e.g. `config --set read_line_threshold=500`.
   - Full big reads still happening: suggest lowering it.

5. Suggest the user mark the new configuration: `/token-lab:experiment start trained-v1 "personal router patterns + checklist"`.
