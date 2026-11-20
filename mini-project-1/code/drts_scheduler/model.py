from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from pathlib import Path
import csv


@dataclass(frozen=True)
class Task:
    task_id: str
    wcet: int
    bcet: int
    period: int
    deadline: int

    @property
    def utilization(self) -> float:
        return self.wcet / self.period


def lcm(a: int, b: int) -> int:
    return abs(a * b) // gcd(a, b)


def hyperperiod(tasks: list[Task]) -> int:
    result = 1
    for task in tasks:
        result = lcm(result, task.period)
    return result


def total_utilization(tasks: list[Task]) -> float:
    return sum(task.utilization for task in tasks)


def priority_order(tasks: list[Task], policy: str) -> list[Task]:
    if policy == "dm":
        return sorted(tasks, key=lambda task: (task.deadline, task.period, task.task_id))
    if policy == "rm":
        return sorted(tasks, key=lambda task: (task.period, task.deadline, task.task_id))
    raise ValueError(f"Unsupported fixed-priority policy: {policy}")


def load_tasks_csv(path: str | Path) -> list[Task]:
    tasks: list[Task] = []
    with Path(path).open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            normalized = {key.lower(): value for key, value in row.items()}
            task = Task(
                task_id=normalized.get("task_id") or normalized["task"],
                wcet=int(normalized["wcet"]),
                bcet=int(normalized["bcet"]),
                period=int(normalized["period"]),
                deadline=int(normalized["deadline"]),
            )
            if task.deadline > task.period:
                raise ValueError(f"{task.task_id}: deadline must be <= period")
            if task.bcet > task.wcet:
                raise ValueError(f"{task.task_id}: bcet must be <= wcet")
            tasks.append(task)
    return tasks
