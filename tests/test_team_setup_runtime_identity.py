import subprocess
import sys
import tomllib
from pathlib import Path

from operation_pancake import team_app


def test_operation_pancake_app_entrypoint_is_team_runtime():
    config = tomllib.loads(Path("pyproject.toml").read_text())
    assert config["project"]["scripts"]["operation-pancake-app"] == "operation_pancake.ocr_team_app_visual:main"


def test_team_runtime_marker_is_code_identity_not_checkout_identity():
    code = """
from operation_pancake import ocr_team_app_visual, team_app
ocr_team_app_visual.install_runtime()
assert ocr_team_app_visual.TEAM_SETUP_BUILD == 'TEAM-SLOT-EXTRACTION-PATCH-1'
assert team_app.TEAM_SETUP_BUILD == 'TEAM-SLOT-EXTRACTION-PATCH-1'
surface = team_app._upload_surface()
assert 'TEAM SETUP BUILD: TEAM-SLOT-EXTRACTION-PATCH-1' in surface
assert 'DROP HANDLER: NOT READY' in surface
assert "setStatus('DROP HANDLER: READY')" in surface
print('SLOT EXTRACTION RUNTIME IDENTITY PASS')
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "SLOT EXTRACTION RUNTIME IDENTITY PASS" in result.stdout


def test_team_setup_declares_no_cache_response_contract():
    src = Path(team_app.__file__).read_text()
    assert '"Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"' in src
    assert '"Pragma", "no-cache"' in src
    assert '"Expires", "0"' in src
