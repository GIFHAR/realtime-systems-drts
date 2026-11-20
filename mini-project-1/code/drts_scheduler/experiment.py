from __future__ import annotations

from pathlib import Path
import argparse
import csv

from .analysis import edf_hyperperiod_wcrt, fixed_priority_wcrt, is_schedulable
from .model import hyperperiod, load_tasks_csv, total_utilization
from .simulation import (
    simulate_edf,
    simulate_edf_stochastic,
    simulate_fixed_priority,
    simulate_fixed_priority_stochastic,
)


def analyze_taskset(path: Path, policy: str) -> dict[str, object]:
    tasks = load_tasks_csv(path)
    end_time = hyperperiod(tasks)
    if policy == "edf":
        analytical = edf_hyperperiod_wcrt(tasks)
        simulation = simulate_edf(tasks, end_time)
        stochastic = simulate_edf_stochastic(tasks, end_time * 3, seed=1)
    else:
        analytical = fixed_priority_wcrt(tasks, policy)
        simulation = simulate_fixed_priority(tasks, policy, end_time)
        stochastic = simulate_fixed_priority_stochastic(tasks, policy, end_time * 3, seed=1)

    stochastic_max = stochastic.observed_response_times()
    stochastic_stats = stochastic.response_time_stats()
    max_stochastic_rt = max(stochastic_max.values(), default=0)
    avg_stochastic_rt = max((stats["avg"] for stats in stochastic_stats.values()), default=0.0)

    return {
        "taskset": path.name,
        "policy": policy.upper(),
        "tasks": len(tasks),
        "utilization": f"{total_utilization(tasks):.6f}",
        "hyperperiod": end_time,
        "analytical_schedulable": is_schedulable(tasks, analytical),
        "simulation_deadline_misses": len(simulation.deadline_misses()),
        "simulation_schedulable": len(simulation.deadline_misses()) == 0,
        "stochastic_max_rt": f"{max_stochastic_rt:.3f}",
        "stochastic_worst_avg_rt": f"{avg_stochastic_rt:.3f}",
        "stochastic_deadline_misses": len(stochastic.deadline_misses()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run scheduling experiments on task set CSV files")
    parser.add_argument("inputs", nargs="+", help="Task set CSV files or folders")
    parser.add_argument("--output", default="results/summary.csv", help="Output summary CSV path")
    parser.add_argument("--policies", nargs="+", choices=["rm", "dm", "edf"], default=["rm", "dm", "edf"])
    args = parser.parse_args()

    taskset_paths: list[Path] = []
    for raw_input in args.inputs:
        path = Path(raw_input)
        if path.is_dir():
            taskset_paths.extend(sorted(path.glob("*.csv")))
        else:
            taskset_paths.append(path)

    rows = []
    for taskset_path in taskset_paths:
        for policy in args.policies:
            rows.append(analyze_taskset(taskset_path, policy))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Analyzed {len(taskset_paths)} task set(s) with {len(args.policies)} policy/policies.")
    print(f"Saved summary: {output_path}")


if __name__ == "__main__":
    main()
