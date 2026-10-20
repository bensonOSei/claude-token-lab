---
description: token-lab report - cost per active hour, context, subagents, implementer quality, routing, bulk-reader, gate
argument-hint: "[normalised|sessions|subagents|quality|bulk-reader|gate|routing] [--no-git]"
---

# token-lab report

Arguments: `$ARGUMENTS`

- No section named: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" report $ARGUMENTS`
- A section named (except routing): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" section $ARGUMENTS`
- routing: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" routing`

The scan reads every transcript under `~/.claude/projects` and can take a minute or two, so give the Bash call a 600000 ms timeout.

Then give the user the conclusion, not the table:
1. **Headline:** $ per active hour, period against period. This is the common ground across busy and quiet weeks. $ per wall-clock hour rises whenever someone simply works more.
2. **What moved it:** context per turn and compactions for main sessions, and subagent $ by role and model.
3. **Quality,** if SDD runs exist: compare each model with itself across periods. The stronger model usually gets the harder tasks, so a cross-model comparison misleads.
4. **One recommended next experiment.** Change one variable at a time.
Call out a sample that is too small (under ~2 days or ~20 tasks).
