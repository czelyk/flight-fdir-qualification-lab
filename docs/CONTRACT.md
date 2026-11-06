# Precise qualification semantics

`fq_init` establishes a fresh in-memory monitor. It rejects invalid policy,
unordered thresholds, zero sample count, zero freshness/gap limits and timing
parameters at or beyond the half-range bound. Init does not preserve a previous
alarm through a processor or application restart.

## Inputs and order at one processing instant

Events are SAMPLE, TICK, INVALID or EPOCH. All timestamps are unsigned 32-bit local
ticks; measured values and thresholds are signed scaled integers. No physical
units, calibration, clock synchronization or flight deadlines are inferred.

1. Reject a backward/ambiguous processing-clock step, mark quality invalid and
   break pending evidence. Preserve the alarm and the last valid clock origin.
2. Expire the last admitted sample when its acquisition age is **greater than**
   max_age. At exact equality it is still fresh.
3. Process the event. An accepted sample updates the evidence before the hold
   timer at that same instant. A timely good sample therefore gets processed
   before a pending bad hold timer can fire.
4. Evaluate the selected qualification contract.

Rejected SAMPLE events do not refresh acquisition time, sequence history or
sample count. Their processing time can still advance a hold timer while the
existing held sample is fresh; the positive return code records rejection.

## Sample admission

The acquisition timestamp must not be in the future, must be within max_age,
and must not move backward relative to the last admitted acquisition. Equal
acquisition ticks with a new sequence are permitted (finite clock resolution).
Sequence movement must be strictly forward and less than 2^31; unsigned wrap
is accepted. Acquisition gaps and every meaningful serial comparison must stay
within the declared half-range. Discontinuities require an explicit lifecycle
decision; this component does not infer a clock reset from ambiguous integers.

An explicit producer EPOCH forgets the sequence history and makes data UNKNOWN.
Until its first admitted sample, it rejects acquisition ticks before the epoch
event. It preserves an existing alarm. Afterward ordinary sequence/acquisition
ordering applies. This is not an authenticated producer identity or protection
against indistinguishable same-tick old packets. Integration should drain old
queued data at a producer restart and handle receiver-clock resets separately.

## Data quality and evidence

Quality is UNKNOWN, FRESH, STALE or INVALID. Startup with no data remains UNKNOWN.
Detecting an outage during input silence requires tick delivery. The caller can
poll or use the [one-shot tick planner](TICKLESS.md). Actual expiry may be noticed
later than the numeric boundary if the caller runs late.

Raw bad evidence is value >= trip_limit; clear evidence is value <= clear_limit.
The open interval between thresholds is neutral. Neutral or opposite evidence
breaks a pending transition. An existing alarm is only cleared by qualifying
clear evidence, not by loss of data or by resetting a producer epoch.

- COUNT uses consecutive admitted qualifying samples. It does not promise dwell
  time. With finite timestamp resolution, distinct same-tick samples can count.
- HOLD starts a timer at reception of its first qualifying sample. It may qualify
  on a later time event with no new measurement, provided held data stays fresh.
- OBSERVED starts at acquisition of its first qualifying sample and qualifies
  only on another admitted endpoint sample spanning the dwell. Each adjacent
  accepted qualifying acquisition gap must be <= max_gap. Greater gaps restart
  the run. Ticks do not extend its evidence span.

A zero dwell is an immediate sample-driven transition for the duration policies.
HOLD and OBSERVED durations are inclusive >= tests. Pending state is cleared
after a transition. Diagnostic counters saturate at UINT32_MAX. One caller at a
time owns each context; there is no lock, scheduler or heap allocation.

None of these policies proves what happened between measurements. OBSERVED is
an observed-evidence contract, not proof of continuous physical failure.
