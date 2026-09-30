#!/bin/bash
# launch_webots_gui.sh — SIH26 Webots GUI Launcher
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

exec bash "$REPO_DIR/scripts/launch_gui_simulator.sh" webots "$@"
