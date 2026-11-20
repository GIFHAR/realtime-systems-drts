from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import json
import math


BITS_PER_BYTE = 8


@dataclass(frozen=True)
class Link:
    link_id: str
    source: str
    destination: str
    source_port: int | None
    destination_port: int | None
    bandwidth_mbps: float
    delay_us: float


@dataclass(frozen=True)
class Stream:
    stream_id: int
    name: str
    source: str
    destination: str
    pcp: int
    size_bytes: float
    period: float
    deadline: float
    path: list[str]
    link_ids: list[str]

    @property
    def avb_class(self) -> str:
        if self.pcp == 2:
            return "A"
        if self.pcp == 1:
            return "B"
        return "BE"

    @property
    def hops(self) -> int:
        return len(self.link_ids)


@dataclass(frozen=True)
class TestCase:
    name: str
    bandwidth_mbps: float
    links: list[Link]
    streams: list[Stream]
    reference_wcrts: dict[int, float]


def transmission_time_us(size_bytes: float, bandwidth_mbps: float) -> float:
    return size_bytes * BITS_PER_BYTE / bandwidth_mbps


def lcm_int(values: list[int]) -> int:
    result = 1
    for value in values:
        result = result * value // math.gcd(result, value)
    return result


def _resolve_route_links(route_hops: list[dict[str, object]], links: list[Link]) -> list[str]:
    by_egress_port = {
        (link.source, link.source_port): link
        for link in links
        if link.source_port is not None
    }
    by_node_pair = {(link.source, link.destination): link for link in links}
    resolved: list[str] = []

    for index, hop in enumerate(route_hops[:-1]):
        source = str(hop["node"])
        source_port = int(hop.get("port", 0))
        next_node = str(route_hops[index + 1]["node"])

        link = by_egress_port.get((source, source_port))
        if link is None:
            link = by_node_pair.get((source, next_node))
        if link is None or link.destination != next_node:
            raise ValueError(
                f"Cannot map route hop {source}:port{source_port} to next node {next_node}"
            )
        resolved.append(link.link_id)

    return resolved


def load_test_case(path: str | Path) -> TestCase:
    case_dir = Path(path)
    topology = json.loads((case_dir / "topology.json").read_text(encoding="utf-8"))["topology"]
    streams_data = json.loads((case_dir / "streams.json").read_text(encoding="utf-8"))["streams"]
    routes_data = json.loads((case_dir / "routes.json").read_text(encoding="utf-8"))["routes"]

    bandwidth = float(topology.get("default_bandwidth_mbps", 100))
    links = [
        Link(
            link_id=str(link["id"]),
            source=link["source"],
            destination=link["destination"],
            source_port=int(link["sourcePort"]) if "sourcePort" in link else None,
            destination_port=int(link["destinationPort"]) if "destinationPort" in link else None,
            bandwidth_mbps=float(link.get("bandwidth_mbps", bandwidth)),
            delay_us=float(link.get("delay", 0.0)),
        )
        for link in topology["links"]
    ]
    routes = {
        int(route["flow_id"]): route["paths"][0]
        for route in routes_data
    }

    streams: list[Stream] = []
    for raw in streams_data:
        destination = raw["destinations"][0]
        route_hops = routes.get(
            int(raw["id"]),
            [{"node": raw["source"], "port": 0}, {"node": destination["id"], "port": 0}],
        )
        path = [str(hop["node"]) for hop in route_hops]
        link_ids = _resolve_route_links(route_hops, links)
        streams.append(
            Stream(
                stream_id=int(raw["id"]),
                name=raw.get("name", f"Stream{raw['id']}"),
                source=raw["source"],
                destination=destination["id"],
                pcp=int(raw["PCP"]),
                size_bytes=float(raw["size"]),
                period=float(raw["period"]),
                deadline=float(destination["deadline"]),
                path=path,
                link_ids=link_ids,
            )
        )

    reference_wcrts: dict[int, float] = {}
    reference_path = case_dir / "WCRTs.csv"
    if reference_path.exists():
        with reference_path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file, delimiter="\t")
            for row in reader:
                reference_wcrts[int(row["ID"])] = float(row["WCRT"])

    return TestCase(
        name=case_dir.name,
        bandwidth_mbps=bandwidth,
        links=links,
        streams=streams,
        reference_wcrts=reference_wcrts,
    )
