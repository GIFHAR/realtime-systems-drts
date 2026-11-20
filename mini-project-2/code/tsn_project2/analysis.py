from __future__ import annotations

from math import ceil

from .model import Link, Stream, TestCase, transmission_time_us


IDLE_SLOPE = 0.5


def _tx(stream: Stream, bandwidth_mbps: float) -> float:
    return transmission_time_us(stream.size_bytes, bandwidth_mbps)


def _link_by_hop(test_case: TestCase, source: str, destination: str) -> Link:
    for link in test_case.links:
        if link.source == source and link.destination == destination:
            return link
    raise KeyError(f"No link from {source} to {destination}")


def _link_by_id(test_case: TestCase, link_id: str) -> Link:
    for link in test_case.links:
        if link.link_id == link_id:
            return link
    raise KeyError(f"No link with id {link_id}")


def _links_for_stream(test_case: TestCase, stream: Stream) -> list[Link]:
    return [_link_by_id(test_case, link_id) for link_id in stream.link_ids]


def _streams_on_link(test_case: TestCase, link: Link) -> list[Stream]:
    return [stream for stream in test_case.streams if link.link_id in stream.link_ids]


def _rta_nonpreemptive(stream: Stream, streams: list[Stream], bandwidth_mbps: float) -> float:
    c_i = _tx(stream, bandwidth_mbps)
    higher = [s for s in streams if s.pcp > stream.pcp]
    lower = [s for s in streams if s.pcp < stream.pcp]
    blocking = max((_tx(s, bandwidth_mbps) for s in lower), default=0.0)
    response = c_i + blocking

    for _ in range(1000):
        interference = sum(ceil(response / hp.period) * _tx(hp, bandwidth_mbps) for hp in higher)
        nxt = c_i + blocking + interference
        if abs(nxt - response) < 1e-9:
            return nxt
        if nxt > 1_000_000_000:
            return nxt
        response = nxt
    return response


def sp_wcd(test_case: TestCase) -> dict[int, float]:
    results: dict[int, float] = {}
    for stream in test_case.streams:
        if stream.pcp == 0:
            continue
        total = 0.0
        for link in _links_for_stream(test_case, stream):
            total += _rta_nonpreemptive(stream, _streams_on_link(test_case, link), link.bandwidth_mbps)
        results[stream.stream_id] = total
    return results


def _same_priority_cbs_response(stream: Stream, same_class: list[Stream], bandwidth_mbps: float) -> float:
    shaped_c_i = _tx(stream, bandwidth_mbps) / IDLE_SLOPE
    others = [s for s in same_class if s.stream_id != stream.stream_id]
    response = shaped_c_i
    for _ in range(1000):
        interference = sum(
            ceil(response / other.period) * (_tx(other, bandwidth_mbps) / IDLE_SLOPE)
            for other in others
        )
        nxt = shaped_c_i + interference
        if abs(nxt - response) < 1e-9:
            return nxt
        if nxt > 1_000_000_000:
            return nxt
        response = nxt
    return response


def cbs_conservative_wcd(test_case: TestCase) -> dict[int, float]:
    """Compute a conservative CBS WCD bound for AVB A/B streams.

    The implementation follows the mini-project simplification: two AVB queues
    shaped with idleSlope=0.5 and a BE queue below them. The bound is
    compositional per hop and accounts for same-priority interference,
    lower-priority blocking, and, for class B, higher-priority class A bursts.
    """

    results: dict[int, float] = {}
    avb = [s for s in test_case.streams if s.pcp in (1, 2)]
    class_a = [s for s in test_case.streams if s.pcp == 2]

    for stream in avb:
        same = [s for s in test_case.streams if s.pcp == stream.pcp]
        lower = [s for s in test_case.streams if s.pcp < stream.pcp]
        lpi = max((_tx(s, test_case.bandwidth_mbps) for s in lower), default=0.0)
        spi = _same_priority_cbs_response(stream, same, test_case.bandwidth_mbps)

        hpi = 0.0
        if stream.pcp == 1 and class_a:
            max_a = max(_tx(s, test_case.bandwidth_mbps) for s in class_a)
            hpi = max_a / IDLE_SLOPE

        results[stream.stream_id] = (spi + lpi + hpi) * stream.hops

    return results


def cbs_wcd(test_case: TestCase) -> dict[int, float]:
    """Compute the simplified CBS WCD used for the provided line-topology cases.

    The project examples use a line topology where all streams share the same
    links. Therefore, the same per-hop interference expression can be applied on
    each hop and then multiplied by the route length. With idleSlope=0.5 and
    sendingSlope=-0.5, same-class AVB interference is counted with factor two.
    """

    results: dict[int, float] = {}

    for stream in test_case.streams:
        if stream.pcp not in (1, 2):
            continue

        total = 0.0
        for link in _links_for_stream(test_case, stream):
            link_streams = _streams_on_link(test_case, link)
            class_a = [s for s in link_streams if s.pcp == 2]
            class_b = [s for s in link_streams if s.pcp == 1]
            best_effort = [s for s in link_streams if s.pcp == 0]

            c_i = _tx(stream, link.bandwidth_mbps)
            if stream.pcp == 2:
                same_class = [s for s in class_a if s.stream_id != stream.stream_id]
                spi = sum(_tx(s, link.bandwidth_mbps) / IDLE_SLOPE for s in same_class)
                lpi = max((_tx(s, link.bandwidth_mbps) for s in class_b + best_effort), default=0.0)
                total += c_i + spi + lpi
            else:
                same_class = [s for s in class_b if s.stream_id != stream.stream_id]
                spi = sum(_tx(s, link.bandwidth_mbps) / IDLE_SLOPE for s in same_class)
                hpi = max((_tx(s, link.bandwidth_mbps) for s in class_a), default=0.0)
                lpi = max((_tx(s, link.bandwidth_mbps) for s in best_effort), default=0.0)
                total += c_i + spi + hpi + 2 * lpi

        results[stream.stream_id] = total

    return results


def schedulability(test_case: TestCase, delays: dict[int, float]) -> dict[int, bool]:
    by_id = {s.stream_id: s for s in test_case.streams}
    return {
        stream_id: delay <= by_id[stream_id].deadline
        for stream_id, delay in delays.items()
    }
