from __future__ import annotations

from pathlib import Path
import unittest

from drts_scheduler.analysis import edf_hyperperiod_wcrt, fixed_priority_wcrt, is_schedulable
from drts_scheduler.experiment import analyze_taskset
from drts_scheduler.model import hyperperiod, load_tasks_csv, total_utilization
from drts_scheduler.simulation import simulate_edf, simulate_edf_stochastic, simulate_fixed_priority


DATA_DIR = Path("data") if Path("data/example_basic.csv").exists() else Path("../input/data")
GITHUB_NOT_SCHEDULABLE = (
    Path("project_drts/test_examples/not_schedulable")
    if Path("project_drts/test_examples/not_schedulable").exists()
    else Path("../input/not_schedulable")
)
BASIC = DATA_DIR / "example_basic.csv"
EDF_BEATS_RM = DATA_DIR / "edf_beats_rm.csv"


class TestProject1(unittest.TestCase):
    def test_basic_taskset_analysis_matches_simulation(self) -> None:
        tasks = load_tasks_csv(BASIC)
        self.assertEqual(hyperperiod(tasks), 20)
        self.assertAlmostEqual(total_utilization(tasks), 0.75)

        analytical = fixed_priority_wcrt(tasks, "dm")
        simulated = simulate_fixed_priority(tasks, "dm", hyperperiod(tasks))

        self.assertTrue(is_schedulable(tasks, analytical))
        self.assertEqual(analytical, simulated.observed_response_times())
        self.assertEqual(simulated.deadline_misses(), [])

    def test_edf_succeeds_where_rm_fails(self) -> None:
        tasks = load_tasks_csv(EDF_BEATS_RM)

        rm_wcrt = fixed_priority_wcrt(tasks, "rm")
        edf_wcrt = edf_hyperperiod_wcrt(tasks)
        edf_sim = simulate_edf(tasks, hyperperiod(tasks))

        self.assertFalse(is_schedulable(tasks, rm_wcrt))
        self.assertTrue(is_schedulable(tasks, edf_wcrt))
        self.assertEqual(edf_sim.deadline_misses(), [])

    def test_stochastic_simulation_reports_average_response_times(self) -> None:
        tasks = load_tasks_csv(EDF_BEATS_RM)
        simulation = simulate_edf_stochastic(tasks, hyperperiod(tasks) * 3, seed=7)
        stats = simulation.response_time_stats()

        self.assertEqual(set(stats), {"T1", "T2", "T3"})
        self.assertLessEqual(stats["T3"]["max"], 12)
        self.assertLessEqual(stats["T3"]["avg"], stats["T3"]["max"])

    def test_github_not_schedulable_expectations(self) -> None:
        rows = {
            (path.name, policy): analyze_taskset(path, policy)
            for path in sorted(GITHUB_NOT_SCHEDULABLE.glob("*.csv"))
            for policy in ("rm", "edf")
        }

        for (name, policy), row in rows.items():
            if policy == "rm":
                self.assertFalse(row["analytical_schedulable"], name)

        exception = "Unschedulable_Full_Utilization_NonUnique_Periods_taskset.csv"
        for (name, policy), row in rows.items():
            if policy == "edf" and name != exception:
                self.assertTrue(row["analytical_schedulable"], name)
            if policy == "edf" and name == exception:
                self.assertFalse(row["analytical_schedulable"], name)


if __name__ == "__main__":
    unittest.main()
