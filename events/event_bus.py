"""Central asynchronous and synchronous Event Bus."""

from collections import defaultdict
from typing import Callable, Dict, List
from events.event import Event, EventType


class EventBus:
    """Publish-Subscribe Event Bus for system-wide decoupled communication."""

    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = defaultdict(list)
        self._global_subscribers: List[Callable[[Event], None]] = []
        self._history: List[Event] = []
        self._max_history: int = 10000

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """Subscribe a handler to a specific event type."""
        self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: Callable[[Event], None]) -> None:
        """Subscribe a handler to all events."""
        self._global_subscribers.append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """Unsubscribe a handler from an event type."""
        if callback in self._subscribers[event_type]:
            self._subscribers[event_type].remove(callback)

    def publish(self, event: Event) -> None:
        """Publish an event to all interested subscribers."""
        if len(self._history) < self._max_history:
            self._history.append(event)
        else:
            self._history.pop(0)
            self._history.append(event)

        for handler in self._subscribers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as e:
                print(f"[EventBus Error] Error in handler {handler} for {event.event_type}: {e}")

        for handler in self._global_subscribers:
            try:
                handler(event)
            except Exception as e:
                print(f"[EventBus Error] Error in global handler {handler} for {event.event_type}: {e}")

    def get_history(self, event_type: EventType = None) -> List[Event]:
        """Get event history, optionally filtered by type."""
        if event_type is None:
            return list(self._history)
        return [e for e in self._history if e.event_type == event_type]

    def clear(self) -> None:
        """Clear subscribers and history."""
        self._subscribers.clear()
        self._global_subscribers.clear()
        self._history.clear()
