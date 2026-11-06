"""Replay an IMU restart model through the C watchdog and two timeout baselines."""
import argparse
import csv
import ctypes as ct
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile

from build import ROOT, compiler, execute
from cases import MASK, event
from native import Event

TICK, SAMPLE, EPOCH = 0, 1, 3
OK, REJECTED = 0, 1
WAITING, TIMED_OUT, SEEN = 0, 1, 2
HORIZON = 64
BUDGETS = (4, 6, 8, 12)
POLICIES = ("continuous", "per_attempt", "capped_per_attempt")
CSV_FIELDS = ("family", "budget", "retry_gap", "retry_count", "reset_checks", "queue_delay",
              "reset_ticks", "first_admitted_tick", "queued_rejections", *POLICIES)
SOURCES = ["src/fq_monitor.c", "src/fq_tickless.c", "src/fq_acquisition.c",
           "experiments/restart_bridge.c"]


@dataclass(frozen=True)
class Scenario:
    family: str
    retry_gap: int = 0
    retry_count: int = 0
    reset_checks: int | None = None
    queue_delay: int | None = None

    @property
    def resets(self):
        return tuple(index * self.retry_gap for index in range(self.retry_count + 1))

    @property
    def arrival(self):
        if self.reset_checks is None:
            return None
        # WAIT_RESET, then one tick each for ENABLE, CONFIGURE and first RUN.
        return self.resets[-1] + self.reset_checks + 3 + self.queue_delay


def scenarios():
    for checks in (1, 2, 4):
        for queue_delay in (0, 2):
            yield Scenario("clean_restart", reset_checks=checks, queue_delay=queue_delay)
            for gap in range(2, 13):
                for retries in (1, 2, 3):
                    yield Scenario("retry_then_recover", gap, retries, checks, queue_delay)
    yield Scenario("reset_stalled")
    for gap in range(2, 13):
        yield Scenario("persistent_retry", gap, HORIZON // gap)


def trace(scenario, origin):
    resets = set(scenario.resets)
    for tick in range((HORIZON if scenario.arrival is None else scenario.arrival) + 1):
        now = origin + tick
        if tick == scenario.arrival:
            yield event(SAMPLE, now, now - scenario.queue_delay, value=5)
        elif tick in resets:
            yield event(EPOCH, now)
        elif tick == 1:
            yield event(SAMPLE, now, origin - 1, value=5)
        else:
            yield event(TICK, now)


class RestartOutput(ct.Structure):
    _fields_ = [("rc", ct.c_int32), ("state", ct.c_uint32), ("missed_windows", ct.c_uint32)]


def load_replay(run, driver):
    shared = ["-shared"] if os.name == "nt" else ["-shared", "-fPIC"]
    library = run / ("restart.dll" if os.name == "nt" else "restart.so")
    args = ["-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-Iinclude", *shared, *SOURCES]
    execute([*driver, *args, "-o", library], ROOT, run / "build.log")
    replay = ct.CDLL(str(library)).fq_restart_replay
    replay.argtypes = [ct.c_uint32, ct.c_uint32, ct.POINTER(Event), ct.c_uint32,
                       ct.POINTER(RestartOutput)]
    replay.restype = ct.c_int
    return replay, args


def watchdog_trace(replay, scenario, budget, origin):
    events = list(trace(scenario, origin))
    incoming = (Event * len(events))(*(Event(**item) for item in events))
    outgoing = (RestartOutput * len(events))()
    if replay(origin, budget, incoming, len(events), outgoing) != OK:
        raise RuntimeError("C watchdog initialization failed")
    return [(result.rc, result.state, result.missed_windows) for result in outgoing]


def per_attempt_notice(events, budget, total_budget=None):
    last_reset = 0
    for tick, entry in enumerate(events):
        if entry["kind"] == EPOCH:
            last_reset = tick
        if tick - last_reset > budget or (total_budget is not None and tick > total_budget):
            return tick
    return None


def reference_attempt_notice(resets, end, budget):
    """Find the first reset window wide enough to reach its deadline."""
    for index, reset in enumerate(resets):
        deadline = reset + budget + 1
        next_reset = resets[index + 1] if index + 1 < len(resets) else end + 1
        if deadline < next_reset:
            return deadline
    return None


def check_case(replay, scenario, budget):
    events = list(trace(scenario, 0))
    observed = watchdog_trace(replay, scenario, budget, 0)
    wrapped = watchdog_trace(replay, scenario, budget, MASK - 4)
    if observed != wrapped:
        raise RuntimeError(f"Clock origin changed C outputs for {scenario}, budget={budget}")

    arrival = scenario.arrival
    total_miss = budget + 1
    for tick, (entry, output) in enumerate(zip(events, observed, strict=True)):
        admitted = tick == arrival
        expected_rc = REJECTED if entry["kind"] == SAMPLE and not admitted else OK
        expected_state = SEEN if admitted else TIMED_OUT if tick >= total_miss else WAITING
        if output != (expected_rc, expected_state, int(tick >= total_miss)):
            raise RuntimeError(f"C replay mismatch at tick {tick} for {scenario}, budget={budget}: {output}")

    end = len(events) - 1
    notice = next((tick for tick, output in enumerate(observed) if output[2]), None)
    per_attempt = per_attempt_notice(events, budget)
    capped = per_attempt_notice(events, budget, 2 * budget)
    reference_attempt = reference_attempt_notice(scenario.resets, end, budget)
    cap_deadline = 2 * budget + 1
    reference_capped = min((tick for tick in (reference_attempt, cap_deadline)
                            if tick is not None and tick <= end), default=None)
    if (per_attempt, capped) != (reference_attempt, reference_capped):
        raise RuntimeError(f"Baseline differs from the window calculation for {scenario}, budget={budget}")
    if per_attempt_notice(events, budget, budget) != notice:
        raise RuntimeError("A budget-matched cap should match the continuous policy in this model")
    return {
        "family": scenario.family,
        "budget": budget,
        "retry_gap": scenario.retry_gap,
        "retry_count": scenario.retry_count,
        "reset_checks": scenario.reset_checks,
        "queue_delay": scenario.queue_delay,
        "reset_ticks": " ".join(map(str, scenario.resets)),
        "first_admitted_tick": arrival,
        "queued_rejections": sum(output[0] == REJECTED for output in observed),
        "continuous": notice,
        "per_attempt": per_attempt,
        "capped_per_attempt": capped,
    }


def summarize(rows):
    summaries = {}
    for budget in BUDGETS:
        recovered = [row for row in rows if row["budget"] == budget and row["first_admitted_tick"] is not None]
        missing = [row for row in rows if row["budget"] == budget and row["first_admitted_tick"] is None]
        summaries[str(budget)] = {}
        for policy in POLICIES:
            delays = [row[policy] for row in missing if row[policy] is not None]
            summaries[str(budget)][policy] = {
                "notices_by_first_admission": sum(row[policy] is not None for row in recovered),
                "recoverable_cases": len(recovered),
                "notices_during_persistent_loss": len(delays),
                "persistent_cases": len(missing),
                "first_notice_range_ticks": [min(delays), max(delays)] if delays else None,
            }
    witnesses = [
        row for row in rows if row["budget"] == 8 and (
            (row["family"] == "clean_restart" and row["reset_checks"] == 2 and row["queue_delay"] == 0)
            or (row["family"] == "retry_then_recover" and row["retry_gap"] == 6
                and row["retry_count"] == 1 and row["reset_checks"] == 2 and row["queue_delay"] == 0)
            or (row["family"] == "persistent_retry" and row["retry_gap"] in (6, 9, 10))
            or row["family"] == "reset_stalled"
        )
    ]
    return {
        "cases": len(rows),
        "logical_horizon_ticks": HORIZON,
        "wrap_replays": len(rows),
        "queued_packets_rejected_per_origin": sum(row["queued_rejections"] for row in rows),
        "budget_matched_cap_agreement_cases": len(rows),
        "by_budget": summaries,
        "witnesses": witnesses,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    compilers = parser.add_mutually_exclusive_group()
    compilers.add_argument("--zig")
    compilers.add_argument("--cc")
    parser.add_argument("--check", action="store_true", help="Compare replay results with the recorded evidence")
    args = parser.parse_args()
    runs = ROOT / "runs"
    runs.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="restart_policy_", dir=runs))
    driver = compiler(args.zig, args.cc)
    replay, build_args = load_replay(run, driver)
    rows = [check_case(replay, scenario, budget) for budget in BUDGETS for scenario in scenarios()]
    measurement = summarize(rows)
    csv_path = run / "cases.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    sources = [*SOURCES, "include/fq_monitor.h", "include/fq_tickless.h", "include/fq_acquisition.h",
               "tools/build.py", "tools/cases.py", "tools/native.py", "tools/run_restart_policy.py"]
    record = {
        "compiler": execute([*driver, "--version"], ROOT, run / "compiler.txt").splitlines()[0],
        "build_arguments": build_args,
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
        "cases_csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "synthetic_inputs": True,
        "physical_tests": False,
        "measurement": measurement,
    }
    (run / "summary.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.check:
        archived = json.loads((ROOT / "results/restart-policy/summary.json").read_text(encoding="utf-8"))
        if any(record[field] != archived[field] for field in ("measurement", "cases_csv_sha256")):
            raise RuntimeError(f"Replay differs from the recorded evidence. Check {run}")
    print(run)
    print(f"{measurement['cases']} cases, {measurement['wrap_replays']} wrap replays")
    print(json.dumps(measurement["by_budget"]["8"], indent=2))


if __name__ == "__main__":
    main()
