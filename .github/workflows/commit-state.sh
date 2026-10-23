#!/usr/bin/env bash
# Commit bot state back to main as github-actions[bot].
# Pull --rebase immediately before push so overlapping jobs do not lose updates.
set -euo pipefail

message="${1:-chore: save bot state [skip ci]}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git add -- *_state.json ai_calendar.json

if git diff --cached --quiet; then
  echo "No state changes."
  exit 0
fi

git commit -m "$message"

for attempt in 1 2 3 4 5; do
  git pull --rebase origin main
  if git push origin HEAD:main; then
    echo "State pushed to main."
    exit 0
  fi
  echo "Push rejected (attempt ${attempt}). Retrying."
  sleep $((attempt * 3))
done

echo "Could not push state to main."
exit 1
