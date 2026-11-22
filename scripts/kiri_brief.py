#!/usr/bin/env python3
"""One-call agent brief for Kiri: stage, risks, next actions, verification.

Combines live upstream facts from kiri_facts.py with local engine signals.
Stdlib only, cross-platform. Prints one JSON object. Never mutates state.
"""

import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("kiri_facts", os.path.join(HERE, "kiri_facts.py"))
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load kiri_facts.py next to kiri_brief.py")
facts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(facts)

CI_KEYS = ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "CIRCLECI", "BUILDKITE", "TEAMCITY_VERSION")
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{16,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{16,}"),
    re.compile(r"(?i)(token|password|secret)=[^\s]+"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._-]{8,}"),
)


def redact(text):
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("<redacted>", text)
    return text


def run(cmd, timeout=8):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return (proc.stdout or "").strip(), proc.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{type(exc).__name__}: {exc}", 1


def docker_cmd(*args, timeout=8):
    return run(["docker", "--context", "kiri", *args], timeout=timeout)


def lines(text, limit=50):
    return [line for line in text.splitlines() if line.strip()][:limit]


def classify(signals):
    """Pure stage classification; ordered by escalation priority."""
    if not signals.get("binary"):
        return "install_required"
    if signals.get("facts_mode") != "degraded" and signals.get("update_available"):
        return "upgrade_available"
    if not signals.get("engine_active"):
        return "engine_stopped"
    if not signals.get("engine_reachable"):
        return "engine_unreachable"
    if signals.get("ci"):
        return "ci_runner"
    if signals.get("incident"):
        return "incident"
    if signals.get("foreign_socket"):
        return "migration"
    if signals.get("running_containers"):
        return "workload_running"
    if signals.get("images"):
        return "ready_idle"
    return "greenfield"


def next_actions(stage, signals, urls):
    installer = urls.get("install_script") or "the installer URL under discovery.resolved_urls"
    release = urls.get("release_api") or "the release URL under discovery.resolved_urls"
    common = [
        "python3 <skill_dir>/scripts/kiri_brief.py  # re-read after every change",
    ]
    playbooks = {
        "install_required": [
            f"Open the discovered download page and install Kiri: {installer}",
            "python3 <skill_dir>/scripts/kiri_brief.py",
        ],
        "upgrade_available": [
            f"Read release notes: {release}",
            "Install from the discovered installer, then restart the engine in a maintenance window",
            "sudo systemctl restart kiri  # Linux, if applicable",
        ],
        "engine_stopped": [
            "sudo systemctl enable --now kiri  # Linux systemd",
            "kiri daemon  # macOS foreground bootstrap when no app is installed",
            "Start the WSL distro that hosts Kiri  # Windows",
        ],
        "engine_unreachable": [
            "bash <skill_dir>/scripts/kiri-context.sh",
            "docker --context kiri info --format '{{.ServerVersion}} {{.OperatingSystem}}'",
            "kiri diag logs --errors -n 50",
        ],
        "ci_runner": [
            "Use templates/github-actions.yml as the CI skeleton",
            "Run the smoke container before any workload step",
            "Tear down the smoke container in an always step",
        ],
        "incident": [
            "kiri diag logs --errors -n 100",
            "kiri diag report --out ./kiri-report.txt  # redacted bundle",
            "Check restarts: systemctl status kiri --no-pager  # Linux",
        ],
        "migration": [
            "Keep the old engine installed until the Kiri smoke test passes",
            "kiri import --list  # macOS only; use docker save/load on Linux",
            "docker context use kiri only after images and volumes are verified",
        ],
        "workload_running": [
            "docker --context kiri ps --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}'",
            "docker --context kiri compose ls",
            "Verify health before any restart or down",
        ],
        "ready_idle": [
            "docker --context kiri run --rm alpine echo KIRI_OK",
            "docker --context kiri compose -f templates/compose-smoke.yaml up -d",
        ],
        "greenfield": [
            "Start from templates/compose-smoke.yaml and adapt names, image and ports",
            "docker --context kiri compose -f docker-compose.yml up -d",
            "Confirm with the verification list below",
        ],
    }
    actions = playbooks.get(stage, [])
    if signals.get("docker_host_override"):
        actions.insert(0, "Unset DOCKER_HOST or always pass --context kiri; env overrides contexts")
    if not signals.get("group_ok") and platform.system() == "Linux":
        actions.insert(0, "Use a new login for the kiri group, or run with sudo; group is root-equivalent")
    return common + actions


def probe():
    system = platform.system()
    binary = shutil.which("kiri")
    docker = shutil.which("docker")

    if system == "Linux":
        state_out, _ = run(["systemctl", "is-active", "kiri"])
        engine_active = state_out == "active"
    elif system == "Darwin":
        out, code = run(["pgrep", "-f", "kiri daemon"])
        engine_active = code == 0 and bool(out)
    else:
        engine_active = bool(binary)

    context_exists = False
    reach_out = ""
    if docker:
        _, context_code = run(["docker", "context", "inspect", "kiri"])
        context_exists = context_code == 0
        reach_out, _ = docker_cmd("info", "--format", "{{.ServerVersion}} {{.OperatingSystem}}", timeout=12)
    engine_reachable = "Kiri" in reach_out

    running_out, _ = docker_cmd("ps", "--format", "{{.Names}}|{{.Image}}|{{.Status}}") if docker else ("", 1)
    all_out, _ = docker_cmd("ps", "-a", "--format", "{{.Names}}|{{.Image}}|{{.Status}}") if docker else ("", 1)
    images_out, _ = docker_cmd("images", "--format", "{{.Repository}}:{{.Tag}}") if docker else ("", 1)
    logs_out, logs_code = run(["kiri", "diag", "logs", "--errors", "-n", "20"], timeout=12) if binary else ("", 1)
    error_lines = [
        line for line in logs_out.splitlines()
        if re.search(r"\b(ERROR|FATAL|PANIC|CRITICAL)\b", line)
    ]
    incident = logs_code == 0 and bool(error_lines[:3])

    foreign_socket = False
    if system == "Linux":
        sock = "/run/docker.sock"
        if os.path.exists(sock):
            if os.path.islink(sock):
                foreign_socket = "kiri" not in (os.readlink(sock) or "").lower()
            else:
                foreign_socket = True

    group_ok = True
    if system == "Linux" and os.geteuid() != 0:
        try:
            import grp
            group_ok = "kiri" in {g.gr_name for g in grp.getgrall() if os.getgid() in g.gr_mem or g.gr_gid in os.getgroups()}
        except (ImportError, OSError):
            group_ok = False

    return {
        "platform": {"system": system, "machine": platform.machine()},
        "binary": binary,
        "docker": docker,
        "docker_host_override": bool(os.environ.get("DOCKER_HOST")),
        "ci": any(os.environ.get(key) for key in CI_KEYS),
        "engine_active": engine_active,
        "engine_reachable": engine_reachable,
        "engine_info": reach_out or None,
        "context_exists": context_exists,
        "foreign_socket": foreign_socket,
        "group_ok": group_ok,
        "running_containers": lines(running_out),
        "all_containers": lines(all_out),
        "images": lines(images_out),
        "incident": incident,
        "incident_excerpt": redact("\n".join(error_lines[:10])) if incident else None,
    }


def build_report():
    local = probe()
    try:
        upstream = facts.resolve()
    except Exception as exc:  # degraded mode must never break the brief
        upstream = {
            "mode": "degraded",
            "error": f"{type(exc).__name__}: {exc}",
            "sources": {},
            "discovery": {"resolved_urls": {}},
            "upstream": {"version": None},
            "comparison": {"update_available": False, "matches_upstream": False},
        }

    signals = dict(local)
    signals["facts_mode"] = upstream.get("mode", "degraded")
    signals["update_available"] = bool(upstream.get("comparison", {}).get("update_available"))
    stage = classify(signals)
    urls = upstream.get("discovery", {}).get("resolved_urls", {})

    risks = ["Containers share the host kernel; Kiri is not a sandbox for hostile code."]
    if not local["binary"]:
        risks.append("Kiri binary missing; no container operation is possible yet.")
    if not local["group_ok"] and local["platform"]["system"] == "Linux":
        risks.append("Current login lacks effective kiri group access; the kiri group is root-equivalent.")
    if local["docker_host_override"]:
        risks.append("DOCKER_HOST is set and overrides docker contexts.")
    if local["foreign_socket"]:
        risks.append("Another engine owns /run/docker.sock; tools that ignore contexts may reach it.")
    if upstream.get("mode") == "degraded":
        risks.append("Upstream facts are degraded; version and docs claims are unverified.")
    if signals["update_available"]:
        risks.append("A newer upstream Kiri release is available.")
    if local["incident"]:
        risks.append("Kiri error logs are non-empty; inspect before changing configuration.")

    verification = [
        "python3 <skill_dir>/scripts/kiri_brief.py  # stage must improve or stay stable",
        "bash <skill_dir>/scripts/kiri-doctor.sh  # SUMMARY fail=0 and smoke container OK",
        "docker --context kiri info --format '{{.ServerVersion}} {{.OperatingSystem}}'  # reports Kiri",
        "docker --context kiri run --rm alpine echo KIRI_OK",
    ]
    if stage in ("workload_running", "ready_idle", "greenfield", "ci_runner"):
        verification.append("docker --context kiri compose -f templates/compose-smoke.yaml up -d && ... down")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": stage,
        "stage_priority": "install > upgrade > engine > context > ci > incident > migration > workload > greenfield",
        "signals": signals,
        "risks": risks,
        "next_actions": next_actions(stage, signals, urls),
        "verification": verification,
        "freshness": {
            "mode": upstream.get("mode"),
            "upstream_version": upstream.get("upstream", {}).get("version"),
            "local_version": upstream.get("local", {}).get("installed_version"),
            "comparison": upstream.get("comparison", {}),
            "resolved_urls": urls,
            "source_statuses": {key: value.get("status") for key, value in upstream.get("sources", {}).items()},
        },
        "limits": [
            "Signals are a snapshot; re-run after every change.",
            "Stage never executes commands; it only recommends them.",
            "Live docs under resolved_urls remain authoritative for command syntax.",
        ],
    }


def main():
    print(json.dumps(build_report(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
