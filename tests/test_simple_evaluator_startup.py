from pathlib import Path

import pytest

from operation_pancake.product_app import (
    DEFAULT_SIMPLE_EVALUATOR_PORT,
    configured_port,
)


ROOT = Path(__file__).resolve().parents[1]


def test_simple_evaluator_uses_canonical_port(monkeypatch):
    monkeypatch.delenv("PANCAKE_PORT", raising=False)
    assert DEFAULT_SIMPLE_EVALUATOR_PORT == 8788
    assert configured_port() == 8788


def test_simple_evaluator_port_can_be_overridden(monkeypatch):
    monkeypatch.setenv("PANCAKE_PORT", "8899")
    assert configured_port() == 8899


@pytest.mark.parametrize("value", ["not-a-port", "0", "65536"])
def test_invalid_simple_evaluator_port_fails_closed(monkeypatch, value):
    monkeypatch.setenv("PANCAKE_PORT", value)
    with pytest.raises(ValueError):
        configured_port()


def test_windows_launcher_and_app_cannot_drift_ports():
    launcher = (ROOT / "scripts" / "Run-Simple-Evaluator.cmd").read_text(encoding="utf-8")
    canonical = str(DEFAULT_SIMPLE_EVALUATOR_PORT)
    assert f"PANCAKE_PORT={canonical}" in launcher
    assert f"--port {canonical}" in launcher
    assert f"127.0.0.1:{canonical}/api/health" in launcher
    assert f"127.0.0.1:{canonical}/" in launcher
