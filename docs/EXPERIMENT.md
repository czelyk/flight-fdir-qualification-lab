# Test design and limits

The C implementation is compared event by event with a separately structured
Python specification using unbounded integer timestamps and lists of qualifying
observations. C stores fixed counters and modular timestamps. The specification
is a test oracle created in the same task; it is not independent peer review or
a certified external model.

## Declared profiles

| Profile | Trip / clear ticks | Age | Gap | Count | Thresholds |
|---|---|---:|---:|---:|---|
| 0 | 4 / 3 | 6 | 2 | 3 | trip >=20, clear <=10 |
| 1 | 2 / 2 | 3 | 1 | 2 | trip >=20, clear <=10 |

These numbers are synthetic units. They are neither mission requirements nor
values fitted to make one filter win.

## Campaigns

- 19 named streams cover sparse observations, bursts, gaps, deadband, invalid and
  stale values, explicit producer epochs, queued pre-epoch data, sequence wrap,
  clock wrap/regression, half-range ambiguity and threshold boundaries.
- Enumerate every length-five word in an eight-token alphabet. Tokens generate
  good, bad, neutral, tick, gap, duplicate, invalid and epoch events. Run two
  configurations, two clock origins (0 and 0xfffffffc) and three policies.
- Compare output digests across the two origins as a clock-translation invariant.
- Add 256 seeded 24-event histories per configuration, reused across three policies.
  Seed 20261104 also covers delayed/future/out-of-order input and extreme values.
- Explicit witnesses check intended semantics beyond C/model agreement: a held
  reading can trip, a same-tick burst can satisfy COUNT, stale/epoch data cannot
  clear a previously asserted alarm, and old queued timestamps are rejected.

All C bytes must match the expected output bytes, including return/error codes,
quality, pending evidence and counters. A mismatch stops the run and writes a
failure trace. Named output files are decoded from actual C output after matching
the reference. Aggregated coverage uses stream hashes and deterministic generators
instead of storing millions of redundant text rows. Inputs are synthetic; there
is no labeled physical truth for detector accuracy or a reliability probability.

## Scope of the other checks

Native boundary tests include generation-independent timer/sequence wrap, config
validation and saturated diagnostic counters. Debug CMake compilation exercises
the same boundary tests; its shared library is additionally compared on named
cases and eight seeded histories.

The ARM fixture compiles the production C and replays those named/eight seeded
histories, using generated expected vectors. It checks actual Cortex-M4 outputs
in Unicorn. It does not test interrupts, a sensor/clock peripheral, RTOS scheduling,
UART transport, physical sensor noise, memory upset or target execution deadlines.

The finite token enumeration is not formal verification over all reachable states,
timestamps, configurations or mission traces. Clock offsets/profiles/policies
reuse evidence and must not be counted as independent physical fault cases.
