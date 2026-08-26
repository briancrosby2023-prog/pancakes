#!/usr/bin/env bash
set -euo pipefail

branch="${OPX026_BRANCH:-agent/op-x-012-reconcile-artifacts}"
max_retries="${OPX026_MAX_RETRIES:-3}"
reverify="${OPX026_REVERIFY_COMMAND:-python -m pytest -q tests -k 'gm or roster or budget or market or role or knowledge' && python -m ruff check . && git diff --check}"

case "$max_retries" in
  ''|*[!0-9]*) echo "OPX026_MAX_RETRIES must be a positive integer" >&2; exit 2 ;;
esac
if (( max_retries < 1 )); then echo "OPX026_MAX_RETRIES must be >= 1" >&2; exit 2; fi

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git add data/research/op_x_026 2>/dev/null || true
if ! git diff --cached --quiet; then
  git commit -m 'Persist OP-X-026 product acceptance evidence'
fi
result_commit="$(git rev-parse HEAD)"
echo "OPX026_RESULT_COMMIT=$result_commit"

for ((attempt=1; attempt<=max_retries; attempt++)); do
  echo "OPX026_PERSISTENCE_ATTEMPT=$attempt"
  git fetch origin "$branch"
  remote_head="$(git rev-parse FETCH_HEAD)"
  if ! git merge-base --is-ancestor "$remote_head" HEAD; then
    echo "Remote advanced to $remote_head; rebasing OP-X-026 result without force."
    if ! git rebase "$remote_head"; then
      git rebase --abort || true
      echo "OP-X-026 persistence conflict; refusing to overwrite concurrent history." >&2
      exit 3
    fi
    echo "Reconciled result; rerunning verification."
    bash -lc "$reverify"
  fi

  if [[ -n "${OPX026_TEST_BEFORE_PUSH_HOOK:-}" ]]; then
    bash -lc "$OPX026_TEST_BEFORE_PUSH_HOOK"
  fi

  if git push origin "HEAD:$branch"; then
    git fetch origin "$branch"
    remote_head="$(git rev-parse FETCH_HEAD)"
    if git merge-base --is-ancestor HEAD "$remote_head"; then
      echo "OPX026_PERSISTED_HEAD=$remote_head"
      exit 0
    fi
  fi
  echo "Push raced with another writer; retrying safely." >&2
done

echo "OP-X-026 evidence could not be persisted after $max_retries attempts; artifact remains authoritative." >&2
exit 4
