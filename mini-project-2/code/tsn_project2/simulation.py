from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count
from math import inf

from .model import Link, Stream, TestCase, lcm_int, transmission_time_us


EPSILON = 1e-9
IDLE_SLOPE = 0.5


@dataclass
class Frame:
    stream: Stream
    frame_id: int
    release: float
    hop_index: int = 0
    start: float | None = None


@dataclass
class Port:
    link: Link
    queues: dict[int, list[Frame]] = field(default_factory=lambda: {2: [], 1: [], 0: []})
    credit: dict[int, float] = field(default_factory=lambda: {2: 0.0, 1: 0.0})
    current: Frame | None = None
    current_pcp: int | None = None
    credit_ready_time: float | None = None

    def update_credit(self, duration: float, use_cbs: bool) -> None:
        if not use_cbs or duration <= 0:
            return

        for pcp in (2, 1):
            if self.current_pcp == pcp:
                self.credit[pcp] -= IDLE_SLOPE * duration
            elif self.queues[pcp] or self.credit[pcp] < 0:
                self.credit[pcp] += IDLE_SLOPE * duration
                if not self.queues[pcp] and self.credit[pcp] > 0:
                    self.credit[pcp] = 0.0
            elif self.credit[pcp] > 0:
                self.credit[pcp] = 0.0

            if abs(self.credit[pcp]) <= EPSILON:
                self.credit[pcp] = 0.0

    def can_send(self, pcp: int, use_cbs: bool) -> bool:
        if not self.queues[pcp]:
            return False
        if not use_cbs or pcp == 0:
            return True
        return self.credit[pcp] >= -EPSILON

    def select_frame(self, use_cbs: bool) -> Frame | None:
        for pcp in (2, 1, 0):
            if self.can_send(pcp, use_cbs):
                self.current_pcp = pcp
                self.current = self.queues[pcp].pop(0)
                return self.current
        return None

    def next_credit_ready(self, now: float) -> float | None:
        candidates = []
        for pcp in (2, 1):
            if self.queues[pcp] and self.credit[pcp] < -EPSILON:
                candidates.append(now + (-self.credit[pcp] / IDLE_SLOPE))
        return min(candidates) if candidates else None

    def finish_current(self) -> Frame | None:
        frame = self.current
        self.current = None
        self.current_pcp = None
        self.credit_ready_time = None
        return frame


class NetworkSimulator:
    def __init__(
        self,
        test_case: TestCase,
        policy: str,
        horizon: int | None = None,
        release_pattern: str = "critical",
    ):
        self.test_case = test_case
        self.policy = policy
        self.use_cbs = policy == "cbs"
        self.end_time = float(horizon or _horizon(test_case))
        self.release_pattern = release_pattern
        self.ports = {link.link_id: Port(link) for link in test_case.links}
        self.link_by_id = {link.link_id: link for link in test_case.links}
        self.events: list[tuple[float, int, str, str | None, Frame | None]] = []
        self.counter = count()
        self.time = 0.0
        self.observed: dict[int, float] = {}

    def run(self) -> dict[int, float]:
        self._generate_releases()
        last_time = 0.0

        while self.events:
            time, _, kind, link_id, frame = heappop(self.events)
            if time > self.end_time + EPSILON:
                break

            elapsed = time - last_time
            for port in self.ports.values():
                port.update_credit(elapsed, self.use_cbs)
            last_time = time
            self.time = time

            if kind == "release" and frame is not None:
                self._enqueue_on_hop(frame, 0)
            elif kind == "tx_end" and link_id is not None:
                self._finish_transmission(link_id)
            elif kind == "credit_ready" and link_id is not None:
                self._try_start(link_id)

        return {
            stream_id: delay
            for stream_id, delay in self.observed.items()
            if _stream_by_id(self.test_case, stream_id).pcp in (1, 2)
        }

    def _schedule(self, time: float, kind: str, link_id: str | None = None, frame: Frame | None = None) -> None:
        heappush(self.events, (time, next(self.counter), kind, link_id, frame))

    def _generate_releases(self) -> None:
        for stream in self.test_case.streams:
            if self.release_pattern == "critical":
                release = 0.0
            elif self.release_pattern == "staggered":
                release = (stream.stream_id % 4) * stream.period / 4.0
            else:
                raise ValueError(f"Unknown release pattern: {self.release_pattern}")
            frame_id = 0
            while release < self.end_time:
                self._schedule(release, "release", frame=Frame(stream, frame_id, release))
                release += stream.period
                frame_id += 1

    def _enqueue_on_hop(self, frame: Frame, hop_index: int) -> None:
        frame.hop_index = hop_index
        link = self._link_for_frame(frame)
        self.ports[link.link_id].queues[frame.stream.pcp].append(frame)
        self._try_start(link.link_id)

    def _try_start(self, link_id: str) -> None:
        port = self.ports[link_id]
        if port.current is not None:
            return

        frame = port.select_frame(self.use_cbs)
        if frame is None:
            self._schedule_credit_ready(link_id)
            return

        port.credit_ready_time = None
        frame.start = self.time
        duration = transmission_time_us(frame.stream.size_bytes, port.link.bandwidth_mbps)
        self._schedule(self.time + duration, "tx_end", link_id=link_id)

    def _finish_transmission(self, link_id: str) -> None:
        port = self.ports[link_id]
        frame = port.finish_current()
        if frame is None:
            return

        self._try_start(link_id)

        next_hop = frame.hop_index + 1
        if next_hop >= len(frame.stream.link_ids):
            response_time = self.time - frame.release
            stream_id = frame.stream.stream_id
            self.observed[stream_id] = max(self.observed.get(stream_id, 0.0), response_time)
            return

        self._enqueue_on_hop(frame, next_hop)

    def _schedule_credit_ready(self, link_id: str) -> None:
        if not self.use_cbs:
            return

        port = self.ports[link_id]
        if port.current is not None or any(port.can_send(pcp, self.use_cbs) for pcp in (2, 1, 0)):
            port.credit_ready_time = None
            return

        ready = port.next_credit_ready(self.time)
        if ready is None or ready is inf:
            port.credit_ready_time = None
            return
        if port.credit_ready_time is not None and abs(port.credit_ready_time - ready) <= EPSILON:
            return

        port.credit_ready_time = ready
        self._schedule(ready, "credit_ready", link_id=link_id)

    def _link_for_frame(self, frame: Frame) -> Link:
        try:
            return self.link_by_id[frame.stream.link_ids[frame.hop_index]]
        except KeyError as exc:
            raise KeyError(f"No link for stream {frame.stream.stream_id} hop {frame.hop_index}") from exc


def _horizon(test_case: TestCase, max_hyperperiod: int = 20000, minimum_hyperperiods: int = 3) -> int:
    periods = [int(s.period) for s in test_case.streams]
    hp = lcm_int(periods)
    return min(hp * minimum_hyperperiods, max_hyperperiod)


def simulate_sp(
    test_case: TestCase,
    horizon: int | None = None,
    release_pattern: str = "critical",
) -> dict[int, float]:
    return NetworkSimulator(test_case, "sp", horizon, release_pattern).run()


def simulate_cbs(
    test_case: TestCase,
    horizon: int | None = None,
    release_pattern: str = "critical",
) -> dict[int, float]:
    return NetworkSimulator(test_case, "cbs", horizon, release_pattern).run()


def _stream_by_id(test_case: TestCase, stream_id: int) -> Stream:
    for stream in test_case.streams:
        if stream.stream_id == stream_id:
            return stream
    raise KeyError(stream_id)
