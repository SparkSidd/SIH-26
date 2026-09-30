# SIH26123 — Webots ROS 2 Experimental Simulation

## Isolated Multi-AMR Warehouse Coordination Experiment

This package is a **completely isolated alternative simulation environment** for the SIH 2026 project:
**Decentralized AMR Fleet Coordination for Smart Warehouses**.

### Architectural Isolation Policy
1. **Gazebo is FROZEN**: The existing Gazebo implementation (`ros2_integration/`) remains 100% untouched.
2. **Core Algorithms Shared**:
   - Hungarian Task Allocation (`coordination/`)
   - Priority Inheritance with Backtracking (PIBT, `planning/pibt.py`)
   - Space-Time A* with Time-Space Reservations (`planning/astar.py`, `planning/reservation.py`)
   - Dynamic Priority & Congestion Tracking (`coordination/congestion.py`)
   - Wait-For Graph (WFG) Deadlock Detection (`coordination/wfg_detector.py`)
   - Safety Supervisor with Continuous Swept-Volume Checking (`safety/supervisor.py`)
3. **Dedicated Simulation Adapter**:
   `simulation/webots/controllers/webots_amr_node.py` adapts the core `FleetCoordinator` to Webots differential-drive AMRs using ROS 2 topics and parameters.

### Directory Structure
```
simulation/webots/
├── config/         # Performance profiles (dev, validation, recording)
├── controllers/    # Webots ROS 2 AMR controller node
├── launch/         # ROS 2 launch files (POC-01, POC-02, 6-AMR fleet)
├── protos/         # Webots AMR and warehouse asset PROTO definitions
├── resource/       # URDF and Webots ROS 2 robot configuration
├── safety/         # Dedicated Webots real-time Safety HUD
├── scripts/        # Linux and Windows execution launchers
└── worlds/         # 25m x 20m Smart Warehouse 3D World (.wbt)
```

### Milestone Roadmap
- [x] **Milestone 0**: Environment audit & Webots R2025a + webots_ros2 integration.
- [ ] **POC-01**: 2 AMRs, head-on corridor traversal, real FleetCoordinator, 0 collisions.
- [ ] **POC-02**: 4 AMRs, crossed paths & congestion yielding, 0 collisions.
- [ ] **Target 6-AMR Fleet**: 6 AMRs, high-density warehouse operations, dynamic blockage recovery, live HUD.
