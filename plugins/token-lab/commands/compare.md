---
description: Compare your numbers with the pretrained reference baseline, or with a friend's exported baseline file
argument-hint: "[path to a friend's baseline json]"
---

Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" compare` with a 600000 ms timeout; if a path was given (`$ARGUMENTS`), add `--ref` and the path. Without a path it compares with the shipped `baseline/pretrained.json`.

Explain the 3-4 biggest differences, and what each suggests trying next as one `/token-lab:experiment`. Prices are list-price estimates, so compare ratios and shapes rather than exact dollars.
