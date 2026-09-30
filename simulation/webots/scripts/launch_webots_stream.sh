#!/bin/bash
# Run Webots in streaming mode - view in browser at http://localhost:1234
pkill -9 -x webots-bin 2>/dev/null; sleep 1

export GALLIUM_DRIVER=d3d12
export MESA_D3D12_DEFAULT_ADAPTER_NAME="Intel"
export LD_LIBRARY_PATH=/usr/local/webots/lib/webots:$LD_LIBRARY_PATH
export DISPLAY=:0
export WAYLAND_DISPLAY=wayland-0
export XDG_RUNTIME_DIR=/mnt/wslg/runtime-dir

WORLD="/mnt/c/Users/thega/PROJECTS/SIH'26/simulation/webots/worlds/warehouse_fleet.wbt"

echo "=== Webots streaming on http://localhost:1234 ==="
echo "=== Open that URL in your Windows browser NOW  ==="

/usr/local/bin/webots --batch --mode=realtime --stream "$WORLD"
