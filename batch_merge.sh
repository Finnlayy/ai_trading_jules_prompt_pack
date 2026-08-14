#!/usr/bin/env bash
# Batch-resolve test PRs: data conflicts -> main's version (or deletion), junk dropped.
set -u
cd "$(dirname "$0")"
REPO="Finnlayy/ai_trading_jules_prompt_pack"
GH="/c/Program Files/GitHub CLI/gh.exe"

is_data() {
  case "$1" in
    data/*|app/data/*|wiki/second_brain*|.Jules/*|.jules/*) return 0 ;;
    *.db) return 0 ;;
    *) return 1 ;;
  esac
}

is_junk() {
  base="$(basename "$1")"
  case "$base" in
    *.orig|*.rej|patch*.diff|pytest_output*.txt|patch_script*.py) return 0 ;;
    *) return 1 ;;
  esac
}

process_pr() {
  local n="$1" branch="$2"
  state=$("$GH" pr view "$n" --repo "$REPO" --json state --jq .state 2>/dev/null)
  if [ "$state" != "OPEN" ]; then echo "===== PR #$n already $state — skip ====="; return 0; fi
  echo "===== PR #$n ($branch) ====="
  git checkout --quiet main || { echo "SKIP: checkout main failed"; return 1; }
  git pull --quiet --ff-only origin main || { echo "SKIP: pull failed"; return 1; }
  git branch -D "pr$n" >/dev/null 2>&1
  git checkout --quiet -b "pr$n" "origin/$branch" || { echo "SKIP: no branch"; return 1; }
  if ! git merge --no-commit --no-ff main >/dev/null 2>&1; then
    # resolve conflicts
    for p in $(git diff --name-only --diff-filter=U); do
      if is_data "$p"; then
        if git cat-file -e "main:$p" 2>/dev/null; then
          git checkout main -- "$p" && git add "$p"
        else
          git rm -q -f "$p" 2>/dev/null || git rm -q --cached "$p"
        fi
      else
        echo "CODE-CONFLICT: $p"
      fi
    done
  fi
  # drop PR-introduced junk
  for p in $(git diff main --name-only --diff-filter=A 2>/dev/null); do
    if is_junk "$p"; then git rm -q -f "$p" && echo "junk dropped: $p"; fi
  done
  git add -A
  if git diff --name-only --diff-filter=U | grep -q .; then
    echo "MANUAL-NEEDED"
    git merge --abort 2>/dev/null
    git checkout --quiet main
    return 2
  fi
  git commit --quiet --no-edit 2>/dev/null || true
  if git push --quiet origin "pr$n:$branch"; then
    sleep 10
    out=$("$GH" pr merge "$n" --repo "$REPO" --merge 2>&1 | tail -1)
    state=$("$GH" pr view "$n" --repo "$REPO" --json state --jq .state)
    echo "MERGE-RESULT: $state $out"
  else
    echo "PUSH-FAILED"
  fi
}

while IFS=$'\t' read -r n branch; do
  process_pr "$n" "$branch"
done <<'EOF'
45	fix-testing-gap-watchlist-manager-10470211274201474961
46	jules-11678610202390391067-14c42fd6
48	test-broker-factory-16989667215757736676
49	fix-live-fill-tracker-tests-5741351084010289955
51	jules-6596719831303432707-ce6aeb1c
53	jules-10637266468850696346-754c6a45
56	fix-test-json-utils-coverage-14527404018604688191
59	jules-11206880904231248358-f1a18e4d
65	test-performance-calculator-3779808663752402885
68	add-watchlist-manager-tests-12943631086431461068
74	test-performance-calculator-14561945165608873238
76	jules-telegram-advisors-tests-5417829170708140148
78	jules-5193028563667368441-4a4fe4bc
80	test-loop-health-monitor-11720252679426844872
133	fix-utils-tests-8479287265844701274
138	fix-glint-broker-coverage-5241467230807609675
156	test/schemas-ai-layer-2428958487146196981
159	jules-9083801453990049597-9bb6ff0b
161	test-json-dumps-17014892817146648674
163	test-json-dumps-default-6929432430231047548
EOF
