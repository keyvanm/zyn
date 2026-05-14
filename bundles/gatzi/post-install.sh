#!/usr/bin/env bash
set -euo pipefail

if ! command -v ya &>/dev/null; then
    echo "gatzi: 'ya' (yazi CLI) not found in PATH" >&2
    echo "       Install yazi first, then re-run: just post-install gatzi" >&2
    exit 1
fi

ya pkg install
