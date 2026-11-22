---
name: kiri-container-runtime
description: Operate Kiri containers at any project stage.
version: 1.1.0
author: DemumuMind (leamanfo), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [kiri, containers, docker, runtime, source-of-truth, agent-workflow]
    related_skills: []
---

# Kiri Container Runtime Skill

This is the complete agent contract for Kiri, a Rust container runtime that serves the Docker Engine API. One call gives the agent everything needed to act: live upstream facts, local engine state, the current project stage, risks, ordered next actions and verification. Complexity and project phase do not change the contract — only the stage does.

Truth rule: live sources discovered at run time beat every file in this skill. `references/` are pattern notes, not authority. Never edit this skill to bump a version or a docs URL.

Don't use for Docker Desktop or OrbStack internals, general Kubernetes administration, or rootless container setups. Kiri's Linux daemon is rootful and the `kiri` group is root-equivalent.

## Agent contract (read first)

1. **First call, always:** `python3 <skill_dir>/scripts/kiri_brief.py`. Resolve `<skill_dir>` with `search_files(target='files')` if unknown. Never hardcode a home directory.
2. **Read the brief in this order:** `stage` → `signals` → `risks` → `next_actions` → `verification` → `freshness`. Do not ask the operator which stage it is; the brief detects it.
3. **Execute `next_actions` in order.** One change per iteration, then re-run the brief. Batch only independent reads.
4. **Finish with `verification`.** A task is not done until the listed checks pass. Never claim success from a command that was not run.
5. **Ask only when the brief cannot answer:** a value only the operator holds (image, port, credentials) or an irreversible external action (public share, deletion, deploy). Assume everything else.
6. **Degraded mode is honest mode.** If `freshness.mode` is `degraded`, name the failed sources and rely on local `kiri --help` only.

## When to Use

- Install, upgrade, start, stop or diagnose Kiri.
- Run containers, Compose stacks, builds and migrations on any project stage.
- Fix a host where `docker` reaches the wrong engine.
- Work in CI, on a greenfield repo, or on a host with live production workloads.
- Use native verbs: `kiri k8s`, `kiri machine`, `kiri share`, `kiri diag`.

## Stage map

The brief's `classify()` applies this fixed priority. Higher stages are blockers.

| Priority | Stage | Signal | Playbook |
| --- | --- | --- | --- |
| 1 | `install_required` | no binary | `references/workflows.md` |
| 2 | `upgrade_available` | upstream newer than local | same |
| 3 | `engine_stopped` | binary, service inactive | same |
| 4 | `engine_unreachable` | service active, API not reachable | same |
| 5 | `ci_runner` | CI env var | same |
| 6 | `incident` | error logs non-empty | same |
| 7 | `migration` | another engine owns the socket | same |
| 8 | `workload_running` | running containers | same |
| 9 | `ready_idle` | images present | same |
| 10 | `greenfield` | empty engine | same |

`ci_runner` outranks `incident` because CI must fail fast on a bad runner; incident playbook still applies if its checks are needed.

## Project adoption contract (YAML)

For "rewrite a project for Kiri", "add Kiri to an existing project" or "start with Kiri as default", load the declarative contract first:

```bash
python3 <skill_dir>/scripts/kiri_apply.py --project <path> --mode auto
```

`templates/project-adoption.yaml` defines three profiles — `greenfield`, `adopt`, `migrate` — with detection signals, required values, ordered steps, safety rules and verification. `kiri_apply.py` parses it with stdlib only, detects the profile from project files, prints a JSON plan, and with `--write` creates `kiri.project.yaml`; for greenfield with `--image`/`--port` it also creates `docker-compose.kiri.yaml`. It never overwrites existing files without `--force`. Ask the operator only for values the contract marks as required (image, port, migration target).

## Universal procedure

1. **Brief.** Run `kiri_brief.py`. Completion: JSON with `stage`, `risks`, `next_actions` and `verification` present.
2. **Resolve live facts.** `scripts/kiri_facts.py` discovers site, docs, release API, installer and checksum feed from GitHub metadata and the homepage. `freshness.resolved_urls` is the only source of command/platform truth. Completion: every source has `ok` or a named error.
3. **Clear blockers.** Execute earlier stages first. Completion: `stage` moved past install/engine/context problems.
4. **Choose the engine explicitly.** Use `docker --context kiri ...` in every script. `DOCKER_HOST` overrides contexts; `kiri <docker-command>` clears `DOCKER_CONTEXT` and forces Kiri. Completion: `docker --context kiri info --format '{{.ServerVersion}} {{.OperatingSystem}}'` contains `Kiri`.
5. **Smoke before work.** `docker --context kiri run --rm alpine echo KIRI_OK` → `KIRI_OK`, exit 0. Completion criterion is the output, not the exit code alone.
6. **Do the work through the stage playbook.** Single container, Compose, multi-project, k3s or machine: all use the same stage gates. Check current verb support in `resolved_urls` before native commands.
7. **Verify and report.** Run the brief's `verification` list. Report stage, source mode, commands actually run and their results.

## Command grammar

| Intent | Form | Notes |
| --- | --- | --- |
| Container lifecycle | `docker --context kiri run\|ps\|logs\|exec\|stop\|rm ...` | Docker CLI aimed at Kiri's socket |
| Compose | `docker --context kiri compose -p <project> -f <file> ...` | Always name the project on shared hosts |
| Builds | `docker --context kiri build ...` or `kiri build` | BuildKit builder; check `host-gateway` caveat |
| Kiri features | `kiri share\|k8s\|machine\|diag\|build-with` | Native verbs; verify platform in live docs |
| Context repair | `bash <skill_dir>/scripts/kiri-context.sh` | Idempotent create/select |
| Health | `bash <skill_dir>/scripts/kiri-doctor.sh` | Real smoke container, fail=0 |

## Complexity tiers

| Tier | Examples | Contract change |
| --- | --- | --- |
| Single container | one-off image, debug shell | same stages; one container at a time |
| Compose stack | app + db + cache | `-p <project>`, verify each service |
| Multi-project host | several repos, shared engine | port table, project names, no cross-project down |
| CI ephemeral | runner, smoke, teardown | `templates/github-actions.yml`, `always` cleanup |
| Cluster / machine | `kiri k8s`, `kiri machine` | verify live platform support, then same gates |
| Migration | Docker Desktop/OrbStack to Kiri | keep old engine until smoke and one workload pass |
| Incident | failing engine or workload | `incident` stage, one fix per iteration |

## Failure protocol

1. Re-run the brief. 2. Match `references/failures.md`. 3. Read live docs if the command may have changed. 4. Apply one fix. 5. Re-run brief and smoke. 6. If still failing, capture `kiri diag report --out <path>` before deeper changes.

## Safety boundaries

- `kiri` group is root-equivalent; never add untrusted accounts.
- Not a sandbox for hostile code; containers share the host kernel.
- `kiri share` is public: require authentication and release it when done.
- Never run `compose down` without `-p` on a shared host.
- Never edit this skill to refresh facts. Override bootstrap only with `KIRI_BOOTSTRAP_REPO`.

## Verification

- `python3 <skill_dir>/scripts/kiri_brief.py` exits 0 with a named stage and no unresolved blockers.
- `python3 <skill_dir>/scripts/kiri_facts.py` reports source statuses and local/upstream comparison.
- `bash <skill_dir>/scripts/kiri-doctor.sh` ends with `SUMMARY ... fail=0` and smoke container `KIRI_DOCTOR_OK`.
- `docker --context kiri compose -f <skill_dir>/templates/compose-smoke.yaml up -d` logs `KIRI_COMPOSE_OK` and removes cleanly.
- `python3 -m unittest discover -s <skill_dir>/tests -v` passes.

## References

- `references/workflows.md` — all stages with commands and completion criteria.
- `references/adoption.md` — how agents use the YAML contract on real projects.
- `references/failures.md` — symptom → check → fix → verify matrix.
- `references/integrations.md` — CI, SDKs, systemd, builds, multi-project hosts, public exposure.
- `references/cli.md` — command patterns; live docs win.
- `references/linux.md` — Linux socket, context, group and upgrade patterns.
- `references/platforms.md` — platform caveats; live docs win.
- `scripts/kiri_brief.py` — single entry point and stage classifier.
- `scripts/kiri_facts.py` — cross-platform live source resolver.
- `scripts/kiri-doctor.sh`, `scripts/kiri-context.sh` — POSIX helpers.
- `templates/compose-smoke.yaml`, `templates/github-actions.yml` — checked skeletons.
- `templates/project-adoption.yaml`, `scripts/kiri_apply.py`, `tests/test_apply.py` — declarative project adoption.
- `tests/test_facts.py`, `tests/test_brief.py` — source relocation, degraded network, stage priority.
