from pathlib import Path
import hashlib, json, subprocess

ROOT=Path(__file__).resolve().parents[1]
ACTION=ROOT/"scripts/pancake_single_worktab_action.py"
RELEASE=ROOT/"runtime/simple_evaluator/RELEASE.json"
ACCEPTED_SHA="b70dcc20caa290c3ef839df6ebdd021f56bad492aca621c1feec2bf2b19b02b2"

def test_accepted_release_sha_is_deterministic():
    release=json.loads(RELEASE.read_text(encoding="utf-8"))
    release["status"]="PRODUCTION_ACCEPTED"
    raw=(json.dumps(release,indent=2)+"\n").encode("utf-8")
    assert hashlib.sha256(raw).hexdigest()==ACCEPTED_SHA

def test_final_verifier_explicitly_requires_accepted_release():
    source=ACTION.read_text(encoding="utf-8")
    assert f'ACCEPTED_RELEASE_SHA256 = "{ACCEPTED_SHA}"' in source
    assert "def verify_installed_files(control, *, prepatch: bool = False, accepted: bool = False)" in source
    assert 'expected_status = "PRODUCTION_ACCEPTED" if accepted else "FROZEN_PENDING_PHYSICAL_ACCEPTANCE"' in source
    assert "verify_installed_files(control, prepatch=False, accepted=True)" in source

def test_pending_verification_remains_pending_before_acceptance():
    source=ACTION.read_text(encoding="utf-8")
    assert "installed_hashes = verify_installed_files(control, prepatch=False)" in source
    assert "PENDING_RELEASE_SHA256" in source

def test_runtime_release_blob_remains_pending():
    release=json.loads(RELEASE.read_text(encoding="utf-8"))
    assert release["status"]=="FROZEN_PENDING_PHYSICAL_ACCEPTANCE"
    assert release["browser_helper_version"]=="1.4.16"
