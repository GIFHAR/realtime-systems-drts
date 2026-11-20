from __future__ import annotations

from pathlib import Path
import argparse
import csv

from .analysis import cbs_wcd, schedulability, sp_wcd
from .model import load_test_case
from .simulation import simulate_cbs, simulate_sp


def _merge_max(*results: dict[int, float]) -> dict[int, float]:
    stream_ids = set().union(*(result.keys() for result in results))
    return {
        stream_id: max(result.get(stream_id, 0.0) for result in results)
        for stream_id in stream_ids
    }


def run_case(case_dir: Path) -> list[dict[str, object]]:
    case = load_test_case(case_dir)
    cbs = cbs_wcd(case)
    sp = sp_wcd(case)
    sim_cbs_critical = simulate_cbs(case, release_pattern="critical")
    sim_cbs_staggered = simulate_cbs(case, release_pattern="staggered")
    sim_sp_critical = simulate_sp(case, release_pattern="critical")
    sim_sp_staggered = simulate_sp(case, release_pattern="staggered")
    sim_cbs = _merge_max(sim_cbs_critical, sim_cbs_staggered)
    sim_sp = _merge_max(sim_sp_critical, sim_sp_staggered)
    cbs_ok = schedulability(case, cbs)
    sp_ok = schedulability(case, sp)
    rows: list[dict[str, object]] = []

    avb_streams = [s for s in case.streams if s.pcp in (1, 2)]
    for stream in avb_streams:
        rows.append(
            {
                "case": case.name,
                "stream_id": stream.stream_id,
                "class": stream.avb_class,
                "pcp": stream.pcp,
                "size_bytes": stream.size_bytes,
                "period": stream.period,
                "deadline": stream.deadline,
                "hops": stream.hops,
                "reference_wcrt": case.reference_wcrts.get(stream.stream_id, ""),
                "reference_schedulable": (
                    case.reference_wcrts.get(stream.stream_id, float("inf")) <= stream.deadline
                    if case.reference_wcrts
                    else ""
                ),
                "cbs_wcd": round(cbs[stream.stream_id], 6),
                "cbs_sim_critical_delay": round(sim_cbs_critical.get(stream.stream_id, 0.0), 6),
                "cbs_sim_staggered_delay": round(sim_cbs_staggered.get(stream.stream_id, 0.0), 6),
                "cbs_sim_max_delay": round(sim_cbs.get(stream.stream_id, 0.0), 6),
                "cbs_schedulable": cbs_ok[stream.stream_id],
                "sp_wcd": round(sp[stream.stream_id], 6),
                "sp_sim_critical_delay": round(sim_sp_critical.get(stream.stream_id, 0.0), 6),
                "sp_sim_staggered_delay": round(sim_sp_staggered.get(stream.stream_id, 0.0), 6),
                "sp_sim_max_delay": round(sim_sp.get(stream.stream_id, 0.0), 6),
                "sp_schedulable": sp_ok[stream.stream_id],
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run TSN CBS/SP experiments")
    parser.add_argument("cases", nargs="+", help="Test case folders or parent folders")
    parser.add_argument("--output", default="results_project2/summary.csv")
    args = parser.parse_args()

    case_dirs: list[Path] = []
    for raw in args.cases:
        path = Path(raw)
        if (path / "streams.json").exists():
            case_dirs.append(path)
        else:
            case_dirs.extend(sorted(p for p in path.glob("test_case_*") if (p / "streams.json").exists()))

    rows: list[dict[str, object]] = []
    for case_dir in case_dirs:
        rows.extend(run_case(case_dir))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Analyzed {len(case_dirs)} test case(s), {len(rows)} AVB stream rows.")
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
