# Alarm timing against NASA Limit Checker

The experiment asks whether a monitor's first alarm matches an independently
defined fault-duration rule when sensor capture, packet arrival and monitor
evaluation happen at different times.

## Comparison

The test executes the existing C99 monitor and three unmodified functions from
NASA's Limit Checker at commit `c9104f85b3a9b795be5c67702c8e190b36e4cdd5`.
[Action-point sampling and consecutive failures](https://github.com/nasa/LC/blob/c9104f85b3a9b795be5c67702c8e190b36e4cdd5/fsw/src/lc_action.c#L41-L248)
and [sample command and aging](https://github.com/nasa/LC/blob/c9104f85b3a9b795be5c67702c8e190b36e4cdd5/fsw/src/lc_cmds.c#L44-L107)
run as compiled C. The fixture has one active action point and one watchpoint.
It supplies a threshold result and reloads the result age on receipt as
[NASA's watchpoint code](https://github.com/nasa/LC/blob/c9104f85b3a9b795be5c67702c8e190b36e4cdd5/fsw/src/lc_watch.c#L398-L451)
does for valid results. The one-watchpoint expression is represented by a stub.
The test records the first request to dispatch a relative time sequence (RTS)
and executes no command. It covers neither full cFS integration nor watchdog
recovery, alarm clearing, multiple watchpoints or real sensor behavior.

Both models see the same arrivals. All nine settings first alert at tick 12 in
the aligned sustained-fault control starting at tick 8. The C99 monitor uses
three samples or a four-tick dwell, a five-tick maximum sample age and a
four-tick observed gap limit. LC uses three consecutive failed evaluations
when evaluated every two ticks, or five when evaluated every tick. We vary
the watchpoint countdown within each cadence. LC consumes an arrival before
evaluating on a shared tick and ages the cached result after evaluating.

The oracle uses the underlying synthetic threshold state, separate from the
packets that reach either monitor. The signal is bad on `[onset, recovery)`.
The first alarm is timely on `[onset + 4, recovery)`, early before dwell
while the signal is bad, and after recovery when the signal is already
normal. A missed alarm is a fault that outlasts dwell and produces no alarm.
An alarm after recovery stays in its own category even for a sustained fault.
Delay is recorded from the first eligible tick and only for timely alarms.

The first 90 cases use evaluation-aligned arrivals with clean, fixed-lag and
dropped-sample variants. The other 108 cases include a one-tick lag,
alternating lag, irregular capture and clusters of three adjacent samples
every six ticks. The clustered schedule sweeps all six onset phases. The
four-tick dwell is an explicit experimental contract. These are generated
signals and logical ticks with no mission timing or measured false-alarm rate.

## Results

| Setting | Timely | Before dwell | After recovery | Missed |
|---|---:|---:|---:|---:|
| C99 count | 72 | 13 | 6 | 22 |
| C99 hold | 87 | 0 | 30 | 11 |
| C99 observed span | 74 | 0 | 6 | 30 |
| LC every 2 ticks, age 1 | 45 | 0 | 7 | 58 |
| LC every 2 ticks, age 2 | 77 | 0 | 18 | 21 |
| LC every 2 ticks, age 3 | 84 | 0 | 28 | 13 |
| LC every tick, age 2 | 37 | 0 | 5 | 68 |
| LC every tick, age 4 | 80 | 0 | 20 | 19 |
| LC every tick, age 6 | 87 | 0 | 30 | 11 |

The table omits cases where no alarm was expected and none occurred.
The full summary and raw case rows preserve them. The counts apply to
the selected workload and do not estimate probabilities.

In the 90 aligned cases, LC age 1 and both C99 evidence-counting policies
had the same first alarm or no alarm in every case. LC age 3 similarly
matched the hold policy. Changing the phase and spacing broke those
matches. Evaluating LC every tick with age 6 matched hold in **all 198
cases**, including exact first alarm ticks. No cost comparison follows
from this match. The fixture measures logical behavior, with no MCU load,
power or cFS scheduler overhead measurements.

One clustered example starts a sustained fault at tick 6. The third bad
sample arrives at tick 8. Count trips there, two ticks before the declared
dwell. Hold and LC at one tick with age 6 trip at tick 10. Observed span
waits for new evidence at tick 12. Conversely, for a three-tick fault
starting at tick 8 with recovery packets dropped, hold and that LC
configuration both alarm at tick 12 after the fault has ended. Observed
span stays silent. Across the entire matrix, observed span produced fewer
post-recovery alarms than the matching LC hold configuration and missed
more sustained faults. The matrix establishes a trade-off under an
explicit oracle. A comparative flight-software claim still needs a
specific monitoring requirement and representative data or physical input.

## Reproduce

```sh
python tools/run_lc_alarm.py --check
```

First use fetches two pinned NASA source files anonymously and verifies their
SHA-256 hashes. The compiler setup is the same as for the other native
tests. The NASA sources are cached in ignored `.tools/`. The extracted
functions, build logs and fresh measurements go under ignored `runs/`.
The script checks the archived case-table hash and deterministic summary.
[Case table](../results/lc-alarm/cases.csv) and
[summary with source pins](../results/lc-alarm/summary.json).
