from __future__ import annotations

from pathlib import Path
import unittest

from tsn_project2.analysis import cbs_wcd, sp_wcd
from tsn_project2.model import load_test_case, transmission_time_us
from tsn_project2.simulation import simulate_cbs


EXAMPLES = (
    Path("project2_tsn_test_cases/examples")
    if Path("project2_tsn_test_cases/examples").exists()
    else Path("../input/examples")
)
EXAMPLE = EXAMPLES / "test_case_1"


class TestProject2(unittest.TestCase):
    def test_parser_loads_reference_case(self) -> None:
        case = load_test_case(EXAMPLE)
        self.assertEqual(case.bandwidth_mbps, 100)
        self.assertEqual(len(case.streams), 10)
        self.assertIn(0, case.reference_wcrts)
        self.assertTrue(all(link.bandwidth_mbps == 100 for link in case.links))

    def test_routes_use_source_egress_ports(self) -> None:
        case = load_test_case(EXAMPLE)
        stream_zero = next(stream for stream in case.streams if stream.stream_id == 0)
        self.assertEqual(stream_zero.path, ["ES1", "SW1", "ES0"])
        self.assertEqual(stream_zero.link_ids, ["Link5", "Link2"])
        self.assertEqual(stream_zero.hops, 2)

    def test_transmission_time_units(self) -> None:
        self.assertAlmostEqual(transmission_time_us(1000, 100), 80.0)

    def test_analysis_returns_avb_streams_only(self) -> None:
        case = load_test_case(EXAMPLE)
        cbs = cbs_wcd(case)
        sp = sp_wcd(case)
        self.assertEqual(set(cbs), set(range(8)))
        self.assertEqual(set(sp), set(range(8)))

    def test_cbs_simulation_is_below_analytical_bound(self) -> None:
        case = load_test_case(EXAMPLE)
        cbs = cbs_wcd(case)
        for pattern in ("critical", "staggered"):
            sim = simulate_cbs(case, release_pattern=pattern)
            for stream_id, observed in sim.items():
                self.assertLessEqual(observed, cbs[stream_id] + 1e-9, pattern)

    def test_cbs_analysis_matches_reference_wcrts(self) -> None:
        for case_dir in sorted(EXAMPLES.glob("test_case_*")):
            case = load_test_case(case_dir)
            cbs = cbs_wcd(case)
            for stream_id, reference in case.reference_wcrts.items():
                self.assertAlmostEqual(cbs[stream_id], reference, msg=f"{case_dir.name}:{stream_id}")

    def test_reference_schedulability_counts(self) -> None:
        expected = {
            "test_case_1": 8,
            "test_case_2": 2,
            "test_case_3": 8,
        }
        for case_name, schedulable_count in expected.items():
            case = load_test_case(EXAMPLES / case_name)
            avb_streams = [stream for stream in case.streams if stream.pcp in (1, 2)]
            count = sum(
                case.reference_wcrts[stream.stream_id] <= stream.deadline
                for stream in avb_streams
            )
            self.assertEqual(count, schedulable_count, case_name)

    def test_all_reference_examples_stay_below_cbs_bound_in_simulation(self) -> None:
        for case_dir in sorted(EXAMPLES.glob("test_case_*")):
            case = load_test_case(case_dir)
            cbs = cbs_wcd(case)
            for pattern in ("critical", "staggered"):
                sim = simulate_cbs(case, release_pattern=pattern)
                for stream_id, observed in sim.items():
                    self.assertLessEqual(observed, cbs[stream_id] + 1e-9, f"{case_dir.name}:{pattern}")


if __name__ == "__main__":
    unittest.main()
