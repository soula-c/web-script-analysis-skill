#!/usr/bin/env python3
"""Summarize likely API endpoints from a sanitized HAR file."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from urllib.parse import urlparse


SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-csrf-token",
    "x-xsrf-token",
    "token",
}


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def content_mime(entry: dict) -> str:
    return entry.get("response", {}).get("content", {}).get("mimeType", "") or ""


def parse_jsonish(text: str):
    if not text or not text.strip():
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def top_keys(value, limit: int = 12):
    if isinstance(value, dict):
        return list(value.keys())[:limit]
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return list(value[0].keys())[:limit]
    return []


def summarize_entry(entry: dict) -> dict:
    request = entry.get("request", {})
    response = entry.get("response", {})
    url = request.get("url", "")
    parsed = urlparse(url)
    post_data = request.get("postData", {}) or {}
    post_text = post_data.get("text", "") or ""
    response_text = response.get("content", {}).get("text", "") or ""
    req_json = parse_jsonish(post_text)
    res_json = parse_jsonish(response_text)
    header_names = [
        h.get("name", "")
        for h in request.get("headers", [])
        if h.get("name", "").lower() not in SENSITIVE_HEADERS
    ]
    return {
        "method": request.get("method", ""),
        "host": parsed.netloc,
        "path": parsed.path,
        "status": response.get("status"),
        "mime": content_mime(entry),
        "request_keys": top_keys(req_json),
        "response_keys": top_keys(res_json),
        "safe_header_names": header_names[:12],
    }


def is_candidate(entry: dict) -> bool:
    request = entry.get("request", {})
    url = request.get("url", "")
    path = urlparse(url).path.lower()
    mime = content_mime(entry).lower()
    if any(x in path for x in ["/log", "/track", "/beacon", "/captcha", ".js", ".css", ".png", ".jpg", ".svg"]):
        return False
    return "json" in mime or request.get("method") in {"POST", "PUT", "PATCH"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("har", type=Path, help="Path to a sanitized HAR file")
    parser.add_argument("--top", type=int, default=50, help="Maximum endpoint rows to print")
    args = parser.parse_args()

    har = load_json(args.har)
    entries = har.get("log", {}).get("entries", [])
    grouped = collections.OrderedDict()
    for entry in entries:
        if not is_candidate(entry):
            continue
        item = summarize_entry(entry)
        key = (item["method"], item["host"], item["path"])
        grouped.setdefault(key, item | {"count": 0, "statuses": collections.Counter()})
        grouped[key]["count"] += 1
        grouped[key]["statuses"][str(item["status"])] += 1

    rows = sorted(grouped.values(), key=lambda x: (-x["count"], x["host"], x["path"]))
    for row in rows[: args.top]:
        statuses = ",".join(f"{k}:{v}" for k, v in row.pop("statuses").items())
        print(json.dumps(row | {"statuses": statuses}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
