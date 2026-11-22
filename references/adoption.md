# Project adoption contract

Use this when the task is not "run a container" but "make this project use Kiri": greenfield, adding Kiri to an existing repo, or migrating from another engine.

## Single entry point

```bash
python3 <skill_dir>/scripts/kiri_apply.py --project <path> --mode auto
```

The script reads `templates/project-adoption.yaml`, detects the profile from project files and prints a JSON plan. It does not edit anything unless `--write` is passed.

## Profiles

| Mode | When | Required values | What is written |
| --- | --- | --- | --- |
| `greenfield` | no compose, Dockerfile or package.json | `image`, `port` | `kiri.project.yaml`, `docker-compose.kiri.yaml` |
| `adopt` | existing compose/Dockerfile/package.json | none | `kiri.project.yaml` |
| `migrate` | references to OrbStack/Docker Desktop/Podman/containerd | `migration_target` | `kiri.project.yaml` |

Detection priority: `migrate` > `adopt` > `greenfield`. Override with `--mode`.

## Agent workflow

1. Run the brief first: `python3 <skill_dir>/scripts/kiri_brief.py`.
2. Run `kiri_apply.py --project <path> --mode auto` and read `plan.mode`, `plan.blockers` and `plan.steps`.
3. Ask the operator only for values in `plan.blockers` or in `safety.ask_only`. Never ask which mode — detection answers it.
4. Run `kiri_apply.py ... --write` once blockers are resolved.
5. Execute `plan.steps` in order. Each step has a `gate`: a checkable completion criterion.
6. Run `plan.verification` plus the brief's `verification`. Report stage and commands actually run.

## Safety rules from the YAML

- Never overwrite an existing compose file.
- Never change the system default Docker context without explicit consent.
- Never expose an unauthenticated service through `kiri share`.
- Never run `compose down` without a project name on a shared host.

`--force` is only for files this tool created. For existing project files, present the intended change and get a decision.

## Greenfield example

```bash
python3 scripts/kiri_apply.py --project ./myapp --mode auto --image nginx:alpine --port 8080 --write
docker --context kiri compose -p myapp -f ./myapp/docker-compose.kiri.yaml up -d
docker --context kiri compose -p myapp -f ./myapp/docker-compose.kiri.yaml logs
```

## Adopt example

```bash
python3 scripts/kiri_apply.py --project ./existing --mode auto --write
docker --context kiri compose -p existing -f ./existing/docker-compose.yml up -d
```

## Migrate example

```bash
python3 scripts/kiri_apply.py --project ./legacy --mode auto --migration-target docker-desktop --write
kiri import --list                     # macOS; Linux: docker save/load through both contexts
docker --context kiri compose -p legacy -f ./legacy/docker-compose.yml up -d
docker context use kiri                # only after smoke and workload pass
```

The YAML is the contract: if it changes, the agent follows the new version without a SKILL.md edit.
