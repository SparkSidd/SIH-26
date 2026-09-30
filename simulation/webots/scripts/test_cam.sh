#!/bin/bash
set -e
export WEBOTS_HOME=/usr/local/webots

# Test 1: Overhead Top-Down (Bird's Eye)
cat << 'EOF' > /tmp/test_cam.py
import os, sys
os.environ["WEBOTS_HOME"] = "/usr/local/webots"
sys.path.append("/usr/local/webots/lib/controller/python")
from controller import Supervisor

s = Supervisor()
vp = s.getFromDef("VIEWPOINT")
if vp:
    vp.getField("position").setSFVec3f([12.0, 9.5, 26.0])
    vp.getField("orientation").setSFRotation([0.0, 0.0, 1.0, 0.0])
    vp.getField("fieldOfView").setSFFloat(1.0)
s.step(32)
EOF

python3 /tmp/test_cam.py 2>/dev/null || true
