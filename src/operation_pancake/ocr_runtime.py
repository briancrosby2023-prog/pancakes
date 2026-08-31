"""Tesseract OCR runtime discovery for Team Setup."""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OCRRuntime:
    ready: bool
    executable: str | None
    version: str | None
    source: str
    message: str


def _windows_candidates(env: dict[str, str]) -> list[Path]:
    roots = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        value = env.get(key)
        if value:
            roots.append(Path(value))
    candidates = []
    for root in roots:
        candidates.extend((
            root / "Tesseract-OCR" / "tesseract.exe",
            root / "Programs" / "Tesseract-OCR" / "tesseract.exe",
        ))
    return candidates


def discover_tesseract(*, platform: str | None = None, env: dict[str, str] | None = None) -> OCRRuntime:
    """Find Tesseract and prove that the discovered executable can run."""
    env = dict(os.environ if env is None else env)
    platform = os.name if platform is None else platform
    configured = env.get("PANCAKE_TESSERACT") or env.get("TESSERACT_CMD")
    probes: list[tuple[str, str]] = []
    if configured:
        probes.append((configured, "environment"))
    on_path = shutil.which("tesseract", path=env.get("PATH"))
    if on_path:
        probes.append((on_path, "PATH"))
    if platform == "nt":
        probes.extend((str(path), "Windows common install location") for path in _windows_candidates(env) if path.is_file())

    seen = set()
    for executable, source in probes:
        normalized = str(Path(executable).expanduser())
        if normalized.casefold() in seen:
            continue
        seen.add(normalized.casefold())
        try:
            result = subprocess.run(
                [normalized, "--version"], capture_output=True, text=True, timeout=10, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            first = (result.stdout or result.stderr).splitlines()
            version = first[0].strip() if first else "version available"
            return OCRRuntime(True, normalized, version, source, f"OCR ENGINE: READY — {version} — {normalized}")

    return OCRRuntime(
        False,
        None,
        None,
        "not found",
        "OCR ENGINE: NOT INSTALLED — Tesseract is required. Install Tesseract OCR for Windows, then restart Pancake. Pancake checks PANCAKE_TESSERACT/TESSERACT_CMD, PATH, Program Files, Program Files (x86), and LocalAppData.",
    )


def diagnostic_line() -> int:
    runtime = discover_tesseract()
    print(f"READY={runtime.ready}")
    print(f"SOURCE={runtime.source}")
    print(f"EXECUTABLE={runtime.executable or 'NOT FOUND'}")
    print(f"VERSION={runtime.version or 'UNAVAILABLE'}")
    print(runtime.message)
    return 0 if runtime.ready else 1
