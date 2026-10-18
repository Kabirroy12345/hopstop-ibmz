#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
echo "[HopStop] Running unit tests..."
python3 -m unittest discover -s tests -p "test_*.py"

if [ ! -f "artifacts/hopstop_model.json" ]; then
    echo "[HopStop] Training model and generating benchmark artifacts..."
    python3 -m hopstop.train_and_benchmark
fi

echo "[HopStop] Starting live analyst console at http://127.0.0.1:8080 ..."
python3 -m hopstop.server
