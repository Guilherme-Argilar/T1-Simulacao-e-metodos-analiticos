from collections import defaultdict
from typing import Dict, List, Optional

class QueueNode:
    def __init__(
        self,
        name: str,
        servers: int,
        capacity: Optional[int],
        min_arrival: Optional[float],
        max_arrival: Optional[float],
        min_service: float,
        max_service: float,
    ):
        self.name = name
        self.num_servers = servers
        self.capacity = float("inf") if capacity is None or capacity < 0 else capacity
        self.min_arrival = min_arrival
        self.max_arrival = max_arrival
        self.min_service = min_service
        self.max_service = max_service

        self.in_system = 0
        self.busy_until_times: List[float] = []

        self.received = 0
        self.completed = 0
        self.lost = 0
        self.time_by_state = defaultdict(float)
        self.last_update_time = 0.0

        self.routes: Dict[str, float] = {}

    def status(self) -> int:
        return self.in_system

    def capacity_value(self) -> float:
        return self.capacity

    def servers_value(self) -> int:
        return self.num_servers

    def inc_loss(self):
        self.lost += 1

    def add_customer(self):
        self.in_system += 1
        self.received += 1

    def remove_customer(self):
        if self.in_system > 0:
            self.in_system -= 1
            self.completed += 1

    def has_space(self) -> bool:
        return self.in_system < self.capacity

    def has_free_server(self) -> bool:
        return len(self.busy_until_times) < self.num_servers

    def update_state_time(self, now: float):
        dt = now - self.last_update_time
        if dt < 0:
            dt = 0
        self.time_by_state[self.in_system] += dt
        self.last_update_time = now
