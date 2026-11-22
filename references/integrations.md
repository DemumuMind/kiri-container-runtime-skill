# Integration patterns

Use these patterns when Kiri is one part of a larger system. The live docs in the brief's `resolved_urls` remain authoritative for flags and platform support.

## Project layout contract

- Keep one compose file per project at the repo root: `docker-compose.yml` or `compose.yaml`.
- Name projects explicitly: `docker --context kiri compose -p <project> ...`. This prevents collisions when several projects share a host.
- Keep `.env` in the project, never in the skill, and never commit it.
- Prefer named volumes for persistent data and bind mounts only for source code.

## Multi-project host

| Concern | Pattern |
| --- | --- |
| Name collisions | `-p <project>` on every compose call |
| Port collisions | One port allocation table per host; check `docker --context kiri ps` before assigning |
| Config drift | Generate compose from a single source; do not hand-maintain three variants |
| Cleanup | `docker --context kiri compose -p <project> down --remove-orphans` for that project only |

## CI

`templates/github-actions.yml` is the minimal skeleton. Rules:

1. Run the brief immediately after install.
2. Fail early on `engine_stopped`, `engine_unreachable` or `incident`.
3. Use one `-p` name per job to avoid runner collisions.
4. Always tear down in an `always` step.
5. Never put secrets in compose files; use CI env vars.

## SDKs and tooling that ignore contexts

`DOCKER_HOST` wins over a docker context. Tools such as docker-py, Testcontainers and IDE plugins often read the env var directly:

```bash
DOCKER_HOST=unix:///run/kiri/docker.sock python your_test.py
```

The Linux service links `/run/docker.sock` to Kiri's socket only while no other engine owns it. If another engine is present, use the explicit `DOCKER_HOST` or the `kiri` context, and state which engine a tool reached.

## systemd and host services

- Linux engine unit: `kiri.service`. Check with `systemctl status kiri --no-pager`.
- Package upgrades do not restart the engine; schedule `sudo systemctl restart kiri` deliberately.
- Run application services on the host through their own systemd units; use Kiri for container workloads, not as a process manager for everything.

## Builds

- `docker --context kiri build` uses BuildKit through a Kiri builder container.
- `kiri build-with` reports/sets which builder plain `docker build` uses.
- For `--add-host name:host-gateway`, see `references/failures.md`.
- Verify a built image by running it, not only by a successful build log.

## Public exposure

`kiri share PORT` creates a public endpoint. Before using it:

1. Confirm the service has authentication.
2. Reserve/name it only if the name is meaningful; check `kiri share status`.
3. Release it when done.
4. Never expose databases, admin panels or unauthenticated dev servers.

## Native extensions

| Command | Use | Constraint |
| --- | --- | --- |
| `kiri k8s start --use` | Single-node k3s for local work | Not a CRI runtime for an external kubelet |
| `kiri machine create NAME --distro ubuntu` | Long-lived Linux environment | Check platform support in live docs |
| `kiri import` | Migrate from OrbStack/Docker Desktop | macOS per current docs; Linux use save/load |
| `kiri bench` | Local benchmark | macOS per current docs; do not quote as universal |
