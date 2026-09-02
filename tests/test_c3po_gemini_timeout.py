import json
import sys
import types

from operation_pancake.c3po_vision import GEMINI_REQUEST_TIMEOUT_MS, GeminiScreenshotTranslator


def test_gemini_client_has_explicit_bounded_timeout(monkeypatch, tmp_path):
    seen = {}
    payload = {"view":"OFFENSE","slots":{"LT1":{"starter":{"observed_name":"Josh Petty","displayed_ovr":80},"backups":[]},"RT1":{"starter":{"observed_name":"Cason Henry","displayed_ovr":85},"backups":[]}}}

    class HttpOptions:
        def __init__(self, timeout): self.timeout = timeout; seen["timeout"] = timeout
    class Interactions:
        def create(self, **kwargs): seen["request"] = kwargs; return types.SimpleNamespace(output_text=json.dumps(payload))
    class Client:
        def __init__(self, **kwargs): seen["client"] = kwargs; self.interactions = Interactions()
        def __enter__(self): return self
        def __exit__(self, *args): return None

    google = types.ModuleType("google"); genai = types.ModuleType("google.genai"); genai.Client = Client; genai.types = types.SimpleNamespace(HttpOptions=HttpOptions); google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google); monkeypatch.setitem(sys.modules, "google.genai", genai)
    image = tmp_path / "screen.png"; image.write_bytes(b"pixels")
    translated = GeminiScreenshotTranslator(api_key="test-key").translate_offense_tackles(image)
    assert seen["timeout"] == GEMINI_REQUEST_TIMEOUT_MS == 15_000
    assert translated.slots["RT1"].starter.observed_name == "Cason Henry"
    assert "test-key" not in json.dumps(seen["request"])
