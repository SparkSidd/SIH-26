#!/bin/bash
source /opt/ros/jazzy/setup.bash
source /home/siddharth/sih26/ros2_ws/install/setup.bash
export PYTHONPATH="/home/siddharth/sih26:/home/siddharth/sih26/ros2_integration:$PYTHONPATH"
"$@"
