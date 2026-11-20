from __future__ import annotations

from math import ceil

from .model import Task, hyperperiod, priority_order
from .simulation import simulate_edf


def fixed_priority_wcrt(tasks: list[Task], policy: str = "dm") -> dict[str, int | None]:
    ordered_tasks = priority_order(tasks, policy)
    response_times: dict[str, int | None] = {}

    for index, task in enumerate(ordered_tasks):
        higher_priority_tasks = ordered_tasks[:index]
        response_time = task.wcet

        while True:
            interference = sum(
                ceil(response_time / hp_task.period) * hp_task.wcet
                for hp_task in higher_priority_tasks
            )
            next_response_time = task.wcet + interference

            if next_response_time == response_time:
                response_times[task.task_id] = response_time
                break

            if next_response_time > task.deadline:
                response_times[task.task_id] = None
                break

            response_time = next_response_time

    return response_times


def is_schedulable(tasks: list[Task], response_times: dict[str, int | None]) -> bool:
    by_id = {task.task_id: task for task in tasks}
    return all(
        response_time is not None and response_time <= by_id[task_id].deadline
        for task_id, response_time in response_times.items()
    )


def edf_hyperperiod_wcrt(tasks: list[Task]) -> dict[str, int | None]:
    end_time = hyperperiod(tasks)
    simulation = simulate_edf(tasks, end_time)
    response_times: dict[str, int | None] = {task.task_id: 0 for task in tasks}

    for job in simulation.jobs:
        if job.response_time is None or job.finish_time is None:
            response_times[job.task_id] = None
            continue
        current = response_times[job.task_id]
        if current is not None:
            response_times[job.task_id] = max(current, job.response_time)

    for job in simulation.deadline_misses():
        response_times[job.task_id] = None

    return response_times
