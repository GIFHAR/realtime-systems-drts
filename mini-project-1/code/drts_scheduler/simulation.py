from __future__ import annotations

from dataclasses import dataclass
from random import Random
from statistics import mean
from typing import Callable

from .model import Task, priority_order


@dataclass
class Job:
    task_id: str
    release_time: int
    absolute_deadline: int
    execution_time: int
    remaining_time: int
    finish_time: int | None = None

    @property
    def response_time(self) -> int | None:
        if self.finish_time is None:
            return None
        return self.finish_time - self.release_time


@dataclass(frozen=True)
class ScheduleSlot:
    start: int
    end: int
    task_id: str


@dataclass(frozen=True)
class SimulationResult:
    schedule: list[ScheduleSlot]
    jobs: list[Job]

    def observed_response_times(self) -> dict[str, int]:
        response_times: dict[str, int] = {}
        for job in self.jobs:
            if job.response_time is None:
                continue
            response_times[job.task_id] = max(
                response_times.get(job.task_id, 0),
                job.response_time,
            )
        return response_times

    def response_time_stats(self) -> dict[str, dict[str, float]]:
        grouped: dict[str, list[int]] = {}
        for job in self.jobs:
            if job.response_time is None:
                continue
            grouped.setdefault(job.task_id, []).append(job.response_time)

        return {
            task_id: {
                "jobs": len(values),
                "avg": mean(values),
                "max": max(values),
            }
            for task_id, values in grouped.items()
        }

    def deadline_misses(self) -> list[Job]:
        return [
            job
            for job in self.jobs
            if job.finish_time is None or job.finish_time > job.absolute_deadline
        ]


def simulate_fixed_priority(
    tasks: list[Task],
    policy: str,
    end_time: int,
) -> SimulationResult:
    ordered_tasks = priority_order(tasks, policy)
    priorities = {task.task_id: index for index, task in enumerate(ordered_tasks)}
    return _simulate(
        tasks,
        end_time,
        execution_time=lambda task: task.wcet,
        key=lambda job: (priorities[job.task_id], job.release_time),
    )


def simulate_edf(tasks: list[Task], end_time: int) -> SimulationResult:
    return _simulate(
        tasks,
        end_time,
        execution_time=lambda task: task.wcet,
        key=lambda job: (job.absolute_deadline, job.release_time, job.task_id),
    )


def simulate_fixed_priority_stochastic(
    tasks: list[Task],
    policy: str,
    end_time: int,
    seed: int = 1,
) -> SimulationResult:
    rng = Random(seed)
    ordered_tasks = priority_order(tasks, policy)
    priorities = {task.task_id: index for index, task in enumerate(ordered_tasks)}
    return _simulate(
        tasks,
        end_time,
        execution_time=lambda task: rng.randint(task.bcet, task.wcet),
        key=lambda job: (priorities[job.task_id], job.release_time),
    )


def simulate_edf_stochastic(tasks: list[Task], end_time: int, seed: int = 1) -> SimulationResult:
    rng = Random(seed)
    return _simulate(
        tasks,
        end_time,
        execution_time=lambda task: rng.randint(task.bcet, task.wcet),
        key=lambda job: (job.absolute_deadline, job.release_time, job.task_id),
    )


def _simulate(
    tasks: list[Task],
    end_time: int,
    execution_time: Callable[[Task], int],
    key,
) -> SimulationResult:
    jobs: list[Job] = []
    ready: list[Job] = []
    schedule: list[ScheduleSlot] = []

    tasks_by_period = sorted(tasks, key=lambda task: (task.period, task.task_id))

    for time in range(end_time):
        for task in tasks_by_period:
            if time % task.period == 0:
                duration = execution_time(task)
                job = Job(
                    task_id=task.task_id,
                    release_time=time,
                    absolute_deadline=time + task.deadline,
                    execution_time=duration,
                    remaining_time=duration,
                )
                jobs.append(job)
                ready.append(job)

        ready = [job for job in ready if job.remaining_time > 0]

        if ready:
            current = min(ready, key=key)
            current.remaining_time -= 1
            if current.remaining_time == 0:
                current.finish_time = time + 1
            _append_slot(schedule, time, time + 1, current.task_id)
        else:
            _append_slot(schedule, time, time + 1, "IDLE")

    return SimulationResult(schedule=schedule, jobs=jobs)


def _append_slot(schedule: list[ScheduleSlot], start: int, end: int, task_id: str) -> None:
    if schedule and schedule[-1].end == start and schedule[-1].task_id == task_id:
        previous = schedule[-1]
        schedule[-1] = ScheduleSlot(previous.start, end, task_id)
    else:
        schedule.append(ScheduleSlot(start, end, task_id))
