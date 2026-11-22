# Upstream source discovery

Only one value is fixed: the upstream repository identity used as bootstrap. Everything else is discovered at runtime.

| Bootstrap | Purpose |
| --- | --- |
| `https://api.github.com/repos/libracoder/kiri` | Repository metadata: homepage, default branch, release API |
| `KIRI_BOOTSTRAP_REPO` | Optional override if the upstream repository moves |
| `GITHUB_TOKEN` / `GH_TOKEN` | Optional Authorization header for `api.github.com` only; never sent to other sources |

From those, `scripts/kiri_facts.py` resolves and verifies:

| Discovered source | How it is found | What it decides |
| --- | --- | --- |
| Official homepage | `homepage` in repository metadata | Root for site links |
| Release API | `releases_url` in repository metadata | Latest tag, date, asset names |
| CLI docs | Link from homepage, falling back to `/docs/cli/` on that homepage | Current command and platform matrix |
| Install script | Link from homepage, falling back to `/install.sh` on that homepage | Checksum host and filename |
| Checksum feed | Link from homepage/download page, or parsed from the install script | Published package versions |
| Feature docs | GitHub contents API using the default branch, or raw URL derived from `html_url` | Current feature support |

No docs URL, checksum path or release version is stored as truth. If a source moves, discovery follows it. If discovery fails, the report is `degraded` and names the failed source.

## Drift policy

1. Run `python3 scripts/kiri_facts.py` before any version-specific answer.
2. Read the current docs from `discovery.resolved_urls`; treat `references/` as pattern notes only.
3. If `comparison.update_available` is true, point at the installer URL found on the current official site. Do not edit the skill to bump a number.
4. In `degraded` mode, name the failed sources and limit claims to local `kiri --help`.
5. A moved upstream repository is handled by setting `KIRI_BOOTSTRAP_REPO`; no code edit is needed.

## Scheduled check and tests

`.github/workflows/source-watch.yml` runs the resolver daily and opens or updates one issue when sources fail or an update is available. `python3 -m unittest discover -s tests -v` simulates a future upstream with different domains and a newer version, plus a network outage.
