[English](README.md) | [Русский](README.ru.md)

# Kiri Container Runtime Skill

An agent skill for the [Kiri](https://runkiri.com/) container runtime. It teaches an AI coding agent to run, inspect and troubleshoot Kiri containers, Compose stacks, builds, local domains, Kubernetes and diagnostics with Docker-compatible commands.

The skill does not hardcode a release version or documentation URLs as truth. On every use, `scripts/kiri_facts.py` discovers the official site, docs, release API and checksum feed from GitHub repository metadata, verifies each source, and compares upstream with the local install. If sources move, the skill follows them without a file edit.

## Why use it

- **Docker-compatible workflow:** `docker --context kiri ...` and `kiri ...` for container lifecycle, Compose and builds.
- **Current without rewrites:** versions and source addresses are resolved at runtime, not frozen in the text.
- **Cross-platform guidance:** Linux runs on the host kernel, macOS uses a small Linux VM, Windows runs inside WSL2. The live docs decide the current command matrix.
- **Safe operations:** explicit engine selection, context checks, smoke containers, token-free diagnostics and honest failure modes.
- **Agent-ready:** one `kiri_brief.py` call returns stage, risks, next actions and verification; `SKILL.md` is a strict operating contract.
- **Declarative adoption:** `templates/project-adoption.yaml` plus `scripts/kiri_apply.py` cover greenfield, adding Kiri to an existing project, and migration with no hardcoded project assumptions.
- **Stage-aware:** install, upgrade, stopped engine, broken context, CI, incident, migration, live workload, idle and greenfield all have their own playbook.

## Install

With the [Agent Skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add DemumuMind/kiri-container-runtime-skill
```

For Hermes Agent, copy the directory into your skills tree:

```bash
git clone https://github.com/DemumuMind/kiri-container-runtime-skill.git
mkdir -p ~/.hermes/skills/software-development
cp -R kiri-container-runtime-skill ~/.hermes/skills/software-development/kiri-container-runtime
```

Restart the agent session so the skill catalog reloads.

## Requirements

| Requirement | Why |
| --- | --- |
| Python 3 standard library | Runs the source resolver; no pip packages |
| Internet access | Needed for live checks; offline mode is reported as `degraded` |
| `GITHUB_TOKEN` or `GH_TOKEN` (optional) | Avoids the anonymous GitHub API rate limit; used only for `api.github.com` requests |
| Kiri installed | The `kiri` binary and engine are the subject of the skill |
| Docker CLI with contexts | The `kiri` context targets the engine socket |
| POSIX shell | Needed by the optional health-check and context scripts |

Install Kiri from the official site discovered by the resolver, or with the documented installer:

```bash
curl -fsSL https://runkiri.com/install.sh | bash
```

## Quick start

```bash
# 1. One call for the whole picture: stage, risks, next actions, verification
python3 scripts/kiri_brief.py

# 2. Deep source check when needed
python3 scripts/kiri_facts.py

# 2b. Project adoption plan (greenfield / adopt / migrate)
python3 scripts/kiri_apply.py --project . --mode auto
# add --write once blockers are resolved

# 3. Work through the Kiri context
docker --context kiri run --rm alpine echo KIRI_OK
docker --context kiri compose -f templates/compose-smoke.yaml up -d
docker --context kiri compose -f templates/compose-smoke.yaml down
```

The agent reads `stage` first, follows `next_actions` in order, and finishes with `verification`. It asks the operator only for values the brief cannot know (image, port, credentials) or before irreversible external actions.

## Repository layout

| Path | Purpose |
| --- | --- |
| `SKILL.md` | Agent contract: first call, stage map, procedure, safety, verification |
| `references/workflows.md` | Stage-by-stage playbooks with completion criteria |
| `references/adoption.md` | How agents use the YAML contract on real projects |
| `references/failures.md` | Symptom → check → fix → verify matrix |
| `references/integrations.md` | CI, SDKs, systemd, builds, multi-project hosts, public exposure |
| `references/cli.md` | Command patterns; verify against the live CLI docs |
| `references/linux.md` | Linux socket, context, group and upgrade patterns |
| `references/platforms.md` | Platform caveats; live docs are authoritative |
| `scripts/kiri_brief.py` | One-call state brief: stage, risks, next actions, verification |
| `scripts/kiri_facts.py` | Dynamic source discovery and version drift check |
| `scripts/kiri-doctor.sh` | Health check plus a real smoke container |
| `scripts/kiri-context.sh` | Idempotent Docker context creation and selection |
| `templates/compose-smoke.yaml` | Minimal Compose end-to-end stack |
| `templates/project-adoption.yaml` | Declarative contract for greenfield/adopt/migrate |
| `scripts/kiri_apply.py` | YAML reader, profile detector and plan/writer |
| `templates/github-actions.yml` | CI skeleton with fail-fast stage check |
| `tests/test_facts.py` | Source-relocation and degraded-network tests |
| `tests/test_brief.py` | Stage-priority and agent-contract tests |
| `tests/test_apply.py` | YAML parsing, detection and safe writes |
| `.github/workflows/source-watch.yml` | Scheduled upstream drift check |

## How freshness works

The only bootstrap value is the upstream GitHub repository identity (`KIRI_BOOTSTRAP_REPO` overrides it if the repository moves). Repository metadata supplies the homepage, default branch and release API. The homepage supplies links to docs, installer and checksums. Each source is hashed, every resolved URL is printed under `discovery.resolved_urls`, and the upstream version is compared with the local install.

A release bump or a new docs domain needs no skill edit. If the bootstrap itself fails, `mode` becomes `degraded`, the failed source is named, and the agent falls back to local `kiri --help` without presenting stale facts as current.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The suite simulates a future upstream with a different docs domain and a newer release, plus a total network failure.

## Keywords

kiri container runtime, runkiri, kiri skill, agent skill, docker desktop alternative, orbstack alternative, containers, docker cli, compose, buildx, linux containers, rust runtime, devops agent, hermes agent skill.

## License

MIT — DemumuMind.
