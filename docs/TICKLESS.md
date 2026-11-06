# One-shot tick scheduling

Call `fq_next_tick_delay()` on an initialized monitor after each processed
event. It returns a delay measured from `monitor.now`. Zero means the monitor
has yet to receive its first processing timestamp. Otherwise, arm a one-shot
timer for the modular timestamp `monitor.now + delay`. The result is a logical
deadline. When programming a real timer, compute the remaining wait against
the current clock and handle a deadline that has already passed.

1. Deliver all external events at a logical processing tick in input order.
   When there is an external event at the scheduled deadline, that event
   advances the monitor. Skip the timer-only tick at that timestamp.
2. When the deadline is reached during silence, deliver one `FQ_TICK`.
3. Recompute the deadline after processing. Cancel or supersede any old timer
   request when a new external event changes it.

The planner selects the earliest relevant instant. A sample expires when its
acquisition age reaches `max_age + 1`. For HOLD, a pending alarm or clear also
has a deadline measured from its first qualifying sample's processing time.
If the two deadlines coincide, the monitor applies expiry first. COUNT and
OBSERVED can qualify only when processing a sample. After the clock is
anchored, a checkpoint at most `2^31 - 1` ticks away keeps successive
processing timestamps within the modular comparison range. With the largest
permitted `max_age`, one checkpoint can precede expiry by a single tick.
Checkpoints advance the processing clock. Sample admission still applies the
existing sequence, acquisition time and epoch rules.

Equivalence with polling assumes time-ordered input, the same order for events
at the same tick and on-time logical timer delivery. If a platform can run the
timer callback before queued input at that tick, dispatch through the
serialized worker and resolve the order there. A late callback can delay a
transition or miss a HOLD window. Pass the actual processing time on late
delivery. The diagnostic HOLD `span` describes elapsed time at the last
processed event and can differ between deadlines when read without stepping.

## Executed comparison

The same C test runs on the host and on emulated Cortex-M4. The periodic
baseline calls the monitor at every tick without external input. The one-shot
worker calls it only at scheduled deadlines. The campaign uses 96-tick
histories, three policies, four trip/clear dwell pairs including zero, four
freshness limits, two clock origins including wrap and 16 deterministic input
streams per configuration. Inputs include silence, delayed acquisition,
same-tick bursts, repeated sequences, invalid data and producer epochs.
Separate direct checks cover alarm and clear deadlines, a competing sample
at the deadline, simultaneous expiry and hold, and half-range checkpoints.

| Policy | Periodic idle ticks | Scheduled idle ticks |
|---|---:|---:|
| COUNT | 36,416 | 1,744 |
| HOLD | 36,416 | 2,094 |
| OBSERVED | 36,416 | 1,744 |
| Total | 109,248 | 5,582 |

Both targets passed 1,536 traces and 55,200 comparisons at external events.
All 5,582 idle alarm or quality transition ticks matched. The comparison
also checks quality and alarm at omitted ticks and compares every output
field, including the diagnostic span, at the external events and the
scheduled ticks. Short traces do not reach the maintenance checkpoint.
The table counts synthetic idle monitor invocations. Actual savings depend on
polling cadence and traffic. Timer programming, interrupt order, target
execution time and power consumption require platform measurements.

```sh
python tools/run_tickless.py
```

For target instruction execution, install the
[optional ARM dependencies](../README.md#optional-cortex-m4-execution)
and run:

```powershell
.venv/Scripts/python tools/run_tickless.py --arm
```

Each run writes a new directory under `runs/`. The checked-in
[JSON result](../results/tickless/tickless.json) includes compiler versions,
build arguments, source hashes and the actual counters.
