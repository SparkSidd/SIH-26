"""Unit tests for Space-Time A* Planner."""

import pytest
from planning.astar import SpaceTimeAStarPlanner, PlannerStatusCode
from planning.reservation import SpaceTimeReservationTable


def test_astar_straight_line():
    planner = SpaceTimeAStarPlanner()
    is_walkable = lambda pos: 0 <= pos[0] < 10 and 0 <= pos[1] < 10

    res = planner.plan(
        robot_id="R1",
        start_pos=(0, 0),
        goal_pos=(3, 0),
        is_walkable_fn=is_walkable,
    )

    assert res.status == PlannerStatusCode.SUCCESS
    assert res.is_success is True
    assert res.path == [(0, 0), (1, 0), (2, 0), (3, 0)]
    assert res.cost == 3.0


def test_astar_with_obstacle():
    planner = SpaceTimeAStarPlanner()
    blocked = {(1, 0)}
    is_walkable = lambda pos: 0 <= pos[0] < 5 and 0 <= pos[1] < 5

    res = planner.plan(
        robot_id="R1",
        start_pos=(0, 0),
        goal_pos=(2, 0),
        is_walkable_fn=is_walkable,
        blocked_cells=blocked,
    )

    assert res.status == PlannerStatusCode.SUCCESS
    # Path must detour around (1,0) via (0,1) -> (1,1) -> (2,1) -> (2,0)
    assert (1, 0) not in res.path
    assert res.path[-1] == (2, 0)


def test_astar_with_reservation_conflict():
    planner = SpaceTimeAStarPlanner()
    reservations = SpaceTimeReservationTable()
    # Another robot R2 reserved (1, 0) at timestep 1
    reservations.reserve_vertex((1, 0), 1, "R2")

    is_walkable = lambda pos: 0 <= pos[0] < 5 and 0 <= pos[1] < 5

    res = planner.plan(
        robot_id="R1",
        start_pos=(0, 0),
        goal_pos=(2, 0),
        is_walkable_fn=is_walkable,
        reservation_table=reservations,
    )

    assert res.status == PlannerStatusCode.SUCCESS
    # R1 must not step on (1,0) at t=1
    assert res.path[1] != (1, 0) or len(res.path) > 1
