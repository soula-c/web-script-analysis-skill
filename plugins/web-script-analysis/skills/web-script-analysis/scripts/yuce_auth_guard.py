#!/usr/bin/env python3
"""Guard Yuce browser login state for API-first web data workflows.

The helper prints sanitized status only. It never prints passwords, cookies,
localStorage values, request headers, or report data.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import socket
import ssl
import struct
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_URL = "https://yuce.vsigo.cn/"
DEFAULT_PROFILE_DIR = "~/.codex/chrome-yuce"


class WebSocket:
    def __init__(self, url: str, timeout: int = 20):
        parsed = urllib.parse.urlparse(url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        self.path = parsed.path + (("?" + parsed.query) if parsed.query else "")
        raw = socket.create_connection((self.host, self.port), timeout=timeout)
        if parsed.scheme == "wss":
            raw = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)
        raw.settimeout(timeout)
        self.sock = raw
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError("CDP websocket handshake failed")

    def send_json(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        header = bytearray([0x81])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self.sock.sendall(bytes(header) + masked)

    def recv_json(self) -> dict[str, Any]:
        while True:
            first = self.sock.recv(2)
            if len(first) < 2:
                raise RuntimeError("CDP websocket closed")
            opcode = first[0] & 0x0F
            length = first[1] & 0x7F
            if length == 126:
                length = struct.unpack("!H", self.sock.recv(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.sock.recv(8))[0]
            masked = bool(first[1] & 0x80)
            mask = self.sock.recv(4) if masked else b""
            data = b""
            while len(data) < length:
                data += self.sock.recv(length - len(data))
            if masked:
                data = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
            if opcode == 0x8:
                raise RuntimeError("CDP websocket closed")
            if opcode == 0x1:
                return json.loads(data.decode("utf-8"))


def cdp(ws: WebSocket, method: str, params: dict[str, Any] | None = None, timeout: int = 20) -> dict[str, Any]:
    command_id = random.randint(100000, 999999)
    ws.send_json({"id": command_id, "method": method, "params": params or {}})
    deadline = time.time() + timeout
    while time.time() < deadline:
        message = ws.recv_json()
        if message.get("id") != command_id:
            continue
        if "error" in message:
            raise RuntimeError(json.dumps(message["error"], ensure_ascii=False))
        return message.get("result", {})
    raise TimeoutError(method)


def cdp_json(port: int, path: str, timeout: int = 5) -> Any:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def cdp_ready(port: int) -> bool:
    try:
        cdp_json(port, "/json/version")
        return True
    except Exception:
        return False


def list_targets(port: int) -> list[dict[str, Any]]:
    return cdp_json(port, "/json/list")


def open_tab(port: int, url: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(url, safe="")
    request = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?{encoded}", method="PUT")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def find_yuce_target(port: int) -> dict[str, Any] | None:
    targets = list_targets(port)
    pages = [row for row in targets if row.get("type") == "page"]
    return next((row for row in pages if "yuce.vsigo.cn" in (row.get("url") or "")), None)


def target_for_yuce(port: int, url: str, open_if_missing: bool) -> tuple[dict[str, Any] | None, bool]:
    target = find_yuce_target(port)
    if target:
        return target, False
    if not open_if_missing:
        return None, False
    return open_tab(port, url), True


def default_chrome_path() -> str:
    if sys.platform == "darwin":
        return "/Applications/Google Chrome.app"
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil_which(name)
        if found:
            return found
    return ""


def shutil_which(name: str) -> str:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return ""


def start_chrome(port: int, profile_dir: str, url: str, chrome_path: str, wait_seconds: int) -> bool:
    profile = str(Path(profile_dir).expanduser())
    Path(profile).mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin" and chrome_path.endswith(".app"):
        cmd = [
            "open",
            "-na",
            chrome_path,
            "--args",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--remote-allow-origins=*",
            url,
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        if not chrome_path:
            raise RuntimeError("Chrome path not found. Pass --chrome-path.")
        cmd = [
            chrome_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--remote-allow-origins=*",
            url,
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if cdp_ready(port):
            return True
        time.sleep(1)
    return False


def evaluate_login_surface(ws_url: str, timeout: int) -> dict[str, Any]:
    ws = WebSocket(ws_url, timeout=timeout)
    cdp(ws, "Runtime.enable", timeout=timeout)
    expr = r"""
(async () => {
  await new Promise(resolve => setTimeout(resolve, 2500));
  const text = (document.body && document.body.innerText || "").slice(0, 3000);
  const passwordInput = !!document.querySelector('input[type="password"]');
  const inputs = Array.from(document.querySelectorAll('input')).map(input => ({
    type: input.type || "",
    placeholder: input.placeholder || "",
    name: input.name || "",
  })).slice(0, 12);
  const loginWords = /(登录|登陆|验证码|请输入|密码)/.test(text);
  const reportWords = /(报表|看板|资源|筛选|查询|导出|图表)/.test(text);
  const localStorageKeyCount = (() => {
    try { return window.localStorage ? window.localStorage.length : null; } catch (_) { return null; }
  })();
  return {
    href: location.href,
    title: document.title || "",
    passwordInput,
    inputCount: inputs.length,
    inputs,
    loginWords,
    reportWords,
    bodyTextLength: text.length,
    localStorageKeyCount,
  };
})()
"""
    result = cdp(ws, "Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True}, timeout=timeout)
    value = (result.get("result") or {}).get("value")
    return value if isinstance(value, dict) else {}


def evaluate_probe(ws_url: str, path: str, method: str, body: str, timeout: int) -> dict[str, Any]:
    ws = WebSocket(ws_url, timeout=timeout)
    cdp(ws, "Runtime.enable", timeout=timeout)
    probe_path = json.dumps(path)
    probe_method = json.dumps(method.upper())
    probe_body = json.dumps(body)
    expr = f"""
(async () => {{
  const path = {probe_path};
  const method = {probe_method};
  const body = {probe_body};
  const options = {{
    method,
    credentials: "include",
    headers: {{"Accept": "application/json, text/plain, */*"}}
  }};
  if (body) {{
    options.headers["Content-Type"] = "application/json;charset=UTF-8";
    options.body = body;
  }}
  const res = await fetch(path, options);
  const contentType = res.headers.get("content-type") || "";
  const text = await res.text();
  let parsed = null;
  try {{ parsed = JSON.parse(text); }} catch (_) {{}}
  return {{
    ok: res.ok,
    status: res.status,
    redirected: res.redirected,
    responseUrlHost: (() => {{ try {{ return new URL(res.url).host; }} catch (_) {{ return ""; }} }})(),
    contentType,
    textLength: text.length,
    jsonType: parsed && Array.isArray(parsed) ? "array" : (parsed && typeof parsed === "object" ? "object" : null),
    jsonKeys: parsed && typeof parsed === "object" && !Array.isArray(parsed) ? Object.keys(parsed).slice(0, 12) : [],
    code: parsed && typeof parsed === "object" ? (parsed.code ?? null) : null,
    hasData: !!(parsed && typeof parsed === "object" && parsed.data !== undefined)
  }};
}})()
"""
    result = cdp(ws, "Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True}, timeout=timeout)
    value = (result.get("result") or {}).get("value")
    return value if isinstance(value, dict) else {}


def classify(surface: dict[str, Any]) -> tuple[str, str]:
    href = str(surface.get("href") or "")
    title = str(surface.get("title") or "")
    password_input = bool(surface.get("passwordInput"))
    login_words = bool(surface.get("loginWords"))
    report_words = bool(surface.get("reportWords"))
    if "login" in href.lower() or password_input:
        return "manual_login_required", "Yuce page is on a login/password surface."
    if login_words and not report_words:
        return "manual_login_required", "Yuce page text looks like a login or verification surface."
    if "yuce.vsigo.cn" in href and (report_words or title):
        return "authenticated", "Yuce page does not look like a login surface."
    return "unknown", "Yuce tab exists, but the page state is not conclusive."


def sanitized_surface(surface: dict[str, Any]) -> dict[str, Any]:
    return {
        "href": surface.get("href"),
        "title": surface.get("title"),
        "passwordInput": surface.get("passwordInput"),
        "inputCount": surface.get("inputCount"),
        "loginWords": surface.get("loginWords"),
        "reportWords": surface.get("reportWords"),
        "bodyTextLength": surface.get("bodyTextLength"),
        "localStorageKeyCount": surface.get("localStorageKeyCount"),
    }


def check_once(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if not cdp_ready(args.port):
        if not args.start_chrome:
            return {
                "ok": False,
                "cdp_reachable": False,
                "login_state": "chrome_unavailable",
                "manual_action": f"Start Chrome with remote debugging port {args.port}, or rerun with --start-chrome.",
            }, 2
        chrome_path = args.chrome_path or default_chrome_path()
        started = start_chrome(args.port, args.profile_dir, args.url, chrome_path, args.chrome_wait_seconds)
        if not started:
            return {
                "ok": False,
                "cdp_reachable": False,
                "login_state": "chrome_unavailable",
                "manual_action": f"Chrome did not become ready on port {args.port}.",
            }, 2

    target, opened = target_for_yuce(args.port, args.url, args.open_if_missing)
    if not target:
        return {
            "ok": False,
            "cdp_reachable": True,
            "target_opened": False,
            "login_state": "yuce_tab_missing",
            "manual_action": "Open a yuce.vsigo.cn tab or rerun with --open-if-missing.",
        }, 1 if args.require_auth else 0

    ws_url = target.get("webSocketDebuggerUrl")
    if not ws_url:
        raise RuntimeError("Yuce target has no webSocketDebuggerUrl")
    surface = evaluate_login_surface(ws_url, args.evaluate_timeout)
    login_state, reason = classify(surface)
    probe = None
    if args.probe_path and login_state == "authenticated":
        probe = evaluate_probe(ws_url, args.probe_path, args.probe_method, args.probe_body, args.evaluate_timeout)
        probe_status = int(probe.get("status") or 0)
        probe_host = str(probe.get("responseUrlHost") or "")
        if probe_status in {401, 403} or "login" in probe_host.lower():
            login_state = "manual_login_required"
            reason = "Yuce probe API indicates the session is unauthorized or redirected to login."
        elif not probe.get("ok"):
            login_state = "unknown"
            reason = "Yuce page looks authenticated, but the probe API did not return a successful response."
    authenticated = login_state == "authenticated"
    status = {
        "ok": authenticated,
        "cdp_reachable": True,
        "target_opened": opened,
        "target_id": target.get("id"),
        "target_url": target.get("url"),
        "login_state": login_state,
        "reason": reason,
        "manual_action": "" if authenticated else "Complete Yuce login in the visible Chrome tab, then rerun the guard.",
        "page": sanitized_surface(surface),
    }
    if probe is not None:
        status["probe"] = probe
    return status, 0 if authenticated or not args.require_auth else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=int(os.environ.get("YUCE_CHROME_PORT", "9222")))
    parser.add_argument("--url", default=os.environ.get("YUCE_URL", DEFAULT_URL))
    parser.add_argument("--open-if-missing", action="store_true")
    parser.add_argument("--start-chrome", action="store_true")
    parser.add_argument("--profile-dir", default=os.environ.get("YUCE_CHROME_PROFILE", DEFAULT_PROFILE_DIR))
    parser.add_argument("--chrome-path", default=os.environ.get("CHROME_PATH", ""))
    parser.add_argument("--chrome-wait-seconds", type=int, default=20)
    parser.add_argument("--evaluate-timeout", type=int, default=20)
    parser.add_argument("--wait-for-manual-login", type=int, default=0, metavar="SECONDS")
    parser.add_argument("--poll-seconds", type=int, default=5)
    parser.add_argument("--probe-path", default="", help="Optional same-origin path/URL to fetch from the Yuce tab.")
    parser.add_argument("--probe-method", default="GET", choices=["GET", "POST", "get", "post"])
    parser.add_argument("--probe-body", default="", help="Optional JSON body for --probe-method POST. Not printed.")
    parser.add_argument("--require-auth", action="store_true")
    args = parser.parse_args()

    try:
        deadline = time.time() + max(0, args.wait_for_manual_login)
        while True:
            status, code = check_once(args)
            if status.get("login_state") == "authenticated" or not args.wait_for_manual_login or time.time() >= deadline:
                print(json.dumps(status, ensure_ascii=False, indent=2))
                return code
            time.sleep(max(1, args.poll_seconds))
    except Exception as exc:
        print(json.dumps({"ok": False, "login_state": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
