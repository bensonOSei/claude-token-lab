#!/usr/bin/env bash
set -uo pipefail
command -v jq >/dev/null 2>&1 || exit 0
input=$(cat)
state="${TOKEN_LAB_HOME:-$HOME/.claude/token-lab}"
cfg="$state/config.json"
LOG="$state/routing.log"
here="$(cd "$(dirname "$0")" && pwd)"
CHECKLIST="$state/checklist.md"
[ -f "$CHECKLIST" ] || CHECKLIST="$here/implementer-checklist.md"

routing=$(jq -r 'if .routing == false then "off" else "on" end' "$cfg" 2>/dev/null || echo on)
checklist=$(jq -r 'if .checklist == false then "off" else "on" end' "$cfg" 2>/dev/null || echo on)
[ "$routing" = "off" ] && [ "$checklist" = "off" ] && exit 0

agent=$(jq -r '.tool_input.subagent_type // "general-purpose"' <<<"$input" 2>/dev/null) || exit 0
model=$(jq -r '.tool_input.model // empty' <<<"$input")
desc=$(jq -r '.tool_input.description // empty' <<<"$input")
prompt=$(jq -r '.tool_input.prompt // empty' <<<"$input")

case "$agent" in ""|general-purpose|claude) ;; *) exit 0 ;; esac
strong=""
case "$model" in *opus*|*fable*) strong=1 ;; esac

lower=$(tr '[:upper:]' '[:lower:]' <<<"$desc")
has() { grep -qE "$1" <<<"$lower"; }
kind=""
extra_allow=$(jq -r '(.routing_allow_patterns // []) | join("|")' "$cfg" 2>/dev/null)
extra_impl=$(jq -r '(.routing_implementer_patterns // []) | join("|")' "$cfg" 2>/dev/null)
if [ -n "$extra_allow" ] && has "$extra_allow"; then
  exit 0
elif [ -n "$extra_impl" ] && has "$extra_impl"; then
  kind="implementer"
elif has '\bplan\b|design|architect|pre-?flight|scan|investigat|debug|diagnos|research|merge|security'; then
  exit 0
elif has 're-?review'; then
  kind="re-review"
elif has '^(review|audit|verify)'; then
  exit 0
elif has '(round|wave|attempt)[^0-9]*[45]\b'; then
  kind="escalation"
elif has '\bfix(es|er)?\b'; then
  kind="implementer"
elif has '^implement|implementer|tasks? [a-z0-9.+ ]*:' && ! has 'review'; then
  kind="implementer"
elif has 'review|audit|verif|check'; then
  exit 0
elif has '^(build|write|add) '; then
  kind="implementer"
fi
[ -z "$kind" ] && exit 0
[ "${TOKEN_LAB_CLASSIFY_ONLY:-}" = "1" ] && { echo "$kind"; exit 0; }

reason=$(grep -o 'OPUS-REASON:.*' <<<"$prompt" | head -1 | tr '\t' ' ' | cut -c1-300)
log() {
  [ "${TOKEN_LAB_DRY_RUN:-}" = "1" ] && return 0
  mkdir -p "$state"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$1" "$kind" "${model:-default}" "$desc" "$reason" >>"$LOG"
}

allow() {
  if [ "$checklist" = "off" ] || [ "$kind" = "re-review" ] || grep -q 'Ship checklist (added by token-lab' <<<"$prompt"; then
    log "$1"
    exit 0
  fi
  log "$1+checklist"
  jq -c --rawfile extra "$CHECKLIST" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "allow", permissionDecisionReason: "token-lab: ship checklist appended to implementer brief", updatedInput: (.tool_input + {prompt: ((.tool_input.prompt // "") + $extra)})}}' <<<"$input"
  exit 0
}

if [ "$routing" = "off" ] || [ -z "$strong" ] || [ "$kind" = "escalation" ]; then
  allow "allowed"
fi
if [ -n "$reason" ]; then
  allow "allowed-with-reason"
fi

log "blocked"
if [ "$kind" = "implementer" ]; then
  echo "Blocked by token-lab: implementer subagents run on Sonnet. Re-dispatch \"$desc\" with model: \"sonnet\". Keep the per-task review on Opus. Fix rounds 4-5 may use Opus. If this task needs design judgment (architecture, concurrency, security, money), add a line 'OPUS-REASON: <why>' to the prompt and dispatch again on Opus." >&2
else
  echo "Blocked by token-lab: scoped re-reviews of a fix diff run on Sonnet. Re-dispatch \"$desc\" with model: \"sonnet\". If the fix touches concurrency, security or money, add 'OPUS-REASON: <why>' to the prompt and dispatch again on Opus." >&2
fi
exit 2
