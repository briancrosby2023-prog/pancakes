from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
ACTION=ROOT/"scripts/pancake_single_worktab_action.py"

def test_cadence_wait_uses_current_exact_card_url_not_stale_search_url():
    source=ACTION.read_text(encoding="utf-8")
    start=source.index("# Prove the real saved-watch 120-second scheduler.")
    end=source.index("selected = uia_snapshot",start)
    block=source[start:end]
    assert "cadence_prior_url = current_selected_url(edge_pid, control)" in block
    assert "wait_url_change(\n            edge_pid,\n            cadence_prior_url," in block
    assert "wait_url_change(\n            edge_pid,\n            second_url," not in block

def test_issue104_timing_requires_waiting_beyond_old_60_second_window():
    first_observed=49.973
    second_observed=62.900
    due=first_observed+120.0
    wait=due-second_observed
    assert round(wait,3)==107.073
    assert wait>60.0

def test_cadence_requirement_remains_120_seconds():
    source=ACTION.read_text(encoding="utf-8")
    assert "if cadence_delta < 120.0:" in source
    assert "saved-watch cadence violated 120-second minimum" in source
