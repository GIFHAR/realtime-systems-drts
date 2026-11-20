from __future__ import annotations

import argparse

from .analysis import edf_hyperperiod_wcrt, fixed_priority_wcrt, is_schedulable
from .export import write_result_csv
from .model import hyperperiod, load_tasks_csv, priority_order, total_utilization
from .simulation import (
    simulate_edf,
    simulate_edf_stochastic,
    simulate_fixed_priority,
    simulate_fixed_priority_stochastic,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="DRTS Mini-project 1 scheduler tool")
    parser.add_argument("taskset", help="Path to task set CSV")
    parser.add_argument(
        "--policy",
        choices=["dm", "rm", "edf"],
        default="dm",
        help="Scheduling policy",
    )
    parser.add_argument(
        "--max-slots",
        type=int,
        default=40,
        help="Maximum number of schedule slots to print",
    )
    parser.add_argument("--output", help="Optional CSV path for saving result table")
    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="Also run a BCET/WCET stochastic simulation with a deterministic seed",
    )
    parser.add_argument("--seed", type=int, default=1, help="Seed for stochastic simulation")
    parser.add_argument(
        "--stochastic-hyperperiods",
        type=int,
        default=3,
        help="Number of hyperperiods for stochastic simulation",
    )
    args = parser.parse_args()

    tasks = load_tasks_csv(args.taskset)

    print("Task set")
    print("--------")
    for task in tasks:
        print(
            f"{task.task_id}: C={task.wcet}, BCET={task.bcet}, "
            f"T={task.period}, D={task.deadline}, U={task.utilization:.3f}"
        )

    print()
    print(f"Total utilization: {total_utilization(tasks):.3f}")
    print(f"Hyperperiod: {hyperperiod(tasks)}")

    end_time = hyperperiod(tasks)
    if args.policy in {"dm", "rm"}:
        print()
        print(f"{args.policy.upper()} priority order")
        print("-----------------")
        print(" > ".join(task.task_id for task in priority_order(tasks, args.policy)))

        response_times = fixed_priority_wcrt(tasks, args.policy)
        print()
        print(f"{args.policy.upper()} analytical WCRT")
        print("-------------------")
        for task in tasks:
            response_time = response_times[task.task_id]
            status = "MISS" if response_time is None else "OK"
            shown_response_time = ">" + str(task.deadline) if response_time is None else str(response_time)
            print(f"{task.task_id}: WCRT={shown_response_time}, D={task.deadline}, {status}")
        print(f"Schedulable: {is_schedulable(tasks, response_times)}")
        simulation = simulate_fixed_priority(tasks, args.policy, end_time)
    else:
        response_times = edf_hyperperiod_wcrt(tasks)
        print()
        print("EDF analytical WCRT")
        print("-------------------")
        for task in tasks:
            response_time = response_times[task.task_id]
            status = "MISS" if response_time is None else "OK"
            shown_response_time = ">" + str(task.deadline) if response_time is None else str(response_time)
            print(f"{task.task_id}: WCRT={shown_response_time}, D={task.deadline}, {status}")
        print(f"Schedulable: {is_schedulable(tasks, response_times)}")
        simulation = simulate_edf(tasks, end_time)

    print()
    print(f"{args.policy.upper()} simulation over [0, {end_time})")
    print("--------------------------------")
    shown_slots = simulation.schedule[: args.max_slots]
    for slot in shown_slots:
        print(f"[{slot.start:>2}, {slot.end:>2}) {slot.task_id}")
    if len(simulation.schedule) > len(shown_slots):
        remaining = len(simulation.schedule) - len(shown_slots)
        print(f"... {remaining} more slots omitted")

    print()
    print("Observed response times")
    print("-----------------------")
    observed = simulation.observed_response_times()
    for task in tasks:
        print(f"{task.task_id}: max observed R={observed.get(task.task_id, 0)}, D={task.deadline}")
    print(f"Deadline misses: {len(simulation.deadline_misses())}")

    if args.stochastic:
        stochastic_end = end_time * args.stochastic_hyperperiods
        if args.policy == "edf":
            stochastic = simulate_edf_stochastic(tasks, stochastic_end, seed=args.seed)
        else:
            stochastic = simulate_fixed_priority_stochastic(tasks, args.policy, stochastic_end, seed=args.seed)

        print()
        print(f"Stochastic {args.policy.upper()} simulation over [0, {stochastic_end})")
        print("------------------------------------------------")
        print("Task  jobs  avg_R  max_R  deadline")
        stats = stochastic.response_time_stats()
        for task in tasks:
            task_stats = stats.get(task.task_id, {"jobs": 0, "avg": 0.0, "max": 0.0})
            print(
                f"{task.task_id:<5} {int(task_stats['jobs']):<5} "
                f"{task_stats['avg']:<6.2f} {task_stats['max']:<6.2f} {task.deadline}"
            )
        print(f"Stochastic deadline misses: {len(stochastic.deadline_misses())}")

    if args.output:
        write_result_csv(args.output, tasks, response_times, observed)
        print()
        print(f"Saved result CSV: {args.output}")


if __name__ == "__main__":
    main()
