# Platform matrix and Linux caveats

Source: `https://docs.runkiri.com/cli/` command table and `https://github.com/libracoder/kiri/blob/main/docs/features.md`.

| Verb | macOS | Linux | Windows (WSL2) |
|---|---|---|---|
| Docker verbs (`run`, `ps`, `exec`, `logs`, `build`, `compose`, `pull`, `images`) | yes | yes | yes |
| `kiri share PORT` | yes | yes | ports only |
| `kiri k8s` | yes | yes | yes, inside WSL |
| `kiri machine` | yes | yes | yes, inside WSL |
| `kiri diag` | yes | yes | yes, inside WSL |
| `kiri usb` | yes | list only on Linux | yes |
| `kiri daemon` | yes | yes | no (Linux side) |
| `kiri bridge` | no | WSL endpoint | used by kiri-win.exe |
| `kiri ui` | yes | full x86-64 package | via the window |
| `kiri setup` | yes | no | no |
| `kiri update [--check]` | check live docs | some Linux builds forward to docker update | no |
| `kiri import` | yes | no | no |
| `kiri bench` | yes | no | no |
| `kiri boot` | yes | no | no |
| `kiri raw` | yes | yes (testing) | no |
| `kiri build-with` | yes | yes | no |

## Why the help text lies on Linux

The `kiri` binary ships one help string for all platforms. Verbs such as `import`, `bench`, `boot`, `setup` and `update` appear in `kiri --help` on Linux but are documented as Mac-only. Do not assume a verb works because it is printed. Check the platform table above or the official docs before building a workflow around it.

## Mac-specific notes (for context only)

On Mac, Kiri boots a ~10 MB Linux VM with Apple's Virtualization framework and talks to a ~900 KB Rust agent over vsock. The VM returns unused memory and sleeps after 60 seconds idle. Container files are visible in Finder under `~/Kiri`. amd64 images run through Rosetta. Local names `<name>.kiri.local` and HTTPS from Kiri's own CA are Mac features. None of that applies to Linux hosts, where containers run on the host kernel.

## Known cross-platform issues

- `docker build --add-host name:host-gateway` fails with the docker-container BuildKit driver. On Linux use the bridge gateway address (`172.18.0.1` by default) or `DOCKER_BUILDKIT=0`.
- GPU support is absent on every platform.
- A `kiri`-group member is root-equivalent on Linux. On Mac, all containers share one VM; that VM is a real wall against the host, but containers inside it are not isolated from each other beyond normal Linux primitives.
