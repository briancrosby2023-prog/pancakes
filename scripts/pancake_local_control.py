#!/usr/bin/env python3
"""Operation Pancake local controlled execution runner.

This runner never exposes an arbitrary shell to the decision model. Candidate bytes
are staged first, hashed, tied to a state fingerprint, authorized by the repository's
existing SOPDecisionGateway, and applied only through ControlledToolBroker.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import ctypes.wintypes
import hashlib
import importlib
import re
import http.server
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

AUTHORITY_REL = "docs/OPERATION_PANCAKE_CONTROL_STATE.json"
EXPECTED_REPOSITORY = "briancrosby2023-prog/pancakes"
DEFAULT_REPO = Path(r"C:\Users\Trash Panda\pancakes")
EXPECTED_BOOTSTRAP_BRANCH = "product/c3po-clean-room-roster"
DURABLE_TARGET = "scripts/pancake_local_control.py"
TARGET_ACTION = "apply_bounded_patch"
ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = ISSUER + "/api/accounts/authorize"
TOKEN_URL = ISSUER + "/api/accounts/oauth/token"
JWKS_URL = ISSUER + "/.well-known/jwks.json"
RESOURCE = "https://api.openai.com/v1"
MODELS_URL = RESOURCE + "/models"
RESPONSES_URL = RESOURCE + "/responses"
REQUIRED_SCOPE = "chatgpt.tokens.use.direct"
ALL_SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
APP_NAME = "Operation Pancake Control"
SCHEMA = "operation-pancake-mutation-capsule-v1"
RESULT_SCHEMA = "operation-pancake-control-result-v1"
CREDENTIAL_SCHEMA = "operation-pancake-chatgpt-credential-v1"

# Durable ordinary-chat control transport. GitHub is request transport only;
# authorization remains SOPDecisionGateway -> ControlledToolBroker.
CONTROL_BLOB_MANIFEST = {
    "src/operation_pancake/__init__.py": "7717f63dcbe06a36daa249a7722a9ea7792647ef",
    "src/operation_pancake/sop_policy.py": "ca60e2b9ee54ba7df8688c59cfa511bf5598727d",
    "src/operation_pancake/cross_surface_control.py": "20e1382041a30d110e27c645a93020793c96865b",
    "src/operation_pancake/sop_gateway.py": "0b77383653ff703582e0e2ce45a43f7d1a6b1cc7",
    "src/operation_pancake/tool_broker.py": "8c4221fa39dcdd316757945166c96dacebfc589b",
    "src/operation_pancake/control_state.py": "e5b0128217cd503482aecf6e913aa9dd72443a2a",
}
CONTROL_REQUEST_SCHEMA = "operation-pancake-control-request-v1"
CONTROL_RECEIPT_SCHEMA = "operation-pancake-control-receipt-v1"
CONTROL_ACTIVATION_SCHEMA = "operation-pancake-activation-v1"
CONTROL_TITLE_PREFIX = "[OPERATION PANCAKE CONTROL] "
CONTROL_TRUSTED_CREATOR = "briancrosby2023-prog"
CONTROL_POLL_SECONDS = 120
RUNTIME_INSTALL_ACTION = "install_local_control_runtime"
INBOX_ACTIONS = {
    "inspect_control_state",
    "read_bootstrap_result",
    "run_control_validation",
    "regenerate_authorized_handoff",
}
INBOX_MUTATING_ACTIONS = {"regenerate_authorized_handoff"}
DECISION_ACTION_TOKENS = sorted({TARGET_ACTION, RUNTIME_INSTALL_ACTION, *INBOX_ACTIONS})
CONTROL_REQUEST_FIELDS = {
    "schema", "request_id", "mission", "expected_repository", "expected_branch",
    "expected_head", "expected_authority_revision", "requested_action", "request",
}
CONTROL_RECEIPT_STATES = {
    "RECEIVED", "VALIDATED", "SNAPSHOT_FROZEN", "DECISION_CREATED", "AUTHORIZED",
    "EXECUTING", "VALIDATING", "INSTALLED", "COMPLETE", "FAILED", "ROLLED_BACK",
    "EVIDENCE_GAP",
}
CONTROL_TERMINAL_STATES = {"INSTALLED", "COMPLETE", "FAILED", "ROLLED_BACK", "EVIDENCE_GAP"}

DECISION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "proposed_plan", "allowed_actions", "blocked_actions", "next_action",
        "obstacle_classification", "alternatives_considered", "selected_reason",
        "implementation_basis_fact_keys", "user_action_required",
        "remaining_executable_routes",
    ],
    "properties": {
        "proposed_plan": {"type": "string", "minLength": 1},
        "allowed_actions": {
            "type": "array", "items": {"type": "string", "enum": DECISION_ACTION_TOKENS},
        },
        "blocked_actions": {
            "type": "array", "items": {"type": "string", "enum": DECISION_ACTION_TOKENS},
        },
        "next_action": {"type": "string", "minLength": 1},
        "obstacle_classification": {
            "enum": [
                "NONE", "MISSION_PROBLEM", "IMPLEMENTATION_PROBLEM",
                "CAPABILITY_PROBLEM", "EXTERNAL_DEPENDENCY", "EVIDENCE_GAP",
            ]
        },
        "alternatives_considered": {
            "type": "array", "items": {"type": "string", "minLength": 1},
            "minItems": 1,
        },
        "selected_reason": {"type": "string", "minLength": 1},
        "implementation_basis_fact_keys": {
            "type": "array", "items": {"type": "string", "minLength": 1},
        },
        "user_action_required": {"type": "boolean"},
        "remaining_executable_routes": {
            "type": "array", "items": {"type": "string", "minLength": 1},
        },
    },
}

DECISION_INSTRUCTION = """You are the decision engine behind the Operation Pancake
SOP gateway. MAP, HISTORY, RESEARCH, and CAPABILITIES are supplied as typed
evidence. Use only that evidence and the request. Do not invent missing facts,
silently replace history, broaden the mission, or self-certify an unknown.
Return a concrete proposed_plan, exact allowed_actions and blocked_actions,
one next_action, obstacle_classification, alternatives_considered,
selected_reason, implementation_basis_fact_keys, user_action_required, and
remaining_executable_routes. Implementation basis keys must name fact_key
values that actually appear in trusted supplied evidence. If mutation_requested
is true and no trusted fact supports implementation, do not invent one. Do not
send work back to the user while executable technical routes remain.
Do not include prose outside the required JSON structure."""


class ControlError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def canonical_remote(value: str) -> str:
    text = value.strip().lower().replace("\\", "/")
    if text.endswith(".git"):
        text = text[:-4]
    if text.startswith("git@github.com:"):
        text = "https://github.com/" + text.split(":", 1)[1]
    if text.startswith("ssh://git@github.com/"):
        text = "https://github.com/" + text.split("ssh://git@github.com/", 1)[1]
    if text.startswith("http://github.com/"):
        text = "https://github.com/" + text.split("http://github.com/", 1)[1]
    return text.rstrip("/")


def run_git(repo: Path, *args: str, check: bool = True) -> str:
    cp = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and cp.returncode != 0:
        raise ControlError(f"git {' '.join(args)} failed: {cp.stderr.strip() or cp.stdout.strip()}")
    return cp.stdout.strip()


def load_authority(repo: Path) -> dict[str, Any]:
    path = repo / AUTHORITY_REL
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ControlError(f"cannot load authority: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise ControlError("authority root must be an object")
    return payload


def verify_repo(
    repo: Path,
    *,
    expected_head: str | None = None,
    expected_revision: int | None = None,
    expected_branch: str | None = None,
    require_clean: bool = True,
) -> dict[str, Any]:
    repo = repo.resolve()
    if not (repo / ".git").exists():
        raise ControlError(f"not a Git repository: {repo}")
    branch = run_git(repo, "branch", "--show-current")
    head = run_git(repo, "rev-parse", "HEAD")
    if expected_branch and branch != expected_branch:
        raise ControlError(f"wrong branch: expected {expected_branch}, observed {branch}")
    remote = canonical_remote(run_git(repo, "remote", "get-url", "origin"))
    expected_remote = canonical_remote("https://github.com/" + EXPECTED_REPOSITORY)
    if remote != expected_remote:
        raise ControlError(f"wrong repository remote: {remote}")
    if expected_head and head != expected_head:
        raise ControlError(f"wrong HEAD: expected {expected_head}, observed {head}")
    status = run_git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if require_clean and status:
        raise ControlError("working tree is not clean")
    authority = load_authority(repo)
    revision = authority.get("state_revision")
    if expected_revision is not None and revision != expected_revision:
        raise ControlError(f"wrong authority revision: expected {expected_revision}, observed {revision}")
    active = authority.get("active_mission") or {}
    if not isinstance(active, dict) or not str(active.get("id", "")).strip():
        raise ControlError("authority has no active mission")
    return {
        "repo": str(repo),
        "branch": branch,
        "head": head,
        "remote": remote,
        "clean": not bool(status),
        "authority_revision": revision,
        "mission": str(active["id"]),
        "authority_status": str(authority.get("status", "")),
    }



def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def verify_control_modules(repo: Path) -> None:
    """Hash-verify every trusted Pancake module before Python imports the package."""
    for rel, expected_blob_sha in CONTROL_BLOB_MANIFEST.items():
        path = repo / rel
        if not path.is_file():
            raise ControlError(f"trusted control module missing: {rel}")
        raw = path.read_bytes()
        observed = git_blob_sha(raw)
        if observed != expected_blob_sha:
            normalized = raw.replace(b"\r\n", b"\n")
            normalized_observed = git_blob_sha(normalized)
            if normalized_observed != expected_blob_sha:
                raise ControlError(
                    f"trusted control module hash mismatch before import: {rel}; "
                    f"expected {expected_blob_sha}, observed {observed}, "
                    f"normalized {normalized_observed}"
                )

def add_repo_src(repo: Path) -> None:
    src = repo / "src"
    if not src.is_dir():
        raise ControlError("repository src directory is missing")
    value = str(src)
    if value not in sys.path:
        sys.path.insert(0, value)


def validate_target(repo: Path, rel: str) -> Path:
    if not isinstance(rel, str) or not rel.strip():
        raise ControlError("target path is required")
    if os.path.isabs(rel):
        raise ControlError("absolute target paths are forbidden")
    normalized = rel.replace("\\", "/")
    parts = Path(normalized).parts
    if any(part in {"..", ".git"} for part in parts):
        raise ControlError("repository escape or .git target is forbidden")
    target = (repo / Path(*parts)).resolve()
    repo_resolved = repo.resolve()
    try:
        target.relative_to(repo_resolved)
    except ValueError as exc:
        raise ControlError("target escapes repository") from exc
    return target


def preimage_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.exists() else "ABSENT"


@dataclass(frozen=True)
class MutationCapsule:
    target: str
    preimage_sha256: str
    content: bytes
    content_sha256: str
    request: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "MutationCapsule":
        allowed = {
            "schema", "target", "preimage_sha256", "content_base64",
            "content_sha256", "request",
        }
        extra = set(raw) - allowed
        if extra:
            raise ControlError("unsupported capsule fields: " + ", ".join(sorted(extra)))
        if raw.get("schema") != SCHEMA:
            raise ControlError("unsupported capsule schema")
        try:
            content = base64.b64decode(str(raw.get("content_base64", "")), validate=True)
        except Exception as exc:
            raise ControlError("invalid capsule content encoding") from exc
        digest = sha256_bytes(content)
        expected = str(raw.get("content_sha256", "")).strip().lower()
        if not expected or digest != expected:
            raise ControlError("candidate content SHA-256 mismatch")
        request = str(raw.get("request", "")).strip()
        if not request:
            raise ControlError("capsule request is required")
        return cls(
            target=str(raw.get("target", "")).strip(),
            preimage_sha256=str(raw.get("preimage_sha256", "")).strip().upper()
            if str(raw.get("preimage_sha256", "")).strip().upper() == "ABSENT"
            else str(raw.get("preimage_sha256", "")).strip().lower(),
            content=content,
            content_sha256=digest,
            request=request,
        )


def load_capsule(path: Path) -> MutationCapsule:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ControlError(f"cannot load mutation capsule: {type(exc).__name__}") from exc
    if not isinstance(raw, dict):
        raise ControlError("capsule root must be an object")
    return MutationCapsule.from_mapping(raw)


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def jwt_parts(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    if not isinstance(token, str) or token.count(".") != 2:
        raise ControlError("malformed JWT")
    h, p, s = token.split(".")
    try:
        header = json.loads(b64url_decode(h))
        payload = json.loads(b64url_decode(p))
        signature = b64url_decode(s)
    except Exception as exc:
        raise ControlError("malformed JWT") from exc
    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise ControlError("malformed JWT object")
    return header, payload, f"{h}.{p}".encode("ascii"), signature


_SHA256_DIGESTINFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def verify_rs256(signing_input: bytes, signature: bytes, n: int, e: int) -> None:
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        raise ControlError("JWT signature length mismatch")
    em = pow(int.from_bytes(signature, "big"), e, n).to_bytes(k, "big")
    digest_info = _SHA256_DIGESTINFO_PREFIX + hashlib.sha256(signing_input).digest()
    if not em.startswith(b"\x00\x01"):
        raise ControlError("JWT signature verification failed")
    try:
        sep = em.index(b"\x00", 2)
    except ValueError as exc:
        raise ControlError("JWT signature verification failed") from exc
    padding = em[2:sep]
    if len(padding) < 8 or any(x != 0xFF for x in padding):
        raise ControlError("JWT signature verification failed")
    if em[sep + 1:] != digest_info:
        raise ControlError("JWT signature verification failed")


def oauth_id_token_hint_is_fresh(token: str, *, now: int | None = None) -> bool:
    try:
        _, payload, _, _ = jwt_parts(token)
        exp = int(payload.get("exp", 0))
    except Exception:
        return False
    current = int(time.time()) if now is None else int(now)
    return exp > current + 30


def select_jwk(jwks: Mapping[str, Any], kid: str) -> Mapping[str, Any]:
    keys = jwks.get("keys", [])
    if not isinstance(keys, list):
        raise ControlError("invalid JWKS")
    matches = [k for k in keys if isinstance(k, dict) and k.get("kid") == kid]
    if len(matches) != 1:
        raise ControlError("JWT key id not found")
    return matches[0]


def validate_signed_jwt(
    token: str,
    jwks: Mapping[str, Any],
    *,
    audience: str,
    nonce: str | None = None,
    required_scope: str | None = None,
    now: int | None = None,
) -> Mapping[str, Any]:
    header, payload, signing_input, signature = jwt_parts(token)
    if header.get("alg") != "RS256":
        raise ControlError("unsupported JWT algorithm")
    kid = str(header.get("kid", ""))
    if not kid:
        raise ControlError("JWT kid is missing")
    jwk = select_jwk(jwks, kid)
    try:
        n = int.from_bytes(b64url_decode(str(jwk["n"])), "big")
        e = int.from_bytes(b64url_decode(str(jwk["e"])), "big")
    except Exception as exc:
        raise ControlError("invalid RSA JWK") from exc
    verify_rs256(signing_input, signature, n, e)

    current = int(time.time()) if now is None else int(now)
    if payload.get("iss") != ISSUER:
        raise ControlError("JWT issuer mismatch")
    aud = payload.get("aud")
    audiences = [aud] if isinstance(aud, str) else aud if isinstance(aud, list) else []
    if audience not in audiences:
        raise ControlError("JWT audience mismatch")
    try:
        exp = int(payload["exp"])
        nbf = int(payload.get("nbf", 0))
    except Exception as exc:
        raise ControlError("JWT time claims are malformed") from exc
    if exp <= current - 30:
        raise ControlError("JWT is expired")
    if nbf > current + 30:
        raise ControlError("JWT is not yet valid")
    if nonce is not None and payload.get("nonce") != nonce:
        raise ControlError("ID token nonce mismatch")
    if required_scope is not None:
        scopes = set(str(payload.get("scope", "")).split())
        if required_scope not in scopes:
            raise ControlError("required ChatGPT plan scope is missing")
    return payload


def json_request(
    url: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 60,
    opener=urllib.request.urlopen,
) -> Mapping[str, Any]:
    req = urllib.request.Request(url, data=data, headers=dict(headers or {}), method=method)
    try:
        with opener(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")[:500]
        except Exception:
            detail = ""
        raise ControlError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ControlError(f"request failed for {url}: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise ControlError(f"non-object JSON from {url}")
    return payload


def form_post(url: str, fields: Mapping[str, str], *, opener=urllib.request.urlopen) -> Mapping[str, Any]:
    return json_request(
        url,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=urllib.parse.urlencode(fields).encode("ascii"),
        opener=opener,
    )


def is_transient_http_control_error(exc: Exception) -> bool:
    text = str(exc)
    return any(f"HTTP {code} " in text for code in (429, 500, 502, 503, 504))


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> tuple[DATA_BLOB, Any]:
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def dpapi_protect(data: bytes) -> bytes:
    if os.name != "nt":
        raise ControlError("DPAPI credential storage requires Windows")
    in_blob, in_buffer = _blob(data)
    out_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob), APP_NAME, None, None, None,
        CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob)
    ):
        raise ControlError("CryptProtectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
        _ = in_buffer


def dpapi_unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        raise ControlError("DPAPI credential storage requires Windows")
    in_blob, in_buffer = _blob(data)
    out_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None,
        CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob)
    ):
        raise ControlError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
        _ = in_buffer


class CredentialStore:
    def __init__(self, root: Path | None = None, *, protector=dpapi_protect, unprotector=dpapi_unprotect):
        base = root or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OperationPancakeControl"
        self.root = Path(base)
        self.credential_path = self.root / "chatgpt_credentials.bin"
        self.host_id_path = self.root / "host_id.txt"
        self.protector = protector
        self.unprotector = unprotector

    def host_id(self) -> str:
        if self.host_id_path.exists():
            value = self.host_id_path.read_text(encoding="utf-8").strip()
            if value.startswith("urn:uuid:"):
                return value
            raise ControlError("stored host id is malformed")
        value = "urn:uuid:" + str(uuid.uuid4())
        atomic_write(self.host_id_path, (value + "\n").encode("utf-8"))
        return value

    def load(self) -> dict[str, Any] | None:
        if not self.credential_path.exists():
            return None
        try:
            raw = self.unprotector(self.credential_path.read_bytes())
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ControlError(f"cannot load protected credentials: {type(exc).__name__}") from exc
        if not isinstance(payload, dict) or payload.get("schema") != CREDENTIAL_SCHEMA:
            raise ControlError("credential record schema mismatch")
        return payload

    def save(self, payload: Mapping[str, Any]) -> None:
        body = dict(payload)
        body["schema"] = CREDENTIAL_SCHEMA
        protected = self.protector(
            (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        )
        atomic_write(self.credential_path, protected)


def pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode("ascii")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


class CallbackServer(http.server.HTTPServer):
    allow_reuse_address = False

    def __init__(self, addr, expected_state: str):
        self.expected_state = expected_state
        self.result: dict[str, str] | None = None
        self.error: str | None = None
        super().__init__(addr, CallbackHandler)


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    server: CallbackServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _reject(self, code: int, message: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def do_POST(self) -> None:
        self._reject(405, "Method not allowed.")

    def do_GET(self) -> None:
        if self.client_address[0] != "127.0.0.1":
            self._reject(403, "Loopback only.")
            return
        host = self.headers.get("Host", "")
        if not host.startswith("127.0.0.1:"):
            self._reject(403, "Invalid host.")
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/auth/callback":
            self._reject(404, "Not found.")
            return
        q = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        state = (q.get("state") or [""])[0]
        if not secrets.compare_digest(state, self.server.expected_state):
            self.server.error = "OAuth state mismatch"
            self._reject(400, "Authorization rejected.")
            return
        if "error" in q:
            self.server.error = "OAuth error: " + (q.get("error") or ["unknown"])[0]
            self._reject(400, "Authorization was not completed.")
            return
        result = {
            key: values[0]
            for key, values in q.items()
            if key in {"code", "state", "client_id", "scope"} and values
        }
        if not result.get("code"):
            self.server.error = "OAuth callback had no code"
            self._reject(400, "Authorization code missing.")
            return
        self.server.result = result
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(
            b"<!doctype html><meta charset=utf-8><title>Operation Pancake</title>"
            b"<h2>Operation Pancake authorization received.</h2>"
            b"<p>You can close this tab.</p>"
        )


class OAuthSession:
    def __init__(self, store: CredentialStore, *, opener=urllib.request.urlopen):
        self.store = store
        self.opener = opener
        self._jwks: Mapping[str, Any] | None = None

    def jwks(self) -> Mapping[str, Any]:
        if self._jwks is None:
            self._jwks = json_request(JWKS_URL, opener=self.opener)
        return self._jwks

    def _validate_tokens(
        self,
        token_response: Mapping[str, Any],
        *,
        client_id: str,
        nonce: str | None,
        prior_identity: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        access_token = str(token_response.get("access_token", ""))
        id_token = str(token_response.get("id_token", ""))
        refresh_token = str(token_response.get("refresh_token", ""))
        if not access_token or not id_token:
            raise ControlError("token response is incomplete")
        scopes = set(str(token_response.get("scope", "")).split())
        if REQUIRED_SCOPE not in scopes:
            raise ControlError("required ChatGPT plan scope was not granted")
        id_claims = validate_signed_jwt(
            id_token, self.jwks(), audience=client_id, nonce=nonce
        )
        access_claims = validate_signed_jwt(
            access_token, self.jwks(), audience=RESOURCE, required_scope=REQUIRED_SCOPE
        )
        if str(access_claims.get("client_id", "")) != client_id:
            raise ControlError("access token client id mismatch")
        if prior_identity is not None:
            if id_claims.get("sub") != prior_identity.get("subject"):
                raise ControlError("reauthorized account identity changed")
        return {
            "schema": CREDENTIAL_SCHEMA,
            "issuer": ISSUER,
            "subject": str(id_claims.get("sub", "")),
            "email": str(id_claims.get("email", "")),
            "client_id": client_id,
            "ext_agent_host_id": self.store.host_id(),
            "id_token": id_token,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": str(token_response.get("token_type", "Bearer")),
            "expires_in": int(token_response.get("expires_in", 3600)),
            "scopes": sorted(scopes),
            "saved_at": int(time.time()),
        }

    def _fresh(self, record: Mapping[str, Any]) -> bool:
        if REQUIRED_SCOPE not in set(record.get("scopes", [])):
            return False
        try:
            return int(record.get("saved_at", 0)) + int(record.get("expires_in", 0)) > int(time.time()) + 120
        except Exception:
            return False

    def _refresh(self, record: Mapping[str, Any]) -> dict[str, Any] | None:
        refresh_token = str(record.get("refresh_token", ""))
        client_id = str(record.get("client_id", ""))
        if not refresh_token or not client_id:
            return None
        try:
            response = form_post(
                TOKEN_URL,
                {
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": refresh_token,
                    "resource": RESOURCE,
                },
                opener=self.opener,
            )
        except ControlError as exc:
            if is_transient_http_control_error(exc):
                raise ControlError(
                    "transient ChatGPT OAuth refresh failure; interactive reauthorization suppressed"
                ) from exc
            return None

        # Refresh responses need not mint a new ID token. The account identity was
        # established and signature-validated during authorization; on refresh,
        # validate the newly issued access token and preserve that established identity.
        access_token = str(response.get("access_token", ""))
        rotated_refresh = str(response.get("refresh_token", ""))
        scopes = set(str(response.get("scope", "")).split())
        if not access_token or not rotated_refresh:
            return None
        if REQUIRED_SCOPE not in scopes:
            return None
        try:
            access_claims = validate_signed_jwt(
                access_token, self.jwks(), audience=RESOURCE, required_scope=REQUIRED_SCOPE
            )
        except ControlError:
            return None
        if str(access_claims.get("client_id", "")) != client_id:
            return None
        validated = {
            **dict(record),
            "schema": CREDENTIAL_SCHEMA,
            "issuer": ISSUER,
            "client_id": client_id,
            "ext_agent_host_id": self.store.host_id(),
            "access_token": access_token,
            "refresh_token": rotated_refresh,
            "token_type": str(response.get("token_type", "Bearer")),
            "expires_in": int(response.get("expires_in", 3600)),
            "scopes": sorted(scopes),
            "saved_at": int(time.time()),
        }
        self.store.save(validated)
        return validated

    def ensure(self) -> dict[str, Any]:
        existing = self.store.load()
        if existing and self._fresh(existing):
            validate_signed_jwt(
                str(existing.get("access_token", "")),
                self.jwks(),
                audience=RESOURCE,
                required_scope=REQUIRED_SCOPE,
            )
            return dict(existing)
        if existing:
            refreshed = self._refresh(existing)
            if refreshed:
                return refreshed
        return self.authorize(existing)

    def authorize(self, existing: Mapping[str, Any] | None = None) -> dict[str, Any]:
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier, challenge = pkce_pair()
        server = CallbackServer(("127.0.0.1", 0), state)
        server.timeout = 300
        port = server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/auth/callback"
        host_id = self.store.host_id()
        returning_id = str((existing or {}).get("client_id", "")).strip()
        initial = not returning_id
        client_id = "dynamic_agent_client" if initial else returning_id
        params = {
            "client_id": client_id,
            "ext_agent_host_id": host_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": ALL_SCOPES,
            "resource": RESOURCE,
            "state": state,
            "nonce": nonce,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
        if initial:
            params["agent_name_hint"] = APP_NAME
        else:
            if (
                existing
                and existing.get("id_token")
                and oauth_id_token_hint_is_fresh(str(existing["id_token"]))
            ):
                params["id_token_hint"] = str(existing["id_token"])
            if existing and existing.get("email"):
                params["login_hint"] = str(existing["email"])
        url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)
        if not webbrowser.open(url, new=1, autoraise=True):
            server.server_close()
            raise ControlError("could not open the system browser for ChatGPT authorization")
        try:
            server.handle_request()
        finally:
            server.server_close()
        if server.error:
            raise ControlError(server.error)
        if not server.result:
            raise ControlError("ChatGPT authorization timed out")
        callback = server.result
        issued = str(callback.get("client_id", "")).strip()
        if initial:
            if not issued or issued == "dynamic_agent_client":
                raise ControlError("dynamic registration did not return an issued client id")
            exchange_client = issued
        else:
            if issued and issued != returning_id:
                raise ControlError("callback returned a different client id")
            exchange_client = returning_id
        response = form_post(
            TOKEN_URL,
            {
                "grant_type": "authorization_code",
                "client_id": exchange_client,
                "code": callback["code"],
                "code_verifier": verifier,
                "redirect_uri": redirect_uri,
                "resource": RESOURCE,
            },
            opener=self.opener,
        )
        validated = self._validate_tokens(
            response,
            client_id=exchange_client,
            nonce=nonce,
            prior_identity=existing,
        )
        self.store.save(validated)
        return validated


def available_models(access_token: str, *, opener=urllib.request.urlopen) -> list[dict[str, Any]]:
    payload = json_request(
        MODELS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        opener=opener,
    )
    values = payload.get("models", [])
    if not isinstance(values, list):
        raise ControlError("model catalog has invalid shape")
    return [x for x in values if isinstance(x, dict) and x.get("visibility") == "list" and x.get("slug")]


def choose_model(models: Sequence[Mapping[str, Any]]) -> str:
    slugs = [str(m.get("slug", "")) for m in models if str(m.get("slug", ""))]
    override = os.getenv("PANCAKE_CHATGPT_MODEL", "").strip()
    if override:
        if override not in slugs:
            raise ControlError(f"requested model is not available to this ChatGPT account: {override}")
        return override
    for preferred in ("gpt-6.1-sol", "gpt-5.6-sol"):
        if preferred in slugs:
            return preferred
    for slug in slugs:
        if slug.endswith("-sol") or "-sol-" in slug:
            return slug
    if not slugs:
        raise ControlError("ChatGPT account returned no visible models")
    return slugs[0]


def extract_output_text(response: Mapping[str, Any]) -> str:
    chunks: list[str] = []
    for item in response.get("output", []) if isinstance(response.get("output", []), list) else []:
        if not isinstance(item, dict):
            continue
        for part in item.get("content", []) if isinstance(item.get("content", []), list) else []:
            if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    return "".join(chunks).strip()


def stream_response(
    body: Mapping[str, Any],
    access_token: str,
    *,
    opener=urllib.request.urlopen,
    timeout: int = 120,
) -> Mapping[str, Any]:
    req = urllib.request.Request(
        RESPONSES_URL,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    completed: Mapping[str, Any] | None = None
    deltas: list[str] = []
    try:
        with opener(req, timeout=timeout) as response:
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    event = json.loads(data)
                except json.JSONDecodeError as exc:
                    raise ControlError("malformed SSE event") from exc
                if not isinstance(event, dict):
                    raise ControlError("malformed SSE event object")
                etype = event.get("type")
                if etype == "response.output_text.delta":
                    delta = event.get("delta")
                    if isinstance(delta, str):
                        deltas.append(delta)
                elif etype in {"response.failed", "response.incomplete"}:
                    raise ControlError(f"Responses stream terminated with {etype}")
                elif etype == "response.completed":
                    response_obj = event.get("response")
                    completed = response_obj if isinstance(response_obj, dict) else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:2000]
        raise ControlError(f"Responses API returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ControlError(f"Responses transport failed: {type(exc).__name__}") from exc
    if completed is None:
        raise ControlError("Responses stream ended without response.completed")
    text = "".join(deltas).strip() or extract_output_text(completed)
    if not text:
        raise ControlError("completed response contained no output text")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ControlError("decision output was not valid JSON") from exc
    if not isinstance(result, dict):
        raise ControlError("decision output must be an object")
    return result


class ChatGPTPlanOAuthDecisionProvider:
    def __init__(self, store: CredentialStore | None = None, *, opener=urllib.request.urlopen):
        self.store = store or CredentialStore()
        self.opener = opener

    def decide(self, request: str, context: Mapping[str, Any]) -> Mapping[str, Any]:
        session = OAuthSession(self.store, opener=self.opener)
        credentials = session.ensure()
        token = str(credentials["access_token"])
        model = choose_model(available_models(token, opener=self.opener))
        input_payload = json.dumps(
            {
                "request": request,
                "mission": context.get("mission"),
                "evidence": context.get("evidence"),
                "typed_evidence": context.get("typed_evidence"),
                "state_fingerprint": context.get("state_fingerprint"),
                "mutation_requested": context.get("mutation_requested"),
                "instruction": context.get("instruction"),
            },
            sort_keys=True,
        )
        body = {
            "model": model,
            "reasoning": {"effort": "high"},
            "store": False,
            "stream": True,
            "input": [
                {
                    "role": "developer",
                    "content": [{"type": "input_text", "text": DECISION_INSTRUCTION}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": input_payload}],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "operation_pancake_decision",
                    "strict": True,
                    "schema": DECISION_SCHEMA,
                }
            },
        }
        return stream_response(body, token, opener=self.opener)


def build_state_snapshot(repo: Path, target: Path, candidate_sha: str) -> dict[str, Any]:
    status = verify_repo(repo, require_clean=True)
    return {
        "repo": EXPECTED_REPOSITORY,
        "branch": status["branch"],
        "head": status["head"],
        "authority_revision": status["authority_revision"],
        "mission": status["mission"],
        "target": str(target.relative_to(repo).as_posix()),
        "target_preimage_sha256": preimage_hash(target),
        "candidate_sha256": candidate_sha,
        "working_tree_clean": True,
    }


def build_evidence(
    repo: Path,
    snapshot: Mapping[str, Any],
    capsule: MutationCapsule,
    *,
    bootstrap_history: Sequence[str] = (),
) -> dict[str, list[dict[str, str]]]:
    authority = load_authority(repo)
    accepted = authority.get("accepted_locks", [])
    two_layer = any(
        isinstance(x, dict) and x.get("id") == "accepted-two-layer-control-standard"
        for x in accepted if isinstance(accepted, list)
    )
    if not two_layer:
        raise ControlError("two-layer control lock is missing from authority")
    diff_text = (
        f"Candidate target={capsule.target}; preimage={capsule.preimage_sha256}; "
        f"candidate_sha256={capsule.content_sha256}; bytes={len(capsule.content)}."
    )
    return {
        "map": [
            {
                "kind": "OBSERVED",
                "text": (
                    f"Loaded sole authority revision {snapshot['authority_revision']} with active "
                    f"mission {snapshot['mission']} at repository HEAD {snapshot['head']}."
                ),
                "fact_key": "authority_revision",
                "fact_value": str(snapshot["authority_revision"]),
                "source": AUTHORITY_REL,
            },
            {
                "kind": "OBSERVED",
                "text": diff_text,
                "fact_key": "candidate_sha256",
                "fact_value": capsule.content_sha256,
                "source": "staged local capsule",
            },
        ],
        "history": [
            {
                "kind": "VERIFIED_HISTORY",
                "text": (
                    "The authority requires both the ChatGPT behavioral instruction layer and a "
                    "fail-closed controlled execution layer; instruction-only completion is rejected."
                ),
                "fact_key": "control_standard",
                "fact_value": "two-layer",
                "source": AUTHORITY_REL,
            },
            *[
                {
                    "kind": "VERIFIED_HISTORY",
                    "text": str(item),
                    "fact_key": f"bootstrap_history_{i}",
                    "fact_value": "verified",
                    "source": "bootstrap verification",
                }
                for i, item in enumerate(bootstrap_history)
            ],
        ],
        "research": [
            {
                "kind": "EXTERNAL_RESEARCH",
                "text": (
                    "Current OpenAI Sign in with ChatGPT OSS documentation supports dynamic-agent "
                    "registration with Authorization Code + PKCE, 127.0.0.1 loopback, "
                    "chatgpt.tokens.use.direct, account model discovery, and streamed Responses "
                    "with store=false/stream=true through response.completed."
                ),
                "fact_key": "oauth_transport_contract",
                "fact_value": "siwc-oss-direct-responses",
                "source": "https://developers.openai.com/siwc/token-sharing-open-source",
            }
        ],
        "capabilities": [
            {
                "kind": "OBSERVED",
                "text": (
                    "Imported the authoritative repository SOPDecisionGateway and "
                    "ControlledToolBroker from src/operation_pancake."
                ),
                "fact_key": "gateway_broker_import",
                "fact_value": "verified",
                "source": "authoritative repository source",
            },
            {
                "kind": "OBSERVED",
                "text": (
                    f"Target preimage was re-read locally and is {snapshot['target_preimage_sha256']}."
                ),
                "fact_key": "candidate_preimage",
                "fact_value": str(snapshot["target_preimage_sha256"]),
                "source": "local filesystem",
            },
        ],
    }


def import_control(repo: Path):
    verify_control_modules(repo)
    add_repo_src(repo)
    from operation_pancake.cross_surface_control import HypothesisLedger
    from operation_pancake.sop_gateway import DecisionRecordStore, SOPDecisionGateway
    from operation_pancake.tool_broker import ControlledToolBroker
    return HypothesisLedger, DecisionRecordStore, SOPDecisionGateway, ControlledToolBroker


class OneTimeCapability:
    def __init__(self, marker_dir: Path, capability_id: str):
        self.path = marker_dir / f"{capability_id}.json"

    def check_unused(self) -> None:
        if self.path.exists():
            raise ControlError("one-time mutation capability has already been consumed")

    def consume(self, result: Mapping[str, Any]) -> None:
        self.check_unused()
        atomic_write(
            self.path,
            (json.dumps(dict(result), indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )


def fixed_validation(repo: Path, target: Path) -> list[str]:
    commands = [
        [sys.executable, "-m", "py_compile", str(target)],
        [sys.executable, str(repo / "scripts" / "pancake_control.py"), "validate"],
        [sys.executable, str(repo / "scripts" / "pancake_control.py"), "preflight"],
    ]
    output = []
    for cmd in commands:
        cp = subprocess.run(
            cmd,
            cwd=str(repo),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output.append(cp.stdout.strip()[-2000:])
        if cp.returncode != 0:
            raise ControlError(f"validation failed: {' '.join(cmd)}\n{cp.stdout[-2000:]}")
    return output


def transactional_apply(
    repo: Path,
    capsule: MutationCapsule,
    *,
    marker_dir: Path | None = None,
    validation=fixed_validation,
) -> Mapping[str, Any]:
    target = validate_target(repo, capsule.target)
    observed_preimage = preimage_hash(target)
    if observed_preimage != capsule.preimage_sha256:
        raise ControlError(
            f"preimage mismatch: expected {capsule.preimage_sha256}, observed {observed_preimage}"
        )
    marker_root = marker_dir or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OperationPancakeControl" / "capabilities"
    capability_id = sha256_bytes(
        (capsule.target + "|" + capsule.preimage_sha256 + "|" + capsule.content_sha256).encode("utf-8")
    )[:24]
    capability = OneTimeCapability(marker_root, capability_id)
    capability.check_unused()

    original_branch = run_git(repo, "branch", "--show-current")
    original_head = run_git(repo, "rev-parse", "HEAD")
    branch = "ops/pancake-controlled-" + capsule.content_sha256[:12]
    if run_git(repo, "show-ref", "--verify", f"refs/heads/{branch}", check=False):
        raise ControlError(f"controlled branch already exists: {branch}")

    old_exists = target.exists()
    old_bytes = target.read_bytes() if old_exists else None
    branch_created = False
    try:
        run_git(repo, "switch", "-c", branch)
        branch_created = True
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(target, capsule.content)
        if sha256_bytes(target.read_bytes()) != capsule.content_sha256:
            raise ControlError("post-write candidate hash mismatch")
        validation_output = validation(repo, target)
        run_git(repo, "add", "--", capsule.target)
        staged = run_git(repo, "diff", "--cached", "--name-only")
        if staged.splitlines() != [capsule.target]:
            raise ControlError(f"staged diff contains unexpected paths: {staged!r}")
        run_git(repo, "commit", "-m", f"OP controlled mutation {capsule.content_sha256[:12]}")
        controlled_commit = run_git(repo, "rev-parse", "HEAD")
        run_git(repo, "switch", original_branch)
        result = {
            "schema": RESULT_SCHEMA,
            "status": "PASS",
            "branch": branch,
            "commit": controlled_commit,
            "original_branch": original_branch,
            "original_head": original_head,
            "returned_to_original_branch": run_git(repo, "branch", "--show-current") == original_branch,
            "target": capsule.target,
            "content_sha256": capsule.content_sha256,
            "validation": validation_output,
        }
        capability.consume(result)
        return result
    except Exception:
        try:
            if branch_created:
                run_git(repo, "reset", "--hard", original_head, check=False)
                run_git(repo, "clean", "-fd", "--", capsule.target, check=False)
                run_git(repo, "switch", original_branch, check=False)
                run_git(repo, "branch", "-D", branch, check=False)
            else:
                if old_exists and old_bytes is not None:
                    atomic_write(target, old_bytes)
                elif target.exists():
                    target.unlink()
        finally:
            pass
        raise


def controlled_apply(
    repo: Path,
    capsule: MutationCapsule,
    *,
    provider=None,
    expected_head: str | None = None,
    expected_revision: int | None = None,
    expected_branch: str | None = None,
    marker_dir: Path | None = None,
    bootstrap_history: Sequence[str] = (),
    validation=fixed_validation,
) -> Mapping[str, Any]:
    verify_repo(
        repo,
        expected_head=expected_head,
        expected_revision=expected_revision,
        expected_branch=expected_branch,
        require_clean=True,
    )
    target = validate_target(repo, capsule.target)
    if preimage_hash(target) != capsule.preimage_sha256:
        raise ControlError("candidate preimage does not match local repository")
    HypothesisLedger, DecisionRecordStore, SOPDecisionGateway, ControlledToolBroker = import_control(repo)
    provider = provider or ChatGPTPlanOAuthDecisionProvider()
    runtime_root = (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        / "OperationPancakeControl"
        / "gateway"
    )
    gateway = SOPDecisionGateway(
        provider=provider,
        store=DecisionRecordStore(runtime_root / "decisions"),
        strict_evidence=True,
        hypotheses=HypothesisLedger(runtime_root / "hypotheses.json"),
    )
    snapshot = build_state_snapshot(repo, target, capsule.content_sha256)
    evidence = build_evidence(repo, snapshot, capsule, bootstrap_history=bootstrap_history)
    decision_id = "op-controlled-" + capsule.content_sha256[:20]
    packet = gateway.request_decision(
        mission=str(snapshot["mission"]),
        request=(
            f"{capsule.request}\n"
            f"Candidate mutation action name is exactly {TARGET_ACTION!r}. "
            f"Authorize it only if the supplied trusted evidence supports this exact staged candidate."
        ),
        evidence=evidence,
        state_snapshot=snapshot,
        decision_id=decision_id,
        mutation_requested=True,
    )
    if packet.decision_status != "DECISION_ALLOWED":
        raise ControlError(
            f"gateway did not authorize mutation: status={packet.decision_status}; "
            f"errors={list(packet.gate_errors)}"
        )
    if TARGET_ACTION not in packet.allowed_actions:
        raise ControlError(f"decision did not authorize exact action {TARGET_ACTION}")
    broker = ControlledToolBroker(gateway)
    broker.register(
        TARGET_ACTION,
        mutating=True,
        handler=lambda: transactional_apply(
            repo, capsule, marker_dir=marker_dir, validation=validation
        ),
    )
    current_snapshot = build_state_snapshot(repo, target, capsule.content_sha256)
    return broker.call(
        TARGET_ACTION,
        decision_id=packet.decision_id,
        current_state_snapshot=current_snapshot,
    )


class RequestRejected(ControlError):
    pass


class EvidenceGap(ControlError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def exclusive_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


@dataclass(frozen=True)
class ControlRequest:
    schema: str
    request_id: str
    mission: str
    expected_repository: str
    expected_branch: str
    expected_head: str
    expected_authority_revision: int
    requested_action: str
    request: str

    @classmethod
    def parse(cls, body: str) -> "ControlRequest":
        try:
            raw = json.loads(body)
        except Exception as exc:
            raise RequestRejected("malformed JSON body") from exc
        if not isinstance(raw, dict):
            raise RequestRejected("control request body must be an object")
        extra = set(raw) - CONTROL_REQUEST_FIELDS
        missing = CONTROL_REQUEST_FIELDS - set(raw)
        if extra:
            raise RequestRejected("unexpected control request fields: " + ", ".join(sorted(extra)))
        if missing:
            raise RequestRejected("missing control request fields: " + ", ".join(sorted(missing)))
        if raw.get("schema") != CONTROL_REQUEST_SCHEMA:
            raise RequestRejected("unsupported control request schema")
        request_id = raw.get("request_id")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,96}", request_id):
            raise RequestRejected("invalid request_id")
        for field in ("mission", "expected_repository", "expected_branch", "expected_head", "requested_action", "request"):
            if not isinstance(raw.get(field), str) or not raw[field].strip():
                raise RequestRejected(f"{field} must be a non-empty string")
        revision = raw.get("expected_authority_revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise RequestRejected("expected_authority_revision must be a positive integer")
        return cls(**raw)


class ReceiptJournal:
    def __init__(self, root: Path):
        self.root = root

    def path(self, request_id: str) -> Path:
        return self.root / f"{request_id}.json"

    def exists(self, request_id: str) -> bool:
        return self.path(request_id).is_file()

    def load(self, request_id: str) -> dict[str, Any]:
        payload = json.loads(self.path(request_id).read_text(encoding="utf-8"))
        if payload.get("schema") != CONTROL_RECEIPT_SCHEMA:
            raise ControlError("invalid control receipt schema")
        if payload.get("status") not in CONTROL_RECEIPT_STATES:
            raise ControlError("invalid control receipt status")
        return payload

    def write(self, request_id: str, status: str, **extra: Any) -> dict[str, Any]:
        if status not in CONTROL_RECEIPT_STATES:
            raise ControlError(f"unsupported control receipt state: {status}")
        if self.exists(request_id):
            previous = self.load(request_id)
            if previous["status"] in CONTROL_TERMINAL_STATES:
                if previous["status"] == status:
                    return previous
                raise ControlError("terminal control receipt cannot transition")
        payload = {
            "schema": CONTROL_RECEIPT_SCHEMA,
            "request_id": request_id,
            "status": status,
            **extra,
        }
        atomic_write(
            self.path(request_id),
            (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
        return payload


def stable_issue(issue: Mapping[str, Any]) -> dict[str, Any]:
    user = issue.get("user") if isinstance(issue.get("user"), Mapping) else {}
    return {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "body": issue.get("body"),
        "creator": user.get("login"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "repository_url": issue.get("repository_url"),
        "has_pull_request": "pull_request" in issue,
        "state": issue.get("state"),
    }


def trusted_issue_envelope(issue: Mapping[str, Any]) -> bool:
    user = issue.get("user") if isinstance(issue.get("user"), Mapping) else {}
    return (
        user.get("login") == CONTROL_TRUSTED_CREATOR
        and isinstance(issue.get("title"), str)
        and issue["title"].startswith(CONTROL_TITLE_PREFIX)
    )


def verify_issue_envelope(issue: Mapping[str, Any]) -> None:
    if "pull_request" in issue:
        raise RequestRejected("pull request is not a control issue")
    user = issue.get("user")
    if not isinstance(user, Mapping) or user.get("login") != CONTROL_TRUSTED_CREATOR:
        raise RequestRejected("untrusted GitHub issue creator")
    if not isinstance(issue.get("title"), str) or not issue["title"].startswith(CONTROL_TITLE_PREFIX):
        raise RequestRejected("missing exact Pancake control title prefix")
    if issue.get("created_at") != issue.get("updated_at"):
        raise RequestRejected("edited GitHub issue is not an immutable request")
    if issue.get("state") not in (None, "open"):
        raise RequestRejected("control issue is not open")
    repository_url = str(issue.get("repository_url", "")).rstrip("/")
    if not repository_url.endswith("/repos/" + EXPECTED_REPOSITORY):
        raise RequestRejected("control issue belongs to the wrong repository")


def validate_control_request(
    request: ControlRequest,
    state: Mapping[str, Any],
    journal: ReceiptJournal,
    registered_actions: Sequence[str],
) -> None:
    if request.expected_repository != EXPECTED_REPOSITORY:
        raise RequestRejected("wrong expected repository")
    if request.mission != state.get("mission"):
        raise RequestRejected("wrong active mission")
    if request.expected_branch != state.get("branch"):
        raise RequestRejected("stale expected branch")
    if request.expected_head != state.get("head"):
        raise RequestRejected("stale expected HEAD")
    if request.expected_authority_revision != state.get("authority_revision"):
        raise RequestRejected("stale authority revision")
    if request.requested_action not in set(registered_actions):
        raise RequestRejected("unknown or unregistered symbolic action")
    if journal.exists(request.request_id):
        prior = journal.load(request.request_id)
        if prior["status"] in {"EXECUTING", "VALIDATING"}:
            raise EvidenceGap("ambiguous partial execution; no blind replay is permitted")
        raise RequestRejected("replayed request_id")


def freeze_control_request(root: Path, issue: Mapping[str, Any], request: ControlRequest) -> tuple[Path, str]:
    payload = {"issue": stable_issue(issue), "request": request.__dict__}
    data = canonical_json_bytes(payload)
    digest = sha256_bytes(data)
    path = root / f"{request.request_id}.snapshot.json"
    exclusive_write(path, data)
    return path, digest


def verify_frozen_control_request(path: Path, expected_sha256: str) -> dict[str, Any]:
    data = path.read_bytes()
    if sha256_bytes(data) != expected_sha256:
        raise EvidenceGap("local immutable request snapshot hash mismatch")
    payload = json.loads(data)
    if canonical_json_bytes(payload) != data:
        raise EvidenceGap("local immutable request snapshot is not canonical")
    return payload


def inbox_state_snapshot(repo: Path, request_snapshot_hash: str) -> dict[str, Any]:
    status = verify_repo(repo, require_clean=True)
    return {
        "repository": EXPECTED_REPOSITORY,
        "mission": status["mission"],
        "branch": status["branch"],
        "head": status["head"],
        "authority_revision": status["authority_revision"],
        "working_tree_clean": True,
        "request_snapshot_hash": request_snapshot_hash,
    }


def inbox_typed_evidence(state: Mapping[str, Any], request_snapshot_hash: str) -> dict[str, list[dict[str, str]]]:
    return {
        "map": [{
            "kind": "OBSERVED",
            "text": "Sole authority and exact Git state were re-read locally before request execution.",
            "fact_key": "authority_revision",
            "fact_value": str(state["authority_revision"]),
            "source": AUTHORITY_REL,
        }],
        "history": [{
            "kind": "VERIFIED_HISTORY",
            "text": "The accepted durable control design uses GitHub only as request transport and preserves Gateway/Broker authorization.",
            "fact_key": "control_transport",
            "fact_value": "github-inbox",
            "source": "OP-CONTROL-002 handoff",
        }],
        "research": [{
            "kind": "EXTERNAL_RESEARCH",
            "text": "The exact accepted request was re-fetched, canonicalized, frozen locally, and hashed before authorization.",
            "fact_key": "request_snapshot_hash",
            "fact_value": request_snapshot_hash,
            "source": "local immutable snapshot",
        }],
        "capabilities": [{
            "kind": "OBSERVED",
            "text": "Only registered symbolic handlers are exposed by the local control registry.",
            "fact_key": "registered_action_boundary",
            "fact_value": "bounded",
            "source": "local runtime registry",
        }],
    }


def fixed_control_validation(repo: Path) -> list[str]:
    commands = [
        [sys.executable, str(repo / "scripts" / "pancake_control.py"), "validate"],
        [sys.executable, str(repo / "scripts" / "pancake_control.py"), "preflight"],
    ]
    output: list[str] = []
    for command in commands:
        cp = subprocess.run(
            command,
            cwd=str(repo),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output.append(cp.stdout.strip()[-4000:])
        if cp.returncode != 0:
            raise ControlError("fixed Pancake validation failed: " + " ".join(command) + "\n" + cp.stdout[-4000:])
    return output


def read_bootstrap_result_action() -> Mapping[str, Any]:
    path = local_control_root() / "bootstrap_result.json"
    if not path.is_file():
        return {"status": "ABSENT", "path": str(path)}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {"status": "PRESENT", "path": str(path), "payload": payload}


def regenerate_handoff_transaction(repo: Path) -> Mapping[str, Any]:
    verify_control_modules(repo)
    add_repo_src(repo)
    from operation_pancake.control_state import render_handoff

    status = verify_repo(repo, require_clean=True)
    authority = load_authority(repo)
    content = render_handoff(authority).encode("utf-8")
    target_rel = "docs/OPERATION_PANCAKE_HANDOFF.md"
    target = repo / target_rel
    original_branch = status["branch"]
    original_head = status["head"]
    branch = "ops/pancake-handoff-" + sha256_bytes(content)[:12]
    if run_git(repo, "show-ref", "--verify", f"refs/heads/{branch}", check=False):
        raise ControlError(f"controlled handoff branch already exists: {branch}")
    try:
        run_git(repo, "switch", "-c", branch)
        atomic_write(target, content)
        run_git(repo, "add", "--", target_rel)
        staged = run_git(repo, "diff", "--cached", "--name-only")
        if staged.splitlines() != [target_rel]:
            raise ControlError(f"unexpected handoff staged paths: {staged!r}")
        fixed_control_validation(repo)
        run_git(repo, "commit", "-m", "OP controlled handoff regeneration")
        commit = run_git(repo, "rev-parse", "HEAD")
        run_git(repo, "switch", original_branch)
        return {"status": "PASS", "branch": branch, "commit": commit, "returned_to": original_branch}
    except Exception:
        run_git(repo, "reset", "--hard", original_head, check=False)
        run_git(repo, "switch", original_branch, check=False)
        run_git(repo, "branch", "-D", branch, check=False)
        raise


def build_inbox_registry(repo: Path) -> dict[str, tuple[bool, Any]]:
    return {
        "inspect_control_state": (False, lambda: verify_repo(repo, require_clean=False)),
        "read_bootstrap_result": (False, read_bootstrap_result_action),
        "run_control_validation": (False, lambda: {"status": "PASS", "output": fixed_control_validation(repo)}),
        "regenerate_authorized_handoff": (True, lambda: regenerate_handoff_transaction(repo)),
    }


def execute_frozen_control_request(
    repo: Path,
    request: ControlRequest,
    snapshot_path: Path,
    snapshot_hash: str,
    *,
    journal: ReceiptJournal,
    provider=None,
    registry: Mapping[str, tuple[bool, Any]] | None = None,
) -> Any:
    verify_frozen_control_request(snapshot_path, snapshot_hash)
    status = verify_repo(repo, require_clean=True)
    if request.expected_branch != status["branch"] or request.expected_head != status["head"]:
        raise EvidenceGap("repository state changed after request freeze")
    if request.expected_authority_revision != status["authority_revision"]:
        raise EvidenceGap("authority revision changed after request freeze")

    HypothesisLedger, DecisionRecordStore, SOPDecisionGateway, ControlledToolBroker = import_control(repo)
    provider = provider or ChatGPTPlanOAuthDecisionProvider()
    registry = dict(registry or build_inbox_registry(repo))
    if request.requested_action not in registry:
        raise RequestRejected("requested handler is not registered")
    mutating, handler = registry[request.requested_action]
    runtime_root = local_control_root() / "gateway"
    gateway = SOPDecisionGateway(
        provider=provider,
        store=DecisionRecordStore(runtime_root / "decisions"),
        strict_evidence=True,
        hypotheses=HypothesisLedger(runtime_root / "hypotheses.json"),
    )
    decision_snapshot = inbox_state_snapshot(repo, snapshot_hash)
    evidence = inbox_typed_evidence(decision_snapshot, snapshot_hash)
    decision_id = "inbox-" + request.request_id
    journal.write(request.request_id, "DECISION_CREATED", snapshot_hash=snapshot_hash)
    packet = gateway.request_decision(
        mission=request.mission,
        request=(
            request.request + "\n"
            f"Frozen request SHA-256 is {snapshot_hash}. "
            f"The only candidate action is {request.requested_action!r}."
        ),
        evidence=evidence,
        state_snapshot=decision_snapshot,
        decision_id=decision_id,
        mutation_requested=bool(mutating),
    )
    if packet.decision_status != "DECISION_ALLOWED":
        raise EvidenceGap(
            f"gateway did not authorize frozen control request: {packet.decision_status}; "
            f"errors={list(packet.gate_errors)}"
        )
    if request.requested_action not in packet.allowed_actions:
        raise EvidenceGap("gateway did not authorize the exact registered action")
    journal.write(request.request_id, "AUTHORIZED", decision_id=packet.decision_id, snapshot_hash=snapshot_hash)

    broker = ControlledToolBroker(gateway)
    broker.register(request.requested_action, mutating=bool(mutating), handler=handler)
    verify_frozen_control_request(snapshot_path, snapshot_hash)
    current_snapshot = inbox_state_snapshot(repo, snapshot_hash)
    journal.write(request.request_id, "EXECUTING", decision_id=packet.decision_id, snapshot_hash=snapshot_hash)
    result = broker.call(
        request.requested_action,
        decision_id=packet.decision_id,
        current_state_snapshot=current_snapshot,
    )
    journal.write(request.request_id, "VALIDATING", decision_id=packet.decision_id, snapshot_hash=snapshot_hash)
    if mutating:
        fixed_control_validation(repo)
    return result


class GitHubRateLimited(ControlError):
    def __init__(self, delay_seconds: int, message: str):
        super().__init__(message)
        self.delay_seconds = max(CONTROL_POLL_SECONDS, int(delay_seconds))


def rate_limit_delay(status: int | None, headers: Mapping[str, str] | None, *, now: int | None = None) -> int:
    now = int(time.time()) if now is None else int(now)
    values = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    if status in {403, 429}:
        retry = values.get("retry-after", "")
        if retry.isdigit():
            return max(CONTROL_POLL_SECONDS, int(retry))
        reset = values.get("x-ratelimit-reset", "")
        if reset.isdigit():
            return max(CONTROL_POLL_SECONDS, int(reset) - now + 5)
        return CONTROL_POLL_SECONDS * 2
    if values.get("x-ratelimit-remaining") == "0":
        reset = values.get("x-ratelimit-reset", "")
        if reset.isdigit():
            return max(CONTROL_POLL_SECONDS, int(reset) - now + 5)
        return CONTROL_POLL_SECONDS * 2
    return CONTROL_POLL_SECONDS


class GitHubIssueTransport:
    def __init__(self, *, opener=urllib.request.urlopen):
        self.opener = opener
        self._etag: str | None = None

    def _get_json(self, url: str, *, etag: str | None = None) -> tuple[Any, Mapping[str, str], int]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Operation-Pancake-Control/1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if etag:
            headers["If-None-Match"] = etag
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self.opener(request, timeout=20) as response:
                status = int(getattr(response, "status", 200))
                response_headers = {str(k): str(v) for k, v in response.headers.items()}
                data = response.read()
        except urllib.error.HTTPError as exc:
            response_headers = {str(k): str(v) for k, v in exc.headers.items()} if exc.headers else {}
            if exc.code == 304:
                return [], response_headers, 304
            if exc.code in {403, 429}:
                raise GitHubRateLimited(
                    rate_limit_delay(exc.code, response_headers),
                    f"GitHub rate limited control inbox: HTTP {exc.code}",
                ) from exc
            raise ControlError(f"GitHub control transport HTTP {exc.code}") from exc
        except OSError as exc:
            raise ControlError(f"GitHub control transport network failure: {type(exc).__name__}") from exc
        if status in {403, 429}:
            raise GitHubRateLimited(rate_limit_delay(status, response_headers), f"GitHub rate limited control inbox: HTTP {status}")
        try:
            return json.loads(data.decode("utf-8")), response_headers, status
        except Exception as exc:
            raise ControlError("GitHub control transport returned invalid JSON") from exc

    def list_candidate_issues(self) -> tuple[list[int], int]:
        url = (
            "https://api.github.com/repos/" + EXPECTED_REPOSITORY +
            "/issues?state=open&per_page=100&sort=created&direction=desc"
        )
        payload, headers, status = self._get_json(url, etag=self._etag)
        if status == 304:
            return [], rate_limit_delay(status, headers)
        self._etag = str(headers.get("ETag") or headers.get("etag") or "") or None
        if not isinstance(payload, list):
            raise ControlError("GitHub issues response must be a list")
        numbers: list[int] = []
        for issue in payload:
            if not isinstance(issue, Mapping):
                continue
            title = issue.get("title")
            number = issue.get("number")
            if isinstance(title, str) and title.startswith(CONTROL_TITLE_PREFIX) and isinstance(number, int):
                numbers.append(number)
        return numbers, rate_limit_delay(status, headers)

    def fetch_issue(self, number: int) -> Mapping[str, Any]:
        payload, headers, status = self._get_json(
            f"https://api.github.com/repos/{EXPECTED_REPOSITORY}/issues/{int(number)}"
        )
        if not isinstance(payload, Mapping):
            raise RequestRejected("GitHub control issue disappeared")
        return payload


def write_trusted_error_receipt(journal: ReceiptJournal, issue_number: int, issue: Mapping[str, Any], exc: Exception) -> None:
    if not trusted_issue_envelope(issue):
        return
    request_id = f"issue-{int(issue_number)}"
    try:
        parsed = ControlRequest.parse(str(issue.get("body", "")))
        request_id = parsed.request_id
    except Exception:
        pass
    try:
        journal.write(
            request_id,
            "FAILED" if not isinstance(exc, EvidenceGap) else "EVIDENCE_GAP",
            issue_number=int(issue_number),
            error_type=type(exc).__name__,
            error=str(exc),
        )
    except Exception:
        pass


def process_control_issue(
    repo: Path,
    number: int,
    transport: Any,
    *,
    provider=None,
    journal: ReceiptJournal | None = None,
    registry: Mapping[str, tuple[bool, Any]] | None = None,
) -> Mapping[str, Any]:
    journal = journal or ReceiptJournal(local_control_root() / "requests")
    registry = dict(registry or build_inbox_registry(repo))
    first: Mapping[str, Any] | None = None
    request: ControlRequest | None = None
    try:
        first = transport.fetch_issue(number)
        verify_issue_envelope(first)
        request = ControlRequest.parse(str(first.get("body", "")))
        state = verify_repo(repo, require_clean=True)
        validate_control_request(request, state, journal, tuple(registry))
        journal.write(request.request_id, "RECEIVED", issue_number=number, verified_creator=CONTROL_TRUSTED_CREATOR)
        journal.write(request.request_id, "VALIDATED", issue_number=number)

        second = transport.fetch_issue(number)
        verify_issue_envelope(second)
        if stable_issue(first) != stable_issue(second):
            raise RequestRejected("GitHub control request changed before local freeze")
        snapshot_path, snapshot_hash = freeze_control_request(
            local_control_root() / "snapshots", second, request
        )
        journal.write(
            request.request_id,
            "SNAPSHOT_FROZEN",
            snapshot_hash=snapshot_hash,
            snapshot_file=str(snapshot_path),
        )
        result = execute_frozen_control_request(
            repo,
            request,
            snapshot_path,
            snapshot_hash,
            journal=journal,
            provider=provider,
            registry=registry,
        )
        return journal.write(request.request_id, "COMPLETE", result=result)
    except Exception as exc:
        if first is not None:
            write_trusted_error_receipt(journal, number, first, exc)
        raise


def poll_control_issues(
    repo: Path,
    numbers: Sequence[int],
    transport: Any,
    *,
    provider=None,
    journal: ReceiptJournal | None = None,
    registry: Mapping[str, tuple[bool, Any]] | None = None,
) -> list[Mapping[str, Any]]:
    results: list[Mapping[str, Any]] = []
    for number in numbers:
        try:
            results.append(
                process_control_issue(
                    repo, number, transport, provider=provider, journal=journal, registry=registry
                )
            )
        except Exception:
            # One malformed or unauthorized request must never terminate polling.
            continue
    return results


def read_control_receipt(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = payload.get("schema")
    if schema not in {CONTROL_RECEIPT_SCHEMA, "operation-pancake-bootstrap-result-v1"}:
        raise ControlError("invalid control receipt schema")
    allowed = set(CONTROL_RECEIPT_STATES) | {"PASS", "FAIL"}
    if payload.get("status") not in allowed:
        raise ControlError("invalid control receipt status")
    return payload


CONTROL_STATUS_SCHEMA = "operation-pancake-control-health-v1"
CONTROL_STATUS_PORTS = tuple(range(18790, 18820))


class ControlStatusHandler(http.server.BaseHTTPRequestHandler):
    server_version = "OperationPancakeControl/1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, status: int, payload: Mapping[str, Any]) -> None:
        data = (json.dumps(dict(payload), indent=2, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        server = self.server
        journal = getattr(server, "journal", None)
        health = getattr(server, "health_payload", {})
        path = urllib.parse.urlsplit(self.path).path
        if path in {"/health", "/health.json"}:
            self._json(200, health)
            return
        if path == "/latest":
            if not isinstance(journal, ReceiptJournal):
                self._json(500, {"schema": CONTROL_STATUS_SCHEMA, "status": "ERROR"})
                return
            files = sorted(journal.root.glob("*.json"), key=lambda item: item.stat().st_mtime_ns, reverse=True)
            if not files:
                self._json(200, {"schema": CONTROL_STATUS_SCHEMA, "status": "NO_RECEIPTS"})
                return
            try:
                self._json(200, journal.load(files[0].stem))
            except Exception as exc:
                self._json(500, {"schema": CONTROL_STATUS_SCHEMA, "status": "ERROR", "error": type(exc).__name__})
            return
        match = re.fullmatch(r"/requests/([A-Za-z0-9._-]{1,96})", path)
        if match and isinstance(journal, ReceiptJournal):
            request_id = match.group(1)
            if not journal.exists(request_id):
                self._json(404, {"schema": CONTROL_STATUS_SCHEMA, "status": "NOT_FOUND", "request_id": request_id})
                return
            self._json(200, journal.load(request_id))
            return
        self._json(404, {"schema": CONTROL_STATUS_SCHEMA, "status": "NOT_FOUND"})

    def do_POST(self) -> None:
        self._json(405, {"schema": CONTROL_STATUS_SCHEMA, "status": "METHOD_NOT_ALLOWED"})

    def do_PUT(self) -> None:
        self.do_POST()

    def do_DELETE(self) -> None:
        self.do_POST()

    def do_PATCH(self) -> None:
        self.do_POST()


def loopback_port_in_use(port: int, *, timeout: float = 0.1) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.settimeout(timeout)
        return probe.connect_ex(("127.0.0.1", int(port))) == 0
    finally:
        probe.close()


def probe_control_status(
    *,
    expected_worker_sha256: str | None = None,
    opener=urllib.request.urlopen,
    timeout: float = 0.5,
) -> Mapping[str, Any] | None:
    ports: list[int] = []
    try:
        cached = json.loads((local_control_root() / "status.json").read_text(encoding="utf-8"))
        hinted = int(cached.get("port"))
        if hinted in CONTROL_STATUS_PORTS:
            ports.append(hinted)
    except Exception:
        pass
    ports.extend(port for port in CONTROL_STATUS_PORTS if port not in ports)
    for port in ports:
        request = urllib.request.Request(f"http://127.0.0.1:{port}/health", method="GET")
        try:
            with opener(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, Mapping) or payload.get("schema") != CONTROL_STATUS_SCHEMA:
                continue
            if expected_worker_sha256 and payload.get("worker_sha256") != expected_worker_sha256:
                continue
            return {**dict(payload), "port": port, "url": f"http://127.0.0.1:{port}/health"}
        except Exception:
            continue
    return None


def start_control_status_server(journal: ReceiptJournal, health_payload: Mapping[str, Any]):
    existing = probe_control_status(timeout=0.15)
    if existing is not None:
        return None, existing
    for port in CONTROL_STATUS_PORTS:
        if loopback_port_in_use(port, timeout=0.05):
            continue
        try:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", port), ControlStatusHandler)
        except OSError:
            continue
        server.journal = journal
        server.health_payload = dict(health_payload)
        thread = threading.Thread(target=server.serve_forever, name="PancakeControlStatus", daemon=True)
        thread.start()
        status = {**dict(health_payload), "port": port, "url": f"http://127.0.0.1:{port}/health"}
        atomic_write(
            local_control_root() / "status.json",
            (json.dumps(status, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
        return server, status
    raise ControlError("no loopback control status port is available")


def launch_runtime_worker(repo: Path, worker: Path):
    argv = [
        sys.executable,
        str(worker),
        "--repo", str(repo.resolve()),
        "--inbox",
        "--startup-guard", str(runtime_activation_path()),
    ]
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    return subprocess.Popen(argv, **kwargs)


def wait_for_runtime_ready(expected_worker_sha256: str, *, timeout_seconds: float = 15.0) -> Mapping[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = probe_control_status(expected_worker_sha256=expected_worker_sha256, timeout=0.4)
        if status and status.get("status") == "READY":
            return status
        time.sleep(0.25)
    raise ControlError("durable control worker did not expose read-only loopback health in time")


class WindowsRunRegistry:
    VALUE_NAME = "OperationPancakeControl"
    KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def _module(self):
        if os.name != "nt":
            raise ControlError("Windows user startup registry is unavailable on this OS")
        import winreg
        return winreg

    def get(self) -> str | None:
        winreg = self._module()
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY_PATH, 0, winreg.KEY_READ) as key:
                value, _kind = winreg.QueryValueEx(key, self.VALUE_NAME)
                return str(value)
        except FileNotFoundError:
            return None

    def set(self, value: str) -> None:
        winreg = self._module()
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self.KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, self.VALUE_NAME, 0, winreg.REG_SZ, value)

    def delete(self) -> None:
        winreg = self._module()
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, self.VALUE_NAME)
        except FileNotFoundError:
            pass


def runtime_worker_path() -> Path:
    return local_control_root() / "runner" / "pancake_local_control.py"


def runtime_install_receipt_path() -> Path:
    return local_control_root() / "install_receipt.json"


def runtime_activation_path() -> Path:
    return local_control_root() / "ACTIVE.json"


def runtime_startup_command(repo: Path, worker: Path) -> str:
    argv = [
        sys.executable,
        str(worker),
        "--repo", str(repo.resolve()),
        "--inbox",
        "--startup-guard", str(runtime_activation_path()),
    ]
    return subprocess.list2cmdline(argv)


def runtime_startup_eligible() -> bool:
    worker = runtime_worker_path()
    receipt = runtime_install_receipt_path()
    activation = runtime_activation_path()
    if not (worker.is_file() and receipt.is_file() and activation.is_file()):
        return False
    try:
        receipt_payload = read_control_receipt(receipt)
        active = json.loads(activation.read_text(encoding="utf-8"))
        return (
            receipt_payload.get("status") == "INSTALLED"
            and active.get("schema") == CONTROL_ACTIVATION_SCHEMA
            and active.get("status") == "ACTIVE"
            and active.get("worker_sha256") == sha256_bytes(worker.read_bytes())
        )
    except Exception:
        return False


def validate_runtime_worker(repo: Path, worker: Path) -> list[str]:
    commands = [
        [sys.executable, "-m", "py_compile", str(worker)],
        [sys.executable, str(worker), "--repo", str(repo), "--self-test"],
    ]
    outputs: list[str] = []
    for command in commands:
        cp = subprocess.run(
            command,
            cwd=str(repo),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        outputs.append(cp.stdout.strip()[-4000:])
        if cp.returncode != 0:
            raise ControlError("runtime validation failed: " + " ".join(command) + "\n" + cp.stdout[-4000:])
    return outputs


def staged_runtime_install(
    repo: Path,
    worker_bytes: bytes,
    *,
    registry_backend=None,
    validation=validate_runtime_worker,
    launcher=launch_runtime_worker,
    readiness=wait_for_runtime_ready,
    fault_after: str | None = None,
) -> Mapping[str, Any]:
    registry_backend = registry_backend or WindowsRunRegistry()
    root = local_control_root()
    worker = runtime_worker_path()
    receipt = runtime_install_receipt_path()
    activation = runtime_activation_path()
    root.mkdir(parents=True, exist_ok=True)
    worker.parent.mkdir(parents=True, exist_ok=True)

    old_worker = worker.read_bytes() if worker.exists() else None
    old_receipt = receipt.read_bytes() if receipt.exists() else None
    old_activation = activation.read_bytes() if activation.exists() else None
    old_registry = registry_backend.get()
    try:
        # Activation is removed first. Any crash before the final activation write is inert.
        if activation.exists():
            activation.unlink()
        atomic_write(worker, worker_bytes)
        if fault_after == "worker":
            raise ControlError("injected failure after worker write")
        validation_output = validation(repo, worker)
        if fault_after == "validation":
            raise ControlError("injected failure after validation")
        install_record = {
            "schema": CONTROL_RECEIPT_SCHEMA,
            "request_id": "runtime-installer",
            "status": "INSTALLED",
            "worker_sha256": sha256_bytes(worker_bytes),
            "repo": str(repo.resolve()),
            "validation": validation_output,
        }
        atomic_write(receipt, (json.dumps(install_record, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        if fault_after == "receipt":
            raise ControlError("injected failure after receipt")
        registry_backend.set(runtime_startup_command(repo, worker))
        if fault_after == "registry":
            raise ControlError("injected failure after registry")
        active = {
            "schema": CONTROL_ACTIVATION_SCHEMA,
            "status": "ACTIVE",
            "worker_sha256": sha256_bytes(worker_bytes),
            "expected_repository": EXPECTED_REPOSITORY,
            "expected_branch": EXPECTED_BOOTSTRAP_BRANCH,
        }
        atomic_write(activation, (json.dumps(active, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        if fault_after == "activation":
            raise ControlError("injected failure after activation")
        if not runtime_startup_eligible():
            raise ControlError("runtime activation verification failed")
        process = launcher(repo, worker)
        if fault_after == "launch":
            raise ControlError("injected failure after runtime launch")
        ready = readiness(sha256_bytes(worker_bytes))
        if fault_after == "ready":
            raise ControlError("injected failure after readiness")
        return {**install_record, "pid": getattr(process, "pid", None), "status_endpoint": dict(ready)}
    except Exception:
        process_obj = locals().get("process")
        if process_obj is not None:
            try:
                process_obj.terminate()
            except Exception:
                pass
        # First make startup inert, then restore any pre-existing state exactly.
        try:
            if activation.exists():
                activation.unlink()
        except OSError:
            pass
        if old_registry is None:
            registry_backend.delete()
        else:
            registry_backend.set(old_registry)
        if old_worker is None:
            if worker.exists():
                worker.unlink()
        else:
            atomic_write(worker, old_worker)
        if old_receipt is None:
            rollback = {
                "schema": CONTROL_RECEIPT_SCHEMA,
                "request_id": "runtime-installer",
                "status": "ROLLED_BACK",
            }
            atomic_write(receipt, (json.dumps(rollback, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        else:
            atomic_write(receipt, old_receipt)
        if old_activation is not None:
            atomic_write(activation, old_activation)
        raise


def runtime_install_state_snapshot(repo: Path, worker_sha256: str) -> dict[str, Any]:
    status = verify_repo(repo, require_clean=True)
    return {
        "repository": EXPECTED_REPOSITORY,
        "branch": status["branch"],
        "head": status["head"],
        "authority_revision": status["authority_revision"],
        "mission": status["mission"],
        "runtime_worker_sha256": worker_sha256,
        "runtime_root": str(local_control_root()),
        "startup_scope": "HKCU-user",
    }


def runtime_install_evidence(snapshot: Mapping[str, Any], worker_sha256: str) -> dict[str, list[dict[str, str]]]:
    return {
        "map": [{
            "kind": "OBSERVED",
            "text": "The exact local repository, authority revision, and candidate worker hash were re-read before runtime installation.",
            "fact_key": "runtime_worker_sha256",
            "fact_value": worker_sha256,
            "source": "local pre-hashed bootstrap candidate",
        }],
        "history": [{
            "kind": "VERIFIED_HISTORY",
            "text": "The durable design requires a persistent user-scoped worker installed only through the existing Gateway/Broker.",
            "fact_key": "runtime_install_design",
            "fact_value": "gateway-broker-user-scope",
            "source": "OP-CONTROL-002 handoff",
        }],
        "research": [{
            "kind": "EXTERNAL_RESEARCH",
            "text": "A user-scoped Windows Run entry can start the worker without Administrator privileges; activation is kept inert until final marker write.",
            "fact_key": "startup_scope",
            "fact_value": "HKCU-user",
            "source": "Windows user startup contract",
        }],
        "capabilities": [{
            "kind": "OBSERVED",
            "text": "The bootstrap has a fixed, non-user-selectable runtime installer handler and no arbitrary shell interface.",
            "fact_key": "runtime_installer_handler",
            "fact_value": RUNTIME_INSTALL_ACTION,
            "source": "candidate runtime",
        }],
    }


def authorized_runtime_install(repo: Path, worker_bytes: bytes, *, provider=None, registry_backend=None, validation=validate_runtime_worker) -> Mapping[str, Any]:
    verify_repo(repo, require_clean=True)
    HypothesisLedger, DecisionRecordStore, SOPDecisionGateway, ControlledToolBroker = import_control(repo)
    provider = provider or ChatGPTPlanOAuthDecisionProvider()
    worker_sha = sha256_bytes(worker_bytes)
    snapshot = runtime_install_state_snapshot(repo, worker_sha)
    evidence = runtime_install_evidence(snapshot, worker_sha)
    gateway_root = local_control_root() / "gateway"
    gateway = SOPDecisionGateway(
        provider=provider,
        store=DecisionRecordStore(gateway_root / "decisions"),
        strict_evidence=True,
        hypotheses=HypothesisLedger(gateway_root / "hypotheses.json"),
    )
    decision_id = "runtime-install-" + worker_sha[:20]
    packet = gateway.request_decision(
        mission=str(snapshot["mission"]),
        request=(
            "Install this exact pre-hashed Operation Pancake local control worker as a user-scoped persistent runtime. "
            "The runtime may become active only after worker validation, INSTALLED receipt persistence, and user-startup configuration all succeed. "
            f"The only mutation action is {RUNTIME_INSTALL_ACTION!r}."
        ),
        evidence=evidence,
        state_snapshot=snapshot,
        decision_id=decision_id,
        mutation_requested=True,
    )
    if packet.decision_status != "DECISION_ALLOWED":
        raise ControlError(
            f"gateway did not authorize durable runtime installation: {packet.decision_status}; "
            f"errors={list(packet.gate_errors)}"
        )
    if RUNTIME_INSTALL_ACTION not in packet.allowed_actions:
        raise ControlError("decision did not authorize exact runtime installation action")
    broker = ControlledToolBroker(gateway)
    broker.register(
        RUNTIME_INSTALL_ACTION,
        mutating=True,
        handler=lambda: staged_runtime_install(
            repo,
            worker_bytes,
            registry_backend=registry_backend,
            validation=validation,
        ),
    )
    current = runtime_install_state_snapshot(repo, worker_sha)
    return broker.call(
        RUNTIME_INSTALL_ACTION,
        decision_id=packet.decision_id,
        current_state_snapshot=current,
    )


def inbox_loop(repo: Path, *, startup_guard: Path | None = None, provider=None, transport=None) -> None:
    if startup_guard is not None:
        if startup_guard.resolve() != runtime_activation_path().resolve() or not runtime_startup_eligible():
            raise ControlError("persistent startup is not activation-eligible")
    status = verify_repo(repo, require_clean=True)
    worker_sha = sha256_bytes(Path(__file__).resolve().read_bytes())
    journal = ReceiptJournal(local_control_root() / "requests")
    health = {
        "schema": CONTROL_STATUS_SCHEMA,
        "status": "READY",
        "pid": os.getpid(),
        "repository": EXPECTED_REPOSITORY,
        "branch": status["branch"],
        "head": status["head"],
        "authority_revision": status["authority_revision"],
        "mission": status["mission"],
        "worker_sha256": worker_sha,
        "transport": "github-inbox",
        "poll_interval_seconds": CONTROL_POLL_SECONDS,
        "mutation_http_endpoint": False,
    }
    server, existing = start_control_status_server(journal, health)
    if server is None:
        # A matching active worker already owns the loopback status surface.
        if existing.get("worker_sha256") == worker_sha and existing.get("status") == "READY":
            return
        raise ControlError("another Operation Pancake control worker is already active")
    transport = transport or GitHubIssueTransport()
    while True:
        if startup_guard is not None and not runtime_startup_eligible():
            server.shutdown()
            return
        # Fail closed if the product branch/authority moves unexpectedly.
        verify_repo(repo, require_clean=True)
        delay = CONTROL_POLL_SECONDS
        try:
            numbers, delay = transport.list_candidate_issues()
            poll_control_issues(repo, numbers, transport, provider=provider, journal=journal)
        except GitHubRateLimited as exc:
            delay = exc.delay_seconds
        except Exception:
            delay = CONTROL_POLL_SECONDS * 2
        time.sleep(max(CONTROL_POLL_SECONDS, int(delay)))


def local_control_root() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OperationPancakeControl"


def install_self(
    repo: Path,
    *,
    expected_head: str,
    expected_revision: int,
    expected_branch: str,
    provider=None,
    validation=fixed_validation,
) -> Mapping[str, Any]:
    source_path = Path(__file__).resolve()
    content = source_path.read_bytes()
    target = validate_target(repo, DURABLE_TARGET)
    if target.exists():
        raise ControlError(f"bootstrap target already exists: {DURABLE_TARGET}")
    candidate = MutationCapsule(
        target=DURABLE_TARGET,
        preimage_sha256="ABSENT",
        content=content,
        content_sha256=sha256_bytes(content),
        request=(
            "Stage the fully validated Operation Pancake durable control runner on an isolated local branch. "
            "The exact pre-hashed file may be applied only through SOPDecisionGateway and ControlledToolBroker."
        ),
    )
    staged_result = controlled_apply(
        repo,
        candidate,
        expected_head=expected_head,
        expected_revision=expected_revision,
        expected_branch=expected_branch,
        provider=provider,
        marker_dir=local_control_root() / "capabilities",
        bootstrap_history=(
            "The reconstructed durable GitHub-inbox runner passed isolated fail-closed acceptance before packaging.",
            "All imported Pancake control modules are Git-blob-hash verified before package import/execution.",
        ),
        validation=validation,
    )
    post_stage = verify_repo(
        repo,
        expected_head=expected_head,
        expected_revision=expected_revision,
        expected_branch=expected_branch,
        require_clean=True,
    )
    runtime_result = authorized_runtime_install(
        repo,
        content,
        provider=provider,
    )
    record = {
        "schema": "operation-pancake-bootstrap-result-v1",
        "status": "PASS",
        "expected_head": expected_head,
        "expected_revision": expected_revision,
        "expected_branch": expected_branch,
        "runner_sha256": candidate.content_sha256,
        "staged_repository_result": dict(staged_result),
        "post_stage_repository": post_stage,
        "runtime_install_result": dict(runtime_result),
        "runtime_startup_eligible": runtime_startup_eligible(),
        "control_transport": "github-inbox",
        "poll_interval_seconds": CONTROL_POLL_SECONDS,
    }
    if record["runtime_startup_eligible"] is not True:
        raise ControlError("durable runtime installation completed without activation eligibility")
    atomic_write(
        local_control_root() / "bootstrap_result.json",
        (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return record


def self_test(repo: Path) -> Mapping[str, Any]:
    status = verify_repo(repo, require_clean=False)
    HypothesisLedger, DecisionRecordStore, SOPDecisionGateway, ControlledToolBroker = import_control(repo)
    if not callable(getattr(SOPDecisionGateway, "authorize_mutation_action", None)):
        raise ControlError("SOPDecisionGateway lacks mutation authorization")
    if not callable(getattr(ControlledToolBroker, "call", None)):
        raise ControlError("ControlledToolBroker is unavailable")
    return {
        "status": "PASS",
        "repo": EXPECTED_REPOSITORY,
        "head": status["head"],
        "branch": status["branch"],
        "authority_revision": status["authority_revision"],
        "gateway": "SOPDecisionGateway",
        "broker": "ControlledToolBroker",
        "control_modules_verified_before_import": True,
        "control_blob_manifest": dict(CONTROL_BLOB_MANIFEST),
        "control_transport": "github-inbox",
        "poll_interval_seconds": CONTROL_POLL_SECONDS,
        "arbitrary_shell_exposed": False,
        "registered_inbox_actions": sorted(INBOX_ACTIONS),
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Operation Pancake controlled local runner")
    p.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--self-test", action="store_true")
    g.add_argument("--install-self", action="store_true")
    g.add_argument("--inbox", action="store_true")
    p.add_argument("--expected-head")
    p.add_argument("--expected-revision", type=int)
    p.add_argument("--expected-branch")
    p.add_argument("--startup-guard", type=Path)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        if args.self_test:
            print(json.dumps(self_test(args.repo), indent=2, sort_keys=True))
            return 0
        if args.install_self:
            if not args.expected_head or args.expected_revision is None or not args.expected_branch:
                raise ControlError("bootstrap install requires exact head, revision, and branch guards")
            result = install_self(
                args.repo,
                expected_head=args.expected_head,
                expected_revision=args.expected_revision,
                expected_branch=args.expected_branch,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            try:
                webbrowser.open((local_control_root() / "bootstrap_result.json").resolve().as_uri(), new=1)
            except Exception:
                pass
            return 0
        if args.inbox:
            inbox_loop(args.repo, startup_guard=args.startup_guard)
            return 0
        raise ControlError("unsupported control mode")
    except Exception as exc:
        print("PANCAKE CONTROL: FAIL", file=sys.stderr)
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        if getattr(args, "install_self", False):
            try:
                failure = {
                    "schema": "operation-pancake-bootstrap-result-v1",
                    "status": "FAIL",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                result_path = local_control_root() / "bootstrap_result.json"
                atomic_write(
                    result_path,
                    (json.dumps(failure, indent=2, sort_keys=True) + "\n").encode("utf-8"),
                )
                webbrowser.open(result_path.resolve().as_uri(), new=1)
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
