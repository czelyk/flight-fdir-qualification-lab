# Local validation — 4 November 2026

The 6 November update adds a separate [tickless validation campaign](docs/TICKLESS.md).
Its [native and Cortex-M4 evidence](results/tickless/tickless.json) records the
same measurements on both targets. The qualification results below are the
original campaign.

| Check | Executed result | Evidence |
|---|---|---|
| Native boundary suite | Qualification, stale/invalid alarm retention, producer epoch, clearing, duplicate admission, wrap, saturation and config checks passed | `results/native/unit.log` |
| C versus structured reference | 394,866 trace comparisons / 2,003,430 per-event comparisons passed | `results/native/summary.json` |
| Clock translation | Equal output digests at origins 0 and 0xfffffffc for both enumerated configurations | `results/native/summary.json` |
| Named and seeded cases | Actual C bytes matched the list-based reference; named CSV retains rejected/error inputs | `results/native/named.csv` |
| ARM execution | 162 traces / 1,638 events passed on compiled Cortex-M4 C | `results/arm/arm.json` |
| Native Debug build | CMake/CTest boundary suite passed; Debug shared library also matched 162 reference traces / 1,638 events | `results/cmake/` |
| Reconstructible witness | Single bad sample, a later tick and staleness reproduced through the C shared library | `results/replay/replay.json` |
| Clean extracted source | Offline verification, full rebuild/campaign, analysis and hold-policy replay passed; output stream digest and named CSV match the original | `provenance/package-check.json` |

Host: Windows, Python 3.12.10, Zig 0.14.1 / Clang 19.1.7. ARM: Arm GNU 15.2.1,
Unicorn 2.1.4 and pyelftools 0.32. Local CMake used a public Ninja 1.13.0 driver.
Compiler commands, C/reference sources, vector and ELF hashes are recorded.

The full host count consists of 114 named comparisons, 393,216 finite token
comparisons and 1,536 seeded comparisons. Inputs are reused across profiles,
policies and clock origins. These are not independent physical failure cases,
detector accuracy estimates or all-state verification. Different policies are
checked against their different declared contracts, not forced to agree.

The ARM monitor context is 104 bytes, output structure 40 bytes, and the standalone
core object has 844 text bytes for this compiler configuration. The full ARM
fixture text is 106,700 bytes because it includes generated test/expected vectors;
BSS is 32 bytes, excluding stack. These are object/section sizes, not production
resource budgets, stack high-water measurements or target execution-time bounds.

No physical sensor, MCU board, peripheral, acquisition/queue latency, noise model,
flight trace, radiation condition or complete mission FDIR chain was validated.
Native Linux and remote GitHub Actions were not run here; workflow configuration
is provided. An internal critique is included; independent peer review and IAC
strong-topic selection remain unperformed.

The local task explicitly selected an already available public Zig/Ninja tool
cache; no earlier project source is needed at runtime. Default Windows setup can
download the same pinned compiler anonymously. Source ZIPs omit all caches,
environments, binaries and .git. The existing research automation remains paused;
no external message, publication, upload or submission was made.
