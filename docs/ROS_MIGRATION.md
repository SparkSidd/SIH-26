# ROS 2 & Gazebo Migration Roadmap

This system has been architected from day one to maintain total separation between the high-level intelligence stack (allocation, congestion estimation, decentralized MAPF, safety supervisor) and low-level physical simulation.

```
       [ HIGH-LEVEL FLEET INTELLIGENCE LAYER (Existing Python Core) ]
         ├── Fleet-Aware Allocator
         ├── LocalWorldModel (Per-AMR Belief)
         ├── PIBT / Space-Time Planner
         └── Deterministic Safety Supervisor
                           │
                           ▼
                 [ EXECUTION ADAPTER ]
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
    [ Python Grid Sim ]        [ ROS 2 + GAZEBO ]
    - ActionExecutor           - ROS2 Node (per robot)
    - MotionModel              - /cmd_vel (geometry_msgs/Twist)
    - 2D Warehouse Grid        - /scan (sensor_msgs/LaserScan)
                               - /odom (nav_msgs/Odometry)
                               - /robot_state (Custom P2P Topic)
```

---

## 1. Concrete Migration Interface

### A. ROS 2 Node Adapter (`amr_node.py`)
```python
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from execution.action import RobotAction, ActionType
from execution.motion_model import MotionModel
from world_model.local_world import LocalWorldModel

class AMRNode(Node):
    def __init__(self, robot_id: str):
        super().__init__(f"amr_{robot_id}")
        self.robot_id = robot_id
        
        # Subscriptions
        self.sub_odom = self.create_subscription(Odometry, f"/{robot_id}/odom", self._on_odom, 10)
        self.sub_scan = self.create_subscription(LaserScan, f"/{robot_id}/scan", self._on_scan, 10)
        
        # Publishers
        self.pub_cmd_vel = self.create_publisher(Twist, f"/{robot_id}/cmd_vel", 10)
        
        # Internal Intelligence stack instance
        self.motion_model = MotionModel()
        self.local_world = LocalWorldModel(self_id=robot_id, map_width=25, map_height=20, ...)
```

### B. Translation from `RobotAction` to `cmd_vel`
```python
def dispatch_action(self, action: RobotAction):
    twist = Twist()
    if action.action_type == ActionType.MOVE:
        twist.linear.x = action.target_velocity
        twist.angular.z = action.target_heading or 0.0
    elif action.action_type in (ActionType.WAIT, ActionType.ESTOP):
        twist.linear.x = 0.0
        twist.angular.z = 0.0
    self.pub_cmd_vel.publish(twist)
```

---

## 2. Gazebo Harmonic Integration Steps
1. **World SDF**: Convert `Warehouse` grid map to Gazebo `.sdf` model with physical walls and shelf models.
2. **Robot URDF/XACRO**: Standard differential drive robot model with 2D LiDAR and wheel encoders.
3. **P2P Wireless**: Use Zenoh or ROS 2 Discovery Server for decentralized inter-robot messaging.
