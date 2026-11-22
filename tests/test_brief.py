"""Tests for the one-call agent brief (stdlib only)."""

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("kiri_brief", ROOT / "scripts" / "kiri_brief.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load kiri_brief.py")
brief = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(brief)

BASE = {
    "binary": "/usr/bin/kiri",
    "facts_mode": "live",
    "update_available": False,
    "engine_active": True,
    "engine_reachable": True,
    "ci": False,
    "incident": False,
    "foreign_socket": False,
    "running_containers": [],
    "images": [],
}


class StageTests(unittest.TestCase):
    def stage(self, **overrides):
        signals = dict(BASE)
        signals.update(overrides)
        return brief.classify(signals)

    def test_priority_order(self):
        self.assertEqual(self.stage(binary=None), "install_required")
        self.assertEqual(self.stage(update_available=True), "upgrade_available")
        self.assertEqual(self.stage(engine_active=False, update_available=True), "upgrade_available")
        self.assertEqual(self.stage(engine_active=False), "engine_stopped")
        self.assertEqual(self.stage(engine_reachable=False), "engine_unreachable")
        self.assertEqual(self.stage(ci=True, incident=True), "ci_runner")
        self.assertEqual(self.stage(incident=True), "incident")
        self.assertEqual(self.stage(foreign_socket=True), "migration")
        self.assertEqual(self.stage(running_containers=["web"]), "workload_running")
        self.assertEqual(self.stage(images=["alpine:latest"]), "ready_idle")
        self.assertEqual(self.stage(), "greenfield")

    def test_degraded_facts_do_not_claim_upgrade(self):
        self.assertEqual(self.stage(facts_mode="degraded", update_available=True), "greenfield")

    def test_next_actions_mention_docker_host_override(self):
        actions = brief.next_actions(
            "engine_unreachable", dict(BASE, docker_host_override=True), {}
        )
        self.assertTrue(any("DOCKER_HOST" in action for action in actions))


if __name__ == "__main__":
    unittest.main()
