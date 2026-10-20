#!/usr/bin/env bash
state="${TOKEN_LAB_HOME:-$HOME/.claude/token-lab}"
if command -v jq >/dev/null 2>&1 && [ "$(jq -r 'if .session_rules == false then "off" else "on" end' "$state/config.json" 2>/dev/null)" = "off" ]; then
  exit 0
fi
cat <<'TXT'
token-lab delegation rules:
- Questions about a large file (350+ lines) or 3+ files: send them to the token-lab:bulk-reader agent with the exact paths. Use Read with offset+limit when you are about to edit.
- Pattern-copy code (a test next to similar tests) goes to token-lab:code-writer, always with a reference file.
- Never delegate debugging, architecture, security, money logic or code review.
- Implementers, fix rounds 1-3, fix waves and re-reviews of a fix run on Sonnet. Per-task and final reviews stay on Opus. If an implementer truly needs Opus, add `OPUS-REASON: <why>` to its prompt.
- The hook appends a ship checklist to implementer briefs. Don't strip it or paste a second copy.
TXT
