import heapq
from typing import List, Optional
from events import Event

class Scheduler:
    def __init__(self):
        self._heap: List[Event] = []

    def add(self, ev: Event):
        ev.bind_sort_index()
        heapq.heappush(self._heap, ev)

    def next(self) -> Optional[Event]:
        if self._heap:
            return heapq.heappop(self._heap)
        return None

    def has_events(self) -> bool:
        return len(self._heap) > 0

    def clear(self):
        self._heap.clear()
