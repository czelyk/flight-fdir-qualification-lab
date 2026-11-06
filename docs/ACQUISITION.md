# First-sample watchdog

The core monitor can expire data after admitting a sample. At startup and
after a producer epoch, it may have no sample to expire. The optional C99
wrapper reports whether the first admissible sample is still expected or its
window has already elapsed. The worker can report that distinction through
telemetry while reading the core's quality and qualification alarm separately.

## Integration

1. Call `fq_acquisition_init(channel, config, now, max_wait)` when you begin
   expecting sensor data. The wrapper uses a core epoch event to anchor the
   processing clock and reject captures before that tick. Initialization
   therefore increments the core's epoch counter once.
2. Send sample, invalid-data, tick and known producer epoch events through
   `fq_acquisition_step()`. Inspect `channel->state` and
   `channel->missed_windows` alongside the core outputs. Use one serialized
   caller per channel.
3. Arm the worker's timer using `fq_acquisition_next_tick_delay()` after
   initialization and each event. Add the delay to `channel->monitor.now`
   in the modular tick domain. Apply the
   [same-tick input and timer rules](TICKLESS.md).

| Acquisition state | Meaning |
|---|---|
| `FQ_AWAITING_FIRST` | The current window is open. |
| `FQ_FIRST_TIMED_OUT` | The current window expired before sample admission. |
| `FQ_FIRST_SEEN` | The monitor admitted the first sample, possibly after its deadline. Inspect core quality for subsequent staleness or invalid data. |

`max_wait` is inclusive and must be less than `2^31`. With a start at
tick 10 and a budget of four ticks, an admissible sample processed at tick 14
is on time. Tick 15 is the first timeout instant. If the next event is a
valid sample at tick 15 or later, the wrapper records a missed window even
when no timer event ran first. The sample transitions the acquisition state
to `FQ_FIRST_SEEN` and the counter retains the miss.

Each window increments the saturating counter at most once. An epoch after
admission starts a new window. An epoch during an unfinished window updates
the core's admission floor while retaining the watchdog's original deadline.
This keeps repeated restart notifications from indefinitely extending the
wait. A sample the core rejects cannot close a window. The transport still
owns draining queued packets whose timestamps cannot distinguish them from
new producer data. A backward processing-clock event leaves the watchdog
anchored at the last valid processing timestamp.

The watchdog uses the same half-range modular clock and one-shot maintenance
checkpoints as the core. A late callback can delay when software reports
a miss. The application supplies the producer epoch, decides when data is
expected and sets the budget. The alarm continues to follow the core's
trip/clear rules, including retention across a live producer epoch.
A full reinitialization resets the RAM state and counters.

## Executed validation

The C fixture crosses three policies, two clock origins, four budgets
(0, 1, 4 and 8), 13 elapsed tick values and four stimuli. The stimuli are
silence, a valid sample, a capture before the epoch and a future capture.
One origin crosses the uint32 wrap. Expected results come from the declared
deadline and sample validity. Windows and Cortex-M4 emulation produced the
same counts.

| Outcome | Cases |
|---|---:|
| On-time admission | 102 |
| Late admission with a recorded miss | 210 |
| Waiting with no admission | 306 |
| Timeout with no admission | 630 |
| Total | 1,248 |

Direct checks also exercise repeated epochs, retention of an existing
alarm, invalid data, a backward processing time, counter saturation and a
maximum wait that crosses a clock checkpoint. The context measured 120
bytes in each tested build, including the 104-byte core context. These are
synthetic logical-time checks. Physical timer delivery, sensor warm-up and
mission-specific time budgets require separate measurements.

```sh
python tools/run_acquisition.py
```

With the [ARM toolchain and Python packages](../README.md#optional-cortex-m4-execution):

```powershell
.venv/Scripts/python tools/run_acquisition.py --arm
```

Runs save build logs and counters under `runs/`. The recorded
[result](../results/acquisition/acquisition.json) records both toolchains and
the source hashes.
