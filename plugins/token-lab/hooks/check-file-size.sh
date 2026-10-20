#!/usr/bin/env bash
set -uo pipefail
command -v jq >/dev/null 2>&1 || exit 0
input=$(cat)
state="${TOKEN_LAB_HOME:-$HOME/.claude/token-lab}"
cfg="$state/config.json"

[ "$(jq -r 'if .gate == false then "off" else "on" end' "$cfg" 2>/dev/null)" = "off" ] && exit 0
[ -n "$(jq -r '.agent_type // empty' <<<"$input" 2>/dev/null)" ] && exit 0

threshold=${CLAUDE_READ_LINE_THRESHOLD:-$(jq -r '.read_line_threshold // 350' "$cfg" 2>/dev/null || echo 350)}
case "$threshold" in ''|*[!0-9]*) threshold=350 ;; esac

tool=$(jq -r '.tool_name // empty' <<<"$input" 2>/dev/null)
cwd=$(jq -r '.cwd // empty' <<<"$input" 2>/dev/null)

if [ "$tool" = "Read" ]; then
  [ -n "$(jq -r '.tool_input.limit // empty' <<<"$input")" ] && exit 0
  file=$(jq -r '.tool_input.file_path // empty' <<<"$input")
elif [ "$tool" = "Bash" ]; then
  cmd=$(jq -r '.tool_input.command // empty' <<<"$input")
  seg=$(grep -oE '(^|[;&|][[:space:]]*)(cat|less|more)[[:space:]]+[^-|;&>< ][^|;&>< ]*[[:space:]]*(\|\|?)?' <<<"$cmd" | head -1)
  case "$seg" in *"||") ;; *"|") exit 0 ;; esac
  file=$(sed -E 's/[[:space:]]*\|*$//' <<<"$seg" | awk '{print $NF}' | tr -d "\"'")
else
  exit 0
fi

[ -z "${file:-}" ] && exit 0
file="${file/#\~/$HOME}"
case "$file" in /*) ;; *) [ -n "$cwd" ] && file="$cwd/$file" ;; esac
[ -f "$file" ] || exit 0
case "$file" in *.png|*.jpg|*.jpeg|*.gif|*.webp|*.pdf|*.ipynb) exit 0 ;; esac
case "$file" in "$HOME/.claude/projects/"*/tool-results/*) exit 0 ;; esac
while IFS= read -r pat; do
  [ -z "$pat" ] && continue
  pat="${pat/#\~/$HOME}"
  # shellcheck disable=SC2254
  case "$file" in $pat) exit 0 ;; esac
done < <(jq -r '.gate_exempt[]? // empty' "$cfg" 2>/dev/null)

lines=$(wc -l <"$file" | tr -d ' ')
if [ "$lines" -gt "$threshold" ]; then
  echo "Blocked: $file is $lines lines (>$threshold). Delegate to the token-lab:bulk-reader agent with your question and the path, or Read with offset+limit if you already know the section you need (e.g. to edit it)." >&2
  exit 2
fi
exit 0
