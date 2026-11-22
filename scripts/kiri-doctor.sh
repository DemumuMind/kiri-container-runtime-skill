#!/usr/bin/env bash
# Read-only health check for a Kiri Linux host, plus one smoke container.
# Usage: bash scripts/kiri-doctor.sh   (SKIP_SMOKE=1 skips the container run)
set -uo pipefail

PASS=0
FAIL=0
ok()   { printf 'OK   %s\n' "$*"; PASS=$((PASS + 1)); }
bad()  { printf 'FAIL %s\n' "$*"; FAIL=$((FAIL + 1)); }
note() { printf 'NOTE %s\n' "$*"; }

command -v kiri >/dev/null 2>&1 && ok "kiri binary: $(command -v kiri)" || bad 'kiri binary missing'

if command -v dpkg-query >/dev/null 2>&1; then
  ver=$(dpkg-query -W -f='${Version}' kiri 2>/dev/null || true)
  [ -n "$ver" ] && ok "package version: $ver" || bad 'kiri package not installed'
else
  note 'dpkg-query unavailable; skipped package version'
fi

state=$(systemctl is-active kiri 2>/dev/null || true)
[ "$state" = active ] && ok 'kiri.service active' || bad "kiri.service: ${state:-unknown}"

if [ -S /run/kiri/docker.sock ]; then
  ok 'engine socket /run/kiri/docker.sock exists'
else
  bad 'engine socket /run/kiri/docker.sock missing'
fi

if [ "$(id -u)" -eq 0 ] || id -nG 2>/dev/null | tr ' ' '\n' | grep -qx kiri; then
  ok 'caller is root or in the kiri group'
else
  note 'kiri group not visible in this login (new login needed); socket access is tested below'
fi

if [ -n "${DOCKER_HOST:-}" ]; then
  note "DOCKER_HOST is set to $DOCKER_HOST and overrides contexts"
fi

if command -v docker >/dev/null 2>&1; then
  info=$(timeout 30 docker --context kiri info --format '{{.ServerVersion}} {{.OperatingSystem}}' 2>&1)
  case "$info" in
    *Kiri*) ok "engine reachable: $info" ;;
    *) bad "engine not reachable via kiri context: $info" ;;
  esac

  if [ "${SKIP_SMOKE:-0}" = 1 ]; then
    note 'smoke container skipped (SKIP_SMOKE=1)'
  else
    out=$(timeout 120 docker --context kiri run --rm alpine echo KIRI_DOCTOR_OK 2>&1)
    case "$out" in
      *KIRI_DOCTOR_OK*) ok 'smoke container ran and exited 0' ;;
      *) bad "smoke container failed: $out" ;;
    esac
  fi
else
  bad 'docker CLI missing'
fi

printf 'SUMMARY pass=%s fail=%s\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
