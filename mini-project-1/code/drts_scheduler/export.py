from __future__ import annotations

from pathlib import Path
import csv

from .model import Task


def write_result_csv(
    path: str | Path,
    tasks: list[Task],
    analytical_response_times: dict[str, int | None],
    observed_response_times: dict[str, int],
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "task_id",
                "wcet",
                "bcet",
                "period",
                "deadline",
                "analytical_wcrt",
                "observed_max_response_time",
                "schedulable",
            ],
        )
        writer.writeheader()
        for task in tasks:
            analytical = analytical_response_times.get(task.task_id)
            writer.writerow(
                {
                    "task_id": task.task_id,
                    "wcet": task.wcet,
                    "bcet": task.bcet,
                    "period": task.period,
                    "deadline": task.deadline,
                    "analytical_wcrt": "" if analytical is None else analytical,
                    "observed_max_response_time": observed_response_times.get(task.task_id, ""),
                    "schedulable": analytical is not None and analytical <= task.deadline,
                }
            )
