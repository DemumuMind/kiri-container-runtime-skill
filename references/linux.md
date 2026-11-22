# Kiri on Linux

Kiri on Linux runs with no VM. `kiri.service` starts `/usr/bin/kiri daemon` on the host kernel; the daemon creates containers with `clone3`, namespaces, a cgroup, overlayfs and seccomp. There is no dockerd, containerd, per-container shim or runc.

## Install facts

```bash
curl -fsSL https://runkiri.com/install.sh | bash     # full package: engine + docker CLI + Compose + buildx
KIRI_LITE=1 bash -c 'curl -fsSL https://runkiri.com/install.sh | bash'   # engine only
```

The installer fetches the `.deb` or `.rpm` from `https://download.runkiri.com`, verifies it against `SHA256SUMS-linux`, and installs it with `sudo` where needed. Version check: `dpkg-query -W -f='${Package} ${Version}\n' kiri`.

The full package installs its own Docker CLI through `update-alternatives` only when no other engine owns `docker`. A CLI installed by another package keeps priority. With `kiri-lite`, point your own CLI at the engine with `export DOCKER_HOST=unix:///run/kiri/docker.sock`.

## Socket, context, group

- Engine socket: `/run/kiri/docker.sock`, mode 0660, owner `root:kiri`.
- While no other Docker engine occupies `/run/docker.sock`, the service symlinks it to Kiri's socket. When Kiri stops, it removes that link if it still points at Kiri.
- The Linux package does not run `kiri setup`; create the context yourself:

```bash
sudo systemctl enable --now kiri
sudo usermod -aG kiri "$USER"        # new login required
docker context create kiri --docker host=unix:///run/kiri/docker.sock
docker context use kiri
docker --context kiri info --format '{{.ServerVersion}} {{.OperatingSystem}}'
```

- `DOCKER_HOST` wins over any context. If a command unexpectedly reaches a different engine, run `env | grep -i docker` and clear the override. The `kiri <docker-command>` shorthand clears `DOCKER_CONTEXT` and sets `DOCKER_HOST` to Kiri's socket, so it is immune to context drift.
- Membership in `kiri` is root-equivalent: a member can run root containers on the host. Do not add untrusted accounts.

## Security boundary

Kiri is not a sandbox for hostile code on Linux. Containers share the host kernel and are separated only by namespaces, cgroups, capabilities and seccomp. Privileged and seccomp-unconfined containers are still blocked from vsock and io_uring, which preserves the host boundary on Mac, but on Linux the daemon and agent run on the host. Run untrusted images only if you accept root-equivalent risk.

## Upgrades

Package upgrades do not stop the running engine or its containers. After `sudo apt install ./kiri_<version>_amd64.deb` (or the `.rpm` equivalent), restart when convenient:

```bash
sudo systemctl restart kiri
kiri ps
```

On some Linux builds `kiri update --check` forwards to `docker update` and errors instead of checking releases. Check the installed version against the official feed directly:

```bash
dpkg-query -W -f='${Version}\n' kiri
curl -fsSL https://download.runkiri.com/SHA256SUMS-linux
curl -fsSL https://api.github.com/repos/libracoder/kiri/releases/latest
```

## Diagnostics

```bash
systemctl status kiri --no-pager
journalctl -u kiri -n 50 --no-pager
kiri diag logs --errors -n 50
kiri diag report --out <path>
```

On a host that has no systemd, Kiri for Linux will not run: the unit is the supported lifecycle.
