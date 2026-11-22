#!/usr/bin/env bash
# Idempotent: ensure the kiri docker context exists and is selected.
# Usage: bash scripts/kiri-context.sh   (does not modify users, groups or the engine)
set -euo pipefail

if ! command -v kiri >/dev/null 2>&1; then
  printf 'kiri binary missing\n' >&2
  exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  printf 'docker CLI missing\n' >&2
  exit 1
fi
if [ "$(systemctl is-active kiri 2>/dev/null || true)" != active ]; then
  printf 'kiri.service is not active; start it with: sudo systemctl enable --now kiri\n' >&2
  exit 1
fi
if [ -n "${DOCKER_HOST:-}" ]; then
  printf 'DOCKER_HOST=%s overrides contexts; unset it before using this script\n' "$DOCKER_HOST" >&2
  exit 1
fi

if docker context inspect kiri >/dev/null 2>&1; then
  printf 'context kiri already exists\n'
else
  docker context create kiri --docker host=unix:///run/kiri/docker.sock
  printf 'context kiri created\n'
fi

docker context use kiri
docker --context kiri info --format '{{.ServerVersion}} {{.OperatingSystem}}'
