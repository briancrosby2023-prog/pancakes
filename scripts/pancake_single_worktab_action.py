from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ACTION = "complete_simple_single_worktab_acceptance"
EXPECTED_AUTHORITY_REVISION = 40
APP = Path(r"C:\Users\Trash Panda\AppData\Local\SimpleEvaluator")
HELPER_DIR = APP / "browser-helper"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
DEBUG_PORT = 9255
EXTENSION_ID = "fgocmjlihbapenekkflcofdjmdodmboe"
EXTENSIONS_LINK_READY_TIMEOUT_SECONDS = 12
EXTENSIONS_LINK_POLL_MS = 250
EXPECTED_HELPER_VERSION = "1.4.14"
EXPECTED_WATCH_SHA256 = "12f0ec58e3784c4a03fa65846ff6ae9df5a0850b88d39686f1eecc9044bfb3c6"
EXPECTED_MANIFEST_SHA256 = "5a92d6cf6e8b78bcc81b17fc94deeba5156f83b97a486a5f72b53563e4db83c2"
EXPECTED_BACKGROUND_SHA256 = "d275b00ddb0d6dd56050145fd527da75538a582f41678c4b2f004d2f78799b0c"
EXPECTED_PREFLIGHT_SHA256 = "6a4c835a95b812f81503a4a36302bed39adf43f38871473f3cda77311dbef59f"
EXPECTED_SERVER_PREPATCH_SHA256 = "bd2be6072354a91a37acc43a16783488abb700ac2784c10641cd4fb1b864dc37"
EXPECTED_SERVER_SHA256 = "bc0582bfc95845d748cec60b21e39181f247b125675070ca87b76fd3c4acf69e"
EXPECTED_UI_SHA256 = "8dc0a0eb54a33ec2e0ee8df243ecbb9b0f7f4e8f764008cb68d843ebe8e2a355"
PENDING_RELEASE_SHA256 = "86c9c3574be1f73d47fb2a21e897d890ee351872bc8d0564a894a091013ccc5e"
PREPATCH_WATCH_SHA256 = "1faebe0b39ecf35879d35d16ce2a0aedb04cf15dc882350e55b39a2fea286912"
PREPATCH_MANIFEST_SHA256 = "51beb29b86febf22cfcbcf50e06a10b3525dbbcbe7e7c537ec6ed8cd8d2d9b97"
PREPATCH_BACKGROUND_SHA256 = "a3ce6c9884a514331bb614c5bbf8ff8b68ea2e56cfdde36a6bdeb616c5c6444e"
PREPATCH_RELEASE_SHA256 = "60549a6729a3205055992c982fb3b180a96ab5a34fec82a26ff57afb914b45d8"
NORMAL_SEARCH_URL = "https://cfb.fan/27/players/#simple-evaluator-worktab"
RUNTIME_POSTIMAGE_REL = Path("runtime") / "simple_evaluator"
BASE_USER_WATCH_HASH = "00eed84885792a43314e78d17a18f228ae8554d35d11fa8c5d84d2154a334105"
BASE_STATE_OBS_HASH = "8af2f5ef3195f5499ef3b9e80038d1e71a7fa2de06eba5ca41767b8a90786733"
BASE_FEED_OBS_HASH = "071ef8007045310d41267b033773b49d33f3c0787a327c6e3a74ad729c9a34d0"
BASE_ALERTS_HASH = "f53c678abb7ff40e4dc9d1ad55db4da27cd0d67766e9a6c1e51092d5794d2ac1"
BASE_RUNTIME_HASH = "fc8fbead3120f4620cac3aebe2b9b5990d7f39e61e97628c28f85bb678d03638"
STALE_TEST_TAB_TITLES = {
    "Kingston Lopa Stars of the Week 90 OVR - College Football 27 - CFB.FAN",
    "New tab",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def json_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def http_json(url: str, *, timeout: float = 3.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run_ps_json(script: str, control) -> Any:
    cp = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if cp.returncode != 0:
        raise control.ControlError("Windows UI Automation failed: " + cp.stdout[-6000:])
    payload = cp.stdout.strip()
    if not payload:
        raise control.ControlError("Windows UI Automation returned no JSON")
    try:
        return json.loads(payload)
    except Exception as exc:
        raise control.ControlError("Windows UI Automation returned invalid JSON: " + payload[-3000:]) from exc


def load_launch_module():
    app_path = str(APP)
    inserted = app_path not in sys.path
    if inserted:
        sys.path.insert(0, app_path)
    try:
        spec = importlib.util.spec_from_file_location("simple_evaluator_launch_acceptance", APP / "launch.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted:
            try:
                sys.path.remove(app_path)
            except ValueError:
                pass


def protected_snapshot() -> dict[str, Any]:
    state = read_json(APP / "app-state.json")
    feed = read_json(APP / "market-feed.json")
    alerts = read_json(APP / "alerts.json")
    runtime = read_json(APP / "watch-runtime.json")
    heartbeat = read_json(APP / "browser-helper-heartbeat.json")
    watches = state.get("watches") if isinstance(state.get("watches"), list) else []
    users = [w for w in watches if not (isinstance(w, dict) and w.get("purpose") == "value_probe")]
    probes = [w for w in watches if isinstance(w, dict) and w.get("purpose") == "value_probe"]
    observations = state.get("observations") if isinstance(state.get("observations"), list) else []
    feed_observations = feed.get("observations") if isinstance(feed.get("observations"), list) else []
    return {
        "user_watch_count": len(users),
        "user_watches_hash": json_hash(users),
        "probe_watch_count": len(probes),
        "state_observation_count": len(observations),
        "state_observations_hash": json_hash(observations),
        "feed_observation_count": len(feed_observations),
        "feed_observations_hash": json_hash(feed_observations),
        "alerts_hash": json_hash(alerts),
        "watch_runtime_hash": json_hash(runtime),
        "value_probe_status": state.get("value_probe_status"),
        "value_probe_rate_limit": state.get("value_probe_rate_limit"),
        "heartbeat": heartbeat,
    }


def verify_protected(snapshot: Mapping[str, Any], control, *, allow_new_observations: bool = False) -> None:
    exact = {
        "user_watch_count": 2,
        "user_watches_hash": BASE_USER_WATCH_HASH,
        "alerts_hash": BASE_ALERTS_HASH,
        "watch_runtime_hash": BASE_RUNTIME_HASH,
    }
    for key, value in exact.items():
        if snapshot.get(key) != value:
            raise control.EvidenceGap(f"protected state drift: {key}={snapshot.get(key)!r}")
    if allow_new_observations:
        if int(snapshot.get("state_observation_count", -1)) < 130:
            raise control.EvidenceGap("state observations regressed")
        if int(snapshot.get("feed_observation_count", -1)) < 100:
            raise control.EvidenceGap("feed observations regressed")
    else:
        expected = {
            "state_observation_count": 130,
            "state_observations_hash": BASE_STATE_OBS_HASH,
            "feed_observation_count": 100,
            "feed_observations_hash": BASE_FEED_OBS_HASH,
        }
        for key, value in expected.items():
            if snapshot.get(key) != value:
                raise control.EvidenceGap(f"protected observation baseline drift: {key}={snapshot.get(key)!r}")
    vp = snapshot.get("value_probe_status") or {}
    rl = snapshot.get("value_probe_rate_limit") or {}
    if vp.get("status") != "RATE_LIMITED" or vp.get("persistent_lock") is not True or rl.get("active") is not True:
        raise control.EvidenceGap("persistent RATE_LIMITED value-probe lock drift")


def verify_installed_files(control, *, prepatch: bool = False) -> dict[str, str]:
    expected = {
        "server.py": EXPECTED_SERVER_PREPATCH_SHA256 if prepatch else EXPECTED_SERVER_SHA256,
        "Simple-Evaluator.html": EXPECTED_UI_SHA256,
        "browser-helper/background.js": PREPATCH_BACKGROUND_SHA256 if prepatch else EXPECTED_BACKGROUND_SHA256,
        "browser-helper/watch.js": PREPATCH_WATCH_SHA256 if prepatch else EXPECTED_WATCH_SHA256,
        "browser-helper/preflight.js": EXPECTED_PREFLIGHT_SHA256,
        "browser-helper/manifest.json": PREPATCH_MANIFEST_SHA256 if prepatch else EXPECTED_MANIFEST_SHA256,
        "RELEASE.json": PREPATCH_RELEASE_SHA256 if prepatch else PENDING_RELEASE_SHA256,
    }
    actual: dict[str, str] = {}
    for rel, digest in expected.items():
        path = APP / rel
        if not path.is_file():
            raise control.EvidenceGap(f"installed single-worktab file is missing: {rel}")
        actual[rel] = sha256(path)
        if actual[rel] != digest:
            raise control.EvidenceGap(f"installed single-worktab file hash drift: {rel}={actual[rel]}")
    manifest = read_json(APP / "browser-helper/manifest.json")
    release = read_json(APP / "RELEASE.json")
    expected_version = "1.4.13" if prepatch else EXPECTED_HELPER_VERSION
    if manifest.get("version") != expected_version:
        raise control.EvidenceGap(f"installed helper manifest is not {expected_version}")
    if release.get("browser_helper_version") != expected_version:
        raise control.EvidenceGap(f"installed release does not expect helper {expected_version}")
    if release.get("status") != "FROZEN_PENDING_PHYSICAL_ACCEPTANCE":
        raise control.EvidenceGap("installed release is not pending physical acceptance")
    return actual


def write_server_bytes_in_place(path: Path, data: bytes, control) -> str:
    try:
        with path.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise control.ControlError(f"server.py in-place write failed: {exc}") from exc
    return sha256(path)


def write_helper_bytes_in_place(path: Path, data: bytes, control) -> str:
    try:
        with path.open("r+b") as handle:
            handle.seek(0)
            handle.write(data)
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise control.ControlError(f"helper in-place write failed for {path.name}: {exc}") from exc
    return sha256(path)


def write_runtime_bytes(path: Path, data: bytes, control) -> str:
    if path.name == "server.py":
        return write_server_bytes_in_place(path, data, control)
    if path.parent == HELPER_DIR:
        return write_helper_bytes_in_place(path, data, control)
    temp = path.with_name(path.name + ".r38.tmp")
    try:
        with temp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except OSError as exc:
        raise control.ControlError(f"runtime postimage write failed for {path.name}: {exc}") from exc
    finally:
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass
    return sha256(path)


def repository_runtime_postimage_bytes(repo: Path, rel: str, control) -> bytes:
    git_path = (RUNTIME_POSTIMAGE_REL / rel).as_posix()
    cp = subprocess.run(
        ["git", "-C", str(repo), "show", f"HEAD:{git_path}"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if cp.returncode != 0:
        detail = cp.stderr.decode("utf-8", "replace").strip()
        raise control.EvidenceGap(f"repository runtime Git blob unavailable: {rel}: {detail}")
    return bytes(cp.stdout)


def patch_installed_runtime(repo: Path, control) -> dict[str, Any]:
    expected_pre = {
        "server.py": EXPECTED_SERVER_PREPATCH_SHA256,
        "RELEASE.json": PREPATCH_RELEASE_SHA256,
        "browser-helper/background.js": PREPATCH_BACKGROUND_SHA256,
        "browser-helper/watch.js": PREPATCH_WATCH_SHA256,
        "browser-helper/manifest.json": PREPATCH_MANIFEST_SHA256,
    }
    expected_post = {
        "server.py": EXPECTED_SERVER_SHA256,
        "RELEASE.json": PENDING_RELEASE_SHA256,
        "browser-helper/background.js": EXPECTED_BACKGROUND_SHA256,
        "browser-helper/watch.js": EXPECTED_WATCH_SHA256,
        "browser-helper/manifest.json": EXPECTED_MANIFEST_SHA256,
    }
    changed = {}
    for rel, post_hash in expected_post.items():
        postimage = repository_runtime_postimage_bytes(repo, rel, control)
        target = APP / rel
        if hashlib.sha256(postimage).hexdigest() != post_hash:
            raise control.EvidenceGap(f"repository runtime Git blob drift: {rel}")
        before = sha256(target)
        if before == post_hash:
            changed[rel] = {"changed": False, "before_sha256": before, "after_sha256": before}
            continue
        if before != expected_pre[rel]:
            raise control.EvidenceGap(f"installed runtime preimage drift: {rel}={before}")
        after = write_runtime_bytes(target, postimage, control)
        if after != post_hash:
            raise control.ControlError(f"installed runtime postimage hash mismatch: {rel}={after}")
        changed[rel] = {"changed": True, "before_sha256": before, "after_sha256": after}
    return changed


def reload_helper_extension(edge_pid: int, control) -> dict[str, Any]:
    # Edge 153 no longer exposes Reload on the extension details surface.
    # The extensions root exposes one explicit Reload button inside the exact
    # Simple Evaluator unpacked-extension card. Use that control; do not toggle
    # enable state, restart the browser, or rely on proximity.
    navigate_selected_url(edge_pid, "edge://extensions/", control)
    ps = rf"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$p=Get-Process -Id {edge_pid} -ErrorAction Stop
$root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$buttons=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,
  [System.Windows.Automation.PropertyCondition]::new(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Button))
$matches=@()
foreach($button in $buttons){{
  if($button.Current.Name -ne "Reload" -or -not $button.Current.IsEnabled){{ continue }}
  $node=$button
  $card=$null
  for($i=0;$i -lt 6;$i++){{
    try{{$node=[System.Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($node)}}catch{{$node=$null}}
    if($null -eq $node){{ break }}
    if($node.Current.ControlType -eq [System.Windows.Automation.ControlType]::ListItem){{
      $label=[string]$node.Current.Name
      if($label.Contains("Simple Evaluator Browser Watch") -and $label.Contains("{EXTENSION_ID}")){{
        $card=$node
        break
      }}
    }}
  }}
  if($null -ne $card){{ $matches += [pscustomobject]@{{Button=$button;Card=$card}} }}
}}
if($matches.Count -ne 1){{ throw ("Expected exactly one exact-card Reload control; observed "+$matches.Count) }}
$target=$matches[0].Button
$beforeOffscreen=[bool]$target.Current.IsOffscreen
try{{
  $scroll=$target.GetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern)
  $scroll.ScrollIntoView()
  Start-Sleep -Milliseconds 300
}}catch{{
  throw ("Exact Reload control does not support ScrollItemPattern: "+$_.Exception.Message)
}}
$afterOffscreen=[bool]$target.Current.IsOffscreen
$invoke=$target.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
$invoke.Invoke()
Start-Sleep -Seconds 2
[pscustomobject]@{{
  ReloadCount=$matches.Count
  ExtensionId="{EXTENSION_ID}"
  CardName=[string]$matches[0].Card.Current.Name
  BeforeOffscreen=$beforeOffscreen
  AfterOffscreen=$afterOffscreen
  Invoked=$true
}} | ConvertTo-Json -Compress
"""
    result = run_ps_json(ps, control)
    if result.get("ReloadCount") != 1 or result.get("Invoked") is not True:
        raise control.ControlError(f"Browser Helper explicit Reload failed: {result!r}")
    if result.get("ExtensionId") != EXTENSION_ID:
        raise control.ControlError(f"Browser Helper explicit Reload identity drift: {result!r}")
    return result


def verify_installed_stop_conditions(control, *, prepatch: bool = False) -> dict[str, Any]:
    watch = (HELPER_DIR / "watch.js").read_text(encoding="utf-8")
    background = (HELPER_DIR / "background.js").read_text(encoding="utf-8")
    required_watch = [
        "const MIN_INTERVAL_SECONDS = 120;",
        "const MIN_PAGE_DWELL_MS = 5000;",
        "user-action-required",
        "access-denied",
        "rate-limited",
        "market-source-error",
        "parse-error",
        "market-timeout",
        "simple-evaluator:browser-work-stop",
        "simple-evaluator:value-probe-rate-limited",
    ]
    required_background = [
        "const MIN_INTERVAL_SECONDS = 120;",
        "simple-evaluator:browser-work-stop",
        "await clearTabSchedule(tabId);",
        "chrome.tabs.update(tabId, {url: workTabUrl",
    ]
    if not prepatch:
        required_watch.extend([
            "normal-search-submitted",
            "normal-search-result-selected",
            "#f_name",
        ])
        required_background.extend([
            "const NORMAL_SEARCH_URL = 'https://cfb.fan/27/players/#simple-evaluator-worktab';",
            "currentBrowserWork",
        ])
    missing = [token for token in required_watch if token not in watch]
    if missing:
        stage = "prepatch" if prepatch else "postpatch"
        raise control.EvidenceGap(f"installed {stage} stop-condition logic drift: " + ", ".join(missing))
    missing_bg = [token for token in required_background if token not in background]
    if missing_bg:
        stage = "prepatch" if prepatch else "postpatch"
        raise control.EvidenceGap(f"installed {stage} scheduler/stop logic drift: " + ", ".join(missing_bg))
    return {
        "stage": "prepatch" if prepatch else "postpatch",
        "watch_stop_tokens": required_watch,
        "background_scheduler_tokens": required_background,
        "watch_sha256": sha256(HELPER_DIR / "watch.js"),
        "background_sha256": sha256(HELPER_DIR / "background.js"),
    }


def evaluator_acceptance(control) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("simple_evaluator_evaluator_acceptance", APP / "evaluator.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    data = read_json(APP / "cards.json")
    cards = data.get("cards") if isinstance(data, dict) else None
    models = data.get("simple_models") if isinstance(data, dict) else None
    if not isinstance(cards, list) or not isinstance(models, dict) or len(cards) != 9206:
        raise control.EvidenceGap("evaluator catalog/model baseline drift")
    if len({str(card.get("id") or "") for card in cards if isinstance(card, dict)}) != len(cards):
        raise control.EvidenceGap("duplicate exact-card identity in evaluator catalog")
    results: dict[str, list[str]] = {}
    for position, model in sorted(models.items()):
        first = module.rank_position(cards, position, model, limit=5)
        second = module.rank_position(cards, position, model, limit=5)
        first_ids = [str(row.get("id") or "") for row in first]
        if first_ids != [str(row.get("id") or "") for row in second]:
            raise control.ControlError(f"nondeterministic evaluator results for {position}")
        if any(str(row.get("program") or "").strip().casefold() == "platinum rare" for row in first):
            raise control.ControlError(f"Platinum Rare leaked into evaluator results for {position}")
        results[position] = first_ids
    required_positions = {
        "QB","HB","FB","WR","TE","LT","LG","C","RG","RT",
        "EDGE","DT","MLB","OLB","CB","FS","SS","K","P",
    }
    if set(results) != required_positions:
        raise control.EvidenceGap(f"supported evaluator positions drift: {sorted(results)}")
    targets = [
        ("Jordan Allen", 91, "FS"),
        ("Ashlynd Barker", 91, "FS"),
        ("Kingston Lopa", 90, "FS"),
        ("Earl Little Jr.", 90, "FS"),
        ("Xavier Filsaime", 90, "FS"),
    ]
    target_rows = []
    for name, ovr, position in targets:
        matches = [
            card for card in cards
            if isinstance(card, dict)
            and str(card.get("name") or "") == name
            and int(card.get("ovr") or -1) == ovr
            and str(card.get("position") or "") == position
        ]
        target_rows.append({"name": name, "ovr": ovr, "position": position, "installed_matches": len(matches)})
    # The current mission explicitly records these newer FS versions as not yet
    # imported. Acceptance must expose that gap rather than silently treating
    # older same-name cards as identity matches.
    if any(row["installed_matches"] for row in target_rows):
        raise control.EvidenceGap("required-FS installed identity baseline changed; authority must be reconciled before acceptance")
    return {
        "catalog_card_count": len(cards),
        "position_count": len(results),
        "top5_ids_by_position": results,
        "fs_top5_ids": results["FS"],
        "platinum_rare_excluded": True,
        "required_fs_installed_identity_checks": target_rows,
        "required_fs_status": "CURRENT_BROWSER_IDENTITIES_OBSERVED_PREVIOUSLY_BUT_NOT_YET_IMPORTED",
    }


def write_full_acceptance(
    *,
    helper: Mapping[str, Any],
    first_obs: Mapping[str, Any],
    cadence_obs: Mapping[str, Any],
    cadence_delta: float,
    tab_cleanup: Mapping[str, Any],
    stop_checks: Mapping[str, Any],
    evaluator_checks: Mapping[str, Any],
    protected_after: Mapping[str, Any],
    restart_port: int,
) -> str:
    path = APP / "PRODUCTION_WORKSTATION_ACCEPTANCE_3T.json"
    result = {
        "schema": "simple-evaluator-production-acceptance-v1",
        "checkpoint": "3T",
        "release_version": "1.2.0",
        "release_status_before_acceptance": "FROZEN_PENDING_PHYSICAL_ACCEPTANCE",
        "status": "PASS",
        "full_single_worktab_acceptance": True,
        "accepted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "browser_family": helper.get("browser_family"),
        "browser_helper_version": EXPECTED_HELPER_VERSION,
        "card_id": str(first_obs.get("card_id") or ""),
        "interval_seconds_required": 120,
        "observed_delta_seconds": round(cadence_delta, 3),
        "first_observation": dict(first_obs),
        "second_cadence_observation": dict(cadence_obs),
        "one_worktab_proof": dict(tab_cleanup),
        "stop_condition_proof": dict(stop_checks),
        "evaluator_checks": dict(evaluator_checks),
        "protected_state_after": dict(protected_after),
        "restart_port": int(restart_port),
    }
    temp = path.with_suffix(".json.r24.tmp")
    temp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temp, path)
    return sha256(path)


def controlled_edge_rows(control) -> list[dict[str, Any]]:
    ps = rf'''
$p=@(Get-CimInstance Win32_Process | Where-Object {{ $_.Name -eq 'msedge.exe' -and $_.CommandLine -notmatch '--type=' -and $_.CommandLine -like '*--load-extension=*SimpleEvaluator*browser-helper*' }} | ForEach-Object {{
  $gp=Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
  if($gp -and $gp.MainWindowHandle -ne 0){{ [pscustomobject]@{{ProcessId=$_.ProcessId;CommandLine=$_.CommandLine;MainWindowHandle=[long]$gp.MainWindowHandle;MainWindowTitle=$gp.MainWindowTitle}} }}
}})
[pscustomobject]@{{Rows=@($p)}} | ConvertTo-Json -Depth 5
'''
    payload = run_ps_json(ps, control)
    rows = payload.get("Rows") or []
    if isinstance(rows, dict):
        rows = [rows]
    return [dict(row) for row in rows if isinstance(row, dict)]


def find_controlled_edge(control, *, allow_absent: bool = False) -> dict[str, Any] | None:
    rows = controlled_edge_rows(control)
    exact = [
        row for row in rows
        if str(HELPER_DIR).lower() in str(row.get("CommandLine") or "").lower()
    ]
    if not exact and allow_absent:
        return None
    if len(exact) != 1:
        raise control.EvidenceGap(f"expected one controlled Edge helper window; observed {len(exact)}")
    return exact[0]


def launch_controlled_edge(queue: Mapping[str, Any], control) -> dict[str, Any]:
    source_url = str(queue.get("source_url") or "")
    if (
        queue.get("active") is not True
        or not source_url.startswith("https://cfb.fan/")
        or "#simple-evaluator-worktab" not in source_url
    ):
        raise control.EvidenceGap("shared CFB.FAN work URL is unavailable for controlled Edge recovery")
    if not EDGE.is_file():
        raise control.EvidenceGap("Microsoft Edge executable is unavailable")
    if find_controlled_edge(control, allow_absent=True) is not None:
        raise control.EvidenceGap("controlled Edge appeared before bounded recovery launch")
    cmd = [
        str(EDGE),
        f"--remote-debugging-port={DEBUG_PORT}",
        "--remote-allow-origins=*",
        f"--load-extension={HELPER_DIR}",
        "--no-first-run",
        "--new-window",
        source_url,
    ]
    subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 15
    last = None
    while time.time() < deadline:
        last = find_controlled_edge(control, allow_absent=True)
        if last is not None:
            cmdline = str(last.get("CommandLine") or "")
            title = str(last.get("MainWindowTitle") or "")
            if (
                f"--remote-debugging-port={DEBUG_PORT}" in cmdline
                and str(HELPER_DIR).lower() in cmdline.lower()
                and title
            ):
                last["LaunchedByAction"] = True
                return last
        time.sleep(0.25)
    raise control.ControlError(f"controlled Edge helper window did not appear after bounded launch: {last!r}")


def navigate_selected_url(edge_pid: int, url: str, control) -> dict[str, Any]:
    safe = str(url).replace("'", "''")
    ps = rf'''
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
$p=Get-Process -Id {edge_pid} -ErrorAction Stop
Add-Type -Namespace OperationPancake -Name Win32Focus -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
'@
$hWnd=[System.IntPtr]$p.MainWindowHandle
if($hWnd -eq [System.IntPtr]::Zero){{ throw "Target Edge window has no main window handle" }}
$SW_RESTORE=9
$null=[OperationPancake.Win32Focus]::ShowWindow($hWnd,$SW_RESTORE)
$root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$cond=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty,"view_1021")
$addr=$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$cond)
if($null -eq $addr){{ throw "Edge address bar not found" }}
$focusDeadline=(Get-Date).AddSeconds(3)
$focused=$false
do{{
  $addr.SetFocus()
  Start-Sleep -Milliseconds 100
  $focused=($addr.Current.HasKeyboardFocus -and ([OperationPancake.Win32Focus]::GetForegroundWindow() -eq $hWnd))
}}while((-not $focused) -and (Get-Date) -lt $focusDeadline)
if(-not $focused){{ throw "Target Edge address bar did not acquire foreground keyboard focus" }}
$vp=$addr.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
$vp.SetValue('{safe}')
[System.Windows.Forms.SendKeys]::SendWait("{{ENTER}}")
Start-Sleep -Seconds 2
$root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$addr=$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$cond)
$actual=""
if($addr){{ try{{ $actual=($addr.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)).Current.Value }}catch{{}} }}
[pscustomobject]@{{Title=$p.MainWindowTitle;Url=$actual}} | ConvertTo-Json -Depth 4
'''
    return dict(run_ps_json(ps, control))


def uia_snapshot(edge_pid: int, control) -> dict[str, Any]:
    ps = rf'''
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$p=Get-Process -Id {edge_pid} -ErrorAction Stop
$root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$addrCond=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty,"view_1021")
$addr=$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$addrCond)
$url=""
if($addr){{ try{{ $url=($addr.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)).Current.Value }}catch{{}} }}
$tabCond=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::TabItem)
$tabs=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$tabCond)
$tabRows=@()
foreach($t in $tabs){{
  $selected=$false
  try{{ $selected=($t.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)).Current.IsSelected }}catch{{}}
  $tabRows += [pscustomobject]@{{Name=[string]$t.Current.Name;Selected=$selected}}
}}
[pscustomobject]@{{Title=$p.MainWindowTitle;Url=$url;Tabs=$tabRows}} | ConvertTo-Json -Depth 5
'''
    return run_ps_json(ps, control)


def open_extensions_root_and_snapshot(edge_pid: int, control) -> dict[str, Any]:
    ps = rf"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$p=Get-Process -Id {edge_pid} -ErrorAction Stop
$deadline=(Get-Date).AddSeconds({EXTENSIONS_LINK_READY_TIMEOUT_SECONDS})
$links=@()
do{{
  $root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
  $all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
  $links=@()
  foreach($e in $all){{
    if(
      $e.Current.ControlType -eq [System.Windows.Automation.ControlType]::Hyperlink -and
      [string]$e.Current.Name -eq "Installed extensions" -and
      $e.Current.IsEnabled
    ){{
      try{{ $null=$e.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern); $links += $e }}catch{{}}
    }}
  }}
  if($links.Count -gt 1){{ throw ("Expected at most one enabled Installed extensions hyperlink during readiness wait; observed "+$links.Count) }}
  if($links.Count -eq 1){{ break }}
  Start-Sleep -Milliseconds {EXTENSIONS_LINK_POLL_MS}
}}while((Get-Date) -lt $deadline)
if($links.Count -ne 1){{ throw ("Expected exactly one enabled Installed extensions hyperlink before readiness deadline; observed "+$links.Count) }}
($links[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)).Invoke()
Start-Sleep -Seconds 2
$root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
$labels=@()
$toggles=@()
foreach($e in $all){{
  $name=[string]$e.Current.Name
  $r=$e.Current.BoundingRectangle
  if($name -match '^(?i:Developer mode)$'){{
    $labels += [pscustomobject]@{{Name=$name;AutomationId=[string]$e.Current.AutomationId;X=[double]$r.X;Y=[double]$r.Y;W=[double]$r.Width;H=[double]$r.Height}}
  }}
  try{{
    $tp=$e.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
    $toggles += [pscustomobject]@{{Name=$name;AutomationId=[string]$e.Current.AutomationId;Enabled=$e.Current.IsEnabled;State=$tp.Current.ToggleState.ToString();X=[double]$r.X;Y=[double]$r.Y;W=[double]$r.Width;H=[double]$r.Height}}
  }}catch{{}}
}}
[pscustomobject]@{{Title=$p.MainWindowTitle;Labels=$labels;Toggles=$toggles}} | ConvertTo-Json -Depth 6
"""
    return run_ps_json(ps, control)

def select_developer_toggle(snapshot: Mapping[str, Any], control) -> dict[str, Any]:
    labels = snapshot.get("Labels") or []
    toggles = snapshot.get("Toggles") or []
    if isinstance(labels, dict):
        labels = [labels]
    if isinstance(toggles, dict):
        toggles = [toggles]

    exact = []
    for toggle in toggles:
        if toggle.get("Enabled") is not True or str(toggle.get("State")) not in {"Off", "On"}:
            continue
        if str(toggle.get("Name") or "").strip().casefold() != "developer mode":
            continue
        if str(toggle.get("AutomationId") or "") != "dev-switch":
            continue
        x = float(toggle.get("X") or 0.0)
        y = float(toggle.get("Y") or 0.0)
        w = float(toggle.get("W") or 0.0)
        h = float(toggle.get("H") or 0.0)
        if w <= 0 or h <= 0:
            continue
        chosen = dict(toggle)
        chosen["Selection"] = "ExactDeveloperModeDevSwitch"
        chosen["Distance"] = 0.0
        exact.append(chosen)
    if len(exact) > 1:
        raise control.EvidenceGap(
            f"Developer mode exact dev-switch remains ambiguous: observed {len(exact)}"
        )
    if len(exact) == 1:
        return exact[0]

    if len(labels) != 1:
        raise control.EvidenceGap(f"expected one Developer mode label; observed {len(labels)}")
    label = labels[0]
    lx = float(label.get("X") or 0.0)
    ly = float(label.get("Y") or 0.0)
    lw = float(label.get("W") or 0.0)
    lh = float(label.get("H") or 0.0)
    if lw <= 0 or lh <= 0:
        raise control.EvidenceGap("Developer mode label has no usable bounding rectangle")
    lcx = lx + lw / 2.0
    lcy = ly + lh / 2.0
    candidates = []
    for toggle in toggles:
        if toggle.get("Enabled") is not True or str(toggle.get("State")) not in {"Off", "On"}:
            continue
        x = float(toggle.get("X") or 0.0)
        y = float(toggle.get("Y") or 0.0)
        w = float(toggle.get("W") or 0.0)
        h = float(toggle.get("H") or 0.0)
        if w <= 0 or h <= 0:
            continue
        cx = x + w / 2.0
        cy = y + h / 2.0
        dy = abs(cy - lcy)
        dx = cx - lcx
        if dx < -20 or dx > 500 or dy > max(35.0, lh * 1.75):
            continue
        distance = math.hypot(max(0.0, dx), dy)
        candidates.append((distance, toggle))
    candidates.sort(key=lambda item: item[0])
    if not candidates:
        raise control.EvidenceGap("no enabled TogglePattern control is spatially associated with Developer mode")
    if len(candidates) > 1 and candidates[1][0] - candidates[0][0] < 40.0:
        raise control.EvidenceGap(
            "Developer mode toggle remains ambiguous: nearest distances "
            + ", ".join(f"{item[0]:.1f}" for item in candidates[:3])
        )
    chosen = dict(candidates[0][1])
    chosen["Selection"] = "SpatialFallback"
    chosen["Distance"] = round(candidates[0][0], 3)
    return chosen


def toggle_exact(edge_pid: int, chosen: Mapping[str, Any], control) -> dict[str, Any]:
    payload = json.dumps(dict(chosen), separators=(",", ":")).replace("'", "''")
    ps = rf'''
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$chosen=ConvertFrom-Json '{payload}'
$p=Get-Process -Id {edge_pid} -ErrorAction Stop
$root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
$matches=@()
foreach($e in $all){{
  try{{ $tp=$e.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern) }}catch{{ continue }}
  if(-not $e.Current.IsEnabled){{ continue }}
  $r=$e.Current.BoundingRectangle
  $aid=[string]$e.Current.AutomationId
  $name=[string]$e.Current.Name
  $sameId=([string]$chosen.AutomationId -ne "" -and $aid -eq [string]$chosen.AutomationId)
  $sameRect=([math]::Abs([double]$r.X-[double]$chosen.X) -le 2 -and [math]::Abs([double]$r.Y-[double]$chosen.Y) -le 2 -and [math]::Abs([double]$r.Width-[double]$chosen.W) -le 2 -and [math]::Abs([double]$r.Height-[double]$chosen.H) -le 2)
  if(($sameId -or $sameRect) -and $tp.Current.ToggleState.ToString() -eq [string]$chosen.State){{ $matches += $e }}
}}
if($matches.Count -ne 1){{ throw ("Exact Developer mode toggle revalidation failed; observed "+$matches.Count) }}
$tp=$matches[0].GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)
$before=$tp.Current.ToggleState.ToString()
$action="AlreadyOn"
if($tp.Current.ToggleState -eq [System.Windows.Automation.ToggleState]::Off){{ $tp.Toggle(); $action="ToggleOn" }}
Start-Sleep -Seconds 2
$after=($matches[0].GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern)).Current.ToggleState.ToString()
[pscustomobject]@{{Before=$before;After=$after;Action=$action;Name=[string]$matches[0].Current.Name;AutomationId=[string]$matches[0].Current.AutomationId}} | ConvertTo-Json -Depth 4
'''
    result = run_ps_json(ps, control)
    if str(result.get("After")) != "On":
        raise control.ControlError(f"Developer mode did not become On: {result!r}")
    return result


def wait_helper(port: int, control, *, seconds: float = 30.0) -> dict[str, Any]:
    deadline = time.time() + seconds
    last = None
    while time.time() < deadline:
        try:
            last = http_json(f"http://127.0.0.1:{port}/browser-helper-status.json", timeout=2)
            if (
                last.get("reported_version") == EXPECTED_HELPER_VERSION
                and last.get("expected_version") == EXPECTED_HELPER_VERSION
                and last.get("version_matches") is True
                and last.get("alive") is True
            ):
                return last
        except Exception:
            pass
        time.sleep(1)
    raise control.ControlError(f"Browser Helper 1.4.13 did not become live: {last!r}")


def choose_work_tab_and_reload(edge_pid: int, queue: Mapping[str, Any], control) -> dict[str, Any]:
    queue_name = str(queue.get("name") or "").replace("'", "''")
    queue_source = str(queue.get("source_url") or "")
    ps = rf'''
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$p=Get-Process -Id {edge_pid} -ErrorAction Stop
$root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$tabCond=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::TabItem)
$tabs=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$tabCond)
$rows=@()
foreach($t in $tabs){{ $rows += [pscustomobject]@{{Name=[string]$t.Current.Name;Element=$t}} }}
$preferred=@($rows | Where-Object {{ $_.Name -like '*{queue_name}*' -and $_.Name -like '*CFB.FAN*' }})
if($preferred.Count -ne 1){{
  $cfb=@($rows | Where-Object {{ $_.Name -like '*CFB.FAN*' }})
  if($cfb.Count -eq 1){{ $preferred=$cfb }} else {{ throw ("Expected one current CFB.FAN work tab; preferred="+$preferred.Count+" all="+$cfb.Count) }}
}}
$tab=$preferred[0].Element
($tab.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)).Select()
Start-Sleep -Milliseconds 500
$root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$addrCond=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty,"view_1021")
$addr=$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$addrCond)
$url=($addr.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)).Current.Value
$all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
$reload=@()
foreach($e in $all){{
  $name=[string]$e.Current.Name
  $aid=[string]$e.Current.AutomationId
  if(
    $e.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and
    $e.Current.IsEnabled -and
    -not $e.Current.IsOffscreen -and
    $aid -eq "view_1003" -and
    $name -match '^(Refresh|Reload|Reload this page)$'
  ){{
    try{{ $null=$e.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern); $reload += $e }}catch{{}}
  }}
}}
if($reload.Count -ne 1){{ throw ("Expected exactly one enabled visible Edge refresh/reload button view_1003; observed "+$reload.Count) }}
($reload[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)).Invoke()
$utc=[DateTime]::UtcNow.ToString("o")
[pscustomobject]@{{Title=[string]$preferred[0].Name;Url=$url;ReloadedAt=$utc;TabCount=$tabs.Count}} | ConvertTo-Json -Depth 4
'''
    result = run_ps_json(ps, control)
    normalized_source = queue_source.split("#", 1)[0].rstrip("/")
    normalized_actual = str(result.get("Url") or "").split("#", 1)[0].rstrip("/")
    if normalized_source and normalized_actual != normalized_source:
        raise control.EvidenceGap(
            f"selected CFB work tab URL is not the current queue source: {normalized_actual!r} != {normalized_source!r}"
        )
    return result


def parse_dt(value: str) -> datetime:
    value = str(value or "").replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def observations() -> list[dict[str, Any]]:
    state = read_json(APP / "app-state.json")
    rows = state.get("observations") if isinstance(state.get("observations"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def wait_observation(card_id: str, *, after: datetime, count_before: int, seconds: float, control) -> tuple[dict[str, Any], float]:
    deadline = time.time() + seconds
    while time.time() < deadline:
        rows = observations()
        if len(rows) > count_before:
            matches = [
                row for row in rows
                if str(row.get("card_id") or "") == card_id
                and row.get("collection_method") == "USER_STARTED_BROWSER_WATCH"
                and row.get("observed_at")
                and parse_dt(str(row["observed_at"])) >= after
            ]
            if matches:
                row = sorted(matches, key=lambda item: str(item.get("observed_at") or ""))[-1]
                elapsed = (parse_dt(str(row["observed_at"])) - after).total_seconds()
                return row, elapsed
        time.sleep(0.5)
    raise control.ControlError(f"no exact-card browser observation arrived for {card_id} within {seconds:.0f}s")


def current_selected_url(edge_pid: int, control) -> str:
    snap = uia_snapshot(edge_pid, control)
    return str(snap.get("Url") or "")


def wait_url_change(edge_pid: int, prior: str, *, seconds: float, control) -> tuple[str, datetime]:
    prior_base = prior.split("#", 1)[0].rstrip("/")
    deadline = time.time() + seconds
    while time.time() < deadline:
        current = current_selected_url(edge_pid, control)
        current_base = current.split("#", 1)[0].rstrip("/")
        if current_base.startswith("https://cfb.fan/") and current_base != prior_base:
            return current, datetime.now(timezone.utc)
        time.sleep(0.1)
    raise control.ControlError("shared work tab did not navigate to the next card")


def close_known_temporary_tabs(edge_pid: int, current_title: str, control) -> dict[str, Any]:
    allowed = list(STALE_TEST_TAB_TITLES) + ["Extensions"]
    allowed_json = json.dumps(allowed).replace("'", "''")
    ps = rf'''
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$allowed=ConvertFrom-Json '{allowed_json}'
$p=Get-Process -Id {edge_pid} -ErrorAction Stop
$root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$tabCond=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::TabItem)
$tabs=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$tabCond)
$closed=@()
foreach($t in @($tabs)){{
  $name=[string]$t.Current.Name
  if($name -eq "{current_title.replace('"', '""')}"){{ continue }}
  $shouldClose=($allowed -contains $name) -or ($name -like 'Extensions*')
  if(-not $shouldClose){{ continue }}
  $buttons=$t.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Button))
  $closers=@()
  foreach($b in $buttons){{ if([string]$b.Current.Name -match '(?i)close tab' -and $b.Current.IsEnabled){{ try{{ $null=$b.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern); $closers += $b }}catch{{}} }} }}
  if($closers.Count -eq 1){{ ($closers[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)).Invoke(); $closed += $name; Start-Sleep -Milliseconds 250 }}
}}
$root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$tabs=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$tabCond)
$names=@(); foreach($t in $tabs){{ $names += [string]$t.Current.Name }}
[pscustomobject]@{{Closed=$closed;Remaining=$names}} | ConvertTo-Json -Depth 5
'''
    return run_ps_json(ps, control)


def listener_pid(port: int) -> int | None:
    cp = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Get-NetTCPConnection -State Listen -LocalPort {int(port)} | Select-Object -First 1 OwningProcess | ConvertTo-Json -Compress"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if cp.returncode != 0 or not cp.stdout.strip():
        return None
    raw = json.loads(cp.stdout)
    return int(raw["OwningProcess"]) if raw and raw.get("OwningProcess") is not None else None


def process_exists(pid: int) -> bool:
    cp = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            f"if(Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue){{exit 0}}else{{exit 1}}",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return cp.returncode == 0


def stop_server(port: int, launch, control) -> int:
    pid = listener_pid(port)
    if not pid:
        raise control.EvidenceGap("Simple Evaluator listener PID is unavailable for stop")
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 10
    listener_gone = False
    while time.time() < deadline:
        if not listener_gone and launch.probe(port, timeout=0.2) is None:
            listener_gone = True
        if listener_gone and not process_exists(pid):
            return int(pid)
        time.sleep(0.05)
    if not listener_gone:
        raise control.ControlError("Simple Evaluator listener did not stop")
    raise control.ControlError("Simple Evaluator process did not fully exit")


def start_server(previous_pid: int | None, launch, control) -> tuple[int, int]:
    cp = subprocess.run(
        [sys.executable, str(APP / "launch.py"), "--browser", "none"],
        cwd=str(APP),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    )
    if cp.returncode != 0:
        raise control.ControlError("dynamic-port launcher failed: " + cp.stdout[-3000:])
    new_port = launch.find_running_server()
    if new_port is None:
        raise control.ControlError("dynamic-port launcher did not produce a capable server")
    new_pid = listener_pid(new_port)
    if not new_pid or (previous_pid is not None and new_pid == previous_pid):
        raise control.ControlError("Simple Evaluator start did not produce a new listener PID")
    return int(new_port), int(new_pid)


def restart_server(port: int, launch, control) -> tuple[int, int]:
    old_pid = stop_server(port, launch, control)
    return start_server(old_pid, launch, control)


def write_release_accepted(control) -> str:
    path = APP / "RELEASE.json"
    release = read_json(path)
    if release.get("browser_helper_version") != EXPECTED_HELPER_VERSION:
        raise control.EvidenceGap("release helper version drift before acceptance write")
    if release.get("status") not in {"FROZEN_PENDING_PHYSICAL_ACCEPTANCE", "PRODUCTION_ACCEPTED"}:
        raise control.EvidenceGap("unexpected release status before acceptance write")
    release["status"] = "PRODUCTION_ACCEPTED"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temp, path)
    return sha256(path)


def run(repo: Path, control) -> Mapping[str, Any]:
    if os.name != "nt":
        raise control.EvidenceGap("single-worktab physical acceptance is Windows-only")
    control.verify_repo(
        repo,
        expected_revision=EXPECTED_AUTHORITY_REVISION,
        expected_branch="product/c3po-clean-room-roster",
        require_clean=True,
    )

    installed_hashes_prepatch = verify_installed_files(control, prepatch=True)
    before = protected_snapshot()
    verify_protected(before, control, allow_new_observations=False)
    prepatch_stop_checks = verify_installed_stop_conditions(control, prepatch=True)
    evaluator_checks = evaluator_acceptance(control)

    launch = load_launch_module()
    port = launch.find_running_server()
    if port is None:
        raise control.EvidenceGap("Simple Evaluator server is not running")

    release_path = APP / "RELEASE.json"
    acceptance_path = APP / "PRODUCTION_WORKSTATION_ACCEPTANCE_3T.json"
    server_path = APP / "server.py"
    runtime_paths = [
        APP / "server.py",
        APP / "RELEASE.json",
        APP / "browser-helper" / "background.js",
        APP / "browser-helper" / "watch.js",
        APP / "browser-helper" / "manifest.json",
    ]
    runtime_backups = {str(path): path.read_bytes() for path in runtime_paths}
    release_backup = runtime_backups[str(release_path)]
    server_backup = runtime_backups[str(server_path)]
    acceptance_existed = acceptance_path.exists()
    acceptance_backup = acceptance_path.read_bytes() if acceptance_existed else None
    runtime_patch: dict[str, Any] | None = None
    edge_pid: int | None = None
    server_stopped_pid: int | None = None

    try:
        # Harden the installed acceptance boundary before activating 1.4.14:
        # stale 1.4.12 Chromium heartbeats can no longer clobber a compatible
        # 1.4.14 heartbeat, and the server can no longer self-certify a narrow PASS.
        # Windows can deny atomic replacement of server.py while the live
        # interpreter still owns the installed file. Stop the exact listener
        # first, apply the already hash-validated patch, then relaunch through
        # the accepted dynamic-port launcher.
        server_stopped_pid = stop_server(int(port), launch, control)
        runtime_patch = patch_installed_runtime(repo, control)
        port, _ = start_server(server_stopped_pid, launch, control)
        server_stopped_pid = None
        installed_hashes = verify_installed_files(control, prepatch=False)
        stop_checks = verify_installed_stop_conditions(control, prepatch=False)

        queue = http_json(f"http://127.0.0.1:{port}/browser-watch-next.json")
        if queue.get("schema") != "simple-evaluator-browser-work-queue-v1" or queue.get("active") is not True:
            raise control.EvidenceGap("single-worktab queue is not active")

        edge = find_controlled_edge(control, allow_absent=True)
        if edge is None:
            edge = launch_controlled_edge(queue, control)
        edge_pid = int(edge["ProcessId"])

        # Revision 19 proved that --load-extension alone is not sufficient.
        # Recovery launch creates only the controlled window; activation still
        # uses the materially distinct, previously successful Developer-mode path.
        details = navigate_selected_url(
            edge_pid,
            f"edge://extensions/?id={EXTENSION_ID}",
            control,
        )
        if "Extensions" not in str(details.get("Title") or ""):
            raise control.EvidenceGap("controlled Edge did not reach the extension-details surface")

        root = open_extensions_root_and_snapshot(edge_pid, control)
        chosen = select_developer_toggle(root, control)
        toggle = toggle_exact(edge_pid, chosen, control)
        details = navigate_selected_url(
            edge_pid,
            f"edge://extensions/?id={EXTENSION_ID}",
            control,
        )
        extension_reload = reload_helper_extension(edge_pid, control)

        activation_queue = http_json(f"http://127.0.0.1:{port}/browser-watch-next.json")
        activation_source = str(activation_queue.get("source_url") or "")
        if (
            activation_queue.get("active") is not True
            or not activation_source.startswith("https://cfb.fan/")
            or not activation_queue.get("card_id")
            or not activation_queue.get("name")
        ):
            raise control.EvidenceGap("exact-card work identity changed before normal-search activation")
        obs_before = observations()
        first_id = str(activation_queue.get("card_id") or "")
        first_started = datetime.now(timezone.utc)
        navigate_selected_url(edge_pid, NORMAL_SEARCH_URL, control)
        helper = wait_helper(int(port), control, seconds=30)
        first_obs, first_elapsed = wait_observation(
            first_id,
            after=first_started,
            count_before=len(obs_before),
            seconds=90,
            control=control,
        )
        if first_elapsed < 5.0:
            raise control.ControlError(
                f"first rendered-page observation violated 5-second dwell: {first_elapsed:.3f}s"
            )

        first_url = current_selected_url(edge_pid, control)
        next_queue = http_json(f"http://127.0.0.1:{port}/browser-watch-next.json")
        next_id = str(next_queue.get("card_id") or "")
        if not next_id or next_id == first_id:
            raise control.EvidenceGap(f"second saved-watch queue card is not distinct: {next_id!r}")
        second_url, navigation_detected_at = wait_url_change(
            edge_pid,
            first_url,
            seconds=30,
            control=control,
        )
        second_obs, second_elapsed = wait_observation(
            next_id,
            after=navigation_detected_at,
            count_before=len(obs_before) + 1,
            seconds=60,
            control=control,
        )
        if second_elapsed < 4.85:
            raise control.ControlError(
                f"second rendered-page observation is inconsistent with 5-second dwell: {second_elapsed:.3f}s"
            )

        # Prove the real saved-watch 120-second scheduler. After both currently-due
        # watches have been observed, the next cycle must wait for a previously
        # observed exact card rather than immediately spinning.
        cadence_queue = http_json(f"http://127.0.0.1:{port}/browser-watch-next.json")
        cadence_id = str(cadence_queue.get("card_id") or "")
        cadence_wait = float(cadence_queue.get("wait_seconds") or 0.0)
        if (
            cadence_queue.get("active") is not True
            or cadence_queue.get("due_now") is True
            or cadence_queue.get("status") != "WAITING"
            or cadence_id not in {first_id, next_id}
            or cadence_wait <= 0.0
            or cadence_wait > 120.25
        ):
            raise control.ControlError(f"120-second saved-watch scheduling proof failed: {cadence_queue!r}")
        prior_obs = first_obs if cadence_id == first_id else second_obs
        cadence_url, cadence_navigation_at = wait_url_change(
            edge_pid,
            second_url,
            seconds=max(35.0, cadence_wait + 35.0),
            control=control,
        )
        cadence_obs, cadence_elapsed = wait_observation(
            cadence_id,
            after=cadence_navigation_at,
            count_before=len(obs_before) + 2,
            seconds=60,
            control=control,
        )
        if cadence_elapsed < 4.85:
            raise control.ControlError(
                f"cadence rendered-page observation is inconsistent with 5-second dwell: {cadence_elapsed:.3f}s"
            )
        cadence_delta = (
            parse_dt(str(cadence_obs.get("observed_at") or ""))
            - parse_dt(str(prior_obs.get("observed_at") or ""))
        ).total_seconds()
        if cadence_delta < 120.0:
            raise control.ControlError(
                f"saved-watch cadence violated 120-second minimum: {cadence_delta:.3f}s"
            )

        selected = uia_snapshot(edge_pid, control)
        selected_title = ""
        tabs = selected.get("Tabs") or []
        if isinstance(tabs, dict):
            tabs = [tabs]
        selected_rows = [row for row in tabs if row.get("Selected") is True]
        if len(selected_rows) == 1:
            selected_title = str(selected_rows[0].get("Name") or "")
        cleanup = close_known_temporary_tabs(edge_pid, selected_title, control)
        remaining = cleanup.get("Remaining") or []
        if isinstance(remaining, str):
            remaining = [remaining]
        cfb_titles = [name for name in remaining if "CFB.FAN" in str(name)]
        if len(cfb_titles) != 1:
            raise control.ControlError(
                f"tab hygiene failed: expected one CFB.FAN tab, observed {len(cfb_titles)}"
            )

        mid = protected_snapshot()
        verify_protected(mid, control, allow_new_observations=True)

        # Restart once while still pending and prove the queue, helper, exact-card
        # observations, server hotfix, and protected state survive.
        restart_port, restart_pid = restart_server(int(port), launch, control)
        helper_after_restart = wait_helper(restart_port, control, seconds=30)
        queue_after_restart = http_json(
            f"http://127.0.0.1:{restart_port}/browser-watch-next.json"
        )
        after_restart = protected_snapshot()
        verify_protected(after_restart, control, allow_new_observations=True)
        if queue_after_restart.get("schema") != "simple-evaluator-browser-work-queue-v1":
            raise control.ControlError("single-worktab queue did not survive dynamic-port restart")
        persisted = observations()
        persisted_ids = {
            str(row.get("card_id") or "")
            for row in persisted
            if isinstance(row, dict)
            and row.get("collection_method") == "USER_STARTED_BROWSER_WATCH"
            and row.get("helper_version") == EXPECTED_HELPER_VERSION
        }
        if not {first_id, next_id}.issubset(persisted_ids):
            raise control.ControlError("exact-card 1.4.14 observations did not persist through restart")

        acceptance_sha = write_full_acceptance(
            helper=helper_after_restart,
            first_obs=prior_obs,
            cadence_obs=cadence_obs,
            cadence_delta=cadence_delta,
            tab_cleanup=cleanup,
            stop_checks=stop_checks,
            evaluator_checks=evaluator_checks,
            protected_after=after_restart,
            restart_port=restart_port,
        )
        accepted_release_sha = write_release_accepted(control)

        # RELEASE is read at server import time. Restart again after the accepted
        # write so health/diagnostics must actually load and report the accepted
        # release, not merely observe the file on disk.
        final_port, final_pid = restart_server(restart_port, launch, control)
        helper_final = wait_helper(final_port, control, seconds=30)
        health_final = http_json(f"http://127.0.0.1:{final_port}/health.json")
        diagnostics_final = http_json(f"http://127.0.0.1:{final_port}/diagnostics.json")
        final_protected = protected_snapshot()
        verify_protected(final_protected, control, allow_new_observations=True)
        if health_final.get("release_status") != "PRODUCTION_ACCEPTED":
            raise control.ControlError(f"accepted release did not survive restart: {health_final!r}")
        diag_release = diagnostics_final.get("release") or {}
        if (
            diagnostics_final.get("deployment_ready") is not True
            or diag_release.get("status") != "PRODUCTION_ACCEPTED"
            or (diagnostics_final.get("browser_helper") or {}).get("version_matches") is not True
        ):
            raise control.ControlError(
                f"final accepted diagnostics are not deployment-ready: {diagnostics_final!r}"
            )
        acceptance_final = http_json(
            f"http://127.0.0.1:{final_port}/production-acceptance.json"
        )
        if (
            acceptance_final.get("status") != "PASS"
            or acceptance_final.get("full_single_worktab_acceptance") is not True
            or float(acceptance_final.get("observed_delta_seconds") or 0) < 120.0
        ):
            raise control.ControlError(f"full acceptance record did not survive restart: {acceptance_final!r}")

        verify_installed_files(control, prepatch=False)
        return {
            "status": "PASS",
            "installed_hashes_before_server_hardening": installed_hashes_prepatch,
            "installed_hashes_after_server_hardening": installed_hashes,
            "runtime_postimages": runtime_patch,
            "edge_pid": edge_pid,
            "developer_mode": toggle,
            "extension_reload": extension_reload,
            "helper_live": helper,
            "first_observation": {
                "card_id": first_id,
                "elapsed_seconds": round(first_elapsed, 3),
                "observed_at": first_obs.get("observed_at"),
                "price_state": first_obs.get("listing_state") or first_obs.get("status"),
            },
            "second_observation": {
                "card_id": next_id,
                "elapsed_from_navigation_detection_seconds": round(second_elapsed, 3),
                "detected_url": second_url,
                "observed_at": second_obs.get("observed_at"),
                "price_state": second_obs.get("listing_state") or second_obs.get("status"),
            },
            "cadence_observation": {
                "card_id": cadence_id,
                "scheduled_wait_seconds": round(cadence_wait, 3),
                "detected_url": cadence_url,
                "elapsed_from_navigation_detection_seconds": round(cadence_elapsed, 3),
                "observed_delta_seconds": round(cadence_delta, 3),
                "observed_at": cadence_obs.get("observed_at"),
            },
            "prepatch_stop_condition_checks": prepatch_stop_checks,
            "stop_condition_checks": stop_checks,
            "evaluator_checks": evaluator_checks,
            "tab_cleanup": cleanup,
            "cfb_tab_count_after_cleanup": len(cfb_titles),
            "restart_pending": {
                "port": restart_port,
                "pid": restart_pid,
                "helper": helper_after_restart,
                "queue": queue_after_restart,
            },
            "restart_accepted": {
                "port": final_port,
                "pid": final_pid,
                "helper": helper_final,
                "health": health_final,
                "diagnostics_deployment_ready": diagnostics_final.get("deployment_ready"),
            },
            "protected_before": before,
            "protected_after_restart": after_restart,
            "protected_final": final_protected,
            "full_acceptance_sha256": acceptance_sha,
            "accepted_release_sha256": accepted_release_sha,
        }
    except Exception:
        # Fail closed and restore every acceptance-boundary file. Best-effort
        # restart reloads the restored pending release/original server if the
        # server hotfix had already been activated.
        try:
            release_path.write_bytes(release_backup)
        except OSError:
            pass
        try:
            if acceptance_existed and acceptance_backup is not None:
                acceptance_path.write_bytes(acceptance_backup)
            elif acceptance_path.exists():
                acceptance_path.unlink()
        except OSError:
            pass
        try:
            # Restore server.py only while its interpreter is stopped. This is
            # required on Windows for the same reason as the forward patch.
            current_port = launch.find_running_server()
            rollback_pid = server_stopped_pid
            if current_port is not None:
                rollback_pid = stop_server(int(current_port), launch, control)
            for raw_path, backup in runtime_backups.items():
                target = Path(raw_path)
                if target.read_bytes() != backup:
                    restored = write_runtime_bytes(target, backup, control)
                    if restored != hashlib.sha256(backup).hexdigest():
                        raise control.ControlError(f"runtime rollback hash mismatch: {target.name}")
            if edge_pid is not None:
                try:
                    navigate_selected_url(edge_pid, f"edge://extensions/?id={EXTENSION_ID}", control)
                    reload_helper_extension(edge_pid, control)
                except Exception:
                    pass
            if rollback_pid is not None:
                start_server(rollback_pid, launch, control)
        except Exception:
            pass
        raise
