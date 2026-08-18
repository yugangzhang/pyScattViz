#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [[ ! -x ".venv/bin/python" ]]; then
    echo "pyScattViz is not installed in this folder yet."
    echo
    echo "Open Terminal and follow the macOS installation section in README.md."
    echo "The environment-creation command is: python3.12 -m venv .venv"
    echo
    read -r -p "Press Return to close this window."
    exit 1
fi

exec ".venv/bin/python" -m pyscattviz "$@"
