#!/usr/bin/env bash
set -euo pipefail

branch="${OPX026_BRANCH:-agent/op-x-012-reconcile-artifacts}"
max_retries="${OPX026_MAX_RETRIES:-3}"
reverify="${OPX026_REVERIFY_COMMAND:-python -m pytest -q tests -k 'gm or roster or budget or market or role or knowledge' && python -m ruff check . && git diff --check}"
closure_record="data/research/op_x_026/closure_gates.json"

case "$max_retries" in
  ''|*[!0-9]*) echo "OPX026_MAX_RETRIES must be a positive integer" >&2; exit 2 ;;
esac
if (( max_retries < 1 )); then echo "OPX026_MAX_RETRIES must be >= 1" >&2; exit 2; fi

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'

# Persistence starts false and is only promoted after the evidence commit is
# confirmed on the remote branch. This makes a failed persistence attempt
# durably truthful instead of optimistic.
if [[ -f "$closure_record" ]]; then
  python - <<'PY'
import json
from pathlib import Path

path = Path('data/research/op_x_026/closure_gates.json')
payload = json.loads(path.read_text())
gates = payload.setdefault('gates', {})
gates['persistence'] = 'failure'
payload['all_required_gates_pass'] = all(value == 'success' for value in gates.values())
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
PY
fi

git add data/research/op_x_026 2>/dev/null || true
if ! git diff --cached --quiet; then
  git commit -m 'Persist OP-X-026 product acceptance evidence'
fi
result_commit="$(git rev-parse HEAD)"
echo "OPX026_RESULT_COMMIT=$result_commit"

persisted=0
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
      echo "OPX026_EVIDENCE_PERSISTED_HEAD=$remote_head"
      persisted=1
      break
    fi
  fi
  echo "Push raced with another writer; retrying safely." >&2
done

if (( persisted != 1 )); then
  echo "OP-X-026 evidence could not be persisted after $max_retries attempts; artifact remains authoritative." >&2
  exit 4
fi

# The remote now contains the evidence commit. Only now may persistence become
# true. Commit that fact separately, then safely establish the final closure
# record on the remote as well.
python - <<'PY'
import json
from pathlib import Path

path = Path('data/research/op_x_026/closure_gates.json')
payload = json.loads(path.read_text())
gates = payload.setdefault('gates', {})
gates['persistence'] = 'success'
payload['all_required_gates_pass'] = all(value == 'success' for value in gates.values())
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
PY

git add "$closure_record"
git commit -m 'Finalize OP-X-026 closure persistence state'

for ((attempt=1; attempt<=max_retries; attempt++)); do
  echo "OPX026_FINALIZATION_ATTEMPT=$attempt"
  git fetch origin "$branch"
  remote_head="$(git rev-parse FETCH_HEAD)"
  if ! git merge-base --is-ancestor "$remote_head" HEAD; then
    echo "Remote advanced to $remote_head during closure finalization; rebasing without force."
    if ! git rebase "$remote_head"; then
      git rebase --abort || true
      echo "OP-X-026 closure finalization conflict; refusing to overwrite concurrent history." >&2
      exit 5
    fi
    bash -lc "$reverify"
  fi
  if git push origin "HEAD:$branch"; then
    git fetch origin "$branch"
    remote_head="$(git rev-parse FETCH_HEAD)"
    if git merge-base --is-ancestor HEAD "$remote_head"; then
      echo "OPX026_PERSISTED_HEAD=$remote_head"
      exit 0
    fi
  fi
  echo "Final closure push raced with another writer; retrying safely." >&2
done

echo "OP-X-026 evidence persisted, but final closure record could not be established remotely." >&2
exit 6
