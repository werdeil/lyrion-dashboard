#!/bin/bash
set -euo pipefail

# Refuses a `git commit` once with the comment lines it adds, so they get re-read
# against CLAUDE.md; run again with the same comments, the commit goes through.

input=$(cat)
command=$(printf '%s' "$input" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("tool_input", {}).get("command", ""))')
case "$command" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

cd "${CLAUDE_PROJECT_DIR:-.}"

# -a/--all commits the tracked changes too, so the diff to read is against HEAD.
if printf '%s' "$command" | grep -Eq 'git commit.*([[:space:]]-[A-Za-z]*a[A-Za-z]*([[:space:]]|$)|--all)'; then
  diff=$(git diff HEAD -U0 --no-color)
else
  diff=$(git diff --cached -U0 --no-color)
fi

comments=$(printf '%s\n' "$diff" | awk '
  /^\+\+\+ / { file = substr($0, 7); next }
  /^@@ / { split($3, a, ","); line = substr(a[1], 2) + 0; next }
  /^\+/ {
    text = substr($0, 2)
    hit = 0
    if (file ~ /\.(py|sh|ya?ml|toml)$/ || file ~ /(^|\/)Dockerfile$/) {
      hit = (text ~ /^[ \t]*#[^!]/ || text ~ /[ \t]#( |$)/)
    } else if (file ~ /\.(js|mjs|css|kt|kts|gradle)$/) {
      hit = (text ~ /^[ \t]*(\/\/|\/\*|\*)/ || text ~ /[ \t]\/\/( |$)/ || text ~ /\/\*/)
    } else if (file ~ /\.html$/) {
      hit = (text ~ /\{#|<!--/)
    }
    if (hit) { sub(/^[ \t]+/, "", text); printf "%s:%d: %s\n", file, line, text }
    line++
  }
')

[ -z "$comments" ] && exit 0

stamp="$(git rev-parse --git-dir)/claude-comment-review"
digest=$(printf '%s' "$comments" | git hash-object --stdin)
if [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$digest" ]; then
  exit 0
fi
printf '%s' "$digest" > "$stamp"

COMMENTS="$comments" python3 -c '
import json, os
reason = (
    "This commit adds the comments below. Re-read each against CLAUDE.md: it must name a "
    "constraint the code cannot show, an external quirk, an accepted risk or a public "
    "contract, in two lines at most, with no motivation or problem-story. Cut or rewrite "
    "the ones that do not, then run the commit again; unchanged comments go through.\n\n"
    + os.environ["COMMENTS"]
)
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": reason,
}}))
'
