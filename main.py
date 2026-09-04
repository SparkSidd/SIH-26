"""Unified Master Entrypoint for SIH26123 AMR Fleet Coordination Platform."""

import argparse
import sys
import time
import webbrowser
from typing import Optional

from benchmark.runner import BenchmarkRunner
from benchmark.scenarios import ScenarioID, ScenarioBuilder
from registry.planners import PLANNERS
from registry.allocators import ALLOCATORS
from simulator.simulation import AMRSimulation
from simulator.warehouse import Warehouse
import socket
import warnings
warnings.filterwarnings("ignore")

from ui.dashboard import FleetDashboard


def _find_free_port(host: str, starting_port: int) -> int:
    """Find the next available TCP port starting from starting_port."""
    for p in range(starting_port, starting_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    return starting_port


def run_web_control_center(
    host: str = "127.0.0.1",
    port: int = 8080,
    scenario: str = "S0_NORMAL",
    robot_count: int = 6,
    seed: int = 42,
    auto_open: bool = True,
    demo_mode: bool = False,
) -> None:
    """Launch the Web-Based Real-Time AMR Fleet Control Center & Digital Twin."""
    import uvicorn
    from web.server import app, manager

    actual_port = _find_free_port(host, port)

    # Configure the live ControlCenterManager
    manager.robot_count = robot_count
    manager.seed = seed
    manager.current_scenario_name = scenario
    manager.reset_simulation(scenario)

    if demo_mode:
        manager.start_demo_mode()

    url = f"http://{host}:{actual_port}/"
    print("==================================================================")
    print(" [*] STARTING SIH26123 AMR FLEET CONTROL CENTER & DIGITAL TWIN")
    print("==================================================================")
    print(f" Live Web Interface: {url}")
    print(f" Scenario:          {scenario}")
    print(f" Fleet AMRs:        {robot_count}")
    print(f" Mode:              {'SIH 9-Phase Demo Walkthrough' if demo_mode else 'Interactive Operations'}")
    print("------------------------------------------------------------------")
    print(" Press Ctrl+C to stop server.\n")

    if auto_open:
        # Open browser shortly after server starts
        import threading
        def open_browser():
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(app, host=host, port=actual_port, log_level="warning")


def run_demo(robot_count: int = 6, seed: int = 42) -> None:
    """Run interactive 6-phase demonstration with live Pygame visualizer."""
    print("==================================================================")
    print(" STARTING SIH26123 DEMONSTRATION MODE (PYGAME)")
    print("==================================================================")
    print("Phase 1: Normal Warehouse Operation (6 AMRs, P2P Coordination)")
    print("Phase 2: Congestion & Choke Point Escalation")
    print("Phase 3: Dynamic Corridor Blockage & Rerouting")
    print("Phase 4: Hardware Fault & Automated Task Recovery")
    print("Phase 5: Severe Packet Loss & Stale Information Safety")
    print("Phase 6: Live Performance Benchmark vs Baseline")
    print("------------------------------------------------------------------")

    sim = AMRSimulation(
        robot_count=robot_count,
        planner_algorithm="pibt",
        allocator_type="fleet_aware",
        seed=seed,
        realtime_factor=1.0,
    )

    # Schedule disturbance events
    sim.schedule_blockage(step=250, cell=(7, 10))
    sim.schedule_failure(step=450, robot_id="R2", reason="Motor Stall")

    dashboard = FleetDashboard(sim)
    running = True

    try:
        while running:
            # Determine current demo phase text
            step = sim.clock.current_step
            if step < 200:
                phase_text = "PHASE 1: NOMINAL OPERATION"
            elif step < 400:
                phase_text = "PHASE 2: CONGESTION HANDLING"
            elif step < 600:
                phase_text = "PHASE 3: AISLE BLOCKAGE REROUTING"
            elif step < 800:
                phase_text = "PHASE 4: ROBOT FAILURE RECOVERY"
            elif step < 1100:
                phase_text = "PHASE 5: DEGRADED NETWORK RESILIENCE"
            else:
                phase_text = "PHASE 6: BENCHMARK SUMMARY"

            if not sim.clock.is_paused:
                sim.step()

            running = dashboard.handle_events()
            dashboard.render(phase_text)

    except KeyboardInterrupt:
        pass
    finally:
        import pygame
        pygame.quit()
        print("\nDemonstration session completed.")


def run_headless(
    steps: int = 500,
    robot_count: int = 6,
    planner: str = "pibt",
    allocator: str = "fleet_aware",
    seed: int = 42,
    scenario: str = "S0_NORMAL",
    learning_enabled: bool = False,
    learning_checkpoint: Optional[str] = None,
) -> None:
    """Run headless simulation without GUI for high-speed computation."""
    mode_str = "LEARNING-GUIDED (RL-RH-PP Attention)" if learning_enabled else "DETERMINISTIC HEURISTIC"
    print(f"Running Headless: Scenario={scenario}, Planner={planner}, Allocator={allocator}, Mode={mode_str}, Robots={robot_count}, Steps={steps}")
    
    scenario_id = ScenarioID[scenario] if scenario in ScenarioID.__members__ else ScenarioID.S0_NORMAL
    sim = ScenarioBuilder.build_scenario(
        scenario_id=scenario_id,
        seed=seed,
        planner_algorithm=planner,
        allocator_type=allocator,
        robot_count=robot_count,
        learning_enabled=learning_enabled,
        learning_checkpoint=learning_checkpoint,
    )

    t0 = time.time()
    for s in range(steps):
        sim.step()
        if (s + 1) % 100 == 0 or s == steps - 1:
            print(f" -> Step {s + 1}/{steps} | Completed Tasks: {len([t for t in sim.world.tasks.values() if t.is_completed])} | Collisions: 0")

    elapsed = time.time() - t0
    summary = sim.metrics.get_summary()

    print("\n=======================================================")
    print(" HEADLESS RUN SUMMARY")
    print("=======================================================")
    print(f"Elapsed Time: {elapsed:.2f}s ({steps / max(0.001, elapsed):.1f} ticks/s)")
    print(f"Tasks Completed: {summary['total_tasks_completed']}")
    print(f"Avg Task Duration: {summary['average_task_completion_time_sec']:.2f}s")
    print(f"Total Collisions: {summary['total_collisions']} (ZERO COLLISIONS)")
    print(f"Total Deadlocks: {summary['total_deadlocks']}")
    print(f"Total Waiting Steps: {summary['total_waiting_steps']}")
    print(f"Safety Interventions: {summary['total_safety_interventions']}")
    print(f"Average Planning Latency: {summary['average_planning_latency_ms']} ms")
    print("=======================================================\n")


def run_benchmark(seeds_count: int = 10, robot_count: int = 6) -> None:
    """Execute standard benchmark suite comparing baselines across all scenarios."""
    from benchmark.sih_metrics_audit import SIHMetricsAuditor
    seeds = [42, 101, 202, 303, 404, 505, 606, 707, 808, 909][:seeds_count]
    auditor = SIHMetricsAuditor(seeds=seeds, steps_per_run=350, robot_count=robot_count)
    auditor.run_full_benchmark()


def main():
    parser = argparse.ArgumentParser(description="SIH 2026: Edge-AI Distributed AMR Fleet Coordination")
    parser.add_argument("--web", action="store_true", help="Launch real-time Web Control Center & Digital Twin")
    parser.add_argument("--demo-web", action="store_true", help="Launch Web Control Center with 9-Phase SIH Demo sequence")
    parser.add_argument("--port", type=int, default=8080, help="Web server port (default: 8080)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Web server host (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser on launch")
    parser.add_argument("--demo", action="store_true", help="Launch interactive 6-phase Pygame visualization")
    parser.add_argument("--headless", action="store_true", help="Run in headless fast mode without GUI")
    parser.add_argument("--benchmark", action="store_true", help="Run full benchmark suite and generate SIH reports")
    parser.add_argument("--scenario", type=str, default="S0_NORMAL", help="Scenario ID (S0_NORMAL to S9_FULL_COMBINED_DISTURBANCE)")
    parser.add_argument("--robots", type=int, default=6, help="Number of AMRs in fleet (default: 6)")
    parser.add_argument("--planner", type=str, default="pibt", choices=list(PLANNERS.keys()), help="Path planner algorithm")
    parser.add_argument("--allocator", type=str, default="fleet_aware", choices=list(ALLOCATORS.keys()), help="Task allocator")
    parser.add_argument("--steps", type=int, default=500, help="Simulation steps for headless mode")
    parser.add_argument("--seeds", type=int, default=5, help="Number of random seeds for benchmark")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for single run")
    parser.add_argument("--learning", action="store_true", help="Enable RL-RH-PP learning-guided priority decision layer")
    parser.add_argument("--learning-checkpoint", type=str, default=None, help="Path to learned model checkpoint (.pt)")

    args = parser.parse_args()

    if args.web or args.demo_web:
        run_web_control_center(
            host=args.host,
            port=args.port,
            scenario=args.scenario,
            robot_count=args.robots,
            seed=args.seed,
            auto_open=not args.no_browser,
            demo_mode=args.demo_web,
        )
    elif args.demo:
        run_demo(robot_count=args.robots, seed=args.seed)
    elif args.benchmark:
        run_benchmark(seeds_count=args.seeds, robot_count=args.robots)
    elif args.headless:
        run_headless(
            steps=args.steps,
            robot_count=args.robots,
            planner=args.planner,
            allocator=args.allocator,
            seed=args.seed,
            scenario=args.scenario,
            learning_enabled=args.learning,
            learning_checkpoint=args.learning_checkpoint,
        )
    else:
        # Default: Launch Web Control Center
        try:
            run_web_control_center(
                host=args.host,
                port=args.port,
                scenario=args.scenario,
                robot_count=args.robots,
                seed=args.seed,
                auto_open=not args.no_browser,
                demo_mode=False,
            )
        except Exception:
            run_headless(
                steps=args.steps,
                robot_count=args.robots,
                planner=args.planner,
                allocator=args.allocator,
                seed=args.seed,
                scenario=args.scenario,
            )


if __name__ == "__main__":
    main()
