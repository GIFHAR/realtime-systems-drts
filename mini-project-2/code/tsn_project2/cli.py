from __future__ import annotations

import argparse

from .analysis import cbs_wcd, sp_wcd
from .model import load_test_case
from .simulation import simulate_cbs, simulate_sp


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze one TSN test case")
    parser.add_argument("case_dir")
    parser.add_argument(
        "--release-pattern",
        choices=("critical", "staggered"),
        default="critical",
        help="Simulation release pattern. Critical releases all streams at t=0.",
    )
    args = parser.parse_args()

    case = load_test_case(args.case_dir)
    cbs = cbs_wcd(case)
    sp = sp_wcd(case)
    sim_cbs = simulate_cbs(case, release_pattern=args.release_pattern)
    sim_sp = simulate_sp(case, release_pattern=args.release_pattern)

    print(f"Test case: {case.name}")
    print(f"Bandwidth: {case.bandwidth_mbps} Mbps")
    print(f"Simulation releases: {args.release_pattern}")
    print()
    print("ID  Class  D       CBS_WCD  CBS_sim  SP_WCD   SP_sim   Reference")
    print("--  -----  ------  -------  -------  -------  -------  ---------")
    for stream in case.streams:
        if stream.pcp not in (1, 2):
            continue
        print(
            f"{stream.stream_id:<3} {stream.avb_class:<5} "
            f"{stream.deadline:<7.1f} {cbs[stream.stream_id]:<8.2f} "
            f"{sim_cbs.get(stream.stream_id, 0.0):<8.2f} "
            f"{sp[stream.stream_id]:<8.2f} {sim_sp.get(stream.stream_id, 0.0):<8.2f} "
            f"{case.reference_wcrts.get(stream.stream_id, '')}"
        )


if __name__ == "__main__":
    main()
