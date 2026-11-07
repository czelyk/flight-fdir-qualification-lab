"""Build and run the restart queue comparison on the host and optionally Cortex-M4."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile

from build import ROOT, compiler, execute

SOURCES = ["src/fq_monitor.c", "src/fq_tickless.c", "src/fq_acquisition.c", "src/fq_ingress.c",
           "experiments/generation_queue.c"]
FLAGS = ["-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-Iinclude"]
POLICIES = ("timestamp_only", "ready_flush", "quiescent_drain", "generation_tag")
METRICS = ("old_admitted", "new_admitted", "missed_windows", "no_new_sample_but_loss_masked")
WORDS = struct.Struct("<18I")


def result(driver, flags, words, run, label):
    if len(words) != len(POLICIES) * len(METRICS) + 2:
        raise RuntimeError("Unexpected fixture output size")
    cases, context_bytes, *counts = words
    per_policy = {}
    for index, policy in enumerate(POLICIES):
        first = index * len(METRICS)
        per_policy[policy] = dict(zip(METRICS, counts[first:first + len(METRICS)], strict=True))
    return {
        "compiler": execute([*driver, "--version"], ROOT, run / f"{label}-compiler.txt").splitlines()[0],
        "build_arguments": flags,
        "context_bytes": context_bytes,
        "measurements": {"queue_cases": cases, "comparisons": cases * len(POLICIES),
                         "clock_wrap_comparisons": cases * len(POLICIES), "policies": per_policy},
    }


def arm_result(gcc, run):
    import elftools
    import unicorn
    from elftools.elf.elffile import ELFFile
    from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_SP

    elf = run / "generation.elf"
    flags = [*FLAGS, "-mcpu=cortex-m4", "-mthumb", "-ffreestanding", "-fno-builtin",
             "-DFQ_ARM_FIXTURE", "-nostartfiles", "-nostdlib", *SOURCES,
             "-T", "cmake/arm-emulation.ld", "-lc", "-lgcc"]
    execute([gcc, *flags, "-o", elf], ROOT, run / "arm-build.log")
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
    cpu.emu_start(symbols["arm_smoke"] | 1, stop, timeout=60_000_000, count=10_000_000)
    if cpu.reg_read(UC_ARM_REG_PC) != stop:
        raise RuntimeError("Cortex-M4 execution bound reached")
    failure = cpu.reg_read(UC_ARM_REG_R0)
    if failure:
        raise RuntimeError(f"Cortex-M4 check failed at experiments/generation_queue.c:{failure}")
    words = WORDS.unpack(cpu.mem_read(symbols["arm_results"], WORDS.size))
    return dict(result([gcc], flags, words, run, "arm"), unicorn=unicorn.__version__,
                pyelftools=elftools.__version__, elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    compilers = parser.add_mutually_exclusive_group()
    compilers.add_argument("--zig")
    compilers.add_argument("--cc")
    parser.add_argument("--arm", action="store_true")
    parser.add_argument("--gcc", default=os.environ.get("ARM_GCC") or shutil.which("arm-none-eabi-gcc"))
    parser.add_argument("--check", action="store_true", help="Compare results with the archived fixture")
    args = parser.parse_args()
    if args.arm and not args.gcc:
        parser.error("--arm needs Arm GNU Toolchain on PATH or --gcc")

    runs = ROOT / "runs"
    runs.mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="generation_", dir=runs))
    driver = compiler(args.zig, args.cc)
    binary = run / ("generation.exe" if os.name == "nt" else "generation")
    flags = [*FLAGS, *SOURCES]
    execute([*driver, *flags, "-o", binary], ROOT, run / "native-build.log")
    words = tuple(map(int, execute([binary], run, run / "native.log").split()))
    sources = [*SOURCES, "include/fq_monitor.h", "include/fq_tickless.h", "include/fq_acquisition.h",
               "include/fq_ingress.h", "cmake/arm-emulation.ld", "tools/build.py", "tools/run_generation.py"]
    record = {
        "native": result(driver, flags, words, run, "native"),
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources},
        "physical_tests": False,
    }
    measurement = record["native"]["measurements"]
    if args.arm:
        record["arm"] = arm_result(args.gcc, run)
        if record["arm"]["measurements"] != measurement:
            raise RuntimeError("Native and Cortex-M4 counters differ")
    output = run / "generation.json"
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.check:
        archived = json.loads((ROOT / "results/generation/generation.json").read_text(encoding="utf-8"))
        if archived["native"]["measurements"] != measurement:
            raise RuntimeError(f"Queue results differ from the archived evidence. Check {run}")
    print(output)
    print(json.dumps(measurement, indent=2))


if __name__ == "__main__":
    main()
