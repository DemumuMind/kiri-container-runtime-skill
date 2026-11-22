# Stage playbooks

`scripts/kiri_brief.py` returns one `stage`. Each stage has one goal, a fixed command order and a completion criterion. Do not skip to a later stage: an earlier stage is an unresolved blocker. Every command uses `docker --context kiri ...` unless the brief says otherwise.

## install_required

Signals: no `kiri` binary. Goal: install from the URL discovered by `kiri_facts.py`.
1. Open `freshness.resolved_urls.install_script` or the download link from the discovered homepage.
2. Install with the official method; do not guess a package name.
3. Re-run the brief. Criterion: `stage` is no longer `install_required`.

## upgrade_available

Signals: upstream version newer than local. Goal: upgrade without surprising restarts.
1. Read release notes from `freshness.resolved_urls.release_api`.
2. Install from the discovered installer. Existing containers keep running on the old engine after a package upgrade.
3. Restart the engine in a maintenance window: `sudo systemctl restart kiri` (Linux) or the platform equivalent.
4. Re-run the brief. Criterion: `comparison.update_available` is false and smoke test passes.

## engine_stopped

Signals: binary present, service not active. Goal: start the engine.
1. Linux: `sudo systemctl enable --now kiri`. macOS: launch Kiri or `kiri daemon`. Windows: start the WSL distro hosting the engine.
2. Re-run the brief. Criterion: `signals.engine_active` is true.

## engine_unreachable

Signals: engine active but `docker --context kiri info` does not report Kiri.
1. `docker context ls` — is there a `kiri` context?
2. `bash <skill_dir>/scripts/kiri-context.sh` — creates/selects it idempotently.
3. `kiri diag logs --errors -n 50`.
4. If `DOCKER_HOST` is set, unset it or always pass `--context kiri`.
5. Criterion: `docker --context kiri info --format '{{.ServerVersion}} {{.OperatingSystem}}'` contains `Kiri`.

## ci_runner

Signals: `CI` or provider env var. Goal: reproducible, ephemeral verification.
1. Use `templates/github-actions.yml` as the skeleton; adapt platform and install method.
2. Run `python3 <skill_dir>/scripts/kiri_brief.py` and fail the job if `stage` is `engine_unreachable`, `engine_stopped` or `incident`.
3. Run the smoke container before workload steps.
4. Tear down in an `always` step: `docker --context kiri compose -f templates/compose-smoke.yaml down`.
5. Criterion: job passes with no lingering container or network.

## incident

Signals: `kiri diag logs --errors` non-empty. Goal: stabilize before changes.
1. Capture `kiri diag logs --errors -n 100` and `kiri diag report --out <path>`.
2. On Linux, check `systemctl status kiri --no-pager` and restart count.
3. Map the symptom with `references/failures.md`.
4. Apply one fix at a time, re-running the brief after each.
5. Criterion: `signals.incident` false and smoke container passes.

## migration

Signals: another engine owns `/run/docker.sock`. Goal: move without breaking existing workflows.
1. Keep the old engine installed until the Kiri smoke test passes.
2. macOS: `kiri import --list`, then import images/volumes/containers. Linux: `docker save` / `docker load` through the two contexts.
3. Verify image IDs and volume contents before `docker context use kiri`.
4. Criterion: Kiri smoke and one real workload pass, then the default context may be switched.

## workload_running

Signals: running containers. Goal: non-destructive inspection and guarded change.
1. List with `docker --context kiri ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'` and `docker --context kiri compose ls`.
2. Check health and logs before any restart/down.
3. Change one service at a time; record its previous image tag.
4. Criterion: affected service healthy, unrelated containers untouched.

## ready_idle

Signals: images exist, no running containers. Goal: prove the runtime, then start work.
1. `docker --context kiri run --rm alpine echo KIRI_OK`.
2. Start the intended stack with an explicit compose file.
3. Criterion: stack healthy and `docker --context kiri ps` shows expected services.

## greenfield

Signals: no images or containers. Goal: start from a checked template.
1. Copy `templates/compose-smoke.yaml`, set names, image and ports.
2. `docker --context kiri compose -f <file> up -d`.
3. Verify with the brief's `verification` list.
4. Criterion: smoke output present and teardown clean.

## Cross-stage rules

- Never ask "which stage?" — the brief answers it. Ask only for values only the operator holds (image name, port, credentials) or before irreversible external actions (public share, deletion, deploy).
- One change per iteration, then re-run the brief. Batch only independent checks.
- Complexity does not change the contract: single container, Compose stack, k3s cluster and machine work all pass through the same stage gates. `kiri k8s`, `kiri machine`, `kiri share` are native verbs; verify their platform in the live docs from `resolved_urls` first.
