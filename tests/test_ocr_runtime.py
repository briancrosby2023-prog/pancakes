import subprocess
from pathlib import Path

from operation_pancake import ocr_runtime, ocr_team_app, team_app


def test_unavailable_is_fail_closed_and_actionable(monkeypatch):
    monkeypatch.setattr(ocr_runtime.shutil, "which", lambda *a, **k: None)
    runtime = ocr_runtime.discover_tesseract(platform="posix", env={"PATH": ""})
    assert not runtime.ready and runtime.executable is None
    assert "NOT INSTALLED" in runtime.message and "Tesseract" in runtime.message


def test_path_discovery_requires_executable_version_probe(monkeypatch):
    monkeypatch.setattr(ocr_runtime.shutil, "which", lambda *a, **k: "/usr/bin/tesseract")
    monkeypatch.setattr(ocr_runtime.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "tesseract 5.3.0\n", ""))
    runtime = ocr_runtime.discover_tesseract(platform="posix", env={"PATH": "/usr/bin"})
    assert runtime.ready and runtime.executable == "/usr/bin/tesseract"
    assert runtime.version == "tesseract 5.3.0" and runtime.source == "PATH"


def test_windows_common_location_discovery(monkeypatch, tmp_path):
    exe = tmp_path / "Tesseract-OCR" / "tesseract.exe"
    exe.parent.mkdir(); exe.write_bytes(b"exe")
    monkeypatch.setattr(ocr_runtime.shutil, "which", lambda *a, **k: None)
    monkeypatch.setattr(ocr_runtime.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "tesseract 5.4.1\n", ""))
    runtime = ocr_runtime.discover_tesseract(platform="nt", env={"ProgramFiles": str(tmp_path), "PATH": ""})
    assert runtime.ready and Path(runtime.executable) == exe
    assert runtime.source == "Windows common install location"


def test_ready_ui_means_version_probe_succeeded(monkeypatch):
    ready = ocr_runtime.OCRRuntime(True, "C:/Tesseract-OCR/tesseract.exe", "tesseract 5.4.1", "test", "OCR ENGINE: READY — tesseract 5.4.1 — C:/Tesseract-OCR/tesseract.exe")
    monkeypatch.setattr(ocr_team_app, "discover_tesseract", lambda: ready)
    page = ocr_team_app._upload_surface()
    assert "TEAM SETUP BUILD: OCR-RUNTIME-PATCH-1" in page
    assert "DROP HANDLER: NOT READY" in page
    assert "OCR ENGINE: READY" in page and "tesseract.exe" in page


def test_production_extractor_invokes_discovered_engine(monkeypatch, tmp_path):
    ready = ocr_runtime.OCRRuntime(True, "C:/Tesseract-OCR/tesseract.exe", "tesseract 5", "test", "ready")
    monkeypatch.setattr(ocr_team_app, "discover_tesseract", lambda: ready)
    seen = {}
    tsv = "level\tleft\ttop\twidth\theight\tconf\ttext\n1\t0\t0\t100\t50\t-1\t\n5\t10\t10\t20\t10\t95\tQB\n"
    def run(args, **kwargs):
        seen["args"] = args
        return subprocess.CompletedProcess(args, 0, tsv, "")
    monkeypatch.setattr(ocr_team_app.subprocess, "run", run)
    image = tmp_path / "team.jpg"; image.write_bytes(b"image")
    words = ocr_team_app._ocr(image)
    assert seen["args"][0] == ready.executable
    assert seen["args"][1] == str(image) and "tsv" in seen["args"]
    assert words and words[0].text == "QB"


def test_supported_runtime_preserves_patch3_dropzone(monkeypatch):
    ready = ocr_runtime.OCRRuntime(True, "/usr/bin/tesseract", "tesseract 5", "test", "OCR ENGINE: READY")
    monkeypatch.setattr(ocr_team_app, "discover_tesseract", lambda: ready)
    page = ocr_team_app._upload_surface()
    assert "window.addEventListener(type,pageGuard,{capture:true,passive:false})" in page
    assert "addFiles(e.dataTransfer.files)" in page
