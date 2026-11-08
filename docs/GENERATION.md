# Sensor generation tags at a reset boundary

An acquisition timestamp with coarse resolution can place a capture just
before reset and a capture just after it on the same tick. After a producer
epoch, the core permits a sample acquired at that tick, and its sequence
history starts over. If the old sample arrives first, it can satisfy the
first-sample watchdog and occupy the same sequence number as the new sample.
An older timestamp that is strictly before the epoch already fails the
existing core check. [Core contract](CONTRACT.md)

A queued data path is a plausible integration context. F Prime documents
that asynchronous input calls can wait for receiver dispatch, and its open
`MpuImu` component provides a sensor-data output port. The test fixture
models a consumer with a ready queue and an optional earlier operation that
can complete after reset. The model and its schedules are authored test
inputs. No F Prime deployment, sensor bus or DMA peripheral was executed.
[F Prime port and component documentation](https://fprime.jpl.nasa.gov/devel/docs/user-manual/overview/03-port-comp-top/) ·
[Pinned MpuImu port definition](https://github.com/fprime-community/fprime-sensors/blob/e5d83d165d5a5ceadc1ea4d0a0d6a74f0d0fbc4f/fprime-sensors/MpuImu/Components/ImuManager/ImuManager.fpp)

## C ingress contract

Use `fq_ingress_init()` with the current producer generation. Record the
32-bit generation at the producer-side capture boundary and keep it with
the sample through buffering and completion. Deliver an explicit
`FQ_EPOCH` for the new generation through the serialized control path.
The [worker example](../examples/worker.c) shows the sample and epoch calls.

- A sample must match the current generation before the normal admission
  checks run. A mismatch advances the watchdog as a tick and increments a
  separate saturating counter. The existing age, acquisition order and
  sequence checks still apply to matching samples.
- An epoch advances the generation only if its unsigned forward distance
  is nonzero and less than half the 32-bit range, and the acquisition layer
  accepts its processing timestamp. Duplicate or older announcements leave
  the epoch floor intact. Tick and invalid-data events ignore the tag.
- Serialize access and keep control announcements ordered with sample
  dispatch. Old-generation samples can still be accepted before the receiver
  learns of a reset. A new-generation sample arriving before its epoch is
  rejected and would require redelivery or producer-side coordination.
- A matching sample captured before the receiver's epoch tick still fails
  the core timestamp floor. Keep the existing clock contract, and avoid
  reusing generation values while old packets can survive. A full receiver
  restart requires the application to reestablish the producer generation.

Use the [optional one-slot handoff](HANDOFF.md) when a synchronized producer
boundary is available and samples can reach the receiver ahead of the notice.

## Measured comparison

The fixture starts from a working stream and processes the epoch before
same-tick data. Old sample cases cover absence, a ready frame and a frame
released after the epoch. Ready and deferred old frames may have the same
tick as the epoch or an earlier one. New sample cases cover absence, an
already queued equal-tick frame, an already queued earlier frame and a
subsequent capture. A deferred completion or later capture is delivered
zero to three ticks after the epoch. With both samples eligible, their
sequence numbers collide. Missing first samples are reported at tick 4.

The comparison executes four alternatives against the same C acquisition
monitor. The ready-only flush clears frames already in the consumer queue.
The coordinated drain is a stronger control: it assumes the producer can
quiesce and cancel or drain **all** old work before publishing new frames.
This removes the old frame without discarding new-generation frames.

| Admission rule | Old samples accepted | New samples accepted | Missed first-sample windows | Loss hidden when no new sample arrived |
|---|---:|---:|---:|---:|
| Timestamp only | 19 | 22 | 12 | 5 |
| Ready-only flush | 16 | 16 | 21 | 4 |
| Coordinated drain | 0 | 31 | 22 | 0 |
| Generation tag | 0 | 31 | 22 | 0 |

Windows and Cortex-M4 emulation matched on **53 queue scenarios**, 212
policy comparisons and a second replay of those comparisons through clock
wrap. An eligibility and delivery-order calculation checks every result.
Direct checks also exercise generation wrap, out-of-order control,
duplicates, clock errors, saturation and late valid samples.

For example, when the old sample carries the epoch tick and a pending
completion releases it at tick 2, timestamp-only admission and the
ready-only flush both admit it. With no new sample, the watchdog then has
no first-sample miss to report. The tag and coordinated drain both preserve
the missing-data report at tick 4. Conversely, when coordinated drain is
available, it matches the tagged outcome throughout this fixture. The
wrapper context measured 128 bytes on both builds, including the 120-byte
acquisition context. It uses a 32-bit generation per captured sample.
The fixture did not measure the real drain latency, tag transport overhead
or frequency of this ordering in a spacecraft.

```sh
python tools/run_generation.py --check
```

With the [ARM toolchain and packages](../README.md#optional-cortex-m4-execution):

```powershell
.venv/Scripts/python tools/run_generation.py --arm --check
```

[Recorded measurements and toolchains](../results/generation/generation.json)
