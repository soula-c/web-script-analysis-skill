#!/usr/bin/env python3
"""Recover Vsigo ERP login state from local environment credentials.

This helper prints sanitized status only. It never prints passwords, account
tokens, app tokens, cookies, or raw authenticated responses.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
import random
import socket
import ssl
import struct
import subprocess
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


BASE_URL = "https://erp-business-common-api.vsigo.cn/ums"
DEFAULT_BUSINESS_ID = "sigo"
DEFAULT_PAGES = [
    "https://idata-dc-admin.vsigo.cn/profits-report/detailNew",
    "https://idata-dc-admin.vsigo.cn/product/product-board",
]


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


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://a.vsigo.cn",
            "Referer": "https://a.vsigo.cn/",
            "User-Agent": "Mozilla/5.0",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            body = {"message": text[:200]}
        return exc.code, body


@dataclass
class LoginState:
    username: str
    password: str
    account_token: str
    business_id: str
    business_name: str
    data_source: str
    admin_id: str
    real_name: str
    user_id: str
    user_name: str
    erp_app_token: str
    apps: list[dict[str, Any]]


def login(username: str, password: str, business_id: str) -> tuple[LoginState, list[dict[str, Any]]]:
    password_md5 = hashlib.md5(password.encode("utf-8")).hexdigest()
    status, body = post_json(
        f"{BASE_URL}/account-login/login",
        {"username": username, "password": password_md5},
    )
    data = body.get("data") if isinstance(body, dict) else {}
    account_token = data.get("account_token") if isinstance(data, dict) else ""
    if status != 200 or body.get("code") != "0" or not account_token:
        raise RuntimeError(f"ERP login failed: http={status} code={body.get('code')} message={body.get('message')}")
    if data.get("remind_change_password"):
        raise RuntimeError("ERP password-change reminder is active; manual login is required.")

    status, businesses_body = post_json(
        f"{BASE_URL}/account/query-account-business",
        {},
        {"accountToken": account_token},
    )
    businesses = businesses_body.get("data") if isinstance(businesses_body.get("data"), list) else []
    if status != 200 or businesses_body.get("code") != "0" or not businesses:
        raise RuntimeError("ERP business query failed or returned no tenants.")
    selected = next((row for row in businesses if row.get("business_id") == business_id), None)
    if not selected:
        available = [row.get("business_id") for row in businesses if row.get("business_id")]
        raise RuntimeError(f"ERP business_id {business_id!r} not available. Available: {available}")

    status, changed_body = post_json(
        f"{BASE_URL}/account/change-account-business",
        {},
        {"accountToken": account_token, "businessId": str(business_id)},
    )
    changed = changed_body.get("data") if isinstance(changed_body.get("data"), dict) else {}
    apps = changed.get("app_list") if isinstance(changed.get("app_list"), list) else []
    erp = next((app for app in apps if app.get("app_name") == "ERP"), None)
    erp_app_token = erp.get("app_token") if isinstance(erp, dict) else ""
    if status != 200 or changed_body.get("code") != "0" or not erp_app_token:
        raise RuntimeError("ERP business switch failed or returned no ERP app token.")

    state = LoginState(
        username=username,
        password=password,
        account_token=account_token,
        business_id=str(selected.get("business_id") or ""),
        business_name=str(selected.get("business_name") or ""),
        data_source=str(selected.get("data_source") or ""),
        admin_id=str(changed.get("admin_id") or ""),
        real_name=str(changed.get("real_name") or ""),
        user_id=str(changed.get("user_id") or ""),
        user_name=str(changed.get("user_name") or ""),
        erp_app_token=str(erp_app_token),
        apps=apps,
    )
    return state, businesses


def list_targets(port: int) -> list[dict[str, Any]]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def open_tab(port: int, url: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(url, safe="")
    request = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?{encoded}", method="PUT")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def target_for_origin(port: int) -> dict[str, Any]:
    targets = list_targets(port)
    target = next((row for row in targets if row.get("type") == "page" and "a.vsigo.cn" in (row.get("url") or "")), None)
    if target:
        return target
    return open_tab(port, "https://a.vsigo.cn/login")


def cookie_params(name: str, value: str, days: int = 3) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "domain": ".vsigo.cn",
        "path": "/",
        "expires": int(time.time() + days * 86400),
        "secure": True,
        "httpOnly": False,
        "sameSite": "Lax",
    }


def inject_browser_state(port: int, state: LoginState, pages: list[str]) -> None:
    target = target_for_origin(port)
    ws = WebSocket(target["webSocketDebuggerUrl"])
    cdp(ws, "Network.enable")
    admin = {
        "UserID": state.admin_id,
        "RealName": state.real_name,
        "UserToken": state.erp_app_token,
        "UserName": state.user_name,
    }
    cookies = {
        "dashboardtoken": base64.b64encode(f"{state.username}:{state.password}".encode("utf-8")).decode("ascii"),
        "login_password": hashlib.md5(state.password.encode("utf-8")).hexdigest(),
        "user_login_token": state.account_token,
        "businessId": state.business_id,
        "business_name": state.business_name,
        "data_source": state.data_source,
        "dataSource": state.data_source,
        "ERP_user_id": state.user_id,
        "login_username": state.user_name,
        "adminName": json.dumps(admin, ensure_ascii=False),
        "otheradminName": json.dumps(admin, ensure_ascii=False),
        "AdminID": state.admin_id,
        "AdminName": state.user_name,
        "hrinfo": state.erp_app_token,
        "app_name": "ERP",
        "token": state.erp_app_token,
    }
    for name, value in cookies.items():
        cdp(ws, "Network.setCookie", cookie_params(name, str(value)))

    cdp(ws, "Runtime.enable")
    script = """
(() => {
  localStorage.setItem("historyruleidarr", "[]");
  localStorage.setItem("otheradminName", __ADMIN__);
  localStorage.setItem("AdminName", __USERNAME__);
  localStorage.setItem("uinfo", __TOKEN__);
  localStorage.setItem("token", __TOKEN__);
  return true;
})()
"""
    script = script.replace("__ADMIN__", json.dumps(json.dumps(admin, ensure_ascii=False)))
    script = script.replace("__USERNAME__", json.dumps(state.user_name))
    script = script.replace("__TOKEN__", json.dumps(state.erp_app_token))
    cdp(ws, "Runtime.evaluate", {"expression": script, "awaitPromise": True, "returnByValue": True})

    for page in pages:
        try:
            open_tab(port, page)
        except Exception:
            pass


def sanitized_summary(state: LoginState, businesses: list[dict[str, Any]], injected: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "business_count": len(businesses),
        "selected_business_id": state.business_id,
        "selected_business_name": state.business_name,
        "user_name": state.user_name,
        "has_account_token": bool(state.account_token),
        "has_erp_app_token": bool(state.erp_app_token),
        "app_count": len(state.apps),
        "browser_state_injected": injected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-env", default="ERP_USER")
    parser.add_argument("--password-env", default="ERP_PASSWORD")
    parser.add_argument("--business-id", default=DEFAULT_BUSINESS_ID)
    parser.add_argument("--port", type=int, default=0, help="Chrome DevTools port for optional browser-state injection.")
    parser.add_argument("--inject-browser-state", action="store_true")
    parser.add_argument("--open-page", action="append", default=[], help="Page to open after browser-state injection. Can be repeated.")
    args = parser.parse_args()

    username = secret(args.user_env, ["TMALL_DAILY_ERP_USER"])
    password = secret(args.password_env, ["TMALL_DAILY_ERP_PASSWORD"])
    if not username or not password:
        raise SystemExit(f"Missing credentials in {args.user_env}/{args.password_env} or supported aliases.")

    state, businesses = login(username, password, args.business_id)
    injected = False
    if args.inject_browser_state:
        if not args.port:
            raise SystemExit("--inject-browser-state requires --port")
        pages = args.open_page or DEFAULT_PAGES
        inject_browser_state(args.port, state, pages)
        injected = True
    print(json.dumps(sanitized_summary(state, businesses, injected), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
