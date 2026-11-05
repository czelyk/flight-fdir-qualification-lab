# Primary sources and prior work

Checked on 4 November 2026 through anonymous public access. Exact acquired source
URLs and byte digests are in provenance/sources.json. No NASA source is a runtime
dependency or copied into the C implementation.

1. [NASA Software Engineering Handbook: Fault Detection and Response](https://swehb.nasa.gov/pages/viewpage.action?pageId=107053215).
   The accessible guidance describes fault-indication filtering, thresholds,
   persistence and responses dependent on mission phase/state. It establishes
   the spacecraft function, not compliance or particular thresholds for this lab.
2. [NASA cFS LC action processing at the reviewed commit](https://github.com/nasa/LC/blob/c9104f85b3a9b795be5c67702c8e190b36e4cdd5/fsw/src/lc_action.c).
   Selected action-processing code explicitly counts consecutive failures and
   clears that count for a stale action-point result. Both ideas predate this
   project. The lab's unique-admitted-sample count policy differs from scheduled
   LC action-point evaluations; it is not an LC reproduction or bug report.
3. [LC watchpoint source](https://github.com/nasa/LC/blob/c9104f85b3a9b795be5c67702c8e190b36e4cdd5/fsw/src/lc_watch.c)
   was acquired and hashed as context. No complete LC integration or source audit
   is claimed. The lab does not claim NASA lacks freshness handling.
4. [NTRS: Methodology for Designing Fault-Protection Software](https://ntrs.nasa.gov/citations/20100021298)
   is a 2006 NASA Tech Brief describing separation of opinions, symptoms, alarms
   and responses. The landing summary/metadata were read; the full underlying
   methodology was not reproduced. The concepts are credited prior work.
5. A legacy JPL Design Principles PDF link redirected to an acquisition landing
   page during this task. The PDF was not obtained. Search snippets were not
   promoted into read requirements or a claim of standards compliance.

Known persistence counters, timers, freshness checks, two-threshold qualification
and half-range serial arithmetic are not inventions of this repository. The
authored contribution is a compact implementation, explicit contract comparison,
structured oracle, reconstructible traces and actual host/target-code evidence.
Scientific novelty and usefulness for a specific mission remain unestablished.
