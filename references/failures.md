# Failure matrix

Read the brief first. Then find the symptom below, run the named check, apply the fix, verify. Do not change configuration before the check.

| Symptom | First check | Fix | Verify |
| --- | --- | --- | --- |
| `context "kiri": context not found` | `docker context ls` | `bash scripts/kiri-context.sh` | `docker --context kiri info` reports Kiri |
| `permission denied` on socket | `id -nG` on Linux; brief `signals.group_ok` | New login after `usermod -aG kiri`, or use sudo | Brief `signals.group_ok` true |
| Commands hit Docker Desktop / another engine | `echo $DOCKER_HOST`; `ls -l /run/docker.sock` | Unset `DOCKER_HOST`, pass `--context kiri`, or use `kiri <docker-command>` | `docker --context kiri info` reports Kiri |
| `kiri update --check` errors as docker update | Live release API from brief | Use `scripts/kiri_facts.py` version comparison | `freshness.upstream_version` populated |
| `host-gateway is not supported` during build | Build command contains `--add-host ...:host-gateway` | Use the bridge gateway address directly or `DOCKER_BUILDKIT=0` | `docker --context kiri build` completes |
| Port already allocated | `docker --context kiri ps -a --format '{{.Names}} {{.Ports}}'` | Stop the conflicting container or change host port | `docker --context kiri ps` shows expected mapping |
| Compose network drift / service not found | `docker --context kiri compose -f <file> ps` | Recreate with `up -d --force-recreate` only for the affected project | `compose ps` healthy |
| Image pull fails | Brief `freshness.mode`; registry reachability | Fix network/credentials; retry pull | `docker --context kiri images` shows tag |
| Container exits immediately | `docker --context kiri logs <name>` | Fix command/env in compose, then recreate | Logs clean, status Up |
| Daemon restarted, records missing | `kiri diag logs --errors -n 50` | Re-create from compose; Kiri records survive normal restarts, a crash needs investigation | `compose up -d`, `ps` healthy |
| Slow small-file bind mounts on macOS | Live docs + issue search on discovered repo | Prefer named volumes for `node_modules`; check upstream issue status | Benchmark in your own project |
| `degraded` freshness mode | `freshness.source_statuses` | Retry network; if bootstrap failed set `KIRI_BOOTSTRAP_REPO`; do not assert versions | Brief `freshness.mode` live |
| Upgrade available but engine old | Brief `stage=upgrade_available` | Follow `references/workflows.md` upgrade playbook | Comparison false, smoke OK |
| Public share unexpected | `kiri share status` | `kiri share logout` or release reserved name; never expose admin panels | Share status clean on discovered service |
| Workload needs GPU / CRI | Live features doc from `resolved_urls` | Kiri has no GPU passthrough and is not a CRI runtime; choose another engine for that workload | Requirement resolved outside Kiri |

## Escalation order

1. Re-run the brief (state changes fast).
2. Check the exact symptom row.
3. Read the live CLI/feature docs from `resolved_urls` if the command may have changed.
4. Apply one fix.
5. Re-run the brief and the smoke verification.
6. If still failing, capture `kiri diag report --out <path>` before deeper changes.
