# Kiri CLI reference — pattern snapshot

Patterns, not truth. Resolve the current verb list and platform matrix with
`python3 scripts/kiri_facts.py` and `https://docs.runkiri.com/cli/` before acting.
Two classes of commands:

1. **Docker verbs** — `kiri run`, `kiri ps`, `kiri exec`, `kiri logs`, `kiri build`, `kiri compose`, `kiri pull`, `kiri images`, etc. The `kiri` binary sets `DOCKER_HOST` to Kiri's socket, removes `DOCKER_CONTEXT`, then executes the Docker CLI. They accept all normal Docker flags.
2. **Kiri-native verbs** — the rest of the list below.

## Full verb map from `kiri --help`

```text
kiri COMMAND            Docker's commands on Kiri: run, ps, exec, logs, stop, rm,
                        images, pull, build, compose, ...
kiri daemon             the engine; serves the Docker Engine API on Kiri's socket
kiri bridge [--socket PATH]      WSL2 endpoint of kiri-win.exe
kiri ui [--start] [--view containers|images|volumes|networks]
                        the window; Linux full x86-64 package only
kiri setup [--use] [--no-agent] | kiri setup --uninstall
                        Mac setup
kiri build-with [docker|kiri]    which builder plain `docker build` uses
kiri update [--check]            see live docs; Linux builds may forward to docker update
kiri diag logs [-f] [--ui|--engine|--cli] [--errors] [--op ID] [-n N]
kiri diag report [--out PATH] [--send]
kiri PORT [NAME]        share a local port; same as `kiri share PORT`
kiri share PORT|CONTAINER [--name N] | share login | logout | status
                        share reserve NAME | names | release NAME
kiri k8s start [--use] | stop | status | delete | set [--lan on|off] [--tls-san NAME,...] [--port N]
kiri usb [list] | attach DEVICE | detach DEVICE | helper remove
kiri machine create NAME [--distro D] [--systemd] | list | shell NAME [-- CMD...]
                        | start | stop | restart | delete NAME
kiri import [orbstack | desktop-linux] [--list | [--force] [image|volume|container NAME]]
                        Mac only
kiri bench [--runs N] [--image IMAGE] [--network none|bridge]   Mac only
kiri boot [--console] [--pings N]                                Mac only
kiri raw run [--rm] [-e KEY=VALUE]... IMAGE [COMMAND...]
kiri raw pull IMAGE | raw images | raw rmi IMAGE...
```

## Docker verbs in practice

Run a short-lived container:

```bash
kiri run --rm alpine echo hello
docker --context kiri run --rm alpine echo hello
```

Both forms are equivalent when no `DOCKER_HOST` overrides the context. Prefer the explicit `--context kiri` form in scripts so the target engine cannot drift.

Long-lived service with published port:

```bash
kiri run -d --name web -p 8080:80 nginx:alpine
kiri ps
kiri logs -f web
kiri exec -it web sh
kiri stop web && kiri rm web
```

Compose (up/down/ps/logs/exec):

```bash
kiri compose -f templates/compose-smoke.yaml up -d
kiri compose -f templates/compose-smoke.yaml ps
kiri compose -f templates/compose-smoke.yaml logs
kiri compose -f templates/compose-smoke.yaml down
```

Builds use BuildKit in a Kiri container (docker-container driver):

```bash
kiri build -t myapp .
kiri build-with            # report which builder plain `docker build` uses
kiri build-with kiri       # force all builds to Kiri
```

## Native verbs worth knowing

- `kiri share 3000` exposes a local port at a random `runkiri.cloud` address; `--name myapp` uses a reserved name. `share status --json` reports active shares. This is a public endpoint — do not expose a service with credentials or an unauthenticated admin panel.
- `kiri k8s start --use` starts a single-node k3s cluster in one container, ready in about 20 seconds, and installs a `kiri` kubectl context. It is not a CRI runtime for an external kubelet.
- `kiri machine create dev --distro ubuntu` creates a long-lived Linux machine; `machine shell dev` opens a shell in it.
- `kiri diag logs --errors -n 50` shows warnings and errors from the engine and CLI. `kiri diag report --out <path>` collects a redacted bundle; `--send` also uploads it.
- `kiri bench` and `kiri import` appear in the Linux help text but are Mac-only per the official platform table.

## Unsupported or absent on Linux

- GPU passthrough is not implemented.
- Kiri is not a CRI runtime; `kiri k8s` is a bundled k3s, not a general kubelet backend.
- The `kiri` group is root-equivalent — treat it like the old `docker` group.

Detailed flags live in the local Docker CLI help (`kiri run --help` prints `docker run` help). Current feature matrix: `https://github.com/libracoder/kiri/blob/main/docs/features.md`.
