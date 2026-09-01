import tomllib
from pathlib import Path

from operation_pancake import ocr_team_app_visual, team_app


def test_operation_pancake_app_entrypoint_is_team_runtime():
    config = tomllib.loads(Path("pyproject.toml").read_text())
    assert config["project"]["scripts"]["operation-pancake-app"] == "operation_pancake.ocr_team_app_visual:main"


def test_team_runtime_marker_is_code_identity_not_checkout_identity():
    original = (team_app.create_handler, team_app._extract, team_app.TEAM_SETUP_BUILD)
    try:
        ocr_team_app_visual.install_runtime()
        assert ocr_team_app_visual.TEAM_SETUP_BUILD == "TEAM-LINEUP-VISUAL-PATCH-1"
        assert team_app.TEAM_SETUP_BUILD == "TEAM-LINEUP-VISUAL-PATCH-1"
        surface = team_app._upload_surface()
        assert "TEAM SETUP BUILD: TEAM-LINEUP-VISUAL-PATCH-1" in surface
        assert "DROP HANDLER: NOT READY" in surface
        assert "setStatus('DROP HANDLER: READY')" in surface
    finally:
        team_app.create_handler, team_app._extract, team_app.TEAM_SETUP_BUILD = original


def test_team_setup_declares_no_cache_response_contract():
    src = Path(team_app.__file__).read_text()
    assert '"Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"' in src
    assert '"Pragma", "no-cache"' in src
    assert '"Expires", "0"' in src
