# First-sample deadlines across IMU restarts

How long can repeated reset attempts defer an outage notice, and how often
does a fixed total budget report a miss while the sensor is still recovering?
This experiment replays one source-grounded restart model through the existing
compiled C watchdog and two reference policies.

## Driver behavior and modeled timing

The F Prime community's `MpuImu` component has a rate-group-driven state
machine. A successful reset proceeds through wait-for-reset, enable,
configure and read. A reset-bit poll can leave the driver waiting. An I2C
error while checking the reset returns it to the reset state. The successful
read action publishes a sample to the connected output port. The two source
files were reviewed at commit `e5d83d165d5a5ceadc1ea4d0a0d6a74f0d0fbc4f`.
[State machine](https://github.com/fprime-community/fprime-sensors/blob/e5d83d165d5a5ceadc1ea4d0a0d6a74f0d0fbc4f/fprime-sensors/MpuImu/Components/ImuManager/ImuStateMachine.fpp) ·
[Driver actions](https://github.com/fprime-community/fprime-sensors/blob/e5d83d165d5a5ceadc1ea4d0a0d6a74f0d0fbc4f/fprime-sensors/MpuImu/Components/ImuManager/ImuManager.cpp)

The fixture primes the C watchdog with a valid sample at tick −1. It feeds
the first reset epoch at tick 0. A queued copy of the old sample arrives at
tick 1, when its age of two ticks is still within the four-tick age limit.
The epoch floor rejects it. A successful attempt completes after 1, 2 or 4
reset-check ticks and one tick each for enable, configure and first read.
The read then reaches the watchdog with a queue delay of 0 or 2 ticks. A
failed attempt waits and encounters a reset-check error one tick before the
next reset. Reset attempts are spaced 2 to 12 ticks apart.

These timings and the pre-reset packet are synthetic. One logical tick
represents one driver service opportunity with an on-time monitor dispatch.
The model includes an eventual successful attempt, repeated retries without
a sample through tick 64, and a reset stall with no retry. It does not run
F Prime, emulate I2C, estimate hardware delays or use mission telemetry. It
treats notifications as observations. The model does not feed them back
into the driver to trigger additional resets or recovery actions.

## Compared policies and outcomes

- **Continuous budget:** the existing C watchdog keeps the budget anchored
  to the first reset until a sample is admitted.
- **Per-attempt budget:** the baseline starts a fresh budget at every reset.
  A reset at the would-be notification tick is processed first.
- **Per-attempt budget with total cap:** the same baseline also reports after
  a total wait of `2B` ticks. The additional budget is a sensitivity control.
  A separate check sets the total cap to `B` and compares it to the watchdog.

All three policies observe identical events through first admission or the
end of the horizon. `B` is inclusive, so a wait started at tick `s`
first expires at `s + B + 1`. A valid sample at that tick is recorded as late.
The two baselines run as sequential Python reference policies. A separate
reset-window calculation checks their first notification ticks. The C
replay checks every event's return code, acquisition state and missed-window
counter against the scenario's planned admission and timeout boundaries.

Each budget has 204 recoverable cases and 12 cases with no sample through
tick 64. The 864 total cases reuse the same workloads at budgets of 4, 6, 8
and 12 ticks. The C replay repeats each case at a second clock origin close
to uint32 wrap and compares all outputs. The table uses `B = 8`.

| Policy | Reports by first admission (of 204) | Reports during loss (of 12) | First report during loss (ticks) |
|---|---:|---:|---:|
| Continuous | 192 | 12 | 9 |
| Per attempt | 79 | 4 | 9 when reported |
| Per attempt with total cap of 16 | 129 | 12 | 9–17 |

The first column includes reports simultaneous with late admission.
These reports may be appropriate if the system has a real availability
deadline. The model supplies no deadline that would classify them as false
alarms. Counts describe the deterministic sweep and carry no event frequencies.

For a concrete recoverable case, the first reset is at tick 0, the retry is
at tick 6 and the first sample arrives at tick 11. The C watchdog reports at
tick 9. The two baselines admit the sample before reporting a miss. If the
same reset interval repeats through tick 64 with no sample, the C watchdog
still reports at tick 9 and the capped baseline reports at tick 17. The
uncapped baseline produces no notice during that horizon. Under the stated
same-tick ordering, a repeated gap at or below `B + 1` can indefinitely defer
an uncapped per-attempt notice if the repeats persist without a sample.

At the same total deadline, the capped baseline matched the existing C
watchdog in all 864 cases. In this model, resetting the local budget can
only move its deadline later, so a cap at the original deadline determines
the first report. The two-budget case quantifies a choice between earlier
reporting and letting more attempts finish. A concrete workload with
measured service timing and a documented availability budget would be
needed to choose a setting for a specific system.

## Reproduce

```sh
python tools/run_restart_policy.py --check
```

The command compiles the unchanged C monitor and watchdog plus a small
replay bridge, runs the sweep and checks its results against the archived
evidence. Each run writes a CSV, source hashes, toolchain details and a
summary under `runs/`. The recorded [case CSV](../results/restart-policy/cases.csv)
uses empty cells for no observed admission or report. The
[summary](../results/restart-policy/summary.json) includes the full budget sweep
and the named examples.
