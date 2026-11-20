# Real-Time Systems (DTU 02225 DRTS)

Two analysis tools I built for DTU's *Distributed Real-Time Systems* course, kept
together because they're the same idea applied at two layers: compute a
worst-case timing bound, then validate it against a simulation.

Both are plain Python (standard library), both come with regression tests, and
both were checked against the course's public GitHub validation cases.

| Project | What it analyses | Package |
|---------|------------------|---------|
| [mini-project-1](mini-project-1/) | CPU task scheduling: RM, DM, EDF schedulability | `drts_scheduler` |
| [mini-project-2](mini-project-2/) | TSN network delay: Credit-Based Shaping vs Strict Priority | `tsn_project2` |

---

## Mini-project 1 - Task scheduling analyzer

Given a set of periodic tasks `(C, T, D)`, decide whether they're schedulable and
compute each task's worst-case response time (WCRT).

- **Fixed priority (RM / DM)** uses exact **response-time analysis** - the
  fixed-point recurrence `R = C_i + Σ ⌈R / T_j⌉·C_j` over higher-priority tasks,
  not just a utilization bound. RM orders by period, DM by deadline.
- **EDF** uses the utilization test for implicit deadlines and a hyperperiod check.
- A **simulation** module cross-checks the analytical verdict by actually running
  the schedule, so a "schedulable" result is backed by a simulated run, not only a
  formula.
- An **experiment runner** batches a whole folder of task sets into one CSV summary.

```bash
cd mini-project-1/code
PYTHONPATH=. python3 -m unittest tests_project1.py
PYTHONPATH=. python3 -m drts_scheduler.cli ../input/data/example_basic.csv --policy dm
PYTHONPATH=. python3 -m drts_scheduler.experiment ../input/data --output ../output/results/local_summary.csv
```

Validation: run against the `github_schedulable_subset` and `not_schedulable`
task sets under `input/`; the tool's verdicts match the expected classification.

## Mini-project 2 - TSN delay analyzer

Given a network topology, a set of AVB streams, and their routes, compute the
worst-case end-to-end delay for each stream and compare two shaping policies.

- **Credit-Based Shaping (CBS)** worst-case delay is computed **link by link**:
  per-hop transmission time, interference from higher-priority streams, blocking
  from a lower-priority frame already in transmission (non-preemptive), and the
  CBS idle-slope credit behaviour, accumulated along the route.
- **Strict Priority (SP)** is computed as a baseline so you can see what CBS buys
  you.
- A **discrete-event simulation** replays the streams under **critical-instant**
  and **staggered** release patterns to bound-check the analytical numbers.

```bash
cd mini-project-2/code
PYTHONPATH=. python3 -m unittest tests_project2.py
PYTHONPATH=. python3 -m tsn_project2.cli ../input/examples/test_case_1
PYTHONPATH=. python3 -m tsn_project2.experiment ../input/examples --output ../output/results_project2/github_examples_summary.csv
```

Input is the standard TSN format: `topology.json`, `streams.json`, `routes.json`,
with `WCRTs.csv` giving the reference delays each test case is checked against.

---

## Why these two together

Scheduling on a CPU and shaping on a TSN link are the same timing problem seen
twice: bound the worst case analytically, then prove the bound holds by
simulation. Keeping both in one repo makes that parallel explicit - the response-time
recurrence in project 1 and the link-aware CBS analysis in project 2 are the same
fixed-point idea, one over tasks sharing a core, the other over frames sharing a
link.

## Tests

```bash
# from each mini-project's code/ directory
PYTHONPATH=. python3 -m unittest discover
```

12 regression tests across the two projects (4 + 8), all passing.

## Note

Coursework for DTU 02225. Published as a portfolio sample of my own implementation.
The input task sets and TSN cases are the course's public validation data.
