#!/usr/bin/env python3
"""Resolve current Kiri facts by discovering official sources at run time.

Only the upstream repository identity is a bootstrap constant. Every
operational URL (site, docs, release feed, checksum feed, feature file) is
discovered from GitHub metadata and the official site on each invocation.
Nothing here is a promise about a release: bodies are hashed and every source
reports its own status so the caller can see exactly what was verified.

Stdlib only, cross-platform. Prints one JSON object to stdout.
"""

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

BOOTSTRAP_REPO = os.environ.get("KIRI_BOOTSTRAP_REPO", "https://api.github.com/repos/libracoder/kiri")
FALLBACK_SITE = "https://runkiri.com/"
USER_AGENT = "curl/8.5.0"  # Cloudflare rejects python-urllib's default UA
TIMEOUT = 12
VERSION_RE = re.compile(r"\b\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.]+)?\b")


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


def request_headers(url):
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_url(url):
    entry = {
        "url": url,
        "status": "error",
        "final_url": None,
        "http_status": None,
        "bytes": 0,
        "sha256": None,
        "error": None,
    }
    try:
        request = urllib.request.Request(url, headers=request_headers(url))
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read()
            entry["final_url"] = getattr(response, "url", url)
            entry["http_status"] = getattr(response, "status", None)
        entry["status"] = "ok"
        entry["bytes"] = len(body)
        entry["sha256"] = hashlib.sha256(body).hexdigest()
        return body, entry
    except (urllib.error.URLError, OSError, ValueError) as exc:
        entry["error"] = f"{type(exc).__name__}: {exc}"
        return b"", entry


def fetch_json(url, fetch_fn):
    body, meta = fetch_fn(url)
    if meta["status"] != "ok":
        return None, meta
    try:
        return json.loads(body.decode("utf-8", errors="replace")), meta
    except (ValueError, AttributeError) as exc:
        meta["status"] = "error"
        meta["error"] = f"invalid JSON: {exc}"
        return None, meta


def links_from(body, base):
    text = body.decode("utf-8", errors="replace")
    parser = LinkParser()
    try:
        parser.feed(text)
    except Exception:
        return []
    result = []
    for href, label in parser.links:
        absolute = urllib.parse.urljoin(base, href)
        if urllib.parse.urlsplit(absolute).scheme in ("http", "https"):
            result.append((absolute, label))
    return result


def pick(links, predicate):
    for url, label in links:
        if predicate(url, label):
            return url
    return None


def is_cli_docs(url, label):
    parts = urllib.parse.urlsplit(url)
    path = parts.path.rstrip("/").lower()
    blob = (parts.netloc + parts.path + label).lower()
    return (path.endswith("/cli") and "docs" in blob) or "cli docs" in blob or "command line" in blob


def is_download(url, label):
    blob = (urllib.parse.urlsplit(url).path + label).lower()
    return "download" in blob or "releases" in blob or "install" in blob


def is_checksum(url, label):
    blob = (urllib.parse.urlsplit(url).path + label).lower()
    return "sha256sums" in blob or "sha256" in blob


def is_install(url, label):
    path = urllib.parse.urlsplit(url).path.lower()
    return path.endswith("install.sh") or "install.sh" in path


def version_values(text):
    return sorted({(tuple(int(x) for x in v.split("-")[0].split("+")[0].split(".")), v)
                   for v in VERSION_RE.findall(text)}, reverse=True)


def strongest_version(texts):
    values = []
    for text in texts:
        values.extend(version_values(text))
    return values[0][1] if values else None


def raw_features_url(repo_data, branch):
    html_url = (repo_data or {}).get("html_url") or re.sub(
        r"^https://api\.github\.com/repos/", "https://github.com/", BOOTSTRAP_REPO
    )
    html_url = html_url.rstrip("/")
    raw = html_url.replace("https://github.com/", "https://raw.githubusercontent.com/", 1)
    return f"{raw}/{branch}/docs/features.md"


def discover(fetch_fn):
    """Return (resolved_urls, discovery_notes, preliminary_sources)."""
    notes = []
    urls = {}
    meta = {}

    repo_data, repo_meta = fetch_json(BOOTSTRAP_REPO, fetch_fn)
    meta["repo_api"] = repo_meta
    if repo_data:
        urls["repo_api"] = BOOTSTRAP_REPO
        homepage = (repo_data.get("homepage") or "").strip()
        branch = repo_data.get("default_branch") or "main"
        releases_template = repo_data.get("releases_url") or ""
        release_api = releases_template.split("{")[0].rstrip("/") + "/latest" if releases_template else BOOTSTRAP_REPO + "/releases/latest"
        urls["release_api"] = release_api
    else:
        notes.append("repository metadata unavailable; using bootstrap fallbacks")
        homepage = FALLBACK_SITE
        branch = "main"
        urls["repo_api"] = BOOTSTRAP_REPO
        urls["release_api"] = BOOTSTRAP_REPO + "/releases/latest"

    if homepage and not homepage.startswith("http"):
        homepage = "https://" + homepage
    urls["homepage"] = homepage

    site_body, site_meta = fetch_fn(homepage)
    meta["homepage"] = site_meta
    site_links = links_from(site_body, homepage) if site_meta["status"] == "ok" else []

    urls["cli_docs"] = (
        pick(site_links, is_cli_docs)
        or urllib.parse.urljoin(homepage, "/docs/cli/")
    )
    download_page = pick(site_links, is_download)
    install_script = pick(site_links, is_install) or urllib.parse.urljoin(homepage, "/install.sh")
    urls["install_script"] = install_script
    meta["install_script"] = {"url": install_script, "discovered": install_script in dict(site_links)}

    checksum = pick(site_links, is_checksum)
    if not checksum and download_page:
        page_body, page_meta = fetch_fn(download_page)
        meta["download_page"] = page_meta
        if page_meta["status"] == "ok":
            page_links = links_from(page_body, page_meta.get("final_url") or download_page)
            checksum = pick(page_links, is_checksum)
            if not download_page.endswith("/download"):
                urls["download_page"] = download_page

    if not checksum:
        script_body, script_meta = fetch_fn(install_script)
        meta["install_script_fetch"] = script_meta
        if script_meta["status"] == "ok":
            script = script_body.decode("utf-8", errors="replace")
            site_match = re.search(r'SITE=["\']?(https?://[^\s"\']+)', script)
            sums_match = re.search(r'([A-Za-z0-9._-]*SHA256SUMS[A-Za-z0-9._-]*)', script, re.IGNORECASE)
            if site_match and sums_match:
                checksum = urllib.parse.urljoin(site_match.group(1).rstrip("/") + "/", sums_match.group(1))
    urls["checksums"] = checksum

    contents_api = f"{BOOTSTRAP_REPO}/contents/docs/features.md?ref={urllib.parse.quote(branch)}"
    contents, contents_meta = fetch_json(contents_api, fetch_fn)
    meta["features_contents"] = contents_meta
    if isinstance(contents, dict):
        urls["features_docs"] = contents.get("download_url") or raw_features_url(repo_data, branch)
    else:
        urls["features_docs"] = raw_features_url(repo_data, branch)
        notes.append("features URL derived from repository metadata")

    return urls, notes, meta, repo_data, branch


def run(cmd):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
        return (proc.stdout or proc.stderr).strip(), proc.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{type(exc).__name__}: {exc}", 1


def local_version():
    for command in (["dpkg-query", "-W", "-f=${Version}", "kiri"],
                    ["rpm", "-q", "--qf", "%{VERSION}", "kiri"]):
        if not shutil.which(command[0]):
            continue
        out, code = run(command)
        if code == 0 and out:
            match = VERSION_RE.search(out)
            return match.group(0) if match else out
    return None


def compare(left, right):
    def parts(value):
        match = VERSION_RE.search(value or "")
        if not match:
            return None
        return tuple(int(x) for x in match.group(0).split("-")[0].split("+")[0].split("."))

    a, b = parts(left), parts(right)
    if not a or not b:
        return None
    return (a > b) - (a < b)


def resolve(fetch_fn=fetch_url):
    urls, notes, discovery_meta, repo_data, branch = discover(fetch_fn)

    sources = {}
    bodies = {}
    required = ["repo_api", "release_api", "checksums", "cli_docs", "features_docs"]
    for name in required:
        url = urls.get(name)
        if not url:
            sources[name] = {"url": None, "status": "error", "error": "source not discovered"}
            bodies[name] = ""
            continue
        body, meta = fetch_fn(url)
        sources[name] = meta
        if name == "features_docs" and url.endswith("?raw=1"):
            pass
        bodies[name] = body.decode("utf-8", errors="replace")

    # GitHub contents API returns base64 when download_url is absent.
    if sources["features_docs"]["status"] == "ok" and bodies["features_docs"].lstrip().startswith("{") and \
            urls["features_docs"] == f"{BOOTSTRAP_REPO}/contents/docs/features.md?ref={urllib.parse.quote(branch)}":
        try:
            payload = json.loads(bodies["features_docs"])
            if isinstance(payload, dict) and payload.get("content"):
                bodies["features_docs"] = base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            pass

    release_version = None
    release_date = None
    assets = []
    if sources["release_api"]["status"] == "ok":
        try:
            data = json.loads(bodies["release_api"])
            release_version = (data.get("tag_name") or "").lstrip("v") or None
            release_date = data.get("published_at")
            assets = [item.get("name", "") for item in data.get("assets", []) if isinstance(item, dict)]
        except (ValueError, AttributeError):
            pass

    checksum_lines = [line for line in bodies["checksums"].splitlines() if "kiri" in line.lower()]
    checksum_versions = strongest_version("\n".join(checksum_lines)) if checksum_lines else None
    upstream = release_version or checksum_versions or strongest_version(" ".join(assets))

    installed = local_version()
    binary_path = shutil.which("kiri")
    help_head = None
    if binary_path:
        out, code = run(["kiri", "--help"])
        if code == 0:
            help_head = out.splitlines()[:12]

    delta = compare(installed, upstream)
    cli_docs = urls.get("cli_docs")
    features_docs = urls.get("features_docs")
    guidance = [
        f"Read {cli_docs} for the current command and platform table." if cli_docs else "CLI docs were not discovered; rely on local kiri --help.",
        f"Read {features_docs} for current feature support." if features_docs else "Feature docs were not discovered.",
        "If mode is degraded, report unverified upstream facts and name the failed sources.",
        "The skill needs no version bump: sources are discovered again on every run.",
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "live" if all(sources[name]["status"] == "ok" for name in required) else "degraded",
        "discovery": {
            "bootstrap": BOOTSTRAP_REPO,
            "homepage": urls.get("homepage"),
            "default_branch": branch,
            "resolved_urls": urls,
            "notes": notes,
            "detail": discovery_meta,
        },
        "sources": sources,
        "upstream": {
            "version": upstream,
            "release_version": release_version,
            "checksum_version": checksum_versions,
            "release_assets": assets[:20],
            "release_tag_date": release_date,
        },
        "local": {
            "kiri_binary": binary_path,
            "installed_version": installed,
            "help_head": help_head,
        },
        "comparison": {
            "update_available": delta == -1,
            "matches_upstream": delta == 0,
        },
        "guidance": guidance,
    }


def main():
    print(json.dumps(resolve(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
