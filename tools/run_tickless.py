"""Run the same periodic-versus-tickless C campaign on the host and optionally ARM."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile

from build import ROOT, compiler, execute

C_FILES = ["src/fq_monitor.c", "src/fq_tickless.c", "tests/tickless.c"]
FLAGS = ["-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-Iinclude"]
POLICIES = ["count", "hold", "observed"]
STATS = struct.Struct("<9I")


def measurements(words):
    traces, inputs, *counts, changes = words
    return {
        "traces": traces,
        "external_event_comparisons": inputs,
        "policies": {
            policy: {"periodic_ticks": periodic, "scheduled_ticks": scheduled}
            for policy, periodic, scheduled in zip(POLICIES, counts[::2], counts[1::2])
        },
        "idle_alarm_or_quality_transition_ticks": changes,
    }


def arm_result(gcc, run):
    import elftools
    import unicorn
    from elftools.elf.elffile import ELFFile
    from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_SP

    elf = run / "tickless.elf"
    target_flags = ["-mcpu=cortex-m4", "-mthumb", "-ffreestanding", "-fno-builtin",
                    "-ffunction-sections", "-fdata-sections", "-DFQ_ARM_FIXTURE",
                    "-nostartfiles", "-nostdlib"]
    linker_flags = ["-T", "cmake/arm-emulation.ld", "-Wl,--gc-sections", "-lc", "-lgcc"]
    args = [*FLAGS, *target_flags, *C_FILES, *linker_flags]
    execute([gcc, *args, "-o", elf], ROOT, run / "arm-build.log")

    cpu = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_THUMB | unicorn.UC_MODE_MCLASS)
    cpu.mem_map(0x10000, 0x40000)
    cpu.mem_map(0x20000000, 0x20000)
    with elf.open("rb") as file:
        image = ELFFile(file)
        for segment in image.iter_segments():
            if segment["p_type"] == "PT_LOAD" and segment["p_filesz"]:
                cpu.mem_write(segment["p_vaddr"], segment.data())
        symbols = {s.name: s["st_value"] for s in image.get_section_by_name(".symtab").iter_symbols()}
    stop = 0x4f000
    cpu.reg_write(UC_ARM_REG_SP, 0x2001fff8)
    cpu.reg_write(UC_ARM_REG_LR, stop | 1)
    cpu.emu_start(symbols["arm_smoke"] | 1, stop, timeout=60_000_000, count=100_000_000)
    if cpu.reg_read(UC_ARM_REG_PC) != stop:
        raise RuntimeError("Cortex-M4 execution bound reached")
    failure = cpu.reg_read(UC_ARM_REG_R0)
    if failure:
        raise RuntimeError(f"Cortex-M4 check failed at tests/tickless.c:{failure}")
    words = STATS.unpack(cpu.mem_read(symbols["arm_results"], STATS.size))
    return {
        "compiler": execute([gcc, "--version"], ROOT, run / "arm-compiler.txt").splitlines()[0],
        "unicorn": unicorn.__version__,
        "pyelftools": elftools.__version__,
        "build_arguments": args,
        "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
        "measurements": measurements(words),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    compilers = parser.add_mutually_exclusive_group()
    compilers.add_argument("--zig")
    compilers.add_argument("--cc")
    parser.add_argument("--arm", action="store_true", help="Also run the campaign in Unicorn")
    parser.add_argument("--gcc", default=os.environ.get("ARM_GCC") or shutil.which("arm-none-eabi-gcc"))
    args = parser.parse_args()
    if args.arm and not args.gcc:
        parser.error("--arm needs Arm GNU Toolchain on PATH or --gcc")

    runs = ROOT / "runs"
    runs.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="tickless_", dir=runs))
    driver = compiler(args.zig, args.cc)
    binary = run / ("tickless.exe" if os.name == "nt" else "tickless")
    build_args = [*FLAGS, *C_FILES]
    execute([*driver, *build_args, "-o", binary], ROOT, run / "native-build.log")
    words = tuple(map(int, execute([binary], run, run / "native.log").split()))
    native = {
        "compiler": execute([*driver, "--version"], ROOT, run / "native-compiler.txt").splitlines()[0],
        "build_arguments": build_args,
        "measurements": measurements(words),
    }
    sources = [*C_FILES, "include/fq_monitor.h", "include/fq_tickless.h",
               "cmake/arm-emulation.ld", "tools/build.py", "tools/run_tickless.py"]
    record = {
        "native": native,
        "source_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in sources},
        "physical_tests": False,
        "target_timing": False,
    }
    if args.arm:
        record["arm"] = arm_result(args.gcc, run)
        if record["arm"]["measurements"] != native["measurements"]:
            raise RuntimeError("Native and Cortex-M4 counters differ")
    output = run / "tickless.json"
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(output)
    print(json.dumps(native["measurements"], indent=2))


if __name__ == "__main__":
    main()
