from setuptools import setup, find_packages
import os
from glob import glob

package_name = "ros2_integration"

setup(
    name=package_name,
    version="1.0.0",
    packages=[package_name, f"{package_name}.mock_ros"],
    package_dir={
        package_name: ".",
        f"{package_name}.mock_ros": "mock_ros",
    },
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        # Launch files
        (f"share/{package_name}/launch", glob("launch/*.py")),
        # Config files
        (f"share/{package_name}/config", glob("config/*.yaml")),
        # World SDF files
        (f"share/{package_name}/worlds", glob("worlds/*.sdf")),
        # Robot model SDF
        (f"share/{package_name}/models/amr", glob("models/amr/*.sdf")),
        (f"share/{package_name}/models/amr", glob("models/amr/*.config")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="SIH26123 Team",
    maintainer_email="sih26123@example.com",
    description="ROS 2 adapter for SIH26123 fleet coordinator",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "amr_node = ros2_integration.amr_node:main",
            "fleet_launcher = ros2_integration.fleet_launcher:main",
            "gazebo_data_logger = ros2_integration.gazebo_data_logger:main",
            "live_demo_task_generator = ros2_integration.live_demo_task_generator:main",
            "fleet_safety_hud = ros2_integration.fleet_safety_hud:main",
            "camera_controller = ros2_integration.camera_controller:main",
        ],
    },
)
