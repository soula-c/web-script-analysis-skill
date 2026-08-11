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
DEFAULT_PROFILE_DIR = "~/.codex/chrome-yuce-tmall-review"
DEFAULT_USER_ENV = "YUCE_USER"
DEFAULT_PASSWORD_ENV = "YUCE_PASSWORD"


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


def _normalized_url(value: str) -> str:
    return urllib.parse.unquote(value or "").rstrip("/")


def _route_key(value: str) -> str:
    parsed = urllib.parse.urlparse(_normalized_url(value))
    fragment = (parsed.fragment or "").split("?", 1)[0].rstrip("/")
    return fragment or parsed.path.rstrip("/")


def _target_matches_url(target_url: str, preferred_url: str) -> bool:
    if not preferred_url:
        return False
    target_norm = _normalized_url(target_url)
    preferred_norm = _normalized_url(preferred_url)
    if target_norm == preferred_norm:
        return True
    if preferred_norm and preferred_norm in target_norm:
        return True
    preferred_route = _route_key(preferred_norm)
    return bool(preferred_route and preferred_route == _route_key(target_norm))


def find_yuce_target(port: int, preferred_url: str = "") -> dict[str, Any] | None:
    targets = list_targets(port)
    pages = [row for row in targets if row.get("type") == "page"]
    yuce_pages = [row for row in pages if "yuce.vsigo.cn" in (row.get("url") or "")]
    if preferred_url:
        preferred = next(
            (row for row in yuce_pages if _target_matches_url(row.get("url") or "", preferred_url)),
            None,
        )
        if preferred:
            return preferred
        return None
    return yuce_pages[0] if yuce_pages else None


def target_for_yuce(port: int, url: str, open_if_missing: bool) -> tuple[dict[str, Any] | None, bool]:
    target = find_yuce_target(port, url)
    if target:
        return target, False
    if not open_if_missing:
        return None, False
    return open_tab(port, url), True


def navigate_target(target: dict[str, Any], url: str, timeout: int) -> None:
    ws_url = target.get("webSocketDebuggerUrl") or ""
    if not ws_url:
        raise RuntimeError("CDP target has no webSocketDebuggerUrl")
    ws = WebSocket(ws_url, timeout=timeout)
    cdp(ws, "Page.enable", timeout=timeout)
    cdp(ws, "Page.navigate", {"url": url}, timeout=timeout)


def recover_yuce_target(
    port: int,
    profile_dir: str,
    url: str,
    stale_target: dict[str, Any] | None,
    chrome_path: str,
    wait_seconds: int,
    evaluate_timeout: int,
) -> tuple[dict[str, Any] | None, bool]:
    """Recover a stuck report tab without closing it or using CDP /json/new."""
    pages = [row for row in list_targets(port) if row.get("type") == "page"]
    stale_id = (stale_target or {}).get("id")
    candidates = [
        row for row in pages
        if row.get("id") != stale_id
        and (row.get("url") or "") in {"about:blank", "chrome://newtab/"}
    ]
    if stale_target:
        candidates.append(stale_target)
    for candidate in candidates:
        try:
            navigate_target(candidate, url, evaluate_timeout)
            break
        except Exception:
            continue
    else:
        open_chrome_url(port, profile_dir, url, chrome_path, wait_seconds)

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        target = find_yuce_target(port, url)
        if target:
            return target, True
        time.sleep(1)
    return None, True


def yuce_url_needs_os_open(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    fragment = parsed.fragment or ""
    return "yuce.vsigo.cn" in (parsed.hostname or "") and (
        "/resource/report-view/" in fragment
        or "/resource/report-edit/" in fragment
        or "/site-view/" in fragment
    )


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


def open_chrome_url(port: int, profile_dir: str, url: str, chrome_path: str, wait_seconds: int) -> bool:
    """Open a Yuce URL through the OS instead of CDP /json/new."""
    chrome_path = chrome_path or default_chrome_path()
    return start_chrome(port, profile_dir, url, chrome_path, wait_seconds)


def launchctl_getenv(name: str) -> str:
    try:
        return subprocess.check_output(["launchctl", "getenv", name], text=True, stderr=subprocess.DEVNULL).strip("\n")
    except Exception:
        return ""


def secret(name: str, aliases: list[str]) -> str:
    for key in [name, *aliases]:
        value = os.environ.get(key) or launchctl_getenv(key)
        if value:
            return value
    return ""


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
    autocomplete: input.autocomplete || "",
  })).slice(0, 12);
  const inputWords = inputs.map(input => [
    input.type,
    input.placeholder,
    input.name,
    input.autocomplete,
  ].join(" ")).join(" ");
  const loginWords = /(登录|登陆|验证码|请输入|密码)/.test(text);
  const reportWords = /(报表|看板|资源|筛选|查询|导出|图表)/.test(text);
  const securityInput = /(验证码|校验码|短信|captcha|mfa|otp|code)/i.test(inputWords);
  const securityWords = /(MFA|二次验证|安全验证|设备验证|滑块|拖动|拼图)/i.test(text);
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
    securityInput,
    securityWords,
    bodyTextLength: text.length,
    localStorageKeyCount,
  };
})()
"""
    result = cdp(ws, "Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True}, timeout=timeout)
    value = (result.get("result") or {}).get("value")
    return value if isinstance(value, dict) else {}


def attempt_password_login(ws_url: str, username: str, password: str, timeout: int) -> dict[str, Any]:
    ws = WebSocket(ws_url, timeout=timeout)
    cdp(ws, "Runtime.enable", timeout=timeout)
    inspect_expr = r"""
(() => {
  const text = (document.body && document.body.innerText || "").slice(0, 5000);
  const inputs = Array.from(document.querySelectorAll("input")).filter(input => {
    const style = getComputedStyle(input);
    return !input.disabled && input.type !== "hidden" && style.display !== "none" && style.visibility !== "hidden";
  });
  const securityInput = inputs.some(input => /(验证码|校验码|短信|captcha|mfa|otp|code)/i.test([
    input.type || "",
    input.placeholder || "",
    input.name || "",
    input.autocomplete || "",
    input.id || "",
  ].join(" ")));
  const securityWords = /(MFA|二次验证|安全验证|设备验证|滑块|拖动|拼图)/i.test(text);
  if (securityInput || securityWords) {
    return {
      attempted: false,
      reason: "security_challenge_detected",
      passwordInputFound: !!document.querySelector('input[type="password"]'),
      usernameInputFound: false,
      clickedLogin: false
    };
  }

  const passwordInput = inputs.find(input => input.type === "password");
  const usernameInput = inputs.find(input => input !== passwordInput && /(user|account|phone|mobile|email|login|name|tel|text|账号|手机号|手机|用户名)/i.test([
    input.type || "",
    input.placeholder || "",
    input.name || "",
    input.autocomplete || "",
    input.id || "",
  ].join(" "))) || inputs.find(input => input !== passwordInput && ["", "text", "tel", "email"].includes((input.type || "").toLowerCase()));
  if (!passwordInput || !usernameInput) {
    return {
      attempted: false,
      reason: "password_login_form_not_found",
      passwordInputFound: !!passwordInput,
      usernameInputFound: !!usernameInput,
      clickedLogin: false
    };
  }
  return {
    attempted: false,
    reason: "password_form_ready",
    passwordInputFound: true,
    usernameInputFound: true,
    clickedLogin: false
  };
})()
"""
    inspect_result = cdp(
        ws,
        "Runtime.evaluate",
        {"expression": inspect_expr, "returnByValue": True},
        timeout=timeout,
    )
    inspected = (inspect_result.get("result") or {}).get("value")
    if not isinstance(inspected, dict) or inspected.get("reason") != "password_form_ready":
        return inspected if isinstance(inspected, dict) else {}

    def trusted_fill(selector_expr: str, value: str) -> bool:
        focus_expr = f"""
(() => {{
  const inputs = Array.from(document.querySelectorAll("input")).filter(input => {{
    const style = getComputedStyle(input);
    return !input.disabled && input.type !== "hidden" && style.display !== "none" && style.visibility !== "hidden";
  }});
  const passwordInput = inputs.find(input => input.type === "password");
  const usernameInput = inputs.find(input => input !== passwordInput && /(user|account|phone|mobile|email|login|name|tel|text|账号|手机号|手机|用户名)/i.test([
    input.type || "", input.placeholder || "", input.name || "", input.autocomplete || "", input.id || ""
  ].join(" "))) || inputs.find(input => input !== passwordInput && ["", "text", "tel", "email"].includes((input.type || "").toLowerCase()));
  const input = {selector_expr};
  if (!input) return false;
  input.focus();
  input.select();
  return true;
}})()
"""
        focused = cdp(
            ws,
            "Runtime.evaluate",
            {"expression": focus_expr, "returnByValue": True},
            timeout=timeout,
        )
        if not bool((focused.get("result") or {}).get("value")):
            return False
        cdp(ws, "Input.insertText", {"text": value}, timeout=timeout)
        cdp(
            ws,
            "Input.dispatchKeyEvent",
            {"type": "keyDown", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9},
            timeout=timeout,
        )
        cdp(
            ws,
            "Input.dispatchKeyEvent",
            {"type": "keyUp", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9},
            timeout=timeout,
        )
        return True

    username_filled = trusted_fill("usernameInput", username)
    password_filled = trusted_fill("passwordInput", password)
    if not username_filled or not password_filled:
        return {
            "attempted": False,
            "reason": "trusted_input_failed",
            "passwordInputFound": password_filled,
            "usernameInputFound": username_filled,
            "clickedLogin": False,
        }

    click_expr = r"""
(() => {
  const passwordInput = document.querySelector('input[type="password"]');
  const buttons = Array.from(document.querySelectorAll("button, [role='button'], input[type='button'], input[type='submit']"));
  const loginButton = buttons.find(button => /(登\s*录|登\s*陆|log\s*in|sign\s*in)/i.test((button.innerText || button.value || button.getAttribute("aria-label") || "").trim()))
    || buttons.find(button => !button.disabled);
  if (loginButton) {
    loginButton.click();
    return true;
  }
  if (passwordInput && passwordInput.form) {
    passwordInput.form.requestSubmit ? passwordInput.form.requestSubmit() : passwordInput.form.submit();
    return true;
  }
  return false;
})()
"""
    clicked = cdp(
        ws,
        "Runtime.evaluate",
        {"expression": click_expr, "returnByValue": True},
        timeout=timeout,
    )
    time.sleep(4.5)
    return {
        "attempted": True,
        "reason": "submitted_password_login_with_trusted_input",
        "passwordInputFound": True,
        "usernameInputFound": True,
        "clickedLogin": bool((clicked.get("result") or {}).get("value")),
    }


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
    security_input = bool(surface.get("securityInput"))
    security_words = bool(surface.get("securityWords"))
    if security_input or security_words:
        return "manual_login_required", "Yuce page requires a verification or security step."
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
        "securityInput": surface.get("securityInput"),
        "securityWords": surface.get("securityWords"),
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

    target = find_yuce_target(args.port, args.url)
    opened = False
    if not target and args.open_if_missing:
        if yuce_url_needs_os_open(args.url):
            opened = open_chrome_url(args.port, args.profile_dir, args.url, args.chrome_path, args.chrome_wait_seconds)
            deadline = time.time() + args.chrome_wait_seconds
            while time.time() < deadline:
                target = find_yuce_target(args.port, args.url)
                if target:
                    break
                time.sleep(1)
        else:
            target, opened = target_for_yuce(args.port, args.url, True)
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
    try:
        surface = evaluate_login_surface(ws_url, args.evaluate_timeout)
    except Exception:
        if not args.open_if_missing:
            raise
        target, opened = recover_yuce_target(
            args.port,
            args.profile_dir,
            args.url,
            target,
            args.chrome_path,
            args.chrome_wait_seconds,
            args.evaluate_timeout,
        )
        if not target:
            raise
        ws_url = target.get("webSocketDebuggerUrl")
        if not ws_url:
            raise RuntimeError("Yuce target has no webSocketDebuggerUrl after reopen")
        surface = evaluate_login_surface(ws_url, args.evaluate_timeout)
    login_state, reason = classify(surface)
    auto_login = None
    if login_state == "manual_login_required" and not args.no_auto_login:
        username = secret(args.user_env, ["YUCE_USERNAME"])
        password = secret(args.password_env, ["YUCE_PASS"])
        if username and password:
            auto_login = attempt_password_login(ws_url, username, password, args.evaluate_timeout)
            if auto_login.get("attempted"):
                surface = evaluate_login_surface(ws_url, args.evaluate_timeout)
                login_state, reason = classify(surface)
                if login_state == "authenticated":
                    reason = "Yuce password login succeeded through environment credentials."
                else:
                    reason = "Yuce password login was submitted, but the page still requires manual verification or did not authenticate."
            elif auto_login.get("reason") == "security_challenge_detected":
                reason = "Yuce page requires CAPTCHA, SMS, MFA, slider, or device verification; manual login is required."
            else:
                reason = "Yuce password login form could not be resolved automatically."
        else:
            reason = f"Yuce credentials are missing. Set {args.user_env}/{args.password_env} or complete manual login."
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
    if auto_login is not None:
        status["auto_login"] = {
            "attempted": bool(auto_login.get("attempted")),
            "reason": auto_login.get("reason"),
            "passwordInputFound": bool(auto_login.get("passwordInputFound")),
            "usernameInputFound": bool(auto_login.get("usernameInputFound")),
            "clickedLogin": bool(auto_login.get("clickedLogin")),
        }
    if probe is not None:
        status["probe"] = probe
    return status, 0 if authenticated or not args.require_auth else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=int(os.environ.get("YUCE_CHROME_PORT", "9224")))
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
    parser.add_argument("--user-env", default=DEFAULT_USER_ENV)
    parser.add_argument("--password-env", default=DEFAULT_PASSWORD_ENV)
    parser.add_argument("--no-auto-login", action="store_true", help="Do not use Yuce credentials from environment variables.")
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
