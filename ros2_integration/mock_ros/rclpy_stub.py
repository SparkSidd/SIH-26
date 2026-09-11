"""
rclpy_stub.py — Transparent mock of the rclpy API for SIL testing.

Matches rclpy 0.18.x (ROS 2 Jazzy) public API surface used by AMRNode.
In-process message delivery via direct callback invocation (no network).
"""

from __future__ import annotations

import threading
import time
import logging
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Global registry for in-process topic routing (SIL message bus)
# ──────────────────────────────────────────────────────────────────────────────
_topic_subscribers: Dict[str, List["Subscription"]] = {}
_topic_lock = threading.Lock()
_node_registry: Dict[str, "Node"] = {}
_initialized = False


def init(args=None) -> None:
    """Mock rclpy.init()."""
    global _initialized
    _initialized = True
    logger.debug("[mock_rclpy] init()")


def shutdown() -> None:
    """Mock rclpy.shutdown()."""
    global _initialized, _topic_subscribers, _node_registry
    _initialized = False
    with _topic_lock:
        _topic_subscribers.clear()
    _node_registry.clear()
    logger.debug("[mock_rclpy] shutdown()")


def ok() -> bool:
    """Mock rclpy.ok()."""
    return _initialized


def spin_once(node: "Node", timeout_sec: float = 0.0) -> None:
    """Mock rclpy.spin_once() — processes pending callbacks."""
    node._process_pending()


def spin(node: "Node") -> None:
    """Mock rclpy.spin() — runs until shutdown."""
    while _initialized:
        node._process_pending()
        time.sleep(0.001)


# ──────────────────────────────────────────────────────────────────────────────
# QoS
# ──────────────────────────────────────────────────────────────────────────────
class QoSProfile:
    def __init__(self, depth: int = 10, **kwargs):
        self.depth = depth


class ReliabilityPolicy:
    RELIABLE = "RELIABLE"
    BEST_EFFORT = "BEST_EFFORT"


class DurabilityPolicy:
    VOLATILE = "VOLATILE"
    TRANSIENT_LOCAL = "TRANSIENT_LOCAL"


class HistoryPolicy:
    KEEP_LAST = "KEEP_LAST"
    KEEP_ALL = "KEEP_ALL"


# ──────────────────────────────────────────────────────────────────────────────
# Timer
# ──────────────────────────────────────────────────────────────────────────────
class Timer:
    def __init__(self, period_sec: float, callback: Callable, node: "Node"):
        self._period = period_sec
        self._callback = callback
        self._node = node
        self._last_fire = time.monotonic()
        self._active = True

    def cancel(self) -> None:
        self._active = False

    def _maybe_fire(self) -> None:
        if not self._active:
            return
        now = time.monotonic()
        if now - self._last_fire >= self._period:
            self._last_fire = now
            self._callback()


# ──────────────────────────────────────────────────────────────────────────────
# Publisher
# ──────────────────────────────────────────────────────────────────────────────
class Publisher:
    def __init__(self, msg_type: Type, topic: str, qos: Any):
        self.msg_type = msg_type
        self.topic = topic
        self.qos = qos
        self._publish_count = 0

    def publish(self, msg: Any) -> None:
        self._publish_count += 1
        # Route to all subscribers of this topic
        with _topic_lock:
            subs = list(_topic_subscribers.get(self.topic, []))
        for sub in subs:
            try:
                sub._enqueue(msg)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[mock_rclpy] Publisher.publish error on %s: %s", self.topic, exc)

    @property
    def publish_count(self) -> int:
        return self._publish_count


# ──────────────────────────────────────────────────────────────────────────────
# Subscription
# ──────────────────────────────────────────────────────────────────────────────
class Subscription:
    def __init__(self, msg_type: Type, topic: str, callback: Callable, qos: Any):
        self.msg_type = msg_type
        self.topic = topic
        self._callback = callback
        self.qos = qos
        self._queue: List[Any] = []
        self._lock = threading.Lock()

        with _topic_lock:
            _topic_subscribers.setdefault(self.topic, []).append(self)

    def _enqueue(self, msg: Any) -> None:
        with self._lock:
            self._queue.append(msg)

    def _drain(self) -> None:
        with self._lock:
            items, self._queue = self._queue, []
        for msg in items:
            try:
                self._callback(msg)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[mock_rclpy] Subscription callback error on %s: %s", self.topic, exc)

    def destroy(self) -> None:
        with _topic_lock:
            subs = _topic_subscribers.get(self.topic, [])
            if self in subs:
                subs.remove(self)


# ──────────────────────────────────────────────────────────────────────────────
# Node
# ──────────────────────────────────────────────────────────────────────────────
class Node:
    """
    Mock rclpy.node.Node.

    Matches the subset of the rclpy Node API used by AMRNode:
      - create_publisher(msg_type, topic, qos)
      - create_subscription(msg_type, topic, callback, qos)
      - create_timer(period_sec, callback)
      - get_logger()
      - get_clock().now()
      - destroy_node()
    """

    def __init__(self, node_name: str, **kwargs):
        self._name = node_name
        self._publishers: List[Publisher] = []
        self._subscriptions: List[Subscription] = []
        self._timers: List[Timer] = []
        self._logger = _NodeLogger(node_name)
        self._clock = _Clock()
        _node_registry[node_name] = self

    # ── Factory methods ──────────────────────────────────────────────────────

    def create_publisher(self, msg_type: Type, topic: str, qos: Any) -> Publisher:
        pub = Publisher(msg_type, topic, qos)
        self._publishers.append(pub)
        return pub

    def create_subscription(
        self,
        msg_type: Type,
        topic: str,
        callback: Callable,
        qos: Any,
    ) -> Subscription:
        sub = Subscription(msg_type, topic, callback, qos)
        self._subscriptions.append(sub)
        return sub

    def create_timer(self, period_sec: float, callback: Callable) -> Timer:
        timer = Timer(period_sec, callback, self)
        self._timers.append(timer)
        return timer

    # ── Utilities ────────────────────────────────────────────────────────────

    def get_logger(self) -> "_NodeLogger":
        return self._logger

    def get_clock(self) -> "_Clock":
        return self._clock

    def get_name(self) -> str:
        return self._name

    def destroy_node(self) -> None:
        for sub in self._subscriptions:
            sub.destroy()
        self._subscriptions.clear()
        self._publishers.clear()
        self._timers.clear()
        _node_registry.pop(self._name, None)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _process_pending(self) -> None:
        """Drain all subscription queues and fire due timers."""
        for sub in self._subscriptions:
            sub._drain()
        for timer in self._timers:
            timer._maybe_fire()


# ──────────────────────────────────────────────────────────────────────────────
# Logger & Clock helpers
# ──────────────────────────────────────────────────────────────────────────────
class _NodeLogger:
    def __init__(self, name: str):
        self._log = logging.getLogger(f"rclpy.{name}")

    def info(self, msg: str) -> None:
        self._log.info(msg)

    def warn(self, msg: str) -> None:
        self._log.warning(msg)

    def error(self, msg: str) -> None:
        self._log.error(msg)

    def debug(self, msg: str) -> None:
        self._log.debug(msg)


class _Time:
    def __init__(self, nanoseconds: int = 0):
        self.nanoseconds = nanoseconds

    def to_sec(self) -> float:
        return self.nanoseconds / 1e9


class _Clock:
    def now(self) -> _Time:
        return _Time(nanoseconds=int(time.monotonic() * 1e9))
