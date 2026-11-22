"""Tests for the declarative YAML adoption contract (stdlib only)."""

import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("kiri_apply", ROOT / "scripts" / "kiri_apply.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load kiri_apply.py")
apply_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(apply_module)


class AdoptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = apply_module.parse_yaml(
            (ROOT / "templates" / "project-adoption.yaml").read_text()
        )

    def test_contract_shape(self):
        self.assertEqual(self.contract["name"], "kiri-project-adoption")
        self.assertEqual(set(self.contract["profiles"]), {"greenfield", "adopt", "migrate"})
        self.assertIsInstance(self.contract["profiles"]["greenfield"]["steps"], list)
        self.assertIsInstance(self.contract["profiles"]["adopt"]["required_values"], list)
        self.assertIsInstance(self.contract["safety"]["never"], list)

    def test_auto_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            self.assertEqual(apply_module.auto_mode(apply_module.detect(root)), "greenfield")
            (root / "docker-compose.yml").write_text("services: {}\n")
            self.assertEqual(apply_module.auto_mode(apply_module.detect(root)), "adopt")
            (root / "README.md").write_text("moved from OrbStack\n")
            self.assertEqual(apply_module.auto_mode(apply_module.detect(root)), "migrate")

    def test_greenfield_plan_and_write(self):
        with tempfile.TemporaryDirectory() as folder:
            values = {"image": "nginx:alpine", "port": "8080", "project": "demo"}
            plan = apply_module.build_plan("greenfield", folder, values, self.contract)
            self.assertEqual(plan["blockers"], [])
            self.assertIn("nginx:alpine", plan["steps"][1]["command"])
            written, warnings = apply_module.write_artifacts(plan, folder, self.contract, values, False)
            self.assertEqual(warnings, [])
            self.assertIn("kiri.project.yaml", written)
            self.assertIn("docker-compose.kiri.yaml", written)
            config = json.loads((pathlib.Path(folder) / "kiri.project.yaml").read_text())
            self.assertEqual(config["mode"], "greenfield")
            overlay = (pathlib.Path(folder) / "docker-compose.kiri.yaml").read_text()
            self.assertIn('"8080:8080"', overlay)

    def test_missing_values_are_blockers(self):
        with tempfile.TemporaryDirectory() as folder:
            plan = apply_module.build_plan("greenfield", folder, {}, self.contract)
            self.assertEqual(plan["blockers"], ["image", "port"])

    def test_existing_compose_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (root / "docker-compose.yml").write_text("services: {}\n")
            plan = apply_module.build_plan("adopt", folder, {}, self.contract)
            written, warnings = apply_module.write_artifacts(plan, folder, self.contract, {}, False)
            self.assertIn("kiri.project.yaml", written)
            self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
