import random
import yaml
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from events import Event, EventType
from queue_node import QueueNode
from scheduler import Scheduler

class Simulator:
    def __init__(self, yaml_file: Optional[str] = None):
        self._cfg = None
        self.queues: Dict[str, QueueNode] = {}
        self.scheduler = Scheduler()
        self.now = 0.0

        self.rng_count = 0
        self.rng_limit = 100000

        self.initial_arrivals: Dict[str, float] = {}
        self.use_seed = False
        self.seed = None

        self._agg_time_by_state: Dict[str, Dict[int, float]] = {}
        self._agg_losses: Dict[str, int] = {}
        self._avg_global_time: float = 0.0
        self._used_seeds: List[int] = []

        if yaml_file:
            self.load_config(yaml_file)

    def load_config(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
            tag = "!PARAMETERS"
            i = text.find(tag)
            if i != -1:
                text = text[i + len(tag):]
            cfg = yaml.safe_load(text)
        self._cfg = cfg
        self._reset_from_cfg(cfg, apply_seed=False)

    def _reset_from_cfg(self, cfg: dict, apply_seed: bool):
        self.queues = {}
        self.scheduler = Scheduler()
        self.now = 0.0
        self.rng_count = 0

        self.rng_limit = int(cfg.get("rndnumbersPerSeed", self.rng_limit))
        self.initial_arrivals = dict(cfg.get("arrivals", {}))

        for name, p in cfg.get("queues", {}).items():
            self.queues[name] = QueueNode(
                name=name,
                servers=int(p["servers"]),
                capacity=p.get("capacity"),
                min_arrival=p.get("minArrival"),
                max_arrival=p.get("maxArrival"),
                min_service=float(p["minService"]),
                max_service=float(p["maxService"]),
            )

        for link in cfg.get("network", []):
            src = link["source"]
            dst = link["target"]
            prob = float(link["probability"])
            if src in self.queues:
                self.queues[src].routes[dst] = prob

        if apply_seed:
            if self.seed is None:
                random.seed()
                self.use_seed = False
            else:
                random.seed(self.seed)
                self.use_seed = True

    def can_draw(self, n: int = 1) -> bool:
        return self.rng_count + n <= self.rng_limit

    def draw_uniform(self) -> Optional[float]:
        if not self.can_draw():
            return None
        self.rng_count += 1
        return random.random()

    def draw_interarrival(self, q: QueueNode) -> Optional[float]:
        r = self.draw_uniform()
        if r is None:
            return None
        return q.min_arrival + r * (q.max_arrival - q.min_arrival)

    def draw_service(self, q: QueueNode) -> Optional[float]:
        r = self.draw_uniform()
        if r is None:
            return None
        return q.min_service + r * (q.max_service - q.min_service)

    def route_next(self, q: QueueNode) -> Optional[str]:
        if not q.routes:
            return None
        r = self.draw_uniform()
        if r is None:
            return None
        acc = 0.0
        for dst, p in q.routes.items():
            acc += p
            if r < acc:
                return dst
        return None

    def accrue_time(self, t: float):
        for q in self.queues.values():
            q.update_state_time(t)
        self.now = t

    def _push(self, ev: Event):
        self.scheduler.add(ev)

    def _start_services(self, q: QueueNode):
        busy = len(q.busy_until_times)
        available_customers = max(0, q.in_system - busy)
        free = max(0, q.num_servers - busy)
        k = min(free, available_customers)
        for _ in range(k):
            s = self.draw_service(q)
            if s is None:
                return
            end = self.now + s
            self._push(Event(end, EventType.DEPARTURE, q.name))
            q.busy_until_times.append(end)

    def handle_arrival(self, ev: Event):
        q = self.queues[ev.src_queue]
        self.accrue_time(ev.time)

        if q.has_space():
            q.add_customer()
            self._start_services(q)
        else:
            q.inc_loss()

        if q.min_arrival is not None and q.max_arrival is not None:
            gap = self.draw_interarrival(q)
            if gap is not None:
                self._push(Event(self.now + gap, EventType.ARRIVAL, ev.src_queue))

    def handle_departure(self, ev: Event):
        q = self.queues[ev.src_queue]
        self.accrue_time(ev.time)

        try:
            q.busy_until_times.remove(ev.time)
        except ValueError:
            if q.busy_until_times:
                q.busy_until_times.pop(0)

        q.remove_customer()

        dst = self.route_next(q)
        if dst and dst in self.queues:
            self._push(Event(ev.time, EventType.TRANSFER, ev.src_queue, dst))

        self._start_services(q)

    def handle_transfer(self, ev: Event):
        self.accrue_time(ev.time)
        dest = self.queues[ev.dst_queue]

        if dest.has_space():
            dest.add_customer()
            self._start_services(dest)
        else:
            dest.inc_loss()

    def _run_once(self) -> Tuple[Dict[str, Dict[int, float]], Dict[str, int], float]:
        t0 = min(self.initial_arrivals.values()) if self.initial_arrivals else 0.0
        self.now = t0
        for q in self.queues.values():
            q.last_update_time = t0

        for name, t in self.initial_arrivals.items():
            if name in self.queues:
                self._push(Event(float(t), EventType.ARRIVAL, name))

        while self.scheduler.has_events() and self.rng_count < self.rng_limit:
            ev = self.scheduler.next()
            if ev.kind == EventType.DEPARTURE:
                self.handle_departure(ev)
            elif ev.kind == EventType.TRANSFER:
                self.handle_transfer(ev)
            else:
                self.handle_arrival(ev)

        for q in self.queues.values():
            q.update_state_time(self.now)

        times = {name: dict(q.time_by_state) for name, q in self.queues.items()}
        losses = {name: q.lost for name, q in self.queues.items()}
        return times, losses, self.now

    def run(self):
        if self._cfg is None:
            raise RuntimeError("config not loaded")

        seeds = self._cfg.get("seeds", [])
        if not seeds:
            seeds = [None]

        acc_times: Dict[str, Dict[int, float]] = {}
        acc_losses: Dict[str, int] = {}
        global_times: List[float] = []
        self._used_seeds = []

        queue_names = list(self._cfg.get("queues", {}).keys())
        for name in queue_names:
            acc_times[name] = defaultdict(float)
            acc_losses[name] = 0

        for sd in seeds:
            self.seed = sd
            if sd is None:
                random.seed()
                self.use_seed = False
            else:
                random.seed(sd)
                self.use_seed = True
                self._used_seeds.append(sd)

            self._reset_from_cfg(self._cfg, apply_seed=False)
            times, losses, tglob = self._run_once()

            global_times.append(tglob)
            for name in queue_names:
                for st, val in times[name].items():
                    acc_times[name][st] += val
                acc_losses[name] += losses[name]

        self._agg_time_by_state = {n: dict(d) for n, d in acc_times.items()}
        self._agg_losses = acc_losses
        self._avg_global_time = sum(global_times) / len(global_times)

        for name in queue_names:
            q = self.queues[name]
            q.time_by_state = defaultdict(float, self._agg_time_by_state[name])
            q.lost = self._agg_losses[name]
        self.now = self._avg_global_time

    def report(self) -> str:
        lines = []
        lines.append("=" * 86)
        lines.append("QUEUEING NETWORK SIMULATOR")
        lines.append("=" * 86)

        if len(self._used_seeds) > 1:
            lines.append(f"Simulation average time: {self._avg_global_time:.4f}")
            lines.append(f"Seeds: {', '.join(map(str, self._used_seeds))}")
            lines.append(f"Random numbers per seed: {self.rng_limit}")
        else:
            lines.append(f"Global simulation time: {self.now:.4f}")
            lines.append(f"Random numbers used: {self.rng_count} (limit {self.rng_limit})")
            if self.use_seed and self.seed is not None:
                lines.append(f"Seed: {self.seed}")
        lines.append("")

        for name in sorted(self.queues.keys()):
            q = self.queues[name]
            lines.append("=" * 86)
            lines.append(f"QUEUE {name}")
            lines.append("-" * 86)
            cap = "Infinite" if q.capacity_value() == float("inf") else str(int(q.capacity_value()))
            lines.append(f"Servers: {q.servers_value()} | Capacity: {cap}")
            if q.min_arrival is not None and q.max_arrival is not None:
                lines.append(f"External arrivals: {q.min_arrival} .. {q.max_arrival}")
            else:
                lines.append("External arrivals: (none)")
            lines.append(f"Service: {q.min_service} .. {q.max_service}")
            if q.routes:
                lines.append("Routing:")
                acc = 0.0
                for d, p in q.routes.items():
                    acc += p
                    lines.append(f"  -> {d}: {p:.3f}")
                if acc < 1.0:
                    lines.append(f"  -> EXIT: {1 - acc:.3f}")
            else:
                lines.append("Routing: EXIT")

            lines.append("")
            total = sum(q.time_by_state.values())
            if total > 0:
                lines.append("State   Acc. time           Probability")
                lines.append("-" * 50)
                for st in sorted(q.time_by_state.keys()):
                    t = q.time_by_state[st]
                    pr = t / total
                    lines.append(f"{st:>4}     {t:>14.4f}      {pr:>12.4%}")

                L = sum(st * (t / total) for st, t in q.time_by_state.items())
                lines.append("")
                lines.append(f"Losses: {q.lost}")
            else:
                lines.append("No accumulated time.")

            lines.append("")

        lines.append("=" * 86)
        return "\n".join(lines)
