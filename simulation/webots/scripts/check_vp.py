import os, sys
os.environ["WEBOTS_HOME"] = "/usr/local/webots"
sys.path.append("/usr/local/webots/lib/controller/python")
from controller import Supervisor

s = Supervisor()
vp = s.getViewpoint()
print("vp is:", vp)
if vp:
    pos = vp.getField("position")
    rot = vp.getField("orientation")
    print("pos field:", pos, "val:", pos.getSFVec3f() if pos else None)
    print("rot field:", rot, "val:", rot.getSFRotation() if rot else None)
