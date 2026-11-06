# Changelog

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
