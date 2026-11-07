# Build and integration notes

The default `tools/run_tests.py` uses the Python standard library and a C99
compiler. It compiles a shared library for ctypes, verifies simple structure
sizes, builds native C boundary tests and then performs C/reference comparisons.
The Python byte-packing bridge assumes a little-endian host. Local execution is
Windows; a Linux workflow is provided but has not run here. Production C uses
fixed-width integer arithmetic and does not depend on that Python byte layout.

Windows uses a locally supplied `--zig path/to/zig.exe`, GCC/Clang through --cc,
or a checksum-pinned public Zig download if no compiler is found. It never
requires a sibling project's sources. The local validation reused a previously
downloaded public Zig executable and Ninja build driver explicitly; the source
ZIP does not include them or hard-code those paths as dependencies.

For the optional Windows CMake route:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install ninja==1.13.0
python -c "import sys;sys.path.insert(0,'tools');from bootstrap_zig import bootstrap;print(bootstrap())"
$repo = (Get-Location).Path.Replace('\','/')
cmake -S . -B build -G Ninja "-DCMAKE_MAKE_PROGRAM=$repo/.venv/Scripts/ninja.exe" "-DCMAKE_TOOLCHAIN_FILE=cmake/zig-windows.cmake" "-DZIG_EXECUTABLE=$repo/.tools/zig-x86_64-windows-0.14.1/zig.exe" "-DCMAKE_BUILD_TYPE=Debug"
cmake --build build
ctest --test-dir build --output-on-failure
```

CMake builds the library, bridge, worker sketch and tests for the core,
tickless planner, first-sample watchdog and generation ingress.
The large reference campaign runs through the separate Python entry point. Both
paths compile authored C with -Wall -Wextra -Werror on the tested Clang/GCC tools.

The ARM runner requires Arm GNU Toolchain plus requirements-arm.txt. It generates
vectors from the list-based specification, links emulator memory addresses and
checks every output field. The fixture's large text section contains expected
test vectors. The small standalone object excludes link/runtime dependencies;
neither it nor the fixture establishes production flash use, peak stack or WCET.

`examples/worker.c` illustrates serialized calls with the
[generation ingress](GENERATION.md),
[first-sample watchdog](ACQUISITION.md) and
[one-shot timer deadline](TICKLESS.md). A real port must supply its
acquisition/processing clock contract, known producer epochs, transport/queue
ownership, timer delivery and a separate response policy. Inspect both return
codes and the quality field at integration.
