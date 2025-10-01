from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class EventType(Enum):
    ARRIVAL = "arrival"
    DEPARTURE = "departure"
    TRANSFER = "transfer"

TYPE_PRIORITY = {
    EventType.DEPARTURE: 0,
    EventType.TRANSFER: 1,
    EventType.ARRIVAL: 2,
}

_seq_counter = 0

def next_seq() -> int:
    global _seq_counter
    _seq_counter += 1
    return _seq_counter

@dataclass(order=True)
class Event:
    sort_index: tuple = field(init=False, repr=False)
    time: float
    kind: EventType = field(compare=False)
    src_queue: str = field(compare=False)
    dst_queue: Optional[str] = field(default=None, compare=False)
    _seq: int = field(default=0, compare=False, repr=False)

    def bind_sort_index(self):
        self._seq = next_seq()
        self.sort_index = (self.time, TYPE_PRIORITY[self.kind], self._seq)

    def __post_init__(self):
        self.bind_sort_index()

    def __repr__(self):
        dst = f"->{self.dst_queue}" if self.dst_queue else ""
        return f"Event({self.kind.value}, t={self.time:.4f}, {self.src_queue}{dst})"
