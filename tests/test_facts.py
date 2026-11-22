"""Tests for runtime source discovery (stdlib only)."""

import importlib.util
import json
import os
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kiri_facts", ROOT / "scripts" / "kiri_facts.py")
facts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(facts)


def meta(url, body, status="ok", final=None):
    return {
        "url": url,
        "status": status,
        "final_url": final or url,
        "http_status": 200 if status == "ok" else None,
        "bytes": len(body),
        "sha256": "0" * 64,
        "error": None if status == "ok" else "simulated failure",
    }


class SourceDiscoveryTests(unittest.TestCase):
    def test_follows_moved_upstream_without_code_edits(self):
        boot = facts.BOOTSTRAP_REPO
        site = "https://new-kiri.example/"
        release_api = "https://api.github.com/repos/libracoder/kiri/releases/latest"
        contents_api = boot + "/contents/docs/features.md?ref=trunk"
        cli_docs = site + "docs/cli/"
        checksums = "https://cdn.new-kiri.example/SHA256SUMS-linux"
        features = "https://raw.githubusercontent.com/libracoder/kiri/trunk/docs/features.md"

        repo = {
            "homepage": site,
            "default_branch": "trunk",
            "releases_url": "https://api.github.com/repos/libracoder/kiri/releases{/id}",
            "html_url": "https://github.com/libracoder/kiri",
        }
        release = {
            "tag_name": "v9.9.9",
            "published_at": "2030-01-01T00:00:00Z",
            "assets": [{"name": "kiri_9.9.9_amd64.deb"}],
        }
        home_html = (
            '<a href="/docs/cli/">Command line and CI</a>'
            '<a href="/install.sh">Install</a>'
            f'<a href="{checksums}">SHA256SUMS-linux</a>'
        ).encode()
        body_by_url = {
            boot: (json.dumps(repo).encode(), meta(boot, json.dumps(repo).encode())),
            site: (home_html, meta(site, home_html)),
            release_api: (json.dumps(release).encode(), meta(release_api, json.dumps(release).encode())),
            cli_docs: (b"# CLI", meta(cli_docs, b"# CLI")),
            checksums: (b"abc  kiri_9.9.9_amd64.deb\n", meta(checksums, b"abc  kiri_9.9.9_amd64.deb\n")),
            contents_api: (json.dumps({"download_url": features}).encode(), meta(contents_api, b"{}")),
            features: (b"# Features", meta(features, b"# Features")),
        }

        def fake_fetch(url):
            if url in body_by_url:
                return body_by_url[url]
            return b"", meta(url, b"", status="error")

        original_version = facts.local_version
        original_which = facts.shutil.which
        original_run = facts.run
        facts.local_version = lambda: "0.2.2"
        facts.shutil.which = lambda cmd: "/usr/bin/kiri" if cmd == "kiri" else None
        facts.run = lambda cmd: ("kiri COMMAND\nkiri daemon\n", 0)
        try:
            report = facts.resolve(fake_fetch)
        finally:
            facts.local_version = original_version
            facts.shutil.which = original_which
            facts.run = original_run

        self.assertEqual(report["mode"], "live")
        self.assertEqual(report["discovery"]["homepage"], site)
        self.assertEqual(report["discovery"]["default_branch"], "trunk")
        self.assertEqual(report["discovery"]["resolved_urls"]["cli_docs"], cli_docs)
        self.assertEqual(report["discovery"]["resolved_urls"]["checksums"], checksums)
        self.assertEqual(report["discovery"]["resolved_urls"]["features_docs"], features)
        self.assertEqual(report["upstream"]["version"], "9.9.9")
        self.assertTrue(report["comparison"]["update_available"])

    def test_degraded_without_network(self):
        def dead_fetch(url):
            return b"", meta(url, b"", status="error")

        report = facts.resolve(dead_fetch)
        self.assertEqual(report["mode"], "degraded")
        self.assertFalse(report["comparison"]["update_available"])
        self.assertTrue(any(s["status"] == "error" for s in report["sources"].values()))

    def test_github_token_header_is_scoped(self):
        original = os.environ.get("GITHUB_TOKEN")
        os.environ["GITHUB_TOKEN"] = "test-token-value"
        try:
            api_headers = facts.request_headers("https://api.github.com/repos/libracoder/kiri")
            site_headers = facts.request_headers("https://runkiri.com/")
        finally:
            if original is None:
                os.environ.pop("GITHUB_TOKEN", None)
            else:
                os.environ["GITHUB_TOKEN"] = original
        self.assertEqual(api_headers["Authorization"], "Bearer test-token-value")
        self.assertNotIn("Authorization", site_headers)


if __name__ == "__main__":
    unittest.main()
