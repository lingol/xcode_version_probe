#!/bin/sh
# Run once per Cloud action, before the carrier framework is built.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
exec python3 -u ci_scripts/run_cloud_probe.py
