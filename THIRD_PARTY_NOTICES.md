# Tools and source provenance

The C monitor, tests, reference, synthetic vectors and authored documentation
use the root MIT license. No cFS, F Prime or other NASA implementation is bundled
or linked. Cited source material is context and prior work, not a dependency or
endorsement. Acquisition hashes and access limits are in provenance/sources.json.

Optional Zig 0.14.1 is fetched from its public distribution with a pinned SHA256.
It retains its own distribution licenses and is ignored by Git. The local task
used an already downloaded copy of that public compiler; new source copies can
select any compatible GCC/Clang or use the anonymous bootstrap.

Optional Arm GNU Toolchain, Unicorn 2.1.4, pyelftools 0.32 and Ninja retain their
respective licenses. Their executables/environments are not part of source ZIPs.
No private portal, hardware authentication token or paid activation is required.
