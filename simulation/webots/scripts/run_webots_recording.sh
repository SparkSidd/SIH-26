#!/bin/bash
set -e

PACED="${1:-false}"
DT="${2:-0.05}"

echo "======================================================================"
echo "  SIH 2026 (SIH26123) — DETERMINISTIC WEBOTS FLEET RECORDING"
echo "  Scenario:   SIH-WEBOTS-REC-01"
echo "  Fleet:      6 Industrial AMRs (R01 - R06)"
echo "  Paced Mode: $PACED (dt=$DT s)"
echo "======================================================================"

export WEBOTS_HOME=/usr/local/webots
export PYTHONPATH=/usr/local/webots/lib/controller/python:.
export PYTHONUNBUFFERED=1

if [ "$PACED" = "true" ] || [ "$PACED" = "1" ]; then
    python3 simulation/webots/scripts/run_webots_recording.py --paced --dt "$DT"
else
    python3 simulation/webots/scripts/run_webots_recording.py
fi
