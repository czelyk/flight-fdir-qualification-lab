# Tools and source provenance

The C monitor, tests, reference, synthetic vectors and authored documentation
use the root MIT license. NASA and F Prime source is not bundled. The
optional Limit Checker comparison fetches and compiles three functions from
[NASA LC](https://github.com/nasa/LC/tree/c9104f85b3a9b795be5c67702c8e190b36e4cdd5)
under its [upstream license](https://github.com/nasa/LC/blob/c9104f85b3a9b795be5c67702c8e190b36e4cdd5/LICENSE).
See [source pins and scope](docs/LC_ALARM.md). Other cited sources are
context and prior work. Acquisition hashes and access limits are in
provenance/sources.json.

Optional Zig 0.14.1 is fetched from its public distribution with a pinned SHA256.
It retains its own distribution licenses and is ignored by Git. The local task
used an already downloaded copy of that public compiler; new source copies can
select any compatible GCC/Clang or use the anonymous bootstrap.

Optional Arm GNU Toolchain, Unicorn 2.1.4, pyelftools 0.32 and Ninja retain their
respective licenses. Their executables/environments are not part of source ZIPs.
No private portal, hardware authentication token or paid activation is required.
