# Internal skeptical review

This is a single-agent internal critique. No independent reviewer, spacecraft
team or conference has selected the project.

**Strongest objection:** freshness and persistence handling are mature FDIR
practice. cFS LC already handles stale results, and a count or held-data timer
may be exactly the right contract for an operational system. The observed-span
variant is therefore not a universally improved detector or a new algorithm.

**Useful implemented result:** the repository makes those different contracts
inspectable on identical admitted evidence, preserves a separate data-quality
state, tests wrap/invalid-order boundaries and ships a small allocation-free C
engine with reconstructible C/reference/ARM comparisons. The source compiles and
executes; it is more than a report or an abstract simulation proposal.

**Where the proposed filter can be worse:** a max-gap setting smaller than actual
sampling gaps repeatedly breaks its run. It can delay or prevent a needed alarm
even when every observed value is bad. Holding a valid measurement can be a
justified operational choice. This lab cannot decide which is correct without
device semantics, uncertainty and response requirements.

**Limits of the evidence:** no physical signal truth, real mission telemetry,
hardware clock/sensor/transport, scheduling bounds, measured CPU timing, noise
model, FMECA, independent reference validation or external peer review. Finite
enumeration and seeded trials do not prove all states. Input admission assumes
one known tick domain and explicitly bounded serial comparisons. A live producer
epoch change is not recovery of the monitor after its own CPU reset.

**Next useful work:** choose a public, concrete spacecraft monitoring function,
identify the needed indication contract, characterize acquisition/queue timing
and fault observability on obtainable hardware, then compare these policies with
the actual existing monitor. Additional random synthetic histories alone cannot
establish operational superiority, scientific novelty or IAC acceptance.

Disposition: complete as a bounded GitHub engineering prototype. Not a completed
strong IAC topic selection. The paused research automation remains paused.
