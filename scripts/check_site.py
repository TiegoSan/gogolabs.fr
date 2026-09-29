#!/usr/bin/env python3
"""Read-only checks for public routes, local links, metadata, and App Store state."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


EXPECTED_ROUTES = {
    "/": "index.html",
    "/support/": "support/index.html",
    "/support.html": "support.html",
    "/support-fr.html": "support-fr.html",
    "/privacy-policy.html": "privacy-policy.html",
    "/privacy-policy-fr.html": "privacy-policy-fr.html",
    "/legal-notice.html": "legal-notice.html",
    "/perroquet/": "perroquet/index.html",
    "/perroquet/support/": "perroquet/support/index.html",
    "/perroquet/privacy/": "perroquet/privacy/index.html",
}

PUBLIC_APPS = {
    "6761286310": ("Coupez!", "2.0"),
    "6761866606": ("Glass Master", "1.3"),
    "6769386761": ("Odile!", "1.0"),
    "6764426243": ("FeedBacks!", "1.0"),
    "6766993396": ("Perroquet Piano", "1.2"),
    "6780059863": ("DoReQuiz", "1.3"),
}

MATERIAL_VERSIONS = {
    "6761286310": "2.0",
    "6761866606": "1.5",
    "6769386761": "1.0",
    "6764426243": "1.2",
    "6766993396": "1.2",
    "6780059863": "1.3",
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.canonicals: list[str] = []
        self.og_urls: list[str] = []
        self.json_ld: list[str] = []
        self._json_depth = 0
        self._json_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"a", "link"} and values.get("href"):
            self.links.append(values["href"] or "")
        if tag in {"img", "script"} and values.get("src"):
            self.links.append(values["src"] or "")
        if tag == "link" and values.get("rel") == "canonical" and values.get("href"):
            self.canonicals.append(values["href"] or "")
        if tag == "meta" and values.get("property") == "og:url" and values.get("content"):
            self.og_urls.append(values["content"] or "")
        if tag == "script" and values.get("type") == "application/ld+json":
            self._json_depth = 1
            self._json_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json_depth:
            self.json_ld.append("".join(self._json_parts))
            self._json_depth = 0

    def handle_data(self, data: str) -> None:
        if self._json_depth:
            self._json_parts.append(data)


def public_html(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.html")
        if not any(part.startswith("_") for part in path.relative_to(root).parts)
        and "private" not in path.relative_to(root).parts
    )


def resolve_local(root: Path, page: Path, raw: str) -> Path | None:
    parsed = urlparse(raw)
    if parsed.scheme or parsed.netloc or raw.startswith(("mailto:", "tel:", "#")):
        return None
    clean = parsed.path
    if not clean:
        return None
    if clean.startswith("/"):
        candidate = root / clean.lstrip("/")
    else:
        candidate = page.parent / clean
    if clean.endswith("/"):
        candidate = candidate / "index.html"
    elif candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate


def check_local(root: Path) -> list[str]:
    failures: list[str] = []
    for route, relative in EXPECTED_ROUTES.items():
        if not (root / relative).is_file():
            failures.append(f"missing route {route}: {relative}")

    pages = public_html(root)
    app_ids: set[str] = set()
    for page in pages:
        parser = PageParser()
        text = page.read_text(encoding="utf-8")
        parser.feed(text)
        label = page.relative_to(root)
        if len(parser.canonicals) != 1:
            failures.append(f"{label}: expected one canonical, found {len(parser.canonicals)}")
        if page.name != "support.html" and not parser.og_urls:
            failures.append(f"{label}: missing og:url")
        if "/support.html" in text and page.name != "support.html":
            failures.append(f"{label}: legacy /support.html link")
        if "id1736156363" in text:
            failures.append(f"{label}: obsolete developer id")
        for match in re.finditer(r"apps\.apple\.com/.+?/id(\d+)", text):
            if match.group(1) != "1887696838":
                app_ids.add(match.group(1))
        for payload in parser.json_ld:
            try:
                json.loads(payload)
            except json.JSONDecodeError as error:
                failures.append(f"{label}: invalid JSON-LD: {error}")
        for raw in parser.links:
            target = resolve_local(root, page, raw)
            if target is not None and not target.exists():
                failures.append(f"{label}: broken local reference {raw} -> {target.relative_to(root)}")

    expected_ids = set(PUBLIC_APPS)
    if app_ids != expected_ids:
        failures.append(f"App Store ids differ: expected {sorted(expected_ids)}, found {sorted(app_ids)}")
    index_text = (root / "index.html").read_text(encoding="utf-8")
    for app_id, (name, version) in PUBLIC_APPS.items():
        if app_id not in index_text or f'"softwareVersion": "{version}"' not in index_text:
            failures.append(f"index metadata missing {name} {version} ({app_id})")
    manifest_path = root / "assets/app-store-assets.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_apps = {item["id"]: item for item in manifest["apps"]}
    except (OSError, KeyError, json.JSONDecodeError) as error:
        failures.append(f"invalid App Store asset manifest: {error}")
    else:
        if set(manifest_apps) != expected_ids:
            failures.append("App Store asset manifest ids differ from the public app set")
        for app_id, (name, version) in PUBLIC_APPS.items():
            item = manifest_apps.get(app_id, {})
            if item.get("name") != name or item.get("publicVersion") != version:
                failures.append(f"asset manifest metadata differs for {name}")
            if item.get("materialVersion") != MATERIAL_VERSIONS[app_id]:
                failures.append(f"asset manifest material version differs for {name}")
            if not item.get("descriptionLocalization"):
                failures.append(f"asset manifest provenance missing for {name}")
            for field in ("icon", "screenshot"):
                relative = item.get(field)
                if not relative or not (root / relative).is_file():
                    failures.append(f"asset manifest missing {field} for {name}")
    return failures


def check_remote() -> list[str]:
    failures: list[str] = []
    ids = ",".join(PUBLIC_APPS)
    request = Request(
        f"https://itunes.apple.com/lookup?id={ids}&country=fr",
        headers={"User-Agent": "GogoLabsSiteCheck/1.0"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            results = json.load(response).get("results", [])
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as urllib_error:
        try:
            response = subprocess.run(
                ["curl", "-fsS", request.full_url],
                check=True,
                capture_output=True,
                text=True,
                timeout=25,
            )
            results = json.loads(response.stdout).get("results", [])
        except (subprocess.SubprocessError, json.JSONDecodeError) as curl_error:
            return [f"Apple lookup failed: urllib={urllib_error}; curl={curl_error}"]
    by_id = {str(item.get("trackId")): item for item in results}
    for app_id, (name, version) in PUBLIC_APPS.items():
        item = by_id.get(app_id)
        if not item:
            failures.append(f"Apple lookup missing {name} ({app_id})")
        elif item.get("version") != version:
            failures.append(f"Apple version drift for {name}: expected {version}, found {item.get('version')}")
        elif not item.get("artworkUrl512") or not item.get("screenshotUrls"):
            failures.append(f"Apple public artwork incomplete for {name}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--remote", action="store_true", help="also verify current Apple public metadata")
    args = parser.parse_args()
    root = args.root.resolve()
    failures = check_local(root)
    if args.remote:
        failures.extend(check_remote())
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"OK: {len(public_html(root))} public HTML files; {len(PUBLIC_APPS)} App Store apps verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
