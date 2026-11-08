# First sample arriving ahead of its reset announcement

When reset notices and samples travel on separate paths, a valid first
sample can reach the receiver before the notice that identifies its producer
generation. A second case occurs when the notice is processed first but
the new sample was captured earlier than that processing time. The strict
[generation ingress](GENERATION.md) rejects both. F Prime's asynchronous
ports illustrate why dispatch can be deferred. The queue order and timings
in this experiment are modeled inputs. [F Prime port documentation](https://fprime.jpl.nasa.gov/devel/docs/user-manual/overview/03-port-comp-top/)

## C handoff

The optional `fq_handoff_t` holds one fresh sample for the immediate
successor generation. A staged sample advances the receiver's timers
without updating its active generation, qualification evidence or accepted
sample count. A second candidate is returned as `FQ_HANDOFF_FULL` while
the occupied slot remains fresh. The slot expires on the next processed
event after its age limit. A valid notification that skips the staged
generation clears the slot.

The caller supplies both the receiver's processing tick and the producer's
reset boundary to `fq_handoff_epoch()`. They must share the same modular
clock domain. The control path must supply the actual producer boundary.
The receiver validates the modular direction of that boundary and the
generation advance. Its watchdog still advances at receiver processing time.
On valid notification, a matching staged sample is replayed once at the
receiver tick using its original capture timestamp. The ordinary admission
checks apply against the producer boundary and sample age.

```c
int replay_rc;
int epoch_rc = fq_handoff_epoch(&channel, now, reset_captured, generation, &replay_rc);
```

The caller can handle the epoch status and the replay result separately.
`FQ_HANDOFF_NO_REPLAY` includes the case where the slot has already expired.
Route sample, tick and invalid-data events through `fq_handoff_step()`.
Timer integration uses `fq_acquisition_next_tick_delay(&channel.ingress.acquisition)`.
Slot expiry needs no timer of its own because every subsequent dispatch
checks freshness before allowing replay. A sample from the previously
active generation can still be accepted before the reset is announced.
Deployments that cannot supply a common capture clock and producer reset
boundary can retain the strict ingress API.

## Executed comparison

The C fixture starts from an active stream. A producer reset occurs at
logical tick 0 and is announced at tick 0–8. One new sample is captured at
tick 0–4 and reaches the receiver zero to two ticks later. The maximum
sample age is four ticks. If notice and delivery share a tick, notice is
processed first. The same 135 cases run at two clock origins and all three
alternatives, for 405 comparisons plus 405 clock-wrap comparisons per target.

| Alternative | First samples admitted |
|---|---:|
| Existing strict ingress | 45 / 135 |
| Receiver staging with producer boundary | 105 / 135 |
| Producer holdback until notice, with producer boundary | 105 / 135 |

For example, a sample captured at tick 1 reaches the receiver at tick 2
before the notice at tick 3. Staging makes it admissible at tick 3.
In the sweep, 45 admissions came from the slot and 15 came from samples
received after the notice but captured before it. The latter benefit comes
from knowing the producer boundary. In 30 cases the sample exceeded its
age limit by the earliest permissible admission tick.

The producer-holdback baseline assumes the producer or transport retains
the same sample until the notice has been processed. It matched staging
throughout the one-sample sweep. Direct checks exercise slot pressure,
replacement after expiry, invalid and duplicate notices, timestamps on
the wrong side of the producer boundary, generation jumps and clock wrap.
Windows and Cortex-M4 emulation returned identical counts. The handoff
context measured 152 bytes on both targets, including the 128-byte strict
ingress context. Real transport timing, coordination cost and operation
with multiple queued samples remain outside the sweep.

```sh
python tools/run_handoff.py --check
```

With the [ARM toolchain and packages](../README.md#optional-cortex-m4-execution):

```powershell
.venv/Scripts/python tools/run_handoff.py --arm --check
```

[Recorded measurements and toolchains](../results/handoff/handoff.json)
