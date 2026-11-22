#!/usr/bin/env python3
"""Read the Kiri project-adoption YAML and emit a safe, actionable plan.

Stdlib only. Never mutates a project unless --write is passed, and even then
refuses to overwrite files it did not create.
"""

import argparse
import json
import os
import pathlib
import re
import sys
from datetime import datetime, timezone
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "project-adoption.yaml"
COMPOSE_NAMES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
OTHER_RUNTIME = re.compile(r"orbstack|docker[ -]?desktop|podman|containerd", re.IGNORECASE)


def strip_comment(line):
    quote = None
    for index, char in enumerate(line):
        if char in "\"'" and (index == 0 or line[index - 1] != "\\"):
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        if char == "#" and quote is None and (index == 0 or line[index - 1].isspace()):
            return line[:index]
    return line


def scalar(value):
    text = value.strip()
    if text == "[]":
        return []
    if text == "{}":
        return {}
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    lowered = text.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if lowered in ("null", "~", ""):
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def parse_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML subset: maps, sequences, nested blocks. No anchors/tags."""
    root: dict[str, Any] = {}
    lines = []
    for raw in text.splitlines():
        cleaned = strip_comment(raw).rstrip()
        if cleaned.strip():
            lines.append((len(cleaned) - len(cleaned.lstrip()), cleaned.strip(), raw))
    stack: list[tuple[int, Any]] = [(-1, root)]
    for index, (indent, content, raw) in enumerate(lines):
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError("invalid indentation at: " + raw)
        parent: Any = stack[-1][1]
        if content.startswith("- "):
            item_text = content[2:].strip()
            if not isinstance(parent, list):
                raise ValueError("sequence outside list at: " + raw)
            if ":" in item_text and not item_text.startswith(("\"", "'")):
                key, _, value = item_text.partition(":")
                item = {key.strip(): scalar(value)}
                parent.append(item)
                stack.append((indent, item))
            else:
                parent.append(scalar(item_text))
            continue
        if ":" not in content:
            raise ValueError("expected key: value at: " + raw)
        key, _, value = content.partition(":")
        key = key.strip()
        if value.strip():
            parent[key] = scalar(value)
        else:
            # Child container type is decided by the next meaningful line.
            child = {}
            if index + 1 < len(lines):
                next_indent, next_content, _ = lines[index + 1]
                if next_indent > indent and next_content.startswith("- "):
                    child = []
            parent[key] = child
            stack.append((indent, child))
    return root


def detect(project):
    root = pathlib.Path(project)
    compose = next((name for name in COMPOSE_NAMES if (root / name).exists()), None)
    signals: dict[str, Any] = {
        "has_compose": compose is not None,
        "has_dockerfile": (root / "Dockerfile").exists(),
        "has_package_json": (root / "package.json").exists(),
        "has_compose": compose is not None,
        "no_compose": compose is None,
        "no_dockerfile": not (root / "Dockerfile").exists(),
        "no_package_json": not (root / "package.json").exists(),
    }
    references = []
    for path in root.iterdir():
        if path.is_file() and path.suffix.lower() in (".md", ".yml", ".yaml", ".toml", ".json", ".txt"):
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            if OTHER_RUNTIME.search(text):
                references.append(str(path.name))
    signals["has_other_runtime_reference"] = bool(references)
    signals["other_runtime_files"] = references
    signals["compose_file"] = compose
    return signals


def auto_mode(signals):
    if signals["has_other_runtime_reference"]:
        return "migrate"
    if signals["has_compose"] or signals["has_dockerfile"] or signals["has_package_json"]:
        return "adopt"
    return "greenfield"


def resolve_command(command, values, project, compose):
    mapping = {
        "IMAGE": values.get("image", "<image>"),
        "PORT": values.get("port", "<port>"),
        "PROJECT": values.get("project", pathlib.Path(project).name),
        "EXISTING_COMPOSE": compose or values.get("compose", "<compose>"),
    }
    for key, value in mapping.items():
        command = command.replace(key, str(value))
    return command


def build_plan(mode, project, values, contract):
    signals = detect(project)
    selected = mode if mode != "auto" else auto_mode(signals)
    profile = contract.get("profiles", {}).get(selected)
    if not profile:
        raise SystemExit(f"unknown profile: {selected}")
    compose = signals.get("compose_file")
    defaults = contract.get("defaults", {})
    resolved_values = dict(values)
    resolved_values.setdefault("project", pathlib.Path(project).name)
    blockers = [name for name in profile.get("required_values", []) if not resolved_values.get(name)]
    steps = []
    for step in profile.get("steps", []):
        entry = dict(step)
        if "command" in entry:
            entry["command"] = resolve_command(entry["command"], resolved_values, project, compose)
        steps.append(entry)
    verification = [
        resolve_command(item, resolved_values, project, compose)
        for item in contract.get("verification", [])
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "contract": contract.get("name"),
        "mode": selected,
        "intent": profile.get("intent"),
        "project": str(pathlib.Path(project).resolve()),
        "signals": signals,
        "defaults": defaults,
        "required_values": profile.get("required_values", []),
        "blockers": blockers,
        "steps": steps,
        "safety": contract.get("safety", {}),
        "verification": verification,
        "artifacts": [defaults.get("config_file", "kiri.project.yaml")],
    }


def write_artifacts(plan, project, contract, values, force):
    root = pathlib.Path(project)
    config_name = contract.get("defaults", {}).get("config_file", "kiri.project.yaml")
    overlay_name = contract.get("defaults", {}).get("overlay_file", "docker-compose.kiri.yaml")
    written = []
    config = root / config_name
    if config.exists() and not force:
        return written, [f"{config_name} exists; use --force to overwrite"]
    payload = {
        "version": contract.get("version", 1),
        "name": contract.get("name"),
        "mode": plan["mode"],
        "project": plan["project"],
        "context": contract.get("defaults", {}).get("context", "kiri"),
        "compose_project": values.get("project", pathlib.Path(project).name),
        "values": values,
        "steps": plan["steps"],
        "verification": plan["verification"],
    }
    config.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    written.append(config_name)

    if plan["mode"] == "greenfield" and values.get("image") and values.get("port"):
        overlay = root / overlay_name
        if overlay.exists() and not force:
            return written, [f"{overlay_name} exists; use --force to overwrite"]
        text = (
            "services:\n"
            "  app:\n"
            f"    image: {values['image']}\n"
            "    ports:\n"
            f"      - \"{values['port']}:8080\"\n"
            "    restart: unless-stopped\n"
        )
        overlay.write_text(text)
        written.append(overlay_name)
    return written, []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="project directory")
    parser.add_argument("--mode", choices=("auto", "greenfield", "adopt", "migrate"), default="auto")
    parser.add_argument("--image", help="image name for greenfield")
    parser.add_argument("--port", help="host port for greenfield")
    parser.add_argument("--migration-target", help="engine being migrated from")
    parser.add_argument("--compose", help="existing compose file for adopt/migrate")
    parser.add_argument("--write", action="store_true", help="write kiri.project.yaml")
    parser.add_argument("--force", action="store_true", help="overwrite files created by this tool")
    parser.add_argument("--contract", default=str(TEMPLATE))
    args = parser.parse_args()

    contract = parse_yaml(pathlib.Path(args.contract).read_text())
    values = {
        "image": args.image,
        "port": args.port,
        "migration_target": args.migration_target,
        "compose": args.compose,
        "project": pathlib.Path(args.project).name,
    }
    plan = build_plan(args.mode, args.project, values, contract)
    result: dict[str, Any] = {"plan": plan}
    if args.write:
        if plan["blockers"]:
            result["write_error"] = "missing required values: " + ", ".join(plan["blockers"])
        else:
            written, result["write_warnings"] = write_artifacts(
                plan, args.project, contract, values, args.force
            )
            result["written"] = written
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
