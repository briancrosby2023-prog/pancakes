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
EXPECTED_AUTHORITY_REVISION = 22
APP = Path(r"C:\Users\Trash Panda\AppData\Local\SimpleEvaluator")
HELPER_DIR = APP / "browser-helper"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
EXPECTED_HELPER_VERSION = "1.4.13"
EXPECTED_WATCH_SHA256 = "1faebe0b39ecf35879d35d16ce2a0aedb04cf15dc882350e55b39a2fea286912"
EXPECTED_MANIFEST_SHA256 = "51beb29b86febf22cfcbcf50e06a10b3525dbbcbe7e7c537ec6ed8cd8d2d9b97"
EXPECTED_BACKGROUND_SHA256 = "a3ce6c9884a514331bb614c5bbf8ff8b68ea2e56cfdde36a6bdeb616c5c6444e"
EXPECTED_PREFLIGHT_SHA256 = "6a4c835a95b812f81503a4a36302bed39adf43f38871473f3cda77311dbef59f"
EXPECTED_SERVER_SHA256 = "bd2be6072354a91a37acc43a16783488abb700ac2784c10641cd4fb1b864dc37"
EXPECTED_UI_SHA256 = "8dc0a0eb54a33ec2e0ee8df243ecbb9b0f7f4e8f764008cb68d843ebe8e2a355"
PENDING_RELEASE_SHA256 = "60549a6729a3205055992c982fb3b180a96ab5a34fec82a26ff57afb914b45d8"
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
    spec = importlib.util.spec_from_file_location("simple_evaluator_launch_acceptance", APP / "launch.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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


def verify_installed_files(control) -> dict[str, str]:
    expected = {
        "server.py": EXPECTED_SERVER_SHA256,
        "Simple-Evaluator.html": EXPECTED_UI_SHA256,
        "browser-helper/background.js": EXPECTED_BACKGROUND_SHA256,
        "browser-helper/watch.js": EXPECTED_WATCH_SHA256,
        "browser-helper/preflight.js": EXPECTED_PREFLIGHT_SHA256,
        "browser-helper/manifest.json": EXPECTED_MANIFEST_SHA256,
        "RELEASE.json": PENDING_RELEASE_SHA256,
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
    if manifest.get("version") != EXPECTED_HELPER_VERSION:
        raise control.EvidenceGap("installed helper manifest is not 1.4.13")
    if release.get("browser_helper_version") != EXPECTED_HELPER_VERSION:
        raise control.EvidenceGap("installed release does not expect helper 1.4.13")
    if release.get("status") != "FROZEN_PENDING_PHYSICAL_ACCEPTANCE":
        raise control.EvidenceGap("installed release is not pending physical acceptance")
    return actual


def find_controlled_edge(control) -> dict[str, Any]:
    helper = str(HELPER_DIR).replace("\\", "\\\\")
    ps = rf'''
$p=@(Get-CimInstance Win32_Process | Where-Object {{ $_.Name -eq 'msedge.exe' -and $_.CommandLine -notmatch '--type=' -and $_.CommandLine -like '*--load-extension=*SimpleEvaluator*browser-helper*' }} | ForEach-Object {{
  $gp=Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
  if($gp -and $gp.MainWindowHandle -ne 0){{ [pscustomobject]@{{ProcessId=$_.ProcessId;CommandLine=$_.CommandLine;MainWindowHandle=[long]$gp.MainWindowHandle;MainWindowTitle=$gp.MainWindowTitle}} }}
}})
$p | ConvertTo-Json -Depth 4
'''
    rows = run_ps_json(ps, control)
    if isinstance(rows, dict):
        rows = [rows]
    rows = rows or []
    exact = [row for row in rows if str(HELPER_DIR).lower() in str(row.get("CommandLine") or "").lower()]
    if len(exact) != 1:
        raise control.EvidenceGap(f"expected one controlled Edge helper window; observed {len(exact)}")
    return exact[0]


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
    ps = rf'''
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$p=Get-Process -Id {edge_pid} -ErrorAction Stop
$root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
$backs=@()
foreach($e in $all){{
  if($e.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and [string]$e.Current.Name -eq "Back" -and $e.Current.IsEnabled){{
    try{{ $null=$e.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern); $backs += $e }}catch{{}}
  }}
}}
if($backs.Count -ne 1){{ throw ("Expected exactly one enabled Extensions Back button; observed "+$backs.Count) }}
($backs[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)).Invoke()
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
'''
    return run_ps_json(ps, control)


def select_developer_toggle(snapshot: Mapping[str, Any], control) -> dict[str, Any]:
    labels = snapshot.get("Labels") or []
    toggles = snapshot.get("Toggles") or []
    if isinstance(labels, dict):
        labels = [labels]
    if isinstance(toggles, dict):
        toggles = [toggles]
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
  if($e.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button -and $e.Current.IsEnabled -and [string]$e.Current.Name -match '^(Reload|Reload this page)$'){{
    try{{ $null=$e.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern); $reload += $e }}catch{{}}
  }}
}}
if($reload.Count -ne 1){{ throw ("Expected exactly one Reload button; observed "+$reload.Count) }}
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


def restart_server(port: int, launch, control) -> tuple[int, int]:
    pid = listener_pid(port)
    if not pid:
        raise control.EvidenceGap("Simple Evaluator listener PID is unavailable for restart")
    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 10
    while time.time() < deadline:
        if launch.probe(port, timeout=0.2) is None:
            break
        time.sleep(0.2)
    else:
        raise control.ControlError("Simple Evaluator server did not stop")
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
    if not new_pid or new_pid == pid:
        raise control.ControlError("Simple Evaluator restart did not produce a new listener PID")
    return int(new_port), int(new_pid)


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
    control.verify_repo(repo, expected_revision=EXPECTED_AUTHORITY_REVISION, expected_branch="product/c3po-clean-room-roster", require_clean=True)
    installed_hashes = verify_installed_files(control)
    before = protected_snapshot()
    verify_protected(before, control, allow_new_observations=False)
    launch = load_launch_module()
    port = launch.find_running_server()
    if port is None:
        raise control.EvidenceGap("Simple Evaluator server is not running")
    queue = http_json(f"http://127.0.0.1:{port}/browser-watch-next.json")
    if queue.get("schema") != "simple-evaluator-browser-work-queue-v1" or queue.get("active") is not True:
        raise control.EvidenceGap("single-worktab queue is not active")
    edge = find_controlled_edge(control)
    edge_pid = int(edge["ProcessId"])
    pre_uia = uia_snapshot(edge_pid, control)
    if "Extensions" not in str(pre_uia.get("Title") or ""):
        raise control.EvidenceGap("controlled Edge window is not on the known extension-details surface")

    root = open_extensions_root_and_snapshot(edge_pid, control)
    chosen = select_developer_toggle(root, control)
    toggle = toggle_exact(edge_pid, chosen, control)
    helper = wait_helper(int(port), control, seconds=30)

    obs_before = observations()
    first_queue = http_json(f"http://127.0.0.1:{port}/browser-watch-next.json")
    first_id = str(first_queue.get("card_id") or "")
    if not first_id:
        raise control.EvidenceGap("first queue card ID is absent")
    reload_info = choose_work_tab_and_reload(edge_pid, first_queue, control)
    reload_at = parse_dt(str(reload_info["ReloadedAt"]))
    first_obs, first_elapsed = wait_observation(
        first_id,
        after=reload_at,
        count_before=len(obs_before),
        seconds=60,
        control=control,
    )
    if first_elapsed < 5.0:
        raise control.ControlError(f"first rendered-page observation violated 5-second dwell: {first_elapsed:.3f}s")

    next_queue = http_json(f"http://127.0.0.1:{port}/browser-watch-next.json")
    next_id = str(next_queue.get("card_id") or "")
    if not next_id or next_id == first_id:
        raise control.EvidenceGap(f"second saved-watch queue card is not distinct: {next_id!r}")
    second_url, navigation_detected_at = wait_url_change(
        edge_pid,
        str(reload_info.get("Url") or ""),
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
        raise control.ControlError(f"tab hygiene failed: expected one CFB.FAN tab, observed {len(cfb_titles)}")

    mid = protected_snapshot()
    verify_protected(mid, control, allow_new_observations=True)
    new_port, new_pid = restart_server(int(port), launch, control)
    helper_after_restart = wait_helper(new_port, control, seconds=30)
    queue_after_restart = http_json(f"http://127.0.0.1:{new_port}/browser-watch-next.json")
    after_restart = protected_snapshot()
    verify_protected(after_restart, control, allow_new_observations=True)
    if queue_after_restart.get("schema") != "simple-evaluator-browser-work-queue-v1":
        raise control.ControlError("single-worktab queue did not survive dynamic-port restart")

    release_backup = (APP / "RELEASE.json").read_bytes()
    try:
        accepted_release_sha = write_release_accepted(control)
        release = read_json(APP / "RELEASE.json")
        if release.get("status") != "PRODUCTION_ACCEPTED":
            raise control.ControlError("release acceptance status write did not persist")
    except Exception:
        (APP / "RELEASE.json").write_bytes(release_backup)
        raise

    return {
        "status": "PASS",
        "installed_hashes_before_acceptance": installed_hashes,
        "edge_pid": edge_pid,
        "developer_mode": toggle,
        "helper_before_restart": helper,
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
        "tab_cleanup": cleanup,
        "cfb_tab_count_after_cleanup": len(cfb_titles),
        "old_server_port": int(port),
        "new_server_port": new_port,
        "new_server_pid": new_pid,
        "helper_after_restart": helper_after_restart,
        "queue_after_restart": queue_after_restart,
        "protected_before": before,
        "protected_after_restart": after_restart,
        "accepted_release_sha256": accepted_release_sha,
    }
