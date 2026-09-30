import os, sys
os.environ["WEBOTS_HOME"] = "/usr/local/webots"
sys.path.append("/usr/local/webots/lib/controller/python")
from controller import Node, Supervisor
print("Node has resetPhysics:", hasattr(Node, "resetPhysics"))
print("Node has getVelocity:", hasattr(Node, "getVelocity"))
print("Node has setVelocity:", hasattr(Node, "setVelocity"))
