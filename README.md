# token-lab

Cut what Claude Code costs you, prove it with your own numbers, and keep cheaper subagents shipping clean code.

token-lab is a Claude Code plugin marketplace with one plugin. It gives you:
- **guardrails** that change how Claude spends tokens;
- **a lab** that measures the effect from the transcripts already on your machine;
- **a trainer** that fits the guardrails to how you work.

It ships pretrained on one heavy user's data (Opus 5.5 with a 1M context, superpowers subagent-driven development, about 50 active hours a week).

## Install

```
/plugin marketplace add bensonOSei/claude-token-lab
/plugin install token-lab@token-lab
```

Restart Claude Code, then run:

```
/token-lab:setup
```

Requirements: `python3` (3.9+) and `jq`. `git` is optional and adds commits and lines to the report. Setup works on macOS and Linux.

## What it changes

| Piece | What it does |
|---|---|
| **File-size gate** (PreToolUse `Read\|Bash`) | Blocks a whole-file `Read` or `cat` of a file over 350 lines in the main session. The model then reads a targeted range, searches the file, or asks `bulk-reader`. It skips subagents, images, PDFs and Claude's own tool-result files. |
| **bulk-reader** agent (Haiku) | Reads big files and answers in at most 40 bullets. In the reference data, a reply averaged about 2.5k tokens instead of 6.4k. |
| **code-writer** agent (Haiku) | Writes pattern-copy code from a reference file and replies in one line. |
| **Model router** (PreToolUse `Agent`) | Sends Opus implementer subagents, fix rounds 1–3, fix waves and re-reviews of fixes back to Sonnet. Per-task and final reviews stay on Opus. Escape hatch: put `OPUS-REASON: <why>` in the prompt. Every decision is logged. |
| **Ship checklist** | Added automatically to every implementer brief. Its 7 checks come from the Critical and Important findings Opus reviewers raised most often on Sonnet's work: guards proven by a failing test, no vacuous tests, contract callers checked, lifecycle edges walked, plan bugs flagged, test evidence pasted. |
| **Session rules** (SessionStart) | Five lines of delegation rules, so you don't have to edit your CLAUDE.md. |

Each piece can be switched off on its own: `lab.py config --set routing=false` (also `gate`, `checklist`, `session_rules`).

## The lab

```
/token-lab:report            publishes the full report as an Artifact page (one URL, updated each run), or one section in chat
/token-lab:experiment        start NAME note | stop | list | presets
/token-lab:train             fit the router, checklist and gate to your own history
/token-lab:compare [file]    your periods against the pretrained reference, or a friend's export
/token-lab:share             export your aggregate numbers to swap with friends
```

The CLI behind the commands also works without Claude:

```
python3 ~/.claude/plugins/marketplaces/token-lab/plugins/token-lab/scripts/lab.py report          # text
python3 ~/.claude/plugins/marketplaces/token-lab/plugins/token-lab/scripts/lab.py report --html   # self-contained HTML page
```

### How an experiment works

An experiment is a named point in time ("from here, autocompact is 50%"). The report splits your transcripts into a baseline (the 7 days before your first experiment) plus one period per experiment, and compares them:
- **$ per active hour.** This is the headline. An active hour is a 5-minute slot with any main-session turn, counted once across parallel sessions, so a busy week doesn't look like a cost regression.
- **$ per turn, per commit and per 1k lines changed.** These show output; they vary with the kind of work.
- **Context per turn, compactions, subagent spend by role and model.**
- **Implementer quality,** if you use superpowers subagent-driven development, scored from each task's first review:
  - share approved on the first review;
  - Critical, Important and Minor findings per task;
  - fix rounds;
  - $ per task;
  - escapes, meaning findings that only the final whole-branch review caught.

Change one thing at a time, and give each experiment a week of normal work.

Costs are list-price estimates, set in `prices` and `multipliers` in the config. Cache reads count at 0.1×, cache writes at 1.25× or 2×, and output at 5×. They're good for comparing your own periods; they are not an invoice.

### Training on your own history

`/token-lab:train` does three things:
1. **Replays your past subagent dispatches through the router,** so you can see what it would block, and lets you add your own include and exclude patterns.
2. **Collects every Critical and Important finding reviewers raised on cheaper-model work** and has Claude group it into your own ship checklist (`~/.claude/token-lab/checklist.md`).
3. **Checks how the file-size gate is used,** to tune the threshold.

Nothing leaves your machine.

## What the pretrained baseline says

From `plugins/token-lab/baseline/pretrained.json` (list-price estimates):

| Period | $ / active hour | $ / turn | Mean context | Turns > 500k | Opus share of subagent $ |
|---|---|---|---|---|---|
| Baseline week | 46.16 | 0.465 | 533k | 56% | 72% |
| Auto-compact at 50% | 46.53 | 0.334 | 283k | 0% | 82% |
| + Sonnet implementer routing (first day) | 43.84 | 0.321 | 265k | 0% | 64% |

What the reference user learned:
- **Auto-compact at 50% was the biggest lever:** about half the context per turn, and 28% cheaper per turn. On 1M models, context re-sent on every turn is most of the bill.
- **The file-size gate and bulk-reader help but are small** if you rarely read whole big files.
- **A Sonnet default for subagents does nothing if your skills always name a model.** The router is what actually moved Opus implementers to Sonnet.
- **On its own tasks, Sonnet wasn't worse than Opus as reviewed:** about 0.6 Important findings per task each, at about a quarter of the cost per task. Opus also got the harder tasks.
- **Two counting traps the lab already handles:**
  - transcripts write one record per content block, so naive turn counts come out about 2× too high;
  - advisor calls report the context twice.

The routing period in the shipped file covers its first day only. It will be refreshed after a full week.

## Privacy

Everything runs locally against `~/.claude/projects`. The only data in this repo is aggregate numbers: rates, medians and counts per period. `/token-lab:share` exports the same shape. It contains no project names, paths, prompts or descriptions.

## Layout

```
.claude-plugin/marketplace.json
plugins/token-lab/
  .claude-plugin/plugin.json
  agents/        bulk-reader.md, code-writer.md
  hooks/         hooks.json, check-file-size.sh, route-subagent-models.sh, session-rules.sh, implementer-checklist.md
  commands/      setup, report, experiment, train, compare, share
  scripts/       lab.py, tokenlab/ (stdlib-only Python), schedule-weekly.sh
  baseline/      pretrained.json
baselines/community/   friends' exported baselines
```

MIT licensed.
