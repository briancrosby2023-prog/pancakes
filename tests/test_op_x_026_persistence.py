from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/persist_op_x_026_evidence.sh"


def git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def commit(repo: Path, text: str, message: str) -> str:
    path = repo / "data/research/op_x_026/result.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(repo, "add", ".")
    git(repo, "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def setup_repos(tmp_path: Path) -> tuple[Path, Path, Path]:
    bare = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    work = tmp_path / "work"
    subprocess.check_call(["git", "init", "--bare", str(bare)])
    subprocess.check_call(["git", "clone", str(bare), str(seed)])
    git(seed, "checkout", "-b", "agent/op-x-012-reconcile-artifacts")
    commit(seed, "base", "base")
    git(seed, "push", "-u", "origin", "HEAD")
    subprocess.check_call(["git", "clone", "-b", "agent/op-x-012-reconcile-artifacts", str(bare), str(work)])
    return bare, seed, work


def run_script(work: Path, **extra: str) -> subprocess.CompletedProcess[str]:
    env = os.environ | {
        "OPX026_BRANCH": "agent/op-x-012-reconcile-artifacts",
        "OPX026_REVERIFY_COMMAND": "git diff --check",
        **extra,
    }
    return subprocess.run(["bash", str(SCRIPT)], cwd=work, env=env, text=True, capture_output=True)


def test_remote_unchanged_persists(tmp_path: Path) -> None:
    bare, _, work = setup_repos(tmp_path)
    commit(work, "result", "local result")
    result = run_script(work)
    assert result.returncode == 0, result.stderr
    assert git(work, "rev-parse", "HEAD") == git(bare, "rev-parse", "refs/heads/agent/op-x-012-reconcile-artifacts")


def test_remote_advanced_is_preserved_and_result_reapplied(tmp_path: Path) -> None:
    bare, seed, work = setup_repos(tmp_path)
    commit(work, "result", "local result")
    concurrent = seed / "concurrent.txt"
    concurrent.write_text("preserve me")
    git(seed, "add", ".")
    git(seed, "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", "concurrent")
    concurrent_sha = git(seed, "rev-parse", "HEAD")
    git(seed, "push")
    result = run_script(work)
    assert result.returncode == 0, result.stderr
    remote = git(bare, "rev-parse", "refs/heads/agent/op-x-012-reconcile-artifacts")
    subprocess.check_call(["git", "merge-base", "--is-ancestor", concurrent_sha, remote], cwd=bare)


def test_conflict_fails_without_force_push(tmp_path: Path) -> None:
    bare, seed, work = setup_repos(tmp_path)
    commit(work, "local", "local result")
    commit(seed, "remote", "conflicting concurrent result")
    remote_before = git(seed, "rev-parse", "HEAD")
    git(seed, "push")
    result = run_script(work)
    assert result.returncode == 3
    assert git(bare, "rev-parse", "refs/heads/agent/op-x-012-reconcile-artifacts") == remote_before


def test_repeated_advancement_is_bounded(tmp_path: Path) -> None:
    if shutil.which("flock") is None:
        pytest.skip("requires flock-capable Linux runner")
    bare, seed, work = setup_repos(tmp_path)
    commit(work, "result", "local result")
    counter = tmp_path / "counter"
    hook = tmp_path / "advance.sh"
    hook.write_text(
        "#!/usr/bin/env bash\nset -e\n"
        f"n=$(cat {counter} 2>/dev/null || echo 0); n=$((n+1)); echo $n > {counter}\n"
        "if [ $n -le 2 ]; then "
        f"cd {seed}; git pull --rebase >/dev/null; echo $n >> race.txt; git add race.txt; "
        "git -c user.name=test -c user.email=test@example.com commit -m race-$n >/dev/null; git push >/dev/null; fi\n"
    )
    hook.chmod(0o755)
    result = run_script(work, OPX026_MAX_RETRIES="3", OPX026_TEST_BEFORE_PUSH_HOOK=str(hook))
    assert result.returncode == 0, result.stderr
    assert "OPX026_PERSISTENCE_ATTEMPT=3" in result.stdout
