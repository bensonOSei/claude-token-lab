---
description: Start, stop or list token-lab experiments - mark the moment you change one thing so the report can compare before and after
argument-hint: "start NAME [note] | stop [NAME] | list | presets"
---

# token-lab experiment

Arguments: `$ARGUMENTS`

An experiment is a named point in time: "from here on, X changed". Each experiment becomes a period in the report, running until the next experiment starts or until it is stopped. The baseline is the 7 days before the first experiment (`lab.py config --set baseline_days=14` to change it).

- `start NAME note...` -> `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" start NAME --note "note"` (use `--at 2026-10-15T09:52` to back-date to when the change really happened)
- `stop [NAME]` -> `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" stop NAME`
- `list` -> `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" list`
- `presets`: offer these, and apply the chosen one only after the user agrees. For a settings.json change, back the file up first, then make the change and run `start` with the preset name:
  - `autocompact-50`: env `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50`
  - `autocompact-40`: env `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=40` (test it after 50 has run for a week)
  - `sonnet-subagents`: env `CLAUDE_CODE_SUBAGENT_MODEL=sonnet`
  - `routing-off`: `lab.py config --set routing=false` (an A/B check that the router is worth having)
  - `checklist-off`: `lab.py config --set checklist=false` (the same check for the ship checklist)
  - `gate-350` / `gate-500`: `lab.py config --set read_line_threshold=500`

Rules to tell the user: change one thing at a time, and run each experiment for at least a week of normal work before judging it. Judge on $ per active hour plus implementer quality, never on $ per wall-clock hour.
