# Actual C/reference results

**394,866 trace comparisons** and
**2,003,430 per-event comparisons** passed for the
three declared policy contracts. This comprises finite token enumeration,
seeded histories and named cases; reused profiles/policies/clock origins are
not independent physical failure modes.

- 19 named input streams x two configurations x three policies.
- Eight-token histories of length 5, two configurations,
  two clock origins and three policies: 393,216 comparisons.
- Seeded mixed histories: 1,536 comparisons,
  seed 20261104. The seed/generator are reproducible, not mission data.
- C and reference output/input stream SHA256 agree:
  `9b2fbe8638ab8eda4d65e3e4672156706c1fd6d92c4d9de7141fa1223ee51a05`.
- A second origin near uint32 wrap produces identical diagnostic output streams.

## Different contracts, different decisions

Synthetic configuration: trip dwell 4 ticks, clear dwell 3 ticks, maximum sample
age 6 ticks, observed-gap budget 2 ticks, count threshold 3. Tick units and
threshold values are deliberately not assigned to a mission.

| Named scenario | Count: first alarm tick | Hold timer | Observed-span |
|---|---:|---:|---:|
| one_sample_then_silence | none | 4 | none |
| same_tick_burst | 0 | none | none |
| gap_then_new_bad | 5 | 5 | none |
| nominal_cadence_agreement | 4 | 4 | 4 |
| qualified_then_stale | 4 | 4 | 4 |

The hold timer may qualify one still-valid held measurement. The count policy
may qualify several admitted samples at one timestamp. The observed-span policy
waits for sufficiently separated endpoint observations and resets its run across
large gaps. These are explicit semantics, not measured false-positive rates.

In the gap example the observed policy does not qualify while the other policies
do. This can delay or prevent a useful trip if the gap budget is too tight. It
is not universally safer or preferable. Choose a contract against the actual
sampling, uncertainty and response requirements; this lab supplies none of those
mission requirements.

Staleness and invalid quality break pending evidence but preserve an already
asserted alarm. Alarm=false with unknown/stale data must not be interpreted as
healthy. All named output rows were obtained from the actual C bytes after a
byte-for-byte reference comparison; `named.csv` includes rejected inputs and
clock errors. No filter observes the physical signal between samples.
