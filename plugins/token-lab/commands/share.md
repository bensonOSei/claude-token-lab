---
description: Export your aggregate numbers to share with friends or contribute to the marketplace's community baselines
argument-hint: "[label]"
---

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" baseline --label "${ARGUMENTS:-anonymous}" --out ~/.claude/token-lab/share-baseline.json` with a 600000 ms timeout.
2. Read the whole file and show the user a short summary of what is in it. It holds only numbers per period: cost and context rates, subagent spend by role and model, and implementer quality rates. It has no project names, paths, prompts or descriptions. Check that yourself before saying so. If anything identifying appears, such as period labels the user typed, point it out and offer to edit it out.
3. Tell them how to share it: send the file to a friend, who runs `/token-lab:compare <path>`, or open a PR adding it under `baselines/community/` in the token-lab marketplace repo. Don't send or upload it yourself.
