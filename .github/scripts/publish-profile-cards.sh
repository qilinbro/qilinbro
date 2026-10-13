#!/usr/bin/env bash
# Publish one validated module without staging README or other generated files.
set -euo pipefail

source_dir=${1:?Expected generated card directory}
card_group=${2:?Expected card group}
: "${TARGET_BRANCH:?Expected target branch}"

python3 .github/scripts/validate-profile-cards.py "$source_dir" --group "$card_group"
python3 .github/scripts/normalize-profile-cards.py "$source_dir" --group "$card_group"
python3 .github/scripts/validate-profile-cards.py "$source_dir" --group "$card_group"
card_list=$(python3 .github/scripts/validate-profile-cards.py "$source_dir" --group "$card_group" --list)
mapfile -t cards <<< "$card_list"
paths=()
for card in "${cards[@]}"; do
  destination="profile/$card"
  mkdir -p "$(dirname "$destination")"
  cp "$source_dir/$card" "$destination"
  paths+=("$destination")
done
git add -- "${paths[@]}"
if git diff --cached --quiet -- "${paths[@]}"; then
  echo "$card_group profile cards are unchanged."
  exit 0
fi
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git commit --only -m "📊 Update $card_group profile cards" -- "${paths[@]}"

# Independent card jobs and WakaTime may publish while this module renders.
# Rebase only this module's commit; never force-push or drop another update.
for attempt in 1 2 3 4 5; do
  git fetch origin "$TARGET_BRANCH"
  git rebase "origin/$TARGET_BRANCH"
  if git push origin "HEAD:$TARGET_BRANCH"; then
    exit 0
  fi
  echo "Branch advanced during publish; retry $attempt of 5."
  if [ "$attempt" -lt 5 ]; then
    sleep "$((attempt * 2))"
  fi
done
echo "Could not publish $card_group cards after five attempts." >&2
exit 1
