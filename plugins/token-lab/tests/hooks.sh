#!/usr/bin/env bash
here="$(cd "$(dirname "$0")/.." && pwd)"; cd "$here/hooks" || exit 1
export TOKEN_LAB_HOME="$(mktemp -d)"; rm -rf "$TOKEN_LAB_HOME"; mkdir -p "$TOKEN_LAB_HOME"
fail=0
mk() { jq -cn --arg t "$1" --arg m "$2" --arg d "$3" --arg p "$4" '{tool_name:"Agent",tool_input:{subagent_type:$t,model:$m,description:$d,prompt:$p}}'; }
t() { out=$(printf '%s' "$2" | ./route-subagent-models.sh 2>/dev/null); rc=$?; inj=$(jq -r '.hookSpecificOutput.updatedInput.prompt // empty' <<<"$out" 2>/dev/null | grep -c "$5"); if [ "$rc" = "$1" ] && [ "$inj" = "$3" ]; then r=ok; else r=FAIL; fail=1; fi; printf '%-4s rc=%s ck=%s  %s\n' "$r" "$rc" "$inj" "$4"; }
M='Ship checklist (added by token-lab'
t 2 "$(mk general-purpose opus 'Implement Task 4: POS' 'do it')" 0 "opus implementer blocked" "$M"
t 0 "$(mk general-purpose sonnet 'Implement Task 4: POS' 'do it')" 1 "sonnet implementer + checklist" "$M"
t 0 "$(mk '' '' 'v2 Task 3: sky light' 'do it')" 1 "default model + checklist" "$M"
t 0 "$(mk general-purpose opus 'Implement Task 4: POS' $'b\nOPUS-REASON: lock-free')" 1 "escape hatch + checklist" "$M"
t 0 "$(mk general-purpose sonnet 'Implement Task 4: POS' $'x\n## Ship checklist (added by token-lab; do all)')" 0 "no double checklist" "$M"
t 0 "$(mk general-purpose opus 'Review Task 4 (spec + quality)' 'x')" 0 "opus review untouched" "$M"
t 2 "$(mk general-purpose opus 'Re-review Task 4 fix round 1' 'x')" 0 "opus re-review blocked" "$M"
t 0 "$(mk general-purpose opus 'Fix round 4 Task 7' 'x')" 1 "round 4 escalation" "$M"
t 0 "$(mk general-purpose opus 'Write v0.8.0 implementation plan' 'x')" 0 "plan untouched" "$M"
t 0 "$(mk money-guardian opus 'Implement nothing' 'x')" 0 "other agent types untouched" "$M"
t 0 'not json' 0 "malformed input" "$M"
echo '{"routing_implementer_patterns":["^polish"],"routing_allow_patterns":["^implement task 9"]}' > "$TOKEN_LAB_HOME/config.json"
t 2 "$(mk general-purpose opus 'Polish: occlude pins' 'x')" 0 "custom implementer pattern blocks" "$M"
t 0 "$(mk general-purpose opus 'Implement Task 9: x' 'x')" 0 "custom allow pattern passes" "$M"
echo '{"routing":false}' > "$TOKEN_LAB_HOME/config.json"
t 0 "$(mk general-purpose opus 'Implement Task 4: POS' 'x')" 1 "routing off: opus allowed, checklist kept" "$M"
printf '\n\n## Ship checklist (added by token-lab; do all of it before you report DONE)\n1. MY OWN ITEM\n' > "$TOKEN_LAB_HOME/checklist.md"
t 0 "$(mk general-purpose sonnet 'Implement Task 4: POS' 'x')" 1 "personal checklist used" "MY OWN ITEM"
echo '{"routing":false,"checklist":false}' > "$TOKEN_LAB_HOME/config.json"
t 0 "$(mk general-purpose opus 'Implement Task 4: POS' 'x')" 0 "both off: untouched" "$M"
echo "--- log lines: $(wc -l < "$TOKEN_LAB_HOME/routing.log")"
rm -f "$TOKEN_LAB_HOME/config.json"; big="$TOKEN_LAB_HOME/big.txt"; seq 1 400 > "$big"; small="$TOKEN_LAB_HOME/s.txt"; seq 1 10 > "$small"
gt() { printf '%s' "$2" | ./check-file-size.sh >/dev/null 2>&1; rc=$?; if [ "$rc" = "$1" ]; then r=ok; else r=FAIL; fail=1; fi; printf '%-4s rc=%s %s\n' "$r" "$rc" "$3"; }
gt 2 "$(jq -cn --arg f "$big" '{tool_name:"Read",tool_input:{file_path:$f}}')" "big read blocked"
gt 0 "$(jq -cn --arg f "$big" '{tool_name:"Read",tool_input:{file_path:$f,limit:50}}')" "targeted read ok"
gt 0 "$(jq -cn --arg f "$small" '{tool_name:"Read",tool_input:{file_path:$f}}')" "small read ok"
gt 2 "$(jq -cn --arg f "$big" '{tool_name:"Bash",tool_input:{command:("cat "+$f)}}')" "cat big blocked"
gt 0 "$(jq -cn --arg f "$big" '{tool_name:"Bash",tool_input:{command:("cat "+$f+" | grep 3")}}')" "piped cat ok"
gt 0 "$(jq -cn --arg f "$big" '{tool_name:"Read",agent_type:"x",tool_input:{file_path:$f}}')" "subagent skipped"
echo "{\"gate_exempt\":[\"$TOKEN_LAB_HOME/*.txt\"]}" > "$TOKEN_LAB_HOME/config.json"
gt 0 "$(jq -cn --arg f "$big" '{tool_name:"Read",tool_input:{file_path:$f}}')" "exempt glob ok"
echo '{"read_line_threshold":500}' > "$TOKEN_LAB_HOME/config.json"
gt 0 "$(jq -cn --arg f "$big" '{tool_name:"Read",tool_input:{file_path:$f}}')" "threshold 500 ok"
echo '{"gate":false}' > "$TOKEN_LAB_HOME/config.json"
gt 0 "$(jq -cn --arg f "$big" '{tool_name:"Read",tool_input:{file_path:$f}}')" "gate off ok"
rm -f "$TOKEN_LAB_HOME/config.json"
[ "$(./session-rules.sh | head -1)" = "token-lab delegation rules:" ] && echo "ok   session rules print" || { echo "FAIL session rules"; fail=1; }
echo '{"session_rules":false}' > "$TOKEN_LAB_HOME/config.json"
[ -z "$(./session-rules.sh)" ] && echo "ok   session rules off" || { echo "FAIL session rules off"; fail=1; }
exit $fail
