# Changelog

## 0.5.0 — 8 November 2026

- Add an optional one-slot C handoff for samples arriving ahead of a reset notice.
- Separate the producer capture boundary from the receiver processing tick.
- Compare strict ingress, receiver staging and producer holdback across 135
  modeled timing cases on Windows and emulated Cortex-M4.

## 0.4.0 — 6 November 2026

- Add an optional generation-tag check at the C acquisition boundary.
- Compare timestamp-only admission, a ready-only flush, coordinated drain
  and generation tags on Windows and emulated Cortex-M4.

## 0.3.1 — 6 November 2026

- Add a source-grounded IMU restart replay with the compiled C watchdog and
  two timeout baselines. Record the notification trade-off and the result at
  a matched total deadline.
- Record 864 case outcomes, clock-wrap checks and rejected pre-reset samples.
  Reproduce the archived measurements in CI.

## 0.3.0 — 6 November 2026

- Add a first-sample watchdog for startup and producer restart. Its deadline,
  state and missed-window counter are separate from sensor fault qualification.
- Schedule first-sample expiry using the one-shot planner. Keep the original
  wait across repeated producer restart notifications until a sample is admitted.
- Add Windows and emulated Cortex-M4 results for 1,248 deadline and admission
  cases, plus direct restart, clock and alarm retention checks.

## 0.2.0 — 6 November 2026

- Add a C99 one-shot tick planner for data expiry, hold completion and
  clock checkpoints, with a worker integration example.
- Compare alarm and quality transitions against periodic polling on native
  Windows and emulated Cortex-M4. Record the tick counts and boundary cases.
- Run the tickless checks in CTest and the Windows and Linux CI jobs.

## 0.1.0 — 4 November 2026 (local prototype)

- C99 count, held-data duration and observed-span qualification contracts.
- Explicit data quality, admission checks, producer epoch and uint32 wrap rules.
- List-based Python reference, finite enumeration and deterministic histories.
- Actual Cortex-M4 output comparisons and CMake/CTest boundary validation.
- Raw named outputs, reconstructible replay, source hashes and bounded claims.
